"""对话路由 — V12 baseline (集成版).

整合 PR #9 Agent 图接入 + legacy 兼容。

POST /api/v1/chat — V12 response envelope 格式。
WS /api/v1/chat/ws — V12 event envelope + Agent graph。

变更（相对于 PR #9 原版）：
  - 去掉模块级 _compiled_graph（延迟到 lazy init）
  - Agent 调用使用 asyncio.to_thread 避免阻塞事件循环
  - 修复 bare except → 结构化日志 + 客户端安全错误
  - 保留 legacy 旧格式兼容（{question} / {data: {question}}）
  - 保留 ChatContext Pydantic 类型（不降级为 dict）
"""

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


@router.post("/chat", response_model=V12Response[ChatDataV1])
async def chat_v1(request: ChatRequestV1):
    """对话接口 — V12 response envelope (mock).

    当 LLM_BACKEND 切换为真实 provider 后，此端点将调用 Agent graph。
    """
    trace_id = str(uuid.uuid4())

    return V12Response(
        data=ChatDataV1(
            answer=f"Mock V12 回答：关于「{request.question[:50]}...」的分析正在开发中。",
            evidence=[
                {"source": "利润表", "field": "营业收入", "value": "1505.60亿（mock）"},
                {
                    "source": "现金流量表",
                    "field": "销售商品收到的现金",
                    "value": "1652.35亿（mock）",
                },
            ],
            graph={
                "nodes": [
                    {
                        "id": "600519",
                        "label": "贵州茅台",
                        "type": "company",
                        "depth": 0,
                    },
                    {
                        "id": "mt_group",
                        "label": "茅台集团",
                        "type": "controller",
                        "depth": 1,
                    },
                ],
                "edges": [
                    {"source": "mt_group", "target": "600519", "relation": "54%控股"}
                ],
            },
            timeline=[
                {
                    "date": "2024-03-01",
                    "title": "发布2023年度报告",
                    "category": "公告",
                    "summary": "公司发布2023年年度报告（mock）",
                    "sentiment": "neutral",
                    "sources": ["上交所公告"],
                },
            ],
            risk_score={
                "overall": 0.15,
                "financial": 0.10,
                "ownership": 0.20,
                "sentiment": 0.05,
            },
            warnings=["mock 预警：关联交易占比略高"],
            missing_modules=[
                "编排Agent",
                "财务勾稽Agent",
                "股权穿透Skill",
                "舆情事件Skill",
            ],
            trace_id=trace_id,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
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
