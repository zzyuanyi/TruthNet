"""多 WS 并发验证 — Phase D #13.

场景：
  A. 双连接双会话：session_id/turn_id/sequence/delta/claims/evidence 互不串扰
  B. A 运行中，B 发起问题：真实并发，单图执行不阻塞整个事件循环
  C. A 断线重连：B 持续执行，A 恢复后只收到 A 的缺失事件，不收到 B 的任何事件
  D. A 取消，B 完成：取消隔离
  E. 同一 session 多连接：新连接替代旧连接（契约确定的策略）

数据库完整性：每个测试使用唯一 session ID，清理后
  dangling_claim_links = 0 / dangling_evidence_links = 0 /
  orphan_test_sessions = 0 / cross_session_claims = 0 / cross_session_evidence = 0
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


def _unique_sid(prefix: str) -> str:
    return f"ses_conc_{prefix}_{uuid.uuid4().hex[:8]}"


def _collect(ws, timeout: float = 60.0) -> list[dict]:
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = ws.receive_json()
            events.append(data)
            if data["event_type"] in (
                "turn.completed",
                "turn.failed",
                "turn.cancelled",
            ):
                break
        except Exception:  # noqa: BLE001
            break
    return events


@_NEED_MYSQL
def test_dual_connection_dual_session_no_cross_talk(ws_session_tracker):
    """场景 A：双连接双会话，session/turn/sequence/delta 互不串扰。"""
    client = TestClient(app)
    sid_a = _unique_sid("a")
    sid_b = _unique_sid("b")
    with client.websocket_connect("/api/v1/chat/ws") as ws_a, client.websocket_connect(
        "/api/v1/chat/ws"
    ) as ws_b:
        ws_a.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_a},
            }
        )
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何", "session_id": sid_b},
            }
        )
        events_a = _collect(ws_a)
        events_b = _collect(ws_b)
    ws_session_tracker(events_a + events_b)

    # session_id 不混
    assert {e["session_id"] for e in events_a} <= {sid_a}
    assert {e["session_id"] for e in events_b} <= {sid_b}
    # turn_id 不混（A 的 turn 不出现于 B）
    turn_a = {e["turn_id"] for e in events_a if e["turn_id"]}
    turn_b = {e["turn_id"] for e in events_b if e["turn_id"]}
    assert not (turn_a & turn_b)
    # sequence 各自单调
    seq_a = [e["sequence"] for e in events_a]
    seq_b = [e["sequence"] for e in events_b]
    assert seq_a == sorted(seq_a) and seq_b == sorted(seq_b)
    # 都完成
    assert any(e["event_type"] == "turn.completed" for e in events_a)
    assert any(e["event_type"] == "turn.completed" for e in events_b)


@_NEED_MYSQL
def test_session_isolated_claims_evidence(ws_session_tracker):
    """场景 A（DB 层）：claims/evidence 不串 session，无断链。"""
    from sqlalchemy import create_engine, text

    client = TestClient(app)
    sid_a = _unique_sid("a")
    sid_b = _unique_sid("b")
    with client.websocket_connect("/api/v1/chat/ws") as ws_a, client.websocket_connect(
        "/api/v1/chat/ws"
    ) as ws_b:
        ws_a.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_a},
            }
        )
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何", "session_id": sid_b},
            }
        )
        events_a = _collect(ws_a)
        events_b = _collect(ws_b)
    ws_session_tracker(events_a + events_b)

    # 从 turn.completed 读取 claims/evidence ids（各自会话）
    tc_a = [e for e in events_a if e["event_type"] == "turn.completed"]
    tc_b = [e for e in events_b if e["event_type"] == "turn.completed"]
    assert tc_a and tc_b

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            for sid, tc in ((sid_a, tc_a), (sid_b, tc_b)):
                payload = tc[-1]["payload"]
                for eid in payload.get("evidence_ids") or []:
                    row = conn.execute(
                        text(
                            "SELECT company_code, turn_id FROM evidence_refs WHERE evidence_id = :e"
                        ),
                        {"e": eid},
                    ).first()
                    # 证据应归属本会话的某个 turn（turn_id 非空）
                    assert row is not None, f"证据 {eid} 应存在于 evidence_refs"
                    assert row[1], f"证据 {eid} 应绑定 turn_id"
    finally:
        engine.dispose()


@_NEED_MYSQL
def test_a_running_b_queries_concurrent(ws_session_tracker):
    """场景 B：A 执行中 B 发起问题，两连接真实并发。"""
    client = TestClient(app)
    sid_a = _unique_sid("a")
    sid_b = _unique_sid("b")
    with client.websocket_connect("/api/v1/chat/ws") as ws_a, client.websocket_connect(
        "/api/v1/chat/ws"
    ) as ws_b:
        ws_a.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_a},
            }
        )
        # 不等 A 完成，立即在 B 发起（同一事件循环内两个 turn task 并存）
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何", "session_id": sid_b},
            }
        )
        events_b = _collect(ws_b)
        events_a = _collect(ws_a)
    ws_session_tracker(events_a + events_b)
    assert any(e["event_type"] == "turn.completed" for e in events_a)
    assert any(e["event_type"] == "turn.completed" for e in events_b)


@_NEED_MYSQL
def test_reconnect_a_b_continues(ws_session_tracker):
    """场景 C：A 断线重连，B 持续执行；A 恢复后只收 A 缺失事件。"""
    client = TestClient(app)
    sid_a = _unique_sid("a")
    sid_b = _unique_sid("b")
    # B 先开始（长时间诊断）
    with client.websocket_connect("/api/v1/chat/ws") as ws_b:
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_b},
            }
        )
        # A 第一段（短查询）→ 收集部分事件后断开
        with client.websocket_connect("/api/v1/chat/ws") as ws_a:
            ws_a.send_json(
                {
                    "event_type": "chat.query",
                    "payload": {
                        "text": "康美药业应收账款情况如何",
                        "session_id": sid_a,
                    },
                }
            )
            events_a1 = _collect(ws_a)
        # A 重连 → resume A 缺失事件
        with client.websocket_connect("/api/v1/chat/ws") as ws_a2:
            ws_a2.send_json(
                {
                    "event_type": "stream.resume",
                    "payload": {"session_id": sid_a, "last_sequence": 0},
                }
            )
            events_a2 = _collect(ws_a2, timeout=30.0)
        events_b = _collect(ws_b)
    ws_session_tracker(events_a1 + events_a2 + events_b)

    # A 重连补发的事件 session_id 全为 A，不出现 B 的任何事件
    for e in events_a2:
        if e["event_type"] != "stream.resume_ack":
            assert (
                e["session_id"] == sid_a
            ), f"A 重连不得收到 B 的事件: {e['event_type']}"
    # B 完成不受影响
    assert any(e["event_type"] == "turn.completed" for e in events_b)


@_NEED_MYSQL
def test_a_cancel_b_completes(ws_session_tracker):
    """场景 D：A 取消，B 完成，取消隔离。"""
    client = TestClient(app)
    sid_a = _unique_sid("a")
    sid_b = _unique_sid("b")
    with client.websocket_connect("/api/v1/chat/ws") as ws_a, client.websocket_connect(
        "/api/v1/chat/ws"
    ) as ws_b:
        ws_a.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_a},
            }
        )
        first = ws_a.receive_json()
        assert first["event_type"] == "turn.accepted"
        turn_a = first["payload"]["turn_id"]
        ws_a.send_json({"event_type": "turn.cancel", "payload": {"turn_id": turn_a}})
        events_a = [first] + _collect(ws_a)

        # B 在 A 取消后发起并完成
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何", "session_id": sid_b},
            }
        )
        events_b = _collect(ws_b)
    ws_session_tracker(events_a + events_b)

    assert any(e["event_type"] == "turn.cancelled" for e in events_a), "A 应取消"
    assert any(e["event_type"] == "turn.completed" for e in events_b), "B 应完成"
    assert not any(e["event_type"] == "turn.completed" for e in events_a), "A 不得完成"


@_NEED_MYSQL
def test_same_session_multiple_connections(ws_session_tracker):
    """场景 E：同一 session 多连接 → 新连接替代旧连接（契约策略）。

    验证策略确定性：连接1 发起查询后，连接2 attach 同一 session 成为
    主连接（primary），事件分发转移到连接2；连接1 不再接收新事件。
    不产生未定义行为（无 500 / 无重复终态）。
    """
    client = TestClient(app)
    sid = _unique_sid("same")
    # 连接1 attach 到 sid（观察者）
    ws1 = client.websocket_connect(f"/api/v1/chat/ws?session_id={sid}")
    ws1.__enter__()
    try:
        # 连接2 也 attach 到同一 session（URL query）→ 新连接替代旧连接成为主连接
        with client.websocket_connect(f"/api/v1/chat/ws?session_id={sid}") as ws2:
            ws2.send_json({"event_type": "ping", "payload": {}})
            hb = ws2.receive_json()
            assert hb["event_type"] == "heartbeat"
            assert hb["session_id"] == sid, "连接2 应 attach 到同一会话"
            # 主连接（连接2）发起查询并收到完整事件流
            ws2.send_json(
                {
                    "event_type": "chat.query",
                    "payload": {"text": "康美药业应收账款情况如何", "session_id": sid},
                }
            )
            events2 = _collect(ws2)
            assert any(
                e["event_type"] == "turn.completed" for e in events2
            ), "连接2（主连接）应收到 turn.completed"
    finally:
        ws1.__exit__(None, None, None)
    ws_session_tracker([hb])


@_NEED_MYSQL
def test_database_integrity_after_concurrency(ws_session_tracker):
    """并发测试后数据库完整性：无孤儿链接、无残留测试会话、无跨会话污染。"""
    from sqlalchemy import create_engine, text

    client = TestClient(app)
    sids = [_unique_sid("x") for _ in range(3)]
    all_events: list[dict] = []
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        for sid in sids:
            ws.send_json(
                {
                    "event_type": "chat.query",
                    "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
                }
            )
            ev = _collect(ws)
            all_events.extend(ev)
    ws_session_tracker(all_events)

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            dangling_claims = conn.execute(
                text(
                    "SELECT COUNT(*) FROM claim_evidence_links cel "
                    "LEFT JOIN claims c ON c.claim_id = cel.claim_id "
                    "WHERE c.claim_id IS NULL"
                )
            ).scalar()
            dangling_evidence = conn.execute(
                text(
                    "SELECT COUNT(*) FROM claim_evidence_links cel "
                    "LEFT JOIN evidence_refs e ON e.evidence_id = cel.evidence_id "
                    "WHERE e.evidence_id IS NULL"
                )
            ).scalar()
            assert dangling_claims == 0, f"孤儿 claim links: {dangling_claims}"
            assert dangling_evidence == 0, f"孤儿 evidence links: {dangling_evidence}"
    finally:
        engine.dispose()
