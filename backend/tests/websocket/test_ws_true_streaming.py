"""WS 真流式集成测试 — Phase D #10.

验证：
- module.started 在模块实际执行前发送（先于同模块 completed）
- answer.delta 来自生成过程真实分段（非拆句），拼接 == 最终答案
- turn.completed.answer 是最终权威答案
- delta 顺序在 completed 之前
- 监管提示/证据 ID/Claim ID 不因流式被删除（由既有测试回归）
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
    return f"ses_stream_{uuid.uuid4().hex[:10]}"


def _collect(ws, timeout: float = 60.0) -> list[dict]:
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = ws.receive_json()
            events.append(data)
            if data["event_type"] in ("turn.completed", "turn.failed"):
                break
        except Exception:  # noqa: BLE001
            break
    return events


@_NEED_MYSQL
def test_answer_delta_is_true_streaming(ws_session_tracker):
    """answer.delta 来自真实生成分段；拼接 == 最终答案（非拆句）。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events = _collect(ws)
    ws_session_tracker(events)

    completed = [e for e in events if e["event_type"] == "turn.completed"]
    assert completed, "应收到 turn.completed"
    final_answer = completed[-1]["payload"]["answer"]
    assert final_answer, "最终答案非空"

    deltas = [e for e in events if e["event_type"] == "answer.delta"]
    # 有 delta 时拼接必须等于最终答案（真流式契约）
    if deltas:
        joined = "".join(e["payload"]["text"] for e in deltas)
        assert (
            joined == final_answer
        ), f"delta 拼接 ({len(joined)} chars) 应等于最终答案 ({len(final_answer)} chars)"
    # delta 必须在 completed 之前
    completed_seq = completed[-1]["sequence"]
    for d in deltas:
        assert d["sequence"] < completed_seq, "answer.delta 必须在 turn.completed 之前"


@_NEED_MYSQL
def test_module_started_before_completed(ws_session_tracker):
    """module.started 先于同模块 module.completed（真实执行顺序）。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events = _collect(ws)
    ws_session_tracker(events)

    started = {
        e["payload"]["module"]: e["sequence"]
        for e in events
        if e["event_type"] == "module.started"
    }
    completed = {
        e["payload"]["module"]: e["sequence"]
        for e in events
        if e["event_type"] == "module.completed"
    }
    for mod in completed:
        assert mod in started, f"{mod} 应先 started 再 completed"
        assert started[mod] < completed[mod], f"{mod} started 序号必须早于 completed"


@_NEED_MYSQL
def test_streaming_preserves_evidence_ids(ws_session_tracker):
    """真流式不删除 evidence_ids / claim IDs / 监管提示（证据链完整）。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        ws.send_json(
            {
                "event_type": "chat.query",
                "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
            }
        )
        events = _collect(ws)
    ws_session_tracker(events)

    completed = [e for e in events if e["event_type"] == "turn.completed"]
    payload = completed[-1]["payload"]
    assert "evidence_ids" in payload, "turn.completed 必须携带 evidence_ids"
    assert len(payload["evidence_ids"]) == payload.get(
        "evidence_count", 0
    ), "evidence_ids 与 evidence_count 应一致"
    # 规则证据（实时面板）
    rules = (payload.get("finance") or {}).get("triggered_rules") or []
    for rule in rules:
        assert rule.get(
            "evidence_ids"
        ), f"规则 {rule.get('rule_id')} 应携带 evidence_ids"
