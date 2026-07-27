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
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.schemas.chat import ChatDataV1, ChatRequestV1
from app.api.v1.schemas.common import ApiMeta, V12Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Graph 实例延迟创建（不在 import 时编译）
_compiled_graph = None


def _get_graph():
    """延迟初始化 Agent graph（避免 import 时副作用）."""
    global _compiled_graph
    if _compiled_graph is None:
        from app.agents.graph import create_agent_graph

        _compiled_graph = create_agent_graph().compile()
        logger.info("Agent graph 已编译")
    return _compiled_graph


def _build_chat_response(result: dict, trace_id: str) -> V12Response[ChatDataV1]:
    """从 Agent graph 结果构建 V12 REST 响应。

    从 Agent State 中提取结构化数据并转换为 API DTO。
    """
    final_response = result.get("final_response")
    claims = result.get("claims", [])
    evidence = result.get("evidence", [])
    module_status = result.get("module_status", {})
    results = result.get("results")

    # 提取 risk_score
    triggered = [c for c in claims if getattr(c, "severity", "") == "red"]
    risk_score = {
        "overall": min(1.0, len(triggered) * 0.25),
        "financial": 0.8
        if any(
            getattr(c, "claim_type", "") == "financial"
            and getattr(c, "severity", "") == "red"
            for c in claims
        )
        else 0.1,
        "ownership": 0.3
        if any(
            getattr(c, "claim_type", "") == "equity"
            and getattr(c, "severity", "") == "red"
            for c in claims
        )
        else 0.1,
        "sentiment": 0.5
        if any(
            getattr(c, "claim_type", "") == "event"
            and getattr(c, "severity", "") == "red"
            for c in claims
        )
        else 0.05,
    }

    # 提取 evidence
    evidence_items = []
    for ev in evidence:
        if isinstance(ev, dict):
            evidence_items.append(
                {
                    "source": ev.get("source_type", ev.get("source_title", "")),
                    "field": ev.get("field_path", ""),
                    "value": str(ev.get("value", "")),
                }
            )
        elif hasattr(ev, "source_type"):
            evidence_items.append(
                {
                    "source": getattr(ev, "source_title", "")
                    or getattr(ev, "source_type", ""),
                    "field": getattr(ev, "field_path", ""),
                    "value": str(getattr(ev, "value", "")),
                }
            )

    # 提取 graph
    graph_data: dict = {"nodes": [], "edges": []}
    if results and getattr(results, "equity", None):
        eq = results.equity
        if hasattr(eq, "graph") and eq.graph:
            graph_data = eq.graph

    # 提取 timeline
    timeline: list = []
    if results and getattr(results, "events", None):
        evt = results.events
        if hasattr(evt, "timeline"):
            timeline = evt.timeline

    # 收集 warnings
    warnings: list[str] = []
    runtime = result.get("runtime")
    if runtime and hasattr(runtime, "warnings"):
        warnings.extend(runtime.warnings)
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
    if final_response:
        answer = getattr(final_response, "answer", "")

    return V12Response(
        data=ChatDataV1(
            answer=answer or "分析完成，未生成结构化答案。",
            evidence=evidence_items
            if evidence_items
            else [
                {
                    "source": "Agent",
                    "field": "state",
                    "value": f"{len(claims)} claims, {len(evidence)} evidence refs",
                }
            ],
            graph=graph_data,
            timeline=timeline,
            risk_score=risk_score,
            warnings=warnings,
            missing_modules=missing_modules,
            trace_id=trace_id,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )


@router.post("/chat", response_model=V12Response[ChatDataV1])
async def chat_v1(request: ChatRequestV1):
    """对话接口 — V12 REST，进入 Agent graph。

    与 WebSocket 使用同一套 Agent 流程和 State。
    """
    trace_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())

    try:
        from app.agents.state import ModuleResults, RuntimeState

        state = {
            "messages": [],
            "user_query": request.question,
            "company": None,
            "plan": None,
            "module_status": {},
            "results": ModuleResults(),
            "evidence": [],
            "claims": [],
            "final_response": None,
            "runtime": RuntimeState(trace_id=trace_id, session_id=session_id),
        }

        # 在线程池中执行 Agent graph（避免阻塞事件循环）
        result = await asyncio.to_thread(_get_graph().invoke, state)
        return _build_chat_response(result, trace_id)

    except Exception:
        logger.exception(
            "REST Agent 执行异常: trace_id=%s question=%.50s",
            trace_id,
            request.question,
        )
        return V12Response(
            data=ChatDataV1(
                answer="处理请求时发生内部错误，请稍后重试。",
                evidence=[],
                graph={},
                timeline=[],
                risk_score={},
                warnings=["内部错误"],
                missing_modules=["Agent 执行失败"],
                trace_id=trace_id,
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


@router.websocket("/chat/ws")
async def websocket_chat_v1(ws: WebSocket):
    """WebSocket 对话端点 — V12 event envelope + Agent graph。

    V12 客户端事件：
      - chat.query: 新问题
      - chat.follow_up: 追问
      - company.confirm: 确认公司选择
      - turn.cancel: 取消当前轮次
      - stream.resume: 断线恢复
      - ping: 心跳

    V12 服务端事件：
      - turn.accepted, turn.completed, turn.failed
      - module.started, module.completed
      - answer.delta, artifact.upsert
      - heartbeat

    兼容旧格式：
      - {question: "..."} → 按 chat.query 处理
      - {data: {question: "..."}} → 按 chat.query 处理
    """
    import asyncio

    await ws.accept()
    session_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    sequence = 0
    cancelled = False

    def _envelope(event_type: str, payload: dict) -> dict:
        nonlocal sequence
        sequence += 1
        return {
            "schema_version": "1.0",
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "session_id": session_id,
            "turn_id": turn_id,
            "sequence": sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "payload": payload,
        }

    try:
        while True:
            raw = await ws.receive_text()

            # 解析 JSON
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {"error_code": "INVALID_JSON", "message": "无效的 JSON 格式"},
                    )
                )
                continue

            # ── 旧格式兼容 ──
            event_type = msg.get("event_type", "")
            payload = msg.get("payload", {})

            if not event_type:
                # 尝试旧格式: {question: "..."} 或 {data: {question: "..."}}
                question = msg.get("question", "") or msg.get("data", {}).get(
                    "question", ""
                )
                if question:
                    event_type = "chat.query"
                    payload = {"text": question}

            # ── 事件分发 ──

            # ping → heartbeat
            if event_type == "ping":
                await ws.send_json(
                    _envelope(
                        "heartbeat",
                        {"server_time": datetime.now(timezone.utc).isoformat()},
                    )
                )
                continue

            # turn.cancel
            if event_type == "turn.cancel":
                cancelled = True
                await ws.send_json(
                    _envelope("turn.cancelled", {"message": "当前轮次已取消"})
                )
                continue

            # stream.resume
            if event_type == "stream.resume":
                # Phase C 实现事件缓冲；当前返回降级错误
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "STREAM_RESUME_UNAVAILABLE",
                            "message": "断线恢复暂不可用（Phase C 实现），请重新发起 query",
                            "recoverable": True,
                        },
                    )
                )
                continue

            # 有效 query 事件
            if event_type not in ("chat.query", "chat.follow_up", "company.confirm"):
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "UNKNOWN_EVENT",
                            "message": f"未知事件类型: {event_type}",
                        },
                    )
                )
                continue

            # company.confirm
            if event_type == "company.confirm":
                await ws.send_json(
                    _envelope("turn.accepted", {"message": "已确认公司"})
                )
                await ws.send_json(
                    _envelope("turn.completed", {"message": "公司确认完成 (mock)"})
                )
                continue

            question = payload.get("text", "")
            if not question:
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "MISSING_QUESTION",
                            "message": "payload.text 为必填项",
                        },
                    )
                )
                continue

            # 每一轮新 turn_id
            turn_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            cancelled = False

            # turn.accepted
            await ws.send_json(
                _envelope(
                    "turn.accepted", {"message": f"已收到问题: {question[:50]}..."}
                )
            )

            try:
                from app.agents.state import ModuleResults, RuntimeState

                state = {
                    "messages": [],
                    "user_query": question,
                    "company": None,
                    "plan": None,
                    "module_status": {},
                    "results": ModuleResults(),
                    "evidence": [],
                    "claims": [],
                    "final_response": None,
                    "runtime": RuntimeState(trace_id=trace_id, session_id=session_id),
                }

                # 使用 asyncio.to_thread 避免阻塞事件循环
                # Phase C 替换为 graph.astream() 实现真流式
                result = await asyncio.to_thread(_get_graph().invoke, state)

                if cancelled:
                    continue

                module_status = result.get("module_status", {})
                final_response = result.get("final_response")

                if not final_response:
                    await ws.send_json(
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "NO_RESPONSE",
                                "message": "Agent 未返回结果",
                            },
                        )
                    )
                    continue

                # module.started + module.completed（真实串行顺序）
                for name, ms in module_status.items():
                    if not cancelled:
                        await ws.send_json(
                            _envelope(
                                "module.started", {"module": name, "status": "running"}
                            )
                        )

                for name, ms in module_status.items():
                    if not cancelled:
                        await ws.send_json(
                            _envelope(
                                "module.completed",
                                {
                                    "module": name,
                                    "status": getattr(ms, "state", "success"),
                                    "duration_ms": getattr(ms, "duration_ms", 0),
                                },
                            )
                        )

                # answer.delta
                if not cancelled:
                    chunks = final_response.answer.split("。")
                    for chunk in chunks:
                        if chunk.strip():
                            await ws.send_json(
                                _envelope(
                                    "answer.delta", {"text": chunk.strip() + "。"}
                                )
                            )

                # artifact.upsert
                if not cancelled:
                    await ws.send_json(
                        _envelope(
                            "artifact.upsert",
                            {
                                "artifact_type": "risk_assessment",
                                "artifact_id": f"risk_{session_id}",
                                "revision": 1,
                                "operation": "replace",
                                "data": {"risk_level": final_response.risk_level},
                            },
                        )
                    )

                # turn.completed
                if not cancelled:
                    await ws.send_json(
                        _envelope(
                            "turn.completed",
                            {
                                "answer": final_response.answer,
                                "risk_level": final_response.risk_level,
                                "claims_count": len(result.get("claims", [])),
                                "follow_ups": getattr(final_response, "follow_ups", []),
                                "evidence_count": len(result.get("evidence", [])),
                            },
                        )
                    )

            except Exception:
                logger.exception(
                    "Agent 执行异常: trace_id=%s session_id=%s question=%.50s",
                    trace_id,
                    session_id,
                    question,
                )
                try:
                    await ws.send_json(
                        _envelope(
                            "turn.failed",
                            {
                                "error_code": "AGENT_ERROR",
                                "message": "处理请求时发生内部错误，请稍后重试",
                                "recoverable": True,
                            },
                        )
                    )
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开: session_id=%s", session_id)
    except Exception:
        logger.exception("WebSocket 未预期异常: session_id=%s", session_id)
