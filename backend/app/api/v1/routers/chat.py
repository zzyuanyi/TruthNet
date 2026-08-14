"""对话路由 — V12 baseline (审计修复版).

POST /api/v1/chat — V12 response envelope + Agent graph (REST)。
WS /api/v1/chat/ws — V12 event envelope + Agent graph (WebSocket)。

审计修复 (P0-1, P0-3):
  - POST /api/v1/chat 不再返回硬编码 mock，改为进入真实 Agent graph
  - REST 与 WS 使用同一套 Agent 流程
  - 移除贵州茅台硬编码 mock
"""

import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.schemas.chat import (
    ChatDataV1,
    ChatEvidenceV1,
    ChatRequestV1,
    ClaimV1,
    CompanyCandidateV1,
    ModuleStatusV1,
)
from app.domain.evidence.models import supporting_evidence_ids
from app.api.v1.schemas.common import ApiMeta, V12Response
from app.api.v1.schemas.ws import (
    ChatQueryPayload,
    CompanyConfirmPayload,
    StreamResumeAckPayload,
    StreamResumePayload,
    TurnCancelledPayload,
    TurnCancelPayload,
)
from app.application.services.ws_session_manager import session_manager
from app.application.services.ws_turn_runner import run_turn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Graph 实例延迟创建（不在 import 时编译）
_compiled_graph = None
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


@dataclass
class _RestSessionGate:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


_rest_session_gates: dict[str, _RestSessionGate] = {}


@asynccontextmanager
async def _serialize_rest_session(session_id: str):
    """Serialize REST turns per session while retaining cross-session concurrency."""
    gate = _rest_session_gates.setdefault(session_id, _RestSessionGate())
    gate.users += 1
    acquired = False
    try:
        await gate.lock.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            gate.lock.release()
        gate.users -= 1
        if gate.users == 0 and _rest_session_gates.get(session_id) is gate:
            _rest_session_gates.pop(session_id, None)


def _get_graph():
    """延迟初始化 Agent graph（避免 import 时副作用）."""
    global _compiled_graph
    if _compiled_graph is None:
        from app.agents.graph import create_agent_graph

        _compiled_graph = create_agent_graph().compile()
        logger.info("Agent graph 已编译")
    return _compiled_graph


def _resolve_data_as_of(result: dict) -> str:
    """实际数据截止日（P2-4）：所有证据 period 解析为 date 取最大值。

    只返回标准化实际日期（YYYY-MM-DD）；用户请求期次原文由
    ChatDataV1.requested_period_text 单独承载，二者不再混用。
    包含 research 等 generate 阶段新增证据（state["evidence"]）。
    """
    from datetime import datetime

    results = result.get("results")
    evidence_items: list = []
    if results is not None:
        for mod in (results.finance, results.equity, results.events):
            if mod is None:
                continue
            evidence_items.extend(getattr(mod, "evidence", []) or [])
    evidence_items.extend(result.get("evidence", []) or [])

    latest = None
    for ev in evidence_items:
        p = str(getattr(ev, "period", "") or "").strip()
        if not p:
            continue
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                d = datetime.strptime(p, fmt)
            except ValueError:
                continue
            if latest is None or d > latest:
                latest = d
            break
    return latest.strftime("%Y-%m-%d") if latest else ""


def _pending_remaining_ids(snapshot: dict) -> list[str]:
    """pending 快照中仍待确认的 mention_id 列表（P0-1：仅 needs_confirmation）。"""
    return [
        mid
        for mid, m in snapshot.get("mentions", {}).items()
        if m.get("status") == "needs_confirmation"
    ]


# v3.3 批次 A（P0-1）：resume 启动的结构化结果——停止传播魔法字符串，
# 路由据此分流且不得再发第二个通用失败事件
_RESUME_STARTED = "started"
_RESUME_WAITING_ORIGIN = "waiting_origin"
_RESUME_TURN_IN_PROGRESS = "turn_in_progress"
_RESUME_RESUME_IN_PROGRESS = "resume_in_progress"
_RESUME_ALREADY_RESUMED = "already_resumed"
_RESUME_FAILED_BEFORE_ACCEPT = "start_failed_before_accept"
_RESUME_FAILED_TERMINAL = "start_failed_terminal_emitted"
_RESUME_STATE_CONFLICT = "state_conflict"


async def _claim_and_start_resume(
    *,
    session,
    sid: str,
    pending: dict,
    snapshot: dict,
    _envelope,
    _emit,
    _run_ws_turn,
    turn_tasks: set,
) -> str:
    """确认完成后的原子领取与 T+1 启动（v3.1 P0-1 + v3.2.1 批次 5 +
    v3.3 批次 A exactly-once 终态 + v3.3.1 §7.2/7.3）。

    1. 等待来源 turn 的 task 结束（TimeoutError 吞掉并继续 claim；
       CancelledError 必须向上抛出——连接关闭后不得继续启动 T+1）；
    2. claim_pending_resume 原子领取（返回一次性 claim token）；
    3. 成功 → accepted 两阶段发送（先同步提交 journal 再投递连接队列，
       取消窗口按"已提交"处理）→ create_task → 锁内原子
       attach_and_consume_pending_resume（claim 三件套校验）；
    4. 任一失败：定向取消新 task、按 claim token abort 回滚 pending；
       已写 accepted 的 turn 经 claim_terminal_event 抢占发送唯一
       RESUME_START_FAILED；未写 accepted 的失败不伪造 turn 终态；
    5. attach 成功后 task 进入连接级 turn_tasks registry（§7.3：
       断线取消与普通 turn 同一生命周期）。

    Returns:
        结构化结果（模块级 _RESUME_* 常量），路由据此分流。
        仅 CancelledError 在完成回滚后继续抛出。
    """
    origin_turn_id = pending["origin_turn_id"]
    origin = session_manager.get_turn(session, origin_turn_id)
    if origin is not None and origin.task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(origin.task), timeout=60)
        except TimeoutError:
            pass  # 来源 turn 未结束：继续 claim，由其返回 ORIGIN_TURN_ACTIVE
    new_turn_id = str(uuid.uuid4())
    status, resume = session_manager.claim_pending_resume(
        session, origin_turn_id, snapshot["revision"], new_turn_id
    )
    logger.info("chat: claim_pending_resume -> %s (new_turn=%s)", status, new_turn_id)
    if status == "ORIGIN_TURN_ACTIVE":
        return _RESUME_WAITING_ORIGIN
    if status == "TURN_IN_PROGRESS":
        return _RESUME_TURN_IN_PROGRESS
    if status == "RESUME_IN_PROGRESS":
        return _RESUME_RESUME_IN_PROGRESS
    if status == "ALREADY_RESUMED":
        return _RESUME_ALREADY_RESUMED
    if status != "OK":
        return _RESUME_STATE_CONFLICT

    # v3.3.1 §7.2：一次性 claim token（attach/abort 三件套校验）
    claim_id = str(resume.get("claim_id") or "")
    task = None
    accepted_journaled = False
    trace_id = ""

    def _abort_resume() -> None:
        """按 claim token abort：返回值必须处理并记录（§7.2 不得忽略）。"""
        outcome = session_manager.abort_claimed_resume(
            session, origin_turn_id, new_turn_id, claim_id
        )
        if outcome.turn_present:
            session_manager.remove_turn(session, new_turn_id)
        logger.warning(
            "chat: abort_claimed_resume owned=%s restored=%s turn=%s terminal=%s",
            outcome.owned,
            outcome.pending_restored,
            outcome.turn_present,
            outcome.terminal_claimed,
        )

    try:
        from app.agents.state import RequestContext
        from app.application.models.company_resolution import EntityResolutionOverride

        override = EntityResolutionOverride(**resume["override"])
        request_context = RequestContext(entity_overrides=override)
        trace_id = str(uuid.uuid4())
        accepted_event = _envelope(
            "turn.accepted",
            {
                "message": f"已收到确认，正在重跑: {str(resume['question'] or '')[:50]}...",
                "turn_id": new_turn_id,
            },
            sid=sid,
            trace_id=trace_id,
            turn_id=new_turn_id,
        )
        # 两阶段发送（v3.3 批次 A）：先同步提交 journal（无取消点）并
        # 记录标志，再 await 连接队列——取消发生在两步之间时按"已提交"
        # 处理终态（已写 journal 的 turn 必须恰好一个终态）
        session_obj = session_manager.get_session(sid)
        if session_obj is not None:
            session_obj.journal.append(accepted_event)
            accepted_journaled = True
        primary = session_manager.primary_connection(sid)
        q = _active_connections.get(primary)
        if q is not None:
            await q.put(accepted_event)
        accepted_at = time.perf_counter()
        task = asyncio.create_task(
            _run_ws_turn(
                session_id=sid,
                turn_id=new_turn_id,
                question=str(resume["question"] or ""),
                trace_id=trace_id,
                request_context=request_context,
                accepted_at=accepted_at,
                _envelope=_envelope,
                _emit=_emit,
            )
        )
        # create_task 后到原子操作之间不得出现 await（新 task 尚未获得
        # 运行机会）；attach + consume 锁内原子完成（claim 三件套）
        if not session_manager.attach_and_consume_pending_resume(
            session, origin_turn_id, new_turn_id, task, claim_id
        ):
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001 — 吸收 CancelledError/任务异常
                pass
            # 先抢占终态（turn 仍在 session.turns），再 abort——保证已写
            # accepted 的 turn 恰好一个终态事件
            if accepted_journaled:
                await _emit_resume_start_failed(
                    session, sid, new_turn_id, trace_id, _envelope
                )
            _abort_resume()
            logger.warning("chat: attach_and_consume 失败（state conflict），已回滚")
            return _RESUME_STATE_CONFLICT
        # v3.3.1 §7.3：T+1 task 进入连接级 registry，断线取消与普通
        # turn 同一生命周期
        turn_tasks.add(task)
        task.add_done_callback(turn_tasks.discard)
        return _RESUME_STARTED
    except asyncio.CancelledError:
        # 完成终态与回滚后继续抛出（连接关闭/服务取消：绝不吞掉）
        if task is not None:
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001
                pass
        if accepted_journaled:
            try:
                await _emit_resume_start_failed(
                    session, sid, new_turn_id, trace_id, _envelope
                )
            except Exception:  # noqa: BLE001 — 连接已断，仅保留服务端状态
                logger.warning("chat: 取消窗口内终态发送失败", exc_info=True)
        _abort_resume()
        raise
    except Exception:
        if task is not None:
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001
                pass
        if accepted_journaled:
            await _emit_resume_start_failed(
                session, sid, new_turn_id, trace_id, _envelope
            )
            _abort_resume()
            logger.warning("chat: resume 启动失败（已发终态）", exc_info=True)
            return _RESUME_FAILED_TERMINAL
        _abort_resume()
        logger.warning("chat: resume 启动失败（accepted 前）", exc_info=True)
        return _RESUME_FAILED_BEFORE_ACCEPT


async def _emit_resume_start_failed(
    session, sid: str, turn_id: str, trace_id: str, _envelope
) -> bool:
    """v3.3 批次 A：已写 accepted 的 resume 启动失败终态——经
    claim_terminal_event 原子抢占，保证该 turn 恰好一个终态事件。

    事件写入走与 accepted 相同的两阶段（先同步 journal 再连接队列），
    不依赖路由闭包内的 _emit（本函数为模块级）。
    """
    if not session_manager.claim_terminal_event(session, turn_id):
        return False
    try:
        event = _envelope(
            "turn.failed",
            {
                "error_code": "RESUME_START_FAILED",
                "message": "确认已保存，但自动重跑启动失败，可安全重试",
                "recoverable": True,
            },
            sid=sid,
            trace_id=trace_id,
            turn_id=turn_id,
        )
        session.journal.append(event)
        primary = session_manager.primary_connection(sid)
        q = _active_connections.get(primary)
        if q is not None:
            await q.put(event)
    except Exception:  # noqa: BLE001 — 连接异常时仅能保留服务端状态
        logger.warning("chat: resume 启动失败终态发送失败", exc_info=True)
    return True


def _build_request_context(
    *, company_code: str = "", as_of: str = "", fiscal_year: int | None = None
):
    """Normalize explicit REST/WS context into the shared Agent model."""
    from app.agents.state import RequestContext
    from app.domain.finance.period import normalize_period

    if fiscal_year is not None:
        return RequestContext(
            company_code=company_code,
            as_of=date(fiscal_year, 12, 31),
            as_of_kind="report_period",
            requested_period_text=f"{fiscal_year}年",
        )
    if as_of:
        normalized = normalize_period(as_of)
        if normalized is None:
            raise ValueError("as_of 必须为 YYYYMMDD、YYYY-MM-DD 或 YYYYQn")
        try:
            parsed = datetime.strptime(normalized, "%Y%m%d").date()
        except ValueError as exc:
            raise ValueError("as_of 不是有效日期") from exc
        return RequestContext(
            company_code=company_code,
            as_of=parsed,
            as_of_kind="as_of",
            requested_period_text=as_of.strip(),
        )
    if company_code:
        return RequestContext(company_code=company_code)
    return None


def _build_chat_response(
    result: dict, trace_id: str, session_id: str = ""
) -> V12Response[ChatDataV1]:
    """从 Agent graph 结果构建 V12 REST 响应。

    从 Agent State 中提取结构化数据并转换为 API DTO。
    """
    final_response = result.get("final_response")
    evidence = result.get("evidence", [])
    module_status = result.get("module_status", {})
    results = result.get("results")

    # 提取 risk_score — 优先使用 risk 节点真实评分（RiskOutput），
    # 不再编造启发式分数（曾返回 overall=0.0 掩盖真实 0.73 的用户可见错误）
    risk_output = result.get("risk_output")
    risk_score: dict = {}
    if risk_output is not None:
        scores = {item.dimension: item.score for item in risk_output.sub_scores}
        risk_score = {
            "overall": risk_output.overall_score,
            "financial": scores.get("finance", 0.0),
            "ownership": scores.get("equity", 0.0),
            "sentiment": scores.get("events", 0.0),
        }

    # 提取 evidence — 统一经 ChatEvidenceV1.from_evidence 映射
    # （旧契约 source/field/value + canonical 字段；无证据返回 []，不编造）
    evidence_items = [ChatEvidenceV1.from_evidence(ev) for ev in evidence]

    # 提取 graph
    graph_data: dict = {"nodes": [], "edges": []}
    equity_chains: list[dict] = []
    if results and getattr(results, "equity", None):
        eq = results.equity
        if hasattr(eq, "graph") and eq.graph:
            graph_data = eq.graph
        # Phase D #12: 正式链路载荷（与 REST equity_chains 一致）
        if hasattr(eq, "chain_details") and eq.chain_details:
            equity_chains = eq.chain_details

    # 提取 timeline
    timeline: list = []
    if results and getattr(results, "events", None):
        evt = results.events
        if hasattr(evt, "timeline"):
            timeline = evt.timeline

    # 收集 warnings（Finance 口径说明恰好一次 + 模块状态）
    warnings: list[str] = []
    runtime = result.get("runtime")
    if runtime and hasattr(runtime, "warnings"):
        warnings.extend(runtime.warnings)
    if results and getattr(results, "finance", None) and results.finance.warnings:
        for w in results.finance.warnings:
            if w and w not in warnings:
                warnings.append(w)
    for name, ms in module_status.items():
        if hasattr(ms, "state") and ms.state in ("partial", "failed"):
            warnings.append(f"模块 {name} 状态: {ms.state}")

    # 检测 missing_modules
    missing_modules: list[str] = []
    expected_modules = {"finance", "equity", "events"}
    for name in expected_modules:
        if name not in module_status:
            missing_modules.append(f"{name} 模块未执行")

    answer = ""
    follow_ups: list[str] = []
    if final_response:
        answer = getattr(final_response, "answer", "")
        follow_ups = getattr(final_response, "follow_ups", []) or []

    # claims — 从 Agent State 透出（结构化问答结论声明，API 公共投影）
    claims_items = [ClaimV1.from_claim(c) for c in result.get("claims", [])]
    # module_status — typed ModuleStatusV1（对象/dict/字符串/None 全兼容）
    module_status_items = {
        k: ModuleStatusV1.from_status(v) for k, v in module_status.items()
    }
    # risk_level — 优先 final_response（最终阶段确定的等级），
    # 不从 risk_score.overall 换算（避免双口径偏差）；risk_output 仅作备用
    risk_level = "unknown"
    if final_response:
        risk_level = getattr(final_response, "risk_level", None) or "unknown"
    elif risk_output is not None:
        risk_level = getattr(risk_output, "risk_level", None) or "unknown"

    # Phase D #16: 模式三要素（phase/alternative_explanation/regulatory_hint）
    pattern_matches = result.get("pattern_matches", []) or []
    pattern_items = [
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
        for m in pattern_matches
    ]

    # #13：可展示证据子集（叶子 Claim 引用，排除综合 risk Claim）
    supporting_ids = set(supporting_evidence_ids(result.get("claims", [])))
    supporting_evidence_items = [
        ev for ev in evidence_items if ev.evidence_id in supporting_ids
    ]

    # P2-4：请求期次原文（与 data_as_of 实际数据截止日分离）
    plan = result.get("plan")
    requested_period_text = (
        getattr(plan, "requested_period_text", "") if plan is not None else ""
    )
    intent = getattr(plan, "intent", "") if plan is not None else ""
    # v3.3.4 方案 §3.3/§6.1：轻量概览结构化载荷（只读追加，向后兼容）
    light_comparison = result.get("light_comparison") or {}
    comparison_mode = light_comparison.get("comparison_mode", "") or ""
    overview_rows = light_comparison.get("overview_rows", []) or []
    requested_scope = light_comparison.get("requested_scope", "") or ""
    next_steps = light_comparison.get("next_steps", []) or []
    company_candidates = [
        CompanyCandidateV1.from_company(item)
        for item in (result.get("company_candidates") or [])
    ]
    # v3.1 P1-5：REST 最小只读 mention 分组（多 mention 时旧字段为空，
    # 新字段提供完整分组；不提供 REST confirm endpoint）
    # v3.3.1 §8.2：追加 grouped alternatives / issues 只读字段
    resolution = result.get("entity_resolution_result")
    company_mentions: list[dict] = []
    segmentation_alternatives: list[dict] = []
    entity_resolution_issues: list[dict] = []
    needs_confirmation = False
    if resolution is not None:
        company_mentions = [m.model_dump() for m in getattr(resolution, "mentions", [])]
        segmentation_alternatives = [
            a.model_dump()
            for a in (getattr(resolution, "segmentation_alternatives", None) or [])
        ]
        entity_resolution_issues = [
            i.model_dump()
            for i in (getattr(resolution, "resolution_issues", None) or [])
        ]
        needs_confirmation = bool(getattr(resolution, "needs_confirmation", False))
        if needs_confirmation:
            follow_ups = list(follow_ups)
            follow_ups.append(
                "存在多个候选公司，请补充完整公司名称，或使用支持候选确认的"
                "聊天窗口继续。"
            )

    return V12Response(
        data=ChatDataV1(
            answer=answer or "分析完成，未生成结构化答案。",
            session_id=session_id,
            company_candidates=company_candidates,
            company_mentions=company_mentions,
            segmentation_alternatives=segmentation_alternatives,
            entity_resolution_issues=entity_resolution_issues,
            needs_confirmation=needs_confirmation,
            evidence=evidence_items,
            graph=graph_data,
            timeline=timeline,
            risk_score=risk_score,
            warnings=warnings,
            missing_modules=missing_modules,
            trace_id=trace_id,
            follow_ups=follow_ups,
            claims=claims_items,
            module_status=module_status_items,
            risk_level=risk_level,
            pattern_matches=pattern_items,
            equity_chains=equity_chains,
            supporting_evidence=supporting_evidence_items,
            requested_period_text=requested_period_text,
            intent=intent,
            comparison_mode=comparison_mode,
            overview_rows=overview_rows,
            requested_scope=requested_scope,
            next_steps=next_steps,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_as_of=_resolve_data_as_of(result),
        ),
        warnings=[],
    )


@router.post("/chat", response_model=V12Response[ChatDataV1])
async def chat_v1(request: ChatRequestV1):
    """对话接口 — V12 REST，进入 Agent graph。

    与 WebSocket 使用同一套 Agent 流程和 State。
    """
    from app.infrastructure.observability.timing import metrics_collector

    trace_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    try:
        from app.agents.state import ModuleResults, RuntimeState

        context = request.context
        request_context = _build_request_context(
            company_code=(context.company_code or "") if context else "",
            fiscal_year=context.fiscal_year if context else None,
        )

        state = {
            "messages": [],
            "user_query": request.question,
            "request_context": request_context,
            "company": None,
            "company_candidates": [],
            "plan": None,
            "module_status": {},
            "results": ModuleResults(),
            "evidence": [],
            "claims": [],
            "final_response": None,
            "runtime": RuntimeState(
                trace_id=trace_id, session_id=session_id, turn_id=turn_id
            ),
        }

        # 在线程池中执行 Agent graph（避免阻塞事件循环）
        with metrics_collector.timed(
            "rest.agent_total_ms", trace_id=trace_id, degraded=False
        ):
            async with _serialize_rest_session(session_id):
                result = await asyncio.to_thread(_get_graph().invoke, state)
        # 各模块耗时（来自 module_status.duration_ms，Phase D #7）
        for name, ms in (result.get("module_status") or {}).items():
            dur = getattr(ms, "duration_ms", None)
            if dur is not None:
                metrics_collector.record(
                    f"rest.module_{name}_ms",
                    float(dur),
                    trace_id=trace_id,
                )
        with metrics_collector.timed(
            "rest.persist_ms", trace_id=trace_id, degraded=False
        ):
            resp = _build_chat_response(result, trace_id, session_id)
        return resp

    except Exception:
        logger.exception(
            "REST Agent 执行异常: trace_id=%s question=%.50s",
            trace_id,
            request.question,
        )
        return V12Response(
            data=ChatDataV1(
                answer="处理请求时发生内部错误，请稍后重试。",
                session_id=session_id,
                evidence=[],
                graph={},
                timeline=[],
                risk_score={},
                warnings=["内部错误"],
                missing_modules=["Agent 执行失败"],
                trace_id=trace_id,
                risk_level="unknown",  # 显式返回（异常无等级结论）
            ),
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
            warnings=[
                {
                    "code": "AGENT_ERROR",
                    "message": "处理请求时发生内部错误",
                    "module": "chat",
                    "recoverable": True,
                }
            ],
        )


# 活跃连接注册表：connection_id → asyncio.Queue[dict]（事件投递队列）
# 由 WS 连接的生命周期管理；关闭时清理。
_active_connections: dict[str, asyncio.Queue] = {}


def _new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


class _ConnectionScope:
    """单个 WS 连接的作用域：绑定连接队列 + 当前逻辑会话.

    新连接替代旧连接策略（WsSessionManager.attach_connection）：
    session 的事件只路由到 primary_connection，确保多连接语义确定。
    """

    def __init__(self, ws: WebSocket, connection_id: str) -> None:
        self.ws = ws
        self.connection_id = connection_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.session_id: str = ""


@router.websocket("/chat/ws")
async def websocket_chat_v1(ws: WebSocket):
    """WebSocket 对话端点 — Phase D #5/#6/#10 重构.

    接收与执行分离：
      - receiver task: 持续读取控制事件（ping / turn.cancel / stream.resume /
        chat.query），不被长 Agent 执行阻塞；
      - sender task: 从连接队列取事件发送（事件先写会话缓冲再投递）；
      - 每个 query 启动独立 turn task（run_turn），支持协作式取消与真流式。

    V12 服务端事件：
      - turn.accepted / turn.completed / turn.failed / turn.cancelled
      - module.started / module.completed
      - answer.delta / artifact.upsert / heartbeat / stream.resume_ack

    兼容旧格式：{question: "..."} / {data: {question: "..."}} → chat.query。
    """
    await ws.accept()
    conn_id = session_manager.new_connection_id()
    scope = _ConnectionScope(ws, conn_id)
    # URL query 兼容（部分客户端在连接时携带）；payload.session_id 仍优先覆盖
    session_id = ws.query_params.get("session_id") or str(uuid.uuid4())
    session = session_manager.attach_connection(session_id, conn_id)
    scope.session_id = session_id
    _active_connections[conn_id] = scope.queue

    turn_tasks: set[asyncio.Task] = set()
    sender_task = asyncio.create_task(_ws_sender(scope, session_id))

    def _envelope(
        event_type: str,
        payload: dict,
        *,
        sid: str,
        trace_id: str = "",
        turn_id: str = "",
    ) -> dict:
        """分配会话内单调递增序号并返回完整九字段信封.

        不直接发送——调用方通过 scope.queue 投递（sender task 发送）。

        turn_id 必须由 turn 相关事件显式传入（accepted/cancelled/completed/
        failed/delta 等）；heartbeat、非法 JSON、未知事件等非 turn 事件保持空串。
        禁止使用连接级全局 turn_id——同一连接可并发多个 turn，会串写。
        """
        seq = session_manager.next_sequence(session)
        env = {
            "schema_version": "1.0",
            "event_id": _new_event_id(),
            "event_type": event_type,
            "session_id": sid,
            "turn_id": turn_id,
            "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id or str(uuid.uuid4()),
            "payload": payload,
        }
        return env

    async def _emit(sid: str, event: dict) -> None:
        """事件 → 会话缓冲 + 当前主连接队列（新连接替代旧连接）."""
        session_obj = session_manager.get_session(sid)
        if session_obj is not None:
            session_obj.journal.append(event)
        primary = session_manager.primary_connection(sid)
        q = _active_connections.get(primary)
        if q is not None:
            await q.put(event)

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _emit(
                    session_id,
                    _envelope(
                        "turn.failed",
                        {"error_code": "INVALID_JSON", "message": "无效的 JSON 格式"},
                        sid=session_id,
                    ),
                )
                continue

            event_type = msg.get("event_type", "")
            payload = msg.get("payload", {})

            # 客户端传入 session_id → 覆盖自动生成的 UUID（多轮记忆前置条件）
            client_sid = payload.get("session_id", "")
            if client_sid and (
                not isinstance(client_sid, str)
                or _SESSION_ID_RE.fullmatch(client_sid) is None
            ):
                await _emit(
                    session_id,
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "INVALID_SESSION_ID",
                            "message": "session_id 格式无效",
                            "recoverable": True,
                        },
                        sid=session_id,
                    ),
                )
                continue
            if client_sid and client_sid != session_id:
                # 切换逻辑会话：attach 到新会话（该连接成为新会话主连接）
                session_manager.detach_connection(session_id, conn_id)
                session_id = client_sid
                scope.session_id = session_id
                session = session_manager.attach_connection(session_id, conn_id)
            sid = session_id

            if not event_type:
                # 旧格式: {question: "..."} 或 {data: {question: "..."}}
                question = msg.get("question", "") or msg.get("data", {}).get(
                    "question", ""
                )
                if question:
                    event_type = "chat.query"
                    payload = {"text": question}

            # ping → heartbeat（不落缓冲，纯存活响应）
            if event_type == "ping":
                await _emit(
                    sid,
                    _envelope(
                        "heartbeat",
                        {"server_time": datetime.now(timezone.utc).isoformat()},
                        sid=sid,
                    ),
                )
                continue

            # turn.cancel — 协作式取消（≤2s 确认；幂等；不影响他会话）
            if event_type == "turn.cancel":
                try:
                    cancel_payload = TurnCancelPayload.model_validate(payload)
                except Exception:  # noqa: BLE001
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "INVALID_CANCEL",
                                "message": "取消请求参数无效",
                            },
                            sid=sid,
                        ),
                    )
                    continue
                await _handle_cancel(sid, cancel_payload, _envelope, _emit)
                continue

            # stream.resume — 断线补发（原 event_id/sequence/turn_id 原样回放）
            if event_type == "stream.resume":
                try:
                    resume_payload = StreamResumePayload.model_validate(payload)
                except Exception:  # noqa: BLE001
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "INVALID_RESUME",
                                "message": "恢复请求参数无效",
                            },
                            sid=sid,
                        ),
                    )
                    continue
                await _handle_resume(sid, resume_payload, _envelope, _emit)
                continue

            # 有效 query 事件
            if event_type not in ("chat.query", "chat.follow_up", "company.confirm"):
                await _emit(
                    sid,
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "UNKNOWN_EVENT",
                            "message": f"未知事件类型: {event_type}",
                        },
                        sid=sid,
                    ),
                )
                continue

            request_context = None
            if event_type == "company.confirm":
                try:
                    confirm = CompanyConfirmPayload.model_validate(payload)
                except Exception:  # noqa: BLE001
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "INVALID_COMPANY_CONFIRM",
                                "message": "公司确认参数无效",
                                "recoverable": True,
                            },
                            sid=sid,
                        ),
                    )
                    continue
                pending = session_manager.get_pending_disambiguation(session)
                pending_turn = (
                    pending.get("origin_turn_id", pending.get("turn_id"))
                    if pending
                    else None
                )
                if pending is None or (
                    confirm.turn_id and confirm.turn_id != pending_turn
                ):
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "NO_PENDING_DISAMBIGUATION",
                                "message": "当前没有待确认的公司候选",
                                "recoverable": True,
                            },
                            sid=sid,
                        ),
                    )
                    continue
                company_code = confirm.company_code

                # ── 新协议（mention 分组：mention_id + revision 成对）──
                if confirm.is_mention_protocol:
                    if confirm.mention_id is None or confirm.revision is None:
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": "mention 协议必须同时提供 mention_id 与 revision",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    status, snapshot = session_manager.confirm_pending_mention(
                        session,
                        pending_turn,
                        confirm.mention_id,
                        company_code,
                        confirm.revision,
                    )
                    if status in (
                        "NO_PENDING",
                        "REVISION_MISMATCH",
                        "INVALID_MENTION",
                        "INVALID_CODE",
                        "NOT_ACCEPTING",
                    ):
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": f"公司确认被拒绝（{status}）",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    remaining = _pending_remaining_ids(snapshot)
                    if status == "ALREADY_RESUMED":
                        # v3.2.1 批次 5：consumed 同值重放 → 幂等完成 ack
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": [],
                                    "resolved": True,
                                    "revision": snapshot["revision"],
                                    "resume_status": "completed",
                                    "message": "确认已生效",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if status == "RESUME_IN_PROGRESS":
                        # v3.2.1 批次 5：resuming 同值重放 → 进行中 ack
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": [],
                                    "resolved": True,
                                    "revision": snapshot["revision"],
                                    "resume_status": "in_progress",
                                    "message": "确认已生效，重跑进行中",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if status == "WAITING":
                        # 部分确认：只 ACK，不启动新 turn（P0-1）
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": remaining,
                                    "resolved": False,
                                    "revision": snapshot["revision"],
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if status == "RELATION_BLOCKED":
                        # P0-3：身份确认但关系未解析 → 澄清，不启动 T+1
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": remaining,
                                    "resolved": False,
                                    "revision": snapshot["revision"],
                                    "relation_status": "needs_clarification",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if status == "IDENTITY_BLOCKED":
                        # v3.3 P0-2：身份集不完整（not_found/refinement/
                        # 重复代码/role 缺失）→ 可诊断阻断，不启动 T+1
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": remaining,
                                    "resolved": False,
                                    "revision": snapshot["revision"],
                                    "resume_status": "identity_blocked",
                                    "message": "公司身份集合不完整，请补充完整公司名称或重新提问",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    # RESUME_READY：ACK(resolved) → 等待来源 turn → claim → T+1
                    await _emit(
                        sid,
                        _envelope(
                            "company.confirm_ack",
                            {
                                "turn_id": pending_turn,
                                "mention_id": confirm.mention_id,
                                "wind_code": company_code,
                                "remaining_mentions": [],
                                "resolved": True,
                                "revision": snapshot["revision"],
                                "resume_status": "waiting",
                            },
                            sid=sid,
                        ),
                    )
                    try:
                        claim_status = await _claim_and_start_resume(
                            session=session,
                            sid=sid,
                            pending=pending,
                            snapshot=snapshot,
                            _envelope=_envelope,
                            _emit=_emit,
                            _run_ws_turn=_run_ws_turn,
                            turn_tasks=turn_tasks,
                        )
                    except asyncio.CancelledError:
                        raise  # helper 已完成回滚，继续传播
                    # v3.3 批次 A：helper 内部处理失败并返回结构化结果，
                    # 路由按 outcome 分流，不得再发送第二个通用失败事件
                    if claim_status == _RESUME_STARTED:
                        continue
                    if claim_status == _RESUME_FAILED_TERMINAL:
                        continue  # helper 已抢占发送唯一 RESUME_START_FAILED
                    if claim_status in (
                        _RESUME_WAITING_ORIGIN,
                        _RESUME_TURN_IN_PROGRESS,
                    ):
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": [],
                                    "resolved": True,
                                    "revision": snapshot["revision"],
                                    "resume_status": "waiting",
                                    "message": "确认已保存，正在等待自动重跑",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if claim_status == _RESUME_RESUME_IN_PROGRESS:
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": [],
                                    "resolved": True,
                                    "revision": snapshot["revision"],
                                    "resume_status": "in_progress",
                                    "message": "确认已生效，重跑进行中",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    if claim_status == _RESUME_ALREADY_RESUMED:
                        await _emit(
                            sid,
                            _envelope(
                                "company.confirm_ack",
                                {
                                    "turn_id": pending_turn,
                                    "mention_id": confirm.mention_id,
                                    "wind_code": company_code,
                                    "remaining_mentions": [],
                                    "resolved": True,
                                    "revision": snapshot["revision"],
                                    "resume_status": "completed",
                                    "message": "确认已生效",
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    # failed_before_accept / state_conflict：pending 已回滚
                    # ready_to_resume（未写 accepted 不伪造 turn 终态），
                    # 发可诊断 ack，用户可重发同一确认恢复
                    await _emit(
                        sid,
                        _envelope(
                            "company.confirm_ack",
                            {
                                "turn_id": pending_turn,
                                "mention_id": confirm.mention_id,
                                "wind_code": company_code,
                                "remaining_mentions": [],
                                "resolved": True,
                                "revision": snapshot["revision"],
                                "resume_status": "waiting",
                                "message": "确认已保存，但自动重跑暂时失败，请重发确认或重新提问",
                            },
                            sid=sid,
                        ),
                    )
                    continue

                # ── 旧协议兼容（无 mention_id/revision）──
                mentions = pending.get("mentions", {})
                if not mentions:
                    # 旧结构 pending（无 mention 分组，8.11 既有形态）：
                    # 保持原逻辑——候选校验 + 带选中代码重跑原问题
                    # （落到下方 turn 启动段，不 continue）
                    allowed_codes = {
                        str(item.get("wind_code") or "")
                        for item in pending.get("candidates", [])
                    }
                    if company_code not in allowed_codes:
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": "确认的公司不在候选列表中",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    question = str(pending.get("question") or "")
                    try:
                        request_context = _build_request_context(
                            company_code=company_code,
                            as_of=str(pending.get("as_of") or ""),
                        )
                    except ValueError:
                        request_context = _build_request_context(
                            company_code=company_code
                        )
                    session_manager.set_pending_disambiguation(session, None)
                else:
                    # 新结构 pending：仅恰好一个 needs_confirmation 且
                    # revision 为初始值允许一次兼容确认（P0-2）
                    remaining = [
                        mid
                        for mid, m in mentions.items()
                        if m.get("status") == "needs_confirmation"
                    ]
                    if len(remaining) != 1 or pending.get("revision") != 0:
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": "存在多个待确认公司，请使用支持 mention 分组确认的客户端",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    allowed_codes = {
                        str(c.get("wind_code") or "")
                        for c in (mentions.get(remaining[0]) or {}).get(
                            "candidates", []
                        )
                    }
                    if company_code not in allowed_codes:
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": "确认的公司不在候选列表中",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    status, snapshot = session_manager.confirm_pending_mention(
                        session,
                        pending_turn,
                        remaining[0],
                        company_code,
                        pending.get("revision", 0),
                    )
                    if status != "RESUME_READY":
                        await _emit(
                            sid,
                            _envelope(
                                "turn.failed",
                                {
                                    "error_code": "INVALID_COMPANY_CONFIRM",
                                    "message": f"公司确认失败（{status}）",
                                    "recoverable": True,
                                },
                                sid=sid,
                            ),
                        )
                        continue
                    await _emit(
                        sid,
                        _envelope(
                            "company.confirm_ack",
                            {
                                "turn_id": pending_turn,
                                "mention_id": remaining[0],
                                "wind_code": company_code,
                                "remaining_mentions": [],
                                "resolved": True,
                                "revision": snapshot["revision"],
                                "resume_status": "waiting",
                            },
                            sid=sid,
                        ),
                    )
                    try:
                        claim_status = await _claim_and_start_resume(
                            session=session,
                            sid=sid,
                            pending=pending,
                            snapshot=snapshot,
                            _envelope=_envelope,
                            _emit=_emit,
                            _run_ws_turn=_run_ws_turn,
                            turn_tasks=turn_tasks,
                        )
                    except asyncio.CancelledError:
                        raise  # helper 已完成回滚，继续传播
                    # v3.3 批次 A：结构化 outcome 分流（旧协议兼容分支）
                    if claim_status in (_RESUME_STARTED, _RESUME_FAILED_TERMINAL):
                        continue
                    resume_status = (
                        "completed"
                        if claim_status == _RESUME_ALREADY_RESUMED
                        else (
                            "in_progress"
                            if claim_status == _RESUME_RESUME_IN_PROGRESS
                            else "waiting"
                        )
                    )
                    message = (
                        "确认已保存，但自动重跑暂时失败，请重发确认或重新提问"
                        if claim_status
                        in (_RESUME_FAILED_BEFORE_ACCEPT, _RESUME_STATE_CONFLICT)
                        else ""
                    )
                    await _emit(
                        sid,
                        _envelope(
                            "company.confirm_ack",
                            {
                                "turn_id": pending_turn,
                                "mention_id": remaining[0],
                                "wind_code": company_code,
                                "remaining_mentions": [],
                                "resolved": True,
                                "revision": snapshot["revision"],
                                "resume_status": resume_status,
                                **({"message": message} if message else {}),
                            },
                            sid=sid,
                        ),
                    )
                    continue
            else:
                raw_text = payload.get("text")
                if not isinstance(raw_text, str) or not raw_text.strip():
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "MISSING_QUESTION",
                                "message": "payload.text 为必填项",
                                "recoverable": True,
                            },
                            sid=sid,
                        ),
                    )
                    continue
                try:
                    query_payload = ChatQueryPayload.model_validate(payload)
                    request_context = _build_request_context(
                        as_of=query_payload.as_of or ""
                    )
                except Exception as exc:  # noqa: BLE001
                    await _emit(
                        sid,
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "INVALID_QUERY",
                                "message": f"查询参数无效: {exc}",
                                "recoverable": True,
                            },
                            sid=sid,
                        ),
                    )
                    continue
                question = query_payload.text
                session_manager.set_pending_disambiguation(session, None)

            # 每一轮新 turn_id + trace_id
            turn_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())

            # 同一会话只允许一个活跃 turn，避免 turn_index/checkpoint 竞争。
            turn = session_manager.start_turn_if_idle(session, turn_id, question)
            if turn is None:
                await _emit(
                    sid,
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "TURN_IN_PROGRESS",
                            "message": "当前会话已有问题正在处理，请等待完成或先取消",
                            "recoverable": True,
                        },
                        sid=sid,
                    ),
                )
                continue

            await _emit(
                sid,
                _envelope(
                    "turn.accepted",
                    {"message": f"已收到问题: {question[:50]}...", "turn_id": turn_id},
                    sid=sid,
                    trace_id=trace_id,
                    turn_id=turn_id,
                ),
            )
            # 性能基准（复核约束）：first_feedback_ms/first_delta_ms 从
            # turn.accepted 实际发送时刻计时，而非 run_turn() 内部——
            # 避免漏掉任务调度/排队时间（perf_counter 同源单调时钟）
            accepted_at = time.perf_counter()

            # 启动独立 turn task（接收与执行分离，不阻塞控制事件）
            task = asyncio.create_task(
                _run_ws_turn(
                    session_id=sid,
                    turn_id=turn_id,
                    question=question,
                    trace_id=trace_id,
                    request_context=request_context,
                    accepted_at=accepted_at,
                    _envelope=_envelope,
                    _emit=_emit,
                )
            )
            # 绑定 ActiveTurn.task：expire_idle 依赖它判断活跃 turn，
            # 不绑定则活跃会话可能被 janitor 误回收
            session_manager.attach_task(session, turn_id, task)
            turn_tasks.add(task)
            task.add_done_callback(turn_tasks.discard)

    except WebSocketDisconnect:
        logger.info(
            "WebSocket 客户端断开: connection=%s session_id=%s", conn_id, session_id
        )
    except Exception:
        logger.exception(
            "WebSocket 未预期异常: connection=%s session_id=%s", conn_id, session_id
        )
    finally:
        # 连接销毁：取消事件发送、清理注册、取消本会话活跃 turn（不取消他会话）
        sender_task.cancel()
        _active_connections.pop(conn_id, None)
        session_manager.detach_connection(session_id, conn_id)
        # 若连接不再属于任何会话 → 会话无活跃连接时按 TTL 回收（不强制关闭）
        # v3.3.1 §7.3：普通 turn 与 T+1 同 registry、同生命周期——
        # 不得只 cancel 不 await（否则 task 可能仍持有资源/写状态）；
        # 每个已 accepted turn 的终态由 runner/取消路径经
        # claim_terminal_event 抢占发送，此处不重复伪造
        pending_tasks = [t for t in list(turn_tasks) if not t.done()]
        for task in pending_tasks:
            task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        # 最后再结束 sender（清理完成后残余事件仍可发送）
        try:
            await sender_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


async def _ws_sender(scope: _ConnectionScope, _session_id: str) -> None:
    """sender task：从连接队列取事件并发送（队列空则等待）。"""
    while True:
        event = await scope.queue.get()
        try:
            await scope.ws.send_json(event)
        except Exception:  # noqa: BLE001
            logger.warning(
                "WS sender 发送失败: connection=%s", scope.connection_id, exc_info=True
            )
            break


async def _handle_cancel(
    sid: str, payload: TurnCancelPayload, _envelope, _emit
) -> None:
    """协作式取消：立即置位 token；当前节点结束后不再启动下一节点。

    终态保证：turn.cancelled 恰好一次，不发送 turn.completed。
    幂等：重复 cancel 返回相同确认，不重复置位。
    不取消同 session 其他 turn / 其他 session 的 turn。
    """
    session_obj = session_manager.get_session(sid)
    if session_obj is None:
        await _emit(
            sid,
            _envelope(
                "turn.failed",
                {
                    "error_code": "SESSION_NOT_FOUND",
                    "message": "会话不存在",
                    "recoverable": True,
                },
                sid=sid,
            ),
        )
        return

    turn = session_manager.get_turn(session_obj, payload.turn_id)
    if turn is None:
        await _emit(
            sid,
            _envelope(
                "turn.failed",
                {
                    "error_code": "TURN_NOT_FOUND",
                    "message": "轮次不存在或已结束",
                    "recoverable": True,
                },
                sid=sid,
            ),
        )
        return

    # 置位取消令牌（幂等；已完成 turn 返回 already_terminal）
    session_manager.cancel_turn(session_obj, payload.turn_id)
    # 原子抢占终态发送权：抢占成功者唯一发送 turn.cancelled（确认与终态合一）；
    # 抢占失败（终态已由 runner / 其他路径发出，含 already_terminal 与重复
    # cancel）→ 不重复发送第二个终态事件。
    if session_manager.claim_terminal_event(session_obj, payload.turn_id):
        await _emit(
            sid,
            _envelope(
                "turn.cancelled",
                TurnCancelledPayload(turn_id=payload.turn_id).model_dump(),
                sid=sid,
                turn_id=payload.turn_id,
            ),
        )


async def _handle_resume(
    sid: str, payload: StreamResumePayload, _envelope, _emit
) -> None:
    """断线补发：按 session_id + last_sequence 回放缓冲事件.

    - 事件顺序严格递增、不重复、使用原 event_id；
    - 跨新 socket 保持 session sequence；
    - 无事件时返回明确 resume 完成状态；
    - 请求序号早于缓存起点 → 可恢复 gap 错误；
    - session 不存在/已过期 → 明确错误；
    - 不允许读取其他 session 的事件。
    """
    session_obj = session_manager.get_session(sid)
    if session_obj is None or not session_manager.session_has_activity(sid):
        await _emit(
            sid,
            _envelope(
                "turn.failed",
                {
                    "error_code": "SESSION_NOT_FOUND",
                    "message": "会话不存在或已过期",
                    "recoverable": True,
                },
                sid=sid,
            ),
        )
        return

    journal = session_obj.journal
    last_sequence = payload.last_sequence
    latest = journal.latest_sequence() or 0
    gap = journal.is_gap(last_sequence)

    if gap:
        earliest = journal.earliest_sequence()
        await _emit(
            sid,
            _envelope(
                "turn.failed",
                {
                    "error_code": "STREAM_GAP",
                    "message": (
                        f"请求序号 {last_sequence} 早于缓冲起点 "
                        f"{earliest}，存在不可恢复断档，请重新发起 query"
                    ),
                    "recoverable": True,
                    "last_sequence": last_sequence,
                    "earliest_sequence": earliest,
                },
                sid=sid,
            ),
        )
        return

    events = journal.events_after(last_sequence)
    for event in events:
        await _emit(sid, event)  # 原 event_id / sequence / turn_id 原样回放

    await _emit(
        sid,
        _envelope(
            "stream.resume_ack",
            StreamResumeAckPayload(
                session_id=sid,
                last_sequence=latest,
                replay_from=last_sequence + 1,
                replay_count=len(events),
                gap=False,
                message=f"已补发 {len(events)} 条事件",
            ).model_dump(),
            sid=sid,
        ),
    )


async def _run_ws_turn(
    *,
    session_id: str,
    turn_id: str,
    question: str,
    trace_id: str,
    _envelope,
    _emit,
    request_context=None,
    accepted_at: float = 0.0,
) -> None:
    """turn task：以 run_turn 执行 Agent graph（真流式 + 协作式取消）。"""
    from app.agents.state import ModuleResults, RuntimeState

    def _build_state() -> dict:
        return {
            "messages": [],
            "user_query": question,
            "request_context": request_context,
            "company": None,
            "company_candidates": [],
            "plan": None,
            "module_status": {},
            "results": ModuleResults(),
            "evidence": [],
            "claims": [],
            "final_response": None,
            "runtime": RuntimeState(
                trace_id=trace_id, session_id=session_id, turn_id=turn_id
            ),
        }

    session_obj = session_manager.get_session(session_id)
    if session_obj is None:
        return
    turn = session_manager.get_turn(session_obj, turn_id)
    if turn is None:
        return

    async def _emit_event(event_type: str, payload: dict) -> None:
        env = _envelope(
            event_type,
            payload,
            sid=session_id,
            trace_id=trace_id,
            turn_id=turn_id,
        )
        await _emit(session_id, env)

    try:
        # 终态事件统一由 run_turn 内部 _emit_terminal_once 原子抢占发送
        await run_turn(
            session=session_obj,
            turn=turn,
            graph=_get_graph(),
            question=question,
            emit=_emit_event,
            build_state=_build_state,
            accepted_at=accepted_at,
        )
    except asyncio.CancelledError:
        # 连接销毁/会话关闭 → turn task 取消（当前节点可结束，后续不再启动）
        logger.info("turn task 已取消: turn=%s session=%s", turn_id, session_id)
        raise
    except Exception:  # noqa: BLE001
        logger.exception(
            "WS turn 执行未预期异常: turn=%s session=%s", turn_id, session_id
        )
        try:
            # 原子抢占终态：若 run_turn 已发出终态（claim 成功），此处跳过，
            # 保证同一 turn 恰好一个终态事件
            if session_manager.claim_terminal_event(session_obj, turn_id):
                await _emit_event(
                    "turn.failed",
                    {
                        "error_code": "AGENT_ERROR",
                        "message": "处理请求时发生内部错误",
                        "recoverable": True,
                    },
                )
        except Exception:  # noqa: BLE001
            pass
    finally:
        session_manager.remove_turn(session_obj, turn_id)
