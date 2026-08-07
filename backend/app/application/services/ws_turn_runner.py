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
from app.application.services.ws_session_manager import (
    ActiveTurn,
    WsSession,
)

logger = logging.getLogger(__name__)

# astream_events 会为内部条件路由（_after_plan 等）也产生 start/end，
# 这些不是对外模块节点，需过滤；同时过滤 graph 包装层名。
# 对外可见模块（发送 module.started/completed）：仅用户请求的模块
# finance/equity/events/risk（与 V12 契约一致，内部节点不对外暴露）。
_VISIBLE_MODULES = frozenset({"finance", "equity", "events", "risk"})
# 需要消费 answer.delta 分段的节点
_DELTA_NODES = frozenset({"generate_answer"})
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
) -> TurnResult:
    token = turn.token
    cancelled = token.cancelled

    # 启动前就已被取消（accepted 后立即取消场景）
    if cancelled:
        await emit(
            "turn.cancelled",
            {
                "turn_id": turn.turn_id,
                "cancelled_at": _utcnow_iso(),
                "message": "当前轮次已取消",
            },
        )
        return TurnResult("cancelled", turn.turn_id, 0)

    state = build_state()
    final_state: dict = state
    # 真正会执行的模块：plan_modules 确定 requested_modules；
    # risk 节点在公司存在时总是执行（不受 plan 门控）。
    executable_modules: set[str] = set()
    has_company = state.get("company") is not None
    # WS 性能埋点（Phase D #7）
    from app.infrastructure.observability.timing import metrics_collector

    ws_t0 = time.perf_counter()
    first_delta_sent = False
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
                    await emit(
                        "module.started",
                        {"module": _event_module(name), "status": "running"},
                    )
                    turn.last_sequence_sent = session.sequence

            elif event_type == "on_chain_end":
                if name in _DELTA_NODES:
                    # 消费 generate_answer 实时构造的 answer.delta 分段
                    while True:
                        seg = sink.get_nowait()
                        if seg is None:
                            break
                        if not first_delta_sent:
                            first_delta_sent = True
                            metrics_collector.record(
                                "ws.first_delta_ms",
                                (time.perf_counter() - ws_t0) * 1000,
                                trace_id=turn.turn_id,
                            )
                        await emit("answer.delta", {"text": seg})
                    if token.cancelled:
                        break
                # 节点完成（对外可见且实际执行的模块）
                if (
                    name in _VISIBLE_MODULES
                    and name in executable_modules
                    and not token.cancelled
                ):
                    await emit(
                        "module.completed",
                        {"module": _event_module(name), "status": "success"},
                    )
                # 不在此 break：需等 LangGraph 根链 on_chain_end 捕获完整最终
                # state（含 final_response/claims/evidence）后再终态判定。
                # 取消时在下一个 on_chain_start 处 break（不启动新节点）。

        # 取消 → 恰好一次 turn.cancelled（不发送 turn.completed）
        if token.cancelled or cancelled:
            # 取消确认可能已由接收循环直接发送（≤2s 确认）；此处兜底防重复
            await emit(
                "turn.cancelled",
                {
                    "turn_id": turn.turn_id,
                    "cancelled_at": _utcnow_iso(),
                    "message": "当前轮次已取消",
                },
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

    except asyncio.CancelledError:
        # turn task 被外部取消（连接销毁 / 清理）
        await emit(
            "turn.cancelled",
            {
                "turn_id": turn.turn_id,
                "cancelled_at": _utcnow_iso(),
                "message": "当前轮次已取消",
            },
        )
        return TurnResult("cancelled", turn.turn_id, session.sequence)
    except Exception:  # noqa: BLE001 — Agent 异常 → turn.failed（不静默吞异常）
        logger.exception(
            "WsTurnRunner 执行异常: turn=%s session=%s question=%.40s",
            turn.turn_id,
            session.session_id,
            question,
        )
        try:
            await emit(
                "turn.failed",
                {
                    "error_code": "AGENT_ERROR",
                    "message": "处理请求时发生内部错误，请稍后重试",
                    "recoverable": True,
                },
            )
        except Exception:  # noqa: BLE001 — 错误事件发送失败仅记录
            logger.warning("WsTurnRunner: 错误事件发送失败", exc_info=True)
        return TurnResult("failed", turn.turn_id, session.sequence)


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
        await emit(
            "turn.failed",
            {
                "error_code": "NO_RESPONSE",
                "message": "Agent 未返回结果",
            },
        )
        return TurnResult("no_response", turn.turn_id, session.sequence)

    # artifact.upsert — 风险等级结构化产物（前端面板消费，V12 契约）
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

    await emit(
        "turn.completed",
        {
            "answer": final_response.answer,
            "risk_level": final_response.risk_level,
            "claims_count": len(state.get("claims", [])),
            "follow_ups": getattr(final_response, "follow_ups", []),
            "evidence_count": len(state.get("evidence", [])),
            "evidence_ids": [
                getattr(ev, "evidence_id", None)
                for ev in state.get("evidence", [])
                if getattr(ev, "evidence_id", None)
            ],
            "warnings": warnings,
            "finance": finance_payload,
            "pattern_matches": pattern_items,
            # Phase D #12: 正式链路载荷（与 REST equity_chains 一致）
            "equity_chains": _extract_equity_chains(state),
        },
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
