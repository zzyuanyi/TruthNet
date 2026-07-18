"""对话路由 — V12 baseline.

POST /api/v1/chat — V12 response envelope 格式。
WS /api/v1/chat/ws — V12 event envelope 格式。
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.schemas.chat import ChatDataV1, ChatRequestV1
from app.api.v1.schemas.common import ApiMeta, V12Response

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

            question = msg.get("question", "") or msg.get("data", {}).get(
                "question", ""
            )

            if not question:
                await ws.send_json(
                    _envelope(
                        "turn.failed",
                        {
                            "error_code": "MISSING_QUESTION",
                            "message": "question 字段为必填项",
                        },
                    )
                )
                continue

            # 1. turn.accepted
            await ws.send_json(
                _envelope(
                    "turn.accepted", {"message": f"已收到问题: {question[:50]}..."}
                )
            )

            # 2. module.started
            await ws.send_json(
                _envelope(
                    "module.started",
                    {"module": "orchestrator", "status": "running"},
                )
            )

            # 3. answer.delta (mock streaming)
            mock_answer = (
                f"Mock V12 回答：关于「{question[:30]}...」的分析正在开发中。"
                "当前 WebSocket V12 event envelope 端点已就绪。"
            )
            for i, chunk in enumerate(
                mock_answer[i : i + 20] for i in range(0, len(mock_answer), 20)
            ):
                if chunk:
                    await ws.send_json(
                        _envelope("answer.delta", {"text": chunk, "index": i})
                    )

            # 4. artifact.upsert
            await ws.send_json(
                _envelope(
                    "artifact.upsert",
                    {
                        "artifact_type": "risk_score",
                        "data": {
                            "overall": 0.15,
                            "financial": 0.10,
                            "ownership": 0.20,
                            "sentiment": 0.05,
                        },
                    },
                )
            )

            # 5. turn.completed
            await ws.send_json(
                _envelope(
                    "turn.completed",
                    {
                        "answer": mock_answer,
                        "evidence": [],
                        "graph": {"nodes": [], "edges": []},
                        "timeline": [],
                        "risk_score": {
                            "overall": 0.0,
                            "financial": 0.0,
                            "ownership": 0.0,
                            "sentiment": 0.0,
                        },
                        "warnings": [],
                        "missing_modules": [
                            "编排Agent",
                            "财务勾稽Agent",
                            "股权穿透Skill",
                        ],
                    },
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
