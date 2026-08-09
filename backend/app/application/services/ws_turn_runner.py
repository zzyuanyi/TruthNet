"""WsTurnRunner — Phase D #5/#6/#10 turn 执行与事件分发.

职责（接收与执行分离）：
  - 启动独立 turn task（asyncio.create_task），不阻塞 WS 接收循环；
  - 使用 graph.astream_events 获取真实节点开始/完成信号；
  - 通过 DeltaSink 接收 generate_answer 实时构造的真实分段 → answer.delta；
  - 读取 cancellation token，当前节点结束后停止，不启动下一个节点；
  - 保证同一 turn 只发送一个终态事件（turn.completed / turn.cancelled / turn.failed）。

设计约束：
  - emit 回调由路由提供（负责 sequence 分配 + 事件缓冲 + socket 发送）；
  - 所有事件按 event_type 分发；module.started 在节点实际执行前发送
    （astream_events on_chain_start），module.completed 在节点返回后发送；
  - 取消：token 置位后，正在执行的节点可完成，但下一个节点不再启动；
    turn.cancelled 恰好一次，不再发送 turn.completed。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.agents.delta_sink import DeltaSink, register_sink, unregister_sink
from app.domain.evidence.models import supporting_evidence_ids
from app.application.services.ws_session_manager import (
    ActiveTurn,
    WsSession,
    session_manager,
)

logger = logging.getLogger(__name__)

# astream_events 会为内部条件路由（_after_plan 等）也产生 start/end，
# 这些不是对外模块节点，需过滤；同时过滤 graph 包装层名。
# 对外可见模块（发送 module.started/completed）：仅用户请求的模块
# finance/equity/events/risk（与 V12 契约一致，内部节点不对外暴露）。
_VISIBLE_MODULES = frozenset({"finance", "equity", "events", "risk"})

# module.started 可选 message：前端显示在独立思考状态区，
# 不写入 assistant 正文（不参与 answer.delta 拼接契约）
_MODULE_STARTED_MESSAGES: dict[str, str] = {
    "finance": "正在核查财务数据（母公司报表口径）",
    "equity": "正在穿透股权结构与实际控制人链路",
    "events": "正在核对公告、评级与事件时间线",
    "risk": "正在综合评估风险等级",
}
# 参与事件过滤的 graph 节点全集（避免内部条件路由名干扰）
_MODULE_NODES = frozenset(
    {
        "load_context",
        "memory",
        "resolve_entity",
        "plan_modules",
        "finance",
        "equity",
        "events",
        "cross_validate",
        "risk",
        "pattern_match",
        "build_claims",
        "generate_answer",
        "validate_evidence",
        "persist_turn",
    }
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


async def _emit_terminal_once(
    session: WsSession, turn: ActiveTurn, event_type: str, payload: dict, emit
) -> bool:
    """原子抢占后发送终态事件（turn.cancelled/completed/failed 统一入口）。

    保证同一 turn 恰好一个终态事件：抢占成功者发送，其余路径跳过。
    """
    if not session_manager.claim_terminal_event(session, turn.turn_id):
        return False
    await emit(event_type, payload)
    return True


class TurnResult:
    """turn 执行结果摘要（终态事件已由 emit 回调发送）。"""

    __slots__ = ("outcome", "turn_id", "sequence")

    def __init__(self, outcome: str, turn_id: str, sequence: int) -> None:
        self.outcome = outcome  # completed / cancelled / failed / no_response
        self.turn_id = turn_id
        self.sequence = sequence


async def run_turn(
    *,
    session: WsSession,
    turn: ActiveTurn,
    graph,
    question: str,
    emit: Callable[[str, dict], Awaitable[None]],
    build_state: Callable[[], dict],
    start_sequence: int = 0,
    accepted_at: float = 0.0,
) -> TurnResult:
    """执行一个 turn，分发事件；返回终态摘要。

    Args:
        session: 所属逻辑会话。
        turn: ActiveTurn（含 cancellation token）。
        graph: 已编译 LangGraph。
        question: 用户问题（用于事件负载展示）。
        emit: 异步事件发送回调 (event_type, payload) → 负责 envelope 组装。
        build_state: 构造初始 AgentState（含 runtime session/turn/trace）。
        start_sequence: 本 turn 起始序号（仅测试/统计用）。
        accepted_at: turn.accepted 实际发送时刻（perf_counter 基准；
            性能指标从此计时，漏掉任务调度时间——复核约束）。
    """
    # 注册 DeltaSink（generate_answer 实时分段 → answer.delta）
    sink = DeltaSink(turn.turn_id)
    register_sink(turn.turn_id, sink)

    try:
        return await _run(
            session=session,
            turn=turn,
            graph=graph,
            question=question,
            emit=emit,
            build_state=build_state,
            sink=sink,
            accepted_at=accepted_at,
        )
    finally:
        sink.close()
        unregister_sink(turn.turn_id)


async def _run(
    *,
    session: WsSession,
    turn: ActiveTurn,
    graph,
    question: str,
    emit: Callable[[str, dict], Awaitable[None]],
    build_state: Callable[[], dict],
    sink: DeltaSink,
    accepted_at: float = 0.0,
) -> TurnResult:
    token = turn.token
    cancelled = token.cancelled

    # 启动前就已被取消（accepted 后立即取消场景；确认事件可能已由路由层
    # 经 claim 发出——此处抢占失败则不重复发送）
    if cancelled:
        await _emit_terminal_once(
            session,
            turn,
            "turn.cancelled",
            {
                "turn_id": turn.turn_id,
                "cancelled_at": _utcnow_iso(),
                "message": "当前轮次已取消",
            },
            emit,
        )
        return TurnResult("cancelled", turn.turn_id, 0)

    state = build_state()
    final_state: dict = state
    # 真正会执行的模块：plan_modules 确定 requested_modules；
    # risk 节点在公司存在时总是执行（不受 plan 门控）。
    executable_modules: set[str] = set()
    has_company = state.get("company") is not None
    # WS 性能埋点（Phase D #7）：以 turn.accepted 实际发送时刻为基准
    # （accepted_at 由路由层传入；测试未传时回退 run_turn 内部起点）
    from app.infrastructure.observability.timing import metrics_collector

    ws_t0 = accepted_at or time.perf_counter()
    first_delta_sent = False
    first_feedback_sent = False
    _aborted = False  # 异常/取消标记（finally 排空时丢弃残留）
    # 模块耗时记录（复核约束）：module.completed 带 duration_ms，
    # 支撑"模块并行后关键路径 max(finance,equity,events)→risk"瓶颈定位
    _module_started_at: dict[str, float] = {}

    # 3️⃣ DeltaSink 实时消费：graph 节点（generate_answer）在 LangGraph 线程
    # 执行期间事件循环空闲——独立任务轮询 sink，push 即发 answer.delta，
    # 不再等 generate_answer on_chain_end（首块 = 第一段构造时刻）。
    # 契约不变：所有 content delta 拼接 == turn.completed.answer。
    sink_stop = asyncio.Event()

    async def _sink_consumer() -> None:
        nonlocal first_delta_sent
        while not sink_stop.is_set():
            seg = sink.get_nowait()
            if seg is not None:
                if not first_delta_sent:
                    first_delta_sent = True
                    metrics_collector.record(
                        "ws.first_delta_ms",
                        (time.perf_counter() - ws_t0) * 1000,
                        trace_id=turn.turn_id,
                    )
                await emit("answer.delta", {"text": seg})
                continue
            # 空缓冲 → 短暂让出事件循环，等待下一段
            try:
                await asyncio.wait_for(sink_stop.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass

    consumer_task = asyncio.create_task(_sink_consumer())
    try:
        # 异步流式执行：on_chain_start → 节点开始，on_chain_end → 节点完成
        async for event in graph.astream_events(state, version="v2"):
            event_type = event.get("event")
            name = event.get("name") or ""
            if event_type == "on_chain_end" and name == "LangGraph":
                # 根链结束 → 完整最终 state（含 final_response / claims / evidence）
                out = event.get("data", {}).get("output")
                if isinstance(out, dict):
                    final_state = out
                continue
            if name not in _MODULE_NODES:
                continue

            if event_type == "on_chain_end" and name == "resolve_entity":
                # 捕获公司解析结果（决定 risk 是否执行）
                out = event.get("data", {}).get("output") or {}
                if out.get("company") is not None:
                    has_company = True
                continue

            if event_type == "on_chain_end" and name == "plan_modules":
                # 捕获执行计划：requested_modules 即实际执行的业务模块
                plan_out = event.get("data", {}).get("output") or {}
                plan = plan_out.get("plan")
                requested = getattr(plan, "requested_modules", None)
                if isinstance(requested, list):
                    executable_modules = set(requested)
                if has_company:
                    executable_modules.add("risk")
                continue

            if event_type == "on_chain_start":
                if token.cancelled:
                    # 当前节点已完成，不启动下一个节点
                    break
                if name in _VISIBLE_MODULES and name in executable_modules:
                    mod = _event_module(name)
                    _module_started_at[name] = time.perf_counter()
                    if not first_feedback_sent:
                        # 首个可见模块启动 = 首反馈（前端思考状态区展示用）
                        first_feedback_sent = True
                        metrics_collector.record(
                            "ws.first_feedback_ms",
                            (time.perf_counter() - ws_t0) * 1000,
                            trace_id=turn.turn_id,
                        )
                    await emit(
                        "module.started",
                        {
                            "module": mod,
                            "status": "running",
                            # 可选 message：前端显示在独立思考状态区，
                            # 不写入 assistant 正文（不参与 delta 拼接）
                            "message": _MODULE_STARTED_MESSAGES.get(mod, ""),
                        },
                    )
                    turn.last_sequence_sent = session.sequence

            elif event_type == "on_chain_end":
                if token.cancelled:
                    break
                # 节点完成（对外可见且实际执行的模块）
                # （delta 分段由 _sink_consumer 实时消费，不再在此批量取）
                if (
                    name in _VISIBLE_MODULES
                    and name in executable_modules
                    and not token.cancelled
                ):
                    started_at = _module_started_at.pop(name, None)
                    await emit(
                        "module.completed",
                        {
                            "module": _event_module(name),
                            "status": "success",
                            "duration_ms": (
                                int((time.perf_counter() - started_at) * 1000)
                                if started_at is not None
                                else None
                            ),
                        },
                    )
                # 不在此 break：需等 LangGraph 根链 on_chain_end 捕获完整最终
                # state（含 final_response/claims/evidence）后再终态判定。
                # 取消时在下一个 on_chain_start 处 break（不启动新节点）。

    except asyncio.CancelledError:
        # turn task 被外部取消（连接销毁 / 清理）
        _aborted = True
        await _emit_terminal_once(
            session,
            turn,
            "turn.cancelled",
            {
                "turn_id": turn.turn_id,
                "cancelled_at": _utcnow_iso(),
                "message": "当前轮次已取消",
            },
            emit,
        )
        return TurnResult("cancelled", turn.turn_id, session.sequence)
    except Exception:  # noqa: BLE001 — Agent 异常 → turn.failed（不静默吞异常）
        _aborted = True
        logger.exception(
            "WsTurnRunner 执行异常: turn=%s session=%s question=%.40s",
            turn.turn_id,
            session.session_id,
            question,
        )
        try:
            await _emit_terminal_once(
                session,
                turn,
                "turn.failed",
                {
                    "error_code": "AGENT_ERROR",
                    "message": "处理请求时发生内部错误，请稍后重试",
                    "recoverable": True,
                },
                emit,
            )
        except Exception:  # noqa: BLE001 — 错误事件发送失败仅记录
            logger.warning("WsTurnRunner: 错误事件发送失败", exc_info=True)
        return TurnResult("failed", turn.turn_id, session.sequence)
    finally:
        # 停止实时消费任务并排空残留段——保证所有 delta 先于终态事件发出；
        # 异常/取消（_aborted）时丢弃残留（终态为 turn.cancelled/failed）
        sink_stop.set()
        try:
            await consumer_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        while True:
            seg = sink.get_nowait()
            if seg is None:
                break
            if _aborted or token.cancelled:
                break
            if not first_delta_sent:
                first_delta_sent = True
                metrics_collector.record(
                    "ws.first_delta_ms",
                    (time.perf_counter() - ws_t0) * 1000,
                    trace_id=turn.turn_id,
                )
            await emit("answer.delta", {"text": seg})

    # 取消 → 恰好一次 turn.cancelled（不发送 turn.completed）；
    # 若路由层取消确认已抢占终态，此处抢占失败即跳过
    if token.cancelled or cancelled:
        await _emit_terminal_once(
            session,
            turn,
            "turn.cancelled",
            {
                "turn_id": turn.turn_id,
                "cancelled_at": _utcnow_iso(),
                "message": "当前轮次已取消",
            },
            emit,
        )
        return TurnResult("cancelled", turn.turn_id, session.sequence)

    result = await _finalize_turn(
        session=session,
        turn=turn,
        emit=emit,
        state=final_state,
    )
    if result.outcome == "completed":
        metrics_collector.record(
            "ws.accepted_to_complete_ms",
            (time.perf_counter() - ws_t0) * 1000,
            trace_id=turn.turn_id,
        )
    return result


def _event_module(node_name: str) -> str:
    """节点名 → 对外 module 名（graph 内部名即对外名）。"""
    return node_name


async def _finalize_turn(
    *,
    session: WsSession,
    turn: ActiveTurn,
    emit: Callable[[str, dict], Awaitable[None]],
    state: dict,
) -> TurnResult:
    """图执行完成（persist_turn 结束）后组装 turn.completed / turn.failed。"""
    final_response = state.get("final_response")
    if final_response is None:
        await _emit_terminal_once(
            session,
            turn,
            "turn.failed",
            {
                "error_code": "NO_RESPONSE",
                "message": "Agent 未返回结果",
            },
            emit,
        )
        return TurnResult("no_response", turn.turn_id, session.sequence)

    plan = state.get("plan")
    intent = getattr(plan, "intent", "") if plan is not None else ""
    candidates = state.get("company_candidates", []) or []
    if candidates:
        candidate_items = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in candidates
        ]
        context_as_of = getattr(plan, "as_of", None) if plan is not None else None
        session_manager.set_pending_disambiguation(
            session,
            {
                "turn_id": turn.turn_id,
                "question": turn.question,
                "as_of": context_as_of.strftime("%Y%m%d") if context_as_of else "",
                "candidates": candidate_items,
            },
        )
        await emit(
            "company.candidates",
            {"turn_id": turn.turn_id, "candidates": candidate_items},
        )
    has_company_analysis = state.get("company") is not None and intent not in {
        "chitchat",
        "guide",
        "unsupported",
        "research",
    }

    # artifact.upsert — 风险等级结构化产物（前端面板消费，V12 契约）
    if has_company_analysis:
        try:
            await emit(
                "artifact.upsert",
                {
                    "artifact_type": "risk_assessment",
                    "artifact_id": f"risk_{session.session_id}",
                    "revision": 1,
                    "operation": "replace",
                    "data": {"risk_level": final_response.risk_level},
                },
            )
        except Exception:  # noqa: BLE001 — artifact 发送失败不阻塞终态
            logger.warning("WsTurnRunner: artifact.upsert 发送失败", exc_info=True)

    # artifact.upsert — 股权链路载荷（Phase D #12，与 REST equity_chains 一致）
    try:
        equity = None
        results_obj = state.get("results")
        if results_obj is not None and getattr(results_obj, "equity", None):
            equity = results_obj.equity
        chain_details = []
        if equity is not None and getattr(equity, "chain_details", None):
            chain_details = equity.chain_details
        if chain_details:
            await emit(
                "artifact.upsert",
                {
                    "artifact_type": "equity_graph",
                    "artifact_id": f"equity_{session.session_id}",
                    "revision": 1,
                    "operation": "replace",
                    "data": {"equity_chains": chain_details},
                },
            )
    except Exception:  # noqa: BLE001 — 链路 artifact 失败不阻塞终态
        logger.warning("WsTurnRunner: equity artifact.upsert 发送失败", exc_info=True)

    results = state.get("results")

    # finance 面板（规则触发 + canonical evidence_ids，前端实时面板）
    finance_payload = None
    warnings: list[str] = []
    if results and getattr(results, "finance", None):
        fin = results.finance
        if fin.warnings:
            for w in fin.warnings:
                if w and w not in warnings:
                    warnings.append(w)
        finance_payload = {
            "rule_statuses": fin.rule_statuses,
            "triggered_rules": [
                {
                    "rule_id": rid,
                    "rule_name": (
                        (fin.rule_details or {}).get(rid, {}).get("rule_name") or rid
                    ),
                    "evidence_ids": (fin.rule_details or {})
                    .get(rid, {})
                    .get("evidence_ids")
                    or [],
                }
                for rid, status in (fin.rule_statuses or {}).items()
                if status == "triggered"
            ],
            "warnings": list(fin.warnings),
            "evidence_count": len(fin.evidence or []),
        }
    runtime = state.get("runtime")
    if runtime and hasattr(runtime, "warnings"):
        for w in runtime.warnings:
            if w and w not in warnings:
                warnings.append(w)
    # Phase D #16: 模式三要素透出（与 REST 一致）
    pattern_items: list[dict] = []
    for m in state.get("pattern_matches", []) or []:
        pattern_items.append(
            {
                "pattern_id": m.get("pattern_id", "")
                if isinstance(m, dict)
                else getattr(m, "pattern_id", ""),
                "pattern_name": m.get("pattern_name", "")
                if isinstance(m, dict)
                else getattr(m, "pattern_name", ""),
                "triggered_rules": m.get("triggered_rules", [])
                if isinstance(m, dict)
                else getattr(m, "triggered_rules", []),
                "confidence": m.get("confidence", "")
                if isinstance(m, dict)
                else getattr(m, "confidence", ""),
                "reasoning": m.get("reasoning", "")
                if isinstance(m, dict)
                else getattr(m, "reasoning", ""),
                "phase": m.get("phase", "")
                if isinstance(m, dict)
                else getattr(m, "phase", ""),
                "alternative_explanation": m.get("alternative_explanation", "")
                if isinstance(m, dict)
                else getattr(m, "alternative_explanation", ""),
                "regulatory_hint": m.get("regulatory_hint", "")
                if isinstance(m, dict)
                else getattr(m, "regulatory_hint", ""),
            }
        )

    # 来源引用（前端渲染可点链接）：带 uri 的证据（公告/研报）排前、
    # 无 uri 的规则证据殿后，总量 ≤10——确保可点链接不被规则证据截断挤掉。
    _src_evs = [
        ev
        for ev in state.get("evidence", [])
        if ev.evidence_id
        and (getattr(ev, "source_title", "") or getattr(ev, "source_uri", ""))
    ]
    _src_evs.sort(
        key=lambda ev: (not bool(getattr(ev, "source_uri", "")), ev.evidence_id)
    )
    _src_sources = [
        {
            "id": ev.evidence_id,
            "title": ev.source_title,
            "source": ev.source_type,
            "url": ev.source_uri or "",
        }
        for ev in _src_evs
    ][:10]

    await _emit_terminal_once(
        session,
        turn,
        "turn.completed",
        {
            "answer": final_response.answer,
            "intent": intent,
            "requested_period_text": (
                getattr(plan, "requested_period_text", "") if plan is not None else ""
            ),
            "risk_level": final_response.risk_level,
            "claims_count": len(state.get("claims", [])),
            "follow_ups": getattr(final_response, "follow_ups", []),
            "evidence_count": len(state.get("evidence", [])),
            "evidence_ids": [
                getattr(ev, "evidence_id", None)
                for ev in state.get("evidence", [])
                if getattr(ev, "evidence_id", None)
            ],
            "sources": _src_sources,
            # #13：可展示叶子证据子集（前端默认展示，保留全量入口）
            "supporting_evidence_ids": supporting_evidence_ids(state.get("claims", [])),
            "warnings": warnings,
            "finance": finance_payload,
            "pattern_matches": pattern_items,
            # Phase D #12: 正式链路载荷（与 REST equity_chains 一致）
            "equity_chains": _extract_equity_chains(state),
            "company_candidates": [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in candidates
            ],
        },
        emit,
    )
    return TurnResult("completed", turn.turn_id, session.sequence)


def _extract_equity_chains(state: dict) -> list[dict]:
    """从 Agent State 提取 equity.chain_details（与 REST equity_chains 一致）。"""
    try:
        results_obj = state.get("results")
        if results_obj is None or not getattr(results_obj, "equity", None):
            return []
        eq = results_obj.equity
        details = getattr(eq, "chain_details", None) or []
        return list(details)
    except Exception:  # noqa: BLE001
        return []
