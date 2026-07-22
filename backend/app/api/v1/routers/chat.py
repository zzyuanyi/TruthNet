"""对话路由 — V12 baseline.

POST /api/v1/chat — V12 response envelope 格式。
WS /api/v1/chat/ws — V12 event envelope + Agent graph。
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.graph import create_agent_graph
from app.agents.state import ModuleResults, RuntimeState
from app.api.v1.schemas.chat import ChatDataV1, ChatRequestV1
from app.api.v1.schemas.common import ApiMeta, V12Response

_compiled_graph = create_agent_graph().compile()
router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=V12Response[ChatDataV1])
async def chat_v1(request: ChatRequestV1):
    """对话接口 — V12 response envelope (mock)."""
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
    """WebSocket 对话端点 — V12 event envelope (mock).

    V12 event types:
    - turn.accepted
    - module.started
    - answer.delta
    - artifact.upsert
    - turn.completed
    - turn.failed
    - heartbeat
    """
    await ws.accept()
    session_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    sequence = 0

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

            event_type = msg.get("event_type", "")
            payload = msg.get("payload", {})

            # backward compat: old {question, data.question} format
            if not event_type:
                question = msg.get("question", "") or msg.get("data", {}).get(
                    "question", ""
                )
                if question:
                    event_type = "chat.query"
                    payload = {"text": question}

            # dispatch
            if event_type == "ping":
                await ws.send_json(
                    _envelope(
                        "heartbeat",
                        {"server_time": datetime.now(timezone.utc).isoformat()},
                    )
                )
                continue

            if event_type == "turn.cancel":
                await ws.send_json(_envelope("turn.completed", {"message": "已取消"}))
                continue

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

            # turn.accepted
            await ws.send_json(
                _envelope(
                    "turn.accepted", {"message": f"已收到问题: {question[:50]}..."}
                )
            )

            try:
                # TODO(Phase C): state 应累积同一会话的 messages，支持多轮记忆
                state = {
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
                result = _compiled_graph.invoke(state)

                # TODO(Phase C): 当搜索返回多候选时，发送 company.candidates 事件等待用户确认
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

                # 3. module.started + module.completed
                for name, ms in module_status.items():
                    await ws.send_json(
                        _envelope(
                            "module.started", {"module": name, "status": "running"}
                        )
                    )
                for name, ms in module_status.items():
                    await ws.send_json(
                        _envelope(
                            "module.completed",
                            {
                                "module": name,
                                "status": ms.state,
                                "duration_ms": ms.duration_ms,
                            },
                        )
                    )

                # 4. answer.delta
                # TODO(Phase C): 替换为 graph.astream() 实现真流式输出
                chunks = final_response.answer.split("。")
                for chunk in chunks:
                    if chunk.strip():
                        await ws.send_json(
                            _envelope("answer.delta", {"text": chunk.strip() + "。"})
                        )

                # 5. artifact.upsert — risk_score
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

                # 6. turn.completed
                await ws.send_json(
                    _envelope(
                        "turn.completed",
                        {
                            "answer": final_response.answer,
                            "risk_level": final_response.risk_level,
                            "claims_count": len(result.get("claims", [])),
                            "follow_ups": final_response.follow_ups,
                            "evidence_count": len(result.get("evidence", [])),
                        },
                    )
                )

            except Exception:
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {"error_code": "AGENT_ERROR", "message": "Agent 执行异常"},
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json(
                _envelope(
                    "turn.failed",
                    {"error_code": "INTERNAL_ERROR", "message": str(exc)},
                )
            )
        except Exception:
            pass
