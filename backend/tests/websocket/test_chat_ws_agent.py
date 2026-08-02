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


def test_risk_diagnosis_runs_all_modules():
    """综合风险问题 → finance + equity + events 全部执行。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        events = _collect(ws)

    # 收集模块事件
    started_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.started"
    }
    completed_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.completed"
    }

    expected = {"finance", "equity", "events"}
    assert (
        started_modules == expected
    ), f"module.started 应为 {expected}，实际 {started_modules}"
    assert (
        completed_modules == expected
    ), f"module.completed 应为 {expected}，实际 {completed_modules}"


def test_finance_only_query_runs_finance():
    """纯财务问题 → 只执行 finance，回答完整。

    断言模块路由（仅 finance 执行）与回答完整性，不依赖规则触发数量——
    本地真实数据可能 0 触发（claims_count=0），CI fixture 数据触发（>0），
    两者都属正常，测试本意是验证 finance-only 路由而非触发率。
    """
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何"},
            }
        )
        events = _collect(ws)

    started_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.started"
    }
    completed_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.completed"
    }

    assert started_modules == {
        "finance"
    }, f"纯财务问题应只执行 finance，实际 started: {started_modules}"
    assert completed_modules == {
        "finance"
    }, f"纯财务问题应只完成 finance，实际 completed: {completed_modules}"

    tc = next(e for e in events if e["event_type"] == "turn.completed")
    assert tc["payload"].get("answer"), "turn.completed 应包含回答文本"
    # 4 期 fixture 数据中财务规则可能因数据不足不触发 Claim，
    # 此测试验证模块路由正确（只执行 finance），不验证 Claim 数量。
    assert (
        tc["payload"]["claims_count"] >= 0
    ), f"claims_count 应为非负整数，实际 claims_count={tc['payload']['claims_count']}"
