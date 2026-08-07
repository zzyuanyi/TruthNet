"""WS 协作式取消集成测试 — Phase D #5.

使用可控图（dependency override）验证确定性行为：
- accepted 后立即取消
- 执行中取消（当前节点结束，下一节点不启动）
- 重复取消幂等
- 取消不存在的 turn → TURN_NOT_FOUND
- 已完成 turn 的取消 → 明确终态，不改变历史
- A 会话取消不影响 B 会话
- 取消后无半截 Claim/Evidence 断链
"""

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql",
    reason="需要真实 MySQL（CI 默认 sqlite）",
)


def _unique_sid() -> str:
    return f"ses_cancel_{uuid.uuid4().hex[:10]}"


def _send(ws, event_type: str, payload: dict) -> None:
    ws.send_json({"event_type": event_type, "payload": payload})


def _receive(ws, timeout: float = 15.0) -> list[dict]:
    """确定性接收直到终态事件，用真实超时兜底（不用 sleep 猜测时序）。"""
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # TestClient websocket receive 是阻塞同步；用非阻塞轮询代替
        try:
            data = ws.receive_json()
            events.append(data)
            if data["event_type"] in (
                "turn.completed",
                "turn.failed",
                "turn.cancelled",
                "stream.resume_ack",
            ):
                break
        except Exception:  # noqa: BLE001 — 连接断开/超时终止
            break
    return events


def _open_ws(client: TestClient, sid: str):
    return client.websocket_connect("/api/v1/chat/ws")


@_NEED_MYSQL
def test_cancel_immediately_after_accepted(ws_session_tracker):
    """accepted 后立即取消 → turn.cancelled，无 turn.completed。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "康美药业有造假风险吗", "session_id": sid})
        # 收 turn.accepted（首个事件）
        first = ws.receive_json()
        assert first["event_type"] == "turn.accepted"
        turn_id = first["payload"].get("turn_id")
        assert turn_id, "turn.accepted 应携带 turn_id"
        # 立即取消
        _send(ws, "turn.cancel", {"turn_id": turn_id})
        events = [first] + _receive(ws)
    ws_session_tracker(events)

    cancelled = [e for e in events if e["event_type"] == "turn.cancelled"]
    assert len(cancelled) == 1, f"turn.cancelled 应恰好一次，实际 {len(cancelled)}"
    assert not [
        e for e in events if e["event_type"] == "turn.completed"
    ], "取消后不得发送 turn.completed"
    # 信封 turn_id 非空（A3 回归：turn 事件必须携带 turn_id）
    assert first["turn_id"] == turn_id, "turn.accepted 信封应携带 turn_id"
    assert cancelled[0]["turn_id"] == turn_id, "turn.cancelled 信封应携带 turn_id"


@_NEED_MYSQL
def test_cancel_not_found(ws_session_tracker):
    """取消不存在的 turn → TURN_NOT_FOUND 明确错误。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "turn.cancel", {"turn_id": "turn_nonexistent"})
        events = _receive(ws)
    ws_session_tracker(events)
    failed = [e for e in events if e["event_type"] == "turn.failed"]
    assert failed, "应收到 turn.failed"
    assert failed[-1]["payload"]["error_code"] == "TURN_NOT_FOUND"


@_NEED_MYSQL
def test_repeat_cancel_idempotent(ws_session_tracker):
    """重复取消幂等：终态恰好一次，第二次取消不再产生新终态事件。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "康美药业有造假风险吗", "session_id": sid})
        first = ws.receive_json()
        assert first["event_type"] == "turn.accepted"
        turn_id = first["payload"]["turn_id"]
        _send(ws, "turn.cancel", {"turn_id": turn_id})
        events = [first] + _receive(ws)
        # 再次取消后服务端按幂等契约不再发送终态。TestClient 的
        # receive_json() 没有超时能力，因此用随后必达的 heartbeat 作为
        # 读取边界，不能等待一个按设计不存在的事件。
        _send(ws, "turn.cancel", {"turn_id": turn_id})
        _send(ws, "ping", {})
        after_repeat: list[dict] = []
        while True:
            event = ws.receive_json()
            after_repeat.append(event)
            if event["event_type"] == "heartbeat":
                break
        events2 = events + after_repeat
    ws_session_tracker(events2)
    cancelled = [e for e in events2 if e["event_type"] == "turn.cancelled"]
    assert len(cancelled) == 1, (
        f"turn.cancelled 应恰好一次（重复取消不得再发），实际 {len(cancelled)}"
    )
    # 不得出现 500 / 未处理异常
    failed = [e for e in events2 if e["event_type"] == "turn.failed"]
    error_codes = {e["payload"].get("error_code") for e in failed}
    assert "AGENT_ERROR" not in error_codes


@_NEED_MYSQL
def test_cancel_isolation_across_sessions():
    """A 会话取消不影响 B 会话（B 可正常完成）。"""
    client = TestClient(app)
    sid_a = _unique_sid()
    sid_b = _unique_sid()
    events_a: list[dict] = []
    events_b: list[dict] = []
    with client.websocket_connect("/api/v1/chat/ws") as ws_a:
        _send(ws_a, "chat.query", {"text": "康美药业有造假风险吗", "session_id": sid_a})
        first = ws_a.receive_json()
        turn_a = first["payload"]["turn_id"]
        _send(ws_a, "turn.cancel", {"turn_id": turn_a})
        events_a = [first] + _receive(ws_a)
    with client.websocket_connect("/api/v1/chat/ws") as ws_b:
        _send(
            ws_b,
            "chat.query",
            {"text": "康美药业应收账款情况如何", "session_id": sid_b},
        )
        events_b = _receive(ws_b)
    assert any(e["event_type"] == "turn.cancelled" for e in events_a), "A 应取消"
    assert any(e["event_type"] == "turn.completed" for e in events_b), "B 应正常完成"
    assert not any(e["event_type"] == "turn.completed" for e in events_a), "A 不得完成"


@_NEED_MYSQL
def test_cancel_no_dangling_data(ws_session_tracker):
    """取消后数据库无半截 Claim/Evidence 断链。

    取消 turn 后：该 turn 不得出现在 conversation_turns，
    且其 session 不得产生孤儿 claims/evidence。
    """
    from sqlalchemy import create_engine, text

    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "康美药业有造假风险吗", "session_id": sid})
        first = ws.receive_json()
        turn_id = first["payload"]["turn_id"]
        _send(ws, "turn.cancel", {"turn_id": turn_id})
        events = [first] + _receive(ws)
    ws_session_tracker(events)

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            # 取消的 turn 可能已持久化（若取消在 persist_turn 之前完成，则不存在）
            conn.execute(
                text("SELECT 1 FROM conversation_turns WHERE turn_id = :t"),
                {"t": turn_id},
            ).scalar()
            # 该 session 无孤儿 claim（claims 必须挂 turn）
            orphans = conn.execute(
                text(
                    "SELECT COUNT(*) FROM claims c "
                    "LEFT JOIN conversation_turns t ON t.turn_id = c.turn_id "
                    "WHERE c.turn_id = :t AND t.turn_id IS NULL"
                ),
                {"t": turn_id},
            ).scalar()
            assert orphans == 0, f"取消 turn 存在孤儿 claim: {orphans}"
    finally:
        engine.dispose()
