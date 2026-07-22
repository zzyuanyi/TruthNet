"""WebSocket Agent Flow 集成测试 — V12 baseline.

验证：
- 9 字段事件信封完整性
- 事件流包含 turn.accepted / module.* / answer.delta / turn.completed
- chat.query + 旧格式兼容
"""

from fastapi.testclient import TestClient

from app.main import app

ENVELOPE_KEYS = {
    "schema_version",
    "event_id",
    "event_type",
    "session_id",
    "turn_id",
    "sequence",
    "timestamp",
    "trace_id",
    "payload",
}


def _collect(ws) -> list[dict]:
    events = []
    while True:
        try:
            data = ws.receive_json()
            events.append(data)
            if data["event_type"] in ("turn.completed", "turn.failed"):
                break
        except Exception:
            break
    return events


def test_chat_query_v12_format():
    """V12 chat.query 格式 → 完整事件流 + 9 字段信封。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        events = _collect(ws)

    assert len(events) >= 5, f"events < 5: {len(events)}"

    event_types = [e["event_type"] for e in events]
    assert "turn.accepted" in event_types
    assert any(t == "module.started" for t in event_types)
    assert any(t == "module.completed" for t in event_types)
    assert any(t == "answer.delta" for t in event_types)
    assert "turn.completed" in event_types

    # envelope integrity
    for e in events:
        missing = ENVELOPE_KEYS - set(e.keys())
        assert not missing, f"missing envelope keys: {missing}"
        assert isinstance(e["sequence"], int) and e["sequence"] > 0

    # turn.completed payload
    tc = next(e for e in events if e["event_type"] == "turn.completed")
    assert tc["sequence"] == len(events)
    assert "answer" in tc["payload"]
    assert "risk_level" in tc["payload"]


def test_chat_query_legacy_format():
    """旧 {question} 格式兼容 → 同样走完流程。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"question": "康美药业"})
        events = _collect(ws)

    event_types = [e["event_type"] for e in events]
    assert "turn.accepted" in event_types
    assert "turn.completed" in event_types


def test_ping():
    """ping → heartbeat 响应。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"event_type": "ping", "payload": {}})
        event = ws.receive_json()

    assert event["event_type"] == "heartbeat"


def test_invalid_json():
    """无效 JSON → turn.failed。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_text("not json")
        event = ws.receive_json()

    assert event["event_type"] == "turn.failed"
    assert event["payload"]["error_code"] == "INVALID_JSON"


def test_missing_text():
    """缺少 payload.text → turn.failed。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"event_type": "chat.query", "payload": {}})
        event = ws.receive_json()

    assert event["event_type"] == "turn.failed"
    assert event["payload"]["error_code"] == "MISSING_QUESTION"
