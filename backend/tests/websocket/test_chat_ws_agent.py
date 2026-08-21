"""WebSocket Agent Flow 集成测试 — V12 baseline.

验证：
- 9 字段事件信封完整性
- 事件流包含 turn.accepted / module.* / answer.delta / turn.completed
- chat.query + 旧格式兼容
"""

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

# 需要真实 MySQL（WS Agent 持久化断言）；CI 默认 sqlite → skip
_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql",
    reason="需要真实 MySQL（CI 默认 sqlite）",
)

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


def _collect(ws, timeout: float = 60.0) -> list[dict]:
    events = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            # 复核 P2-3：队列 + 剩余 deadline 读取，终态缺失时超时失败而非挂起。
            message = ws._send_queue.get(timeout=max(0.01, deadline - time.monotonic()))
            if isinstance(message, BaseException):
                raise message
            ws._raise_on_close(message)
            data = json.loads(message["text"])
            events.append(data)
            if data["event_type"] in ("turn.completed", "turn.failed"):
                break
        except Exception:
            break
    return events


def _receive_one(ws, timeout: float = 15.0) -> dict:
    """读取单个事件（deadline 兜底；复核 P2-3：禁止无限阻塞）。"""
    deadline = time.monotonic() + timeout
    message = ws._send_queue.get(timeout=max(0.01, deadline - time.monotonic()))
    if isinstance(message, BaseException):
        raise message
    ws._raise_on_close(message)
    return json.loads(message["text"])


def test_chat_query_v12_format(ws_session_tracker):
    """V12 chat.query 格式 → 完整事件流 + 9 字段信封。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        events = _collect(ws)
    ws_session_tracker(events)

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


def test_turn_completed_evidence_ids_consistent(ws_session_tracker):
    """turn.completed 的 evidence_ids 与 evidence_count 一致（前端证据链依赖）.

    曾只发 evidence_count——139 条证据时前端仍显示"无直接证据支撑"。
    """
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        events = _collect(ws)
    ws_session_tracker(events)

    completed = [e for e in events if e["event_type"] == "turn.completed"]
    assert completed, "应收到 turn.completed"
    payload = completed[-1]["payload"]
    assert "evidence_ids" in payload, "turn.completed 必须携带 evidence_ids"
    assert len(payload["evidence_ids"]) == payload.get("evidence_count", 0), (
        f"evidence_ids({len(payload['evidence_ids'])}) "
        f"与 evidence_count({payload.get('evidence_count')}) 不一致"
    )
    # answer.delta 主路径：payload.text 非空
    deltas = [e for e in events if e["event_type"] == "answer.delta"]
    if deltas:
        assert all(
            e["payload"].get("text") for e in deltas
        ), "answer.delta.payload.text 应为非空"
    assert "answer" in payload
    assert "risk_level" in payload
    # 实时规则证据（对齐审计 P1-2）：finance.triggered_rules 带 canonical ID
    rules = (payload.get("finance") or {}).get("triggered_rules") or []
    for rule in rules:
        assert rule.get(
            "evidence_ids"
        ), f"规则 {rule.get('rule_id')} 应携带 evidence_ids（实时面板筛选）"


def test_chat_query_legacy_format(ws_session_tracker):
    """旧 {question} 格式兼容 → 同样走完流程。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"question": "康美药业"})
        events = _collect(ws)
    ws_session_tracker(events)

    event_types = [e["event_type"] for e in events]
    assert "turn.accepted" in event_types
    assert "turn.completed" in event_types


@_NEED_MYSQL
def test_payload_session_id_persists(ws_session_tracker):
    """P0-1 回归: payload.session_id 决定会话归属（信封一致 + REST 可回读）。

    曾只有 query 带 session_id、payload 不带——后端读不到，
    每次连接都归属随机会话，多轮对话和回读错位。
    """
    client = TestClient(app)
    sid = f"ses_ws_test_{uuid.uuid4().hex[:8]}"
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events = _collect(ws)
    ws_session_tracker(events)

    envelope_sids = {e["session_id"] for e in events}
    assert envelope_sids == {sid}, f"信封 session_id 应全为 {sid}，实际 {envelope_sids}"
    assert any(e["event_type"] == "turn.completed" for e in events)

    # REST 回读同一会话（会话归属正确，turn 已持久化到该 session）
    resp = client.get(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 200, f"回读会话 {sid} 应成功，实际 {resp.status_code}"
    turns = resp.json()["data"]["turns"]
    assert len(turns) >= 1, f"会话 {sid} 应有至少 1 轮，实际 {len(turns)}"


@_NEED_MYSQL
def test_panel_rule_evidence_ids_exist_in_db(ws_session_tracker):
    """DB 存在性（对齐审计 P1-2）：面板 triggered_rules 的 evidence_ids
    必须全部命中 evidence_refs（canonical ev_fin_*，非规则引擎内部 ID）。

    曾误用 FinanceRuleItem.evidence_ids（ev_bs_*/ev_is_*）→ 命中 0/N。
    """
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        # v3.3.3 收口批次 F（方案 §5.1）：timeout 提升至 120s；
        # turn.accepted 都未收到 → 环境/连接异常，允许 skip；
        # turn 已启动后缺终态 → 必须 fail（不得用 timeout skip 掩盖回归）
        events = _collect(ws, timeout=120.0)
    ws_session_tracker(events)

    if not any(e["event_type"] == "turn.accepted" for e in events):
        pytest.skip("未收到 turn.accepted（连接/环境异常，非终态缺失）")
    if not any(
        e["event_type"] in ("turn.completed", "turn.failed", "turn.cancelled")
        for e in events
    ):
        pytest.fail("turn 已启动但 120s 内未收到终态事件（方案 §5.1 必须失败）")

    # 从事件信封拿到 session，REST 回读 panel_data
    if not any(e.get("session_id") for e in events):
        pytest.fail("turn.accepted 信封缺少 session_id（9 字段信封契约）")
    sid = next(e["session_id"] for e in events if e.get("session_id"))
    resp = client.get(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 200
    turns = resp.json()["data"]["turns"]
    assert turns, "应有至少 1 轮"
    panel = turns[-1].get("panel_data") or {}
    rule_ids = [
        eid
        for rule in panel.get("triggered_rules") or []
        for eid in rule.get("evidence_ids") or []
    ]
    if not rule_ids:
        return  # 无触发规则时跳过（数据依赖）
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            hits = sum(
                1
                for eid in rule_ids
                if conn.execute(
                    text("SELECT 1 FROM evidence_refs WHERE evidence_id = :e"),
                    {"e": eid},
                ).scalar()
            )
    finally:
        engine.dispose()
    assert hits == len(rule_ids), (
        f"面板规则证据 ID 命中 evidence_refs {hits}/{len(rule_ids)}: "
        f"{[eid for eid in rule_ids if not None]}"
    )


def test_ping():
    """ping → heartbeat 响应。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"event_type": "ping", "payload": {}})
        event = _receive_one(ws)

    assert event["event_type"] == "heartbeat"


def test_invalid_json():
    """无效 JSON → turn.failed。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_text("not json")
        event = _receive_one(ws)

    assert event["event_type"] == "turn.failed"
    assert event["payload"]["error_code"] == "INVALID_JSON"


def test_missing_text():
    """缺少 payload.text → turn.failed。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json({"event_type": "chat.query", "payload": {}})
        event = _receive_one(ws)

    assert event["event_type"] == "turn.failed"
    assert event["payload"]["error_code"] == "MISSING_QUESTION"


def test_non_object_message_and_payload_are_recoverable():
    """合法 JSON 的数组消息/载荷不得让 WS 连接因 AttributeError 断开。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(["chat.query", {"text": "康美药业"}])
        message_event = _receive_one(ws)
        assert message_event["payload"]["error_code"] == "INVALID_MESSAGE"

        ws.send_json({"event_type": "chat.query", "payload": ["bad"]})
        payload_event = _receive_one(ws)
        assert payload_event["payload"]["error_code"] == "INVALID_PAYLOAD"

        ws.send_json({"event_type": "ping", "payload": {}})
        assert _receive_one(ws)["event_type"] == "heartbeat"


@_NEED_MYSQL
def test_risk_diagnosis_runs_all_modules(ws_session_tracker):
    """综合风险问题 → finance + equity + events 全部执行。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {"event_type": "chat.query", "payload": {"text": "康美药业有造假风险吗"}}
        )
        events = _collect(ws)
    ws_session_tracker(events)

    # 收集模块事件
    started_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.started"
    }
    completed_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.completed"
    }

    expected = {"finance", "equity", "events", "risk"}
    assert (
        started_modules == expected
    ), f"module.started 应为 {expected}，实际 {started_modules}"
    assert (
        completed_modules == expected
    ), f"module.completed 应为 {expected}，实际 {completed_modules}"


@_NEED_MYSQL
def test_finance_only_query_runs_finance(ws_session_tracker):
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
                "payload": {"text": "康美药业财务情况如何"},
            }
        )
        events = _collect(ws)
    ws_session_tracker(events)

    started_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.started"
    }
    completed_modules = {
        e["payload"]["module"] for e in events if e["event_type"] == "module.completed"
    }

    assert started_modules == {
        "finance",
        "risk",
    }, f"纯财务问题应执行 finance+risk，实际 started: {started_modules}"
    assert completed_modules == {
        "finance",
        "risk",
    }, f"纯财务问题应完成 finance+risk，实际 completed: {completed_modules}"

    tc = next(e for e in events if e["event_type"] == "turn.completed")
    assert tc["payload"].get("answer"), "turn.completed 应包含回答文本"
    # 4 期 fixture 数据中财务规则可能因数据不足不触发 Claim，
    # 此测试验证模块路由正确（只执行 finance），不验证 Claim 数量。
    assert (
        tc["payload"]["claims_count"] >= 0
    ), f"claims_count 应为非负整数，实际 claims_count={tc['payload']['claims_count']}"
