"""WS 断线恢复集成测试 — Phase D #6.

验证：
- stream.resume 补发所有 sequence > last_sequence 的事件
- 顺序严格递增、不重复、使用原 event_id
- 跨新 socket 保持 session sequence
- 无事件时返回明确 resume 完成状态
- 请求序号早于缓存起点 → STREAM_GAP 可恢复错误
- session 不存在 → SESSION_NOT_FOUND
- 不允许读取其他 session 的事件
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
    return f"ses_resume_{uuid.uuid4().hex[:10]}"


def _collect(ws, timeout: float = 60.0, *, terminal_ack: bool = False) -> list[dict]:
    """确定性收集事件；正常对话等 turn 终态，resume 场景等 stream.resume_ack。

    初始 chat.query 为全模块诊断（含 Neo4j/LLM），需较长等待；
    resume 补发（terminal_ack=True）通常秒级。
    terminal_ack=True 时等 stream.resume_ack 或错误终态（turn.failed）
    停止（补发的 turn.completed 只是回放内容，不能提前终止）。
    """
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = ws.receive_json()
            events.append(data)
            if terminal_ack and data["event_type"] in (
                "stream.resume_ack",
                "turn.failed",
            ):
                break
            if not terminal_ack and data["event_type"] in (
                "turn.completed",
                "turn.failed",
                "turn.cancelled",
            ):
                break
        except Exception:  # noqa: BLE001
            break
    return events


@_NEED_MYSQL
def test_resume_replays_missing_events_no_dup(ws_session_tracker):
    """断线后 resume：补发缺失事件，无重复、顺序递增、原 event_id。"""
    client = TestClient(app)
    sid = _unique_sid()
    # 第一次连接：执行一轮完整对话并收集事件
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events1 = _collect(ws)
    ws_session_tracker(events1)
    assert any(e["event_type"] == "turn.completed" for e in events1), "首轮应完成"
    latest_seq = max(e["sequence"] for e in events1)
    assert latest_seq >= 3, f"应产生至少 3 个事件，实际 {latest_seq}"

    # 模拟断线：取掉前 N 个事件，用 stream.resume 补发
    drop = max(1, len(events1) // 2)
    seen = events1[:-drop]
    last_sequence = seen[-1]["sequence"] if seen else 0
    seen_ids = {e["event_id"] for e in seen}

    with client.websocket_connect("/api/v1/chat/ws") as ws2:
        ws2.send_json(
            {
                "event_type": "stream.resume",
                "payload": {"session_id": sid, "last_sequence": last_sequence},
            }
        )
        replay = _collect(ws2, terminal_ack=True)
    ws_session_tracker(replay)

    ack = [e for e in replay if e["event_type"] == "stream.resume_ack"]
    assert ack, "应收到 stream.resume_ack"
    assert (
        ack[-1]["payload"]["replay_count"] == len(replay) - 1
    ), f"ack replay_count={ack[-1]['payload']['replay_count']} 与补发数不符"

    # 补发事件顺序严格递增，不重复，无已见 ID
    replayed = [e for e in replay if e["event_type"] != "stream.resume_ack"]
    seqs = [e["sequence"] for e in replayed]
    assert seqs == sorted(seqs), "补发顺序必须严格递增"
    assert len(set(seqs)) == len(seqs), "补发不得重复"
    assert all(s > last_sequence for s in seqs), "只补发 last_sequence 之后的事件"
    new_ids = {e["event_id"] for e in replayed}
    assert not (new_ids & seen_ids), "补发不得重复已见 event_id"


@_NEED_MYSQL
def test_resume_uses_original_ids(ws_session_tracker):
    """补发使用原 event_id / sequence / turn_id（不重新生成）。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events1 = _collect(ws)
    ws_session_tracker(events1)

    # 记录首轮全部事件指纹
    original = {e["event_id"]: (e["sequence"], e["turn_id"]) for e in events1}
    drop = max(1, len(events1) // 2)
    seen = events1[:-drop]
    last_seq = seen[-1]["sequence"]

    with client.websocket_connect("/api/v1/chat/ws") as ws2:
        ws2.send_json(
            {
                "event_type": "stream.resume",
                "payload": {"session_id": sid, "last_sequence": last_seq},
            }
        )
        replay = _collect(ws2, terminal_ack=True)
    ws_session_tracker(replay)

    for e in replay:
        if e["event_type"] == "stream.resume_ack":
            continue
        assert e["event_id"] in original, "补发 event_id 必须与首轮一致（不重新生成）"
        assert e["sequence"] == original[e["event_id"]][0], "补发 sequence 必须原样"
        assert e["turn_id"] == original[e["event_id"]][1], "补发 turn_id 必须原样"


@_NEED_MYSQL
def test_resume_no_events_returns_ack(ws_session_tracker):
    """无事件可补发 → 明确 resume 完成状态（replay_count=0）。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events1 = _collect(ws)
    ws_session_tracker(events1)
    latest = max(e["sequence"] for e in events1)

    with client.websocket_connect("/api/v1/chat/ws") as ws2:
        ws2.send_json(
            {
                "event_type": "stream.resume",
                "payload": {"session_id": sid, "last_sequence": latest},
            }
        )
        ack = _collect(ws2, terminal_ack=True)
    ws_session_tracker(ack)
    acks = [e for e in ack if e["event_type"] == "stream.resume_ack"]
    assert acks, "应收到 stream.resume_ack"
    assert acks[-1]["payload"]["replay_count"] == 0, "无事件时应 replay_count=0"
    assert acks[-1]["payload"]["gap"] is False


@_NEED_MYSQL
def test_resume_gap_error(ws_session_tracker):
    """请求序号早于缓存起点 → STREAM_GAP 可恢复错误。

    通过直接操作内存会话的 journal 制造"缓存起点较高"的确定性场景：
    journal 清空后手动 append 高序号事件 → 客户端 last_sequence 远低于起点。
    """
    from app.application.services.ws_session_manager import session_manager

    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events1 = _collect(ws)
    ws_session_tracker(events1)

    # 制造确定性 gap：清空 journal，模拟"高序号已发送但已被 TTL/上限丢弃"
    s = session_manager.get_session(sid)
    assert s is not None, "会话应在内存中"
    s.journal.clear()
    s.journal.append(
        {
            "schema_version": "1.0",
            "event_id": "evt_fake_10",
            "event_type": "module.completed",
            "session_id": sid,
            "turn_id": "turn_fake",
            "sequence": 10,
            "timestamp": "2026-08-07T00:00:00+00:00",
            "trace_id": "trace_fake",
            "payload": {},
        }
    )
    # 客户端 last_sequence=5，缓存起点=10 → gap
    with client.websocket_connect("/api/v1/chat/ws") as ws2:
        ws2.send_json(
            {
                "event_type": "stream.resume",
                "payload": {"session_id": sid, "last_sequence": 5},
            }
        )
        resp = _collect(ws2, terminal_ack=True)
    ws_session_tracker(resp)
    failed = [e for e in resp if e["event_type"] == "turn.failed"]
    assert failed, "应收到 turn.failed"
    assert failed[-1]["payload"]["error_code"] == "STREAM_GAP"
    assert failed[-1]["payload"].get("recoverable") is True


@_NEED_MYSQL
def test_resume_session_not_found(ws_session_tracker):
    """session 不存在 → SESSION_NOT_FOUND。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "stream.resume",
                "payload": {"session_id": "ses_does_not_exist_xyz", "last_sequence": 0},
            }
        )
        resp = _collect(ws, terminal_ack=True)
    failed = [e for e in resp if e["event_type"] == "turn.failed"]
    assert failed, "应收到 turn.failed"
    assert failed[-1]["payload"]["error_code"] == "SESSION_NOT_FOUND"


@_NEED_MYSQL
def test_resume_cannot_read_other_session(ws_session_tracker):
    """不允许通过 resume 读取其他 session 的事件（会话级隔离）。

    验证：对 session B 发起 resume 只返回 B 的事件，
    绝不包含 session A 的事件（journal 按 session 隔离）。
    """
    client = TestClient(app)
    sid_a = _unique_sid()
    sid_b = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid_a},
            }
        )
        events_a = _collect(ws)
    ws_session_tracker(events_a)
    sid_a_events = [e for e in events_a if e.get("session_id") == sid_a]
    assert sid_a_events, "A 会话应产生事件"

    with client.websocket_connect("/api/v1/chat/ws") as ws_b:
        ws_b.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业应收账款情况如何", "session_id": sid_b},
            }
        )
        events_b = _collect(ws_b)
        # B 断线后 resume B：只补 B 的事件，绝不含 A 的事件
        ws_b2 = client.websocket_connect("/api/v1/chat/ws")
        with ws_b2:
            ws_b2.send_json(
                {
                    "event_type": "stream.resume",
                    "payload": {"session_id": sid_b, "last_sequence": 0},
                }
            )
            resp_b = _collect(ws_b2, terminal_ack=True)
    ws_session_tracker(events_b + resp_b)
    leaked_a = [
        e
        for e in resp_b
        if e["event_type"] != "stream.resume_ack" and e.get("session_id") == sid_a
    ]
    assert not leaked_a, "resume B 不得泄露 A 的事件"
    # B 的事件（resume 补发）session_id 全为 B
    for e in resp_b:
        if e["event_type"] != "stream.resume_ack":
            assert e["session_id"] == sid_b, "补发事件必须属于 B 会话"
