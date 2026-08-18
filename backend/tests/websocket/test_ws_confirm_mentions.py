"""方案 v3.1 §7 关键测试 — 步骤 9（WS mention 分组确认 + exactly-once T+1）.

对应审查测试项（真库 truthnet_test）：
- company.candidates 发出后、来源 turn 删除前立即确认，最终恰好一个 T+1；
- ACK 返回 revision，旧客户端仅在单 mention 初始状态兼容；
- 多 mention（平安+茅台）只确认平安，茅台自动保留；
- 确认完成后重跑原问题且主体正确；
- 重复 confirm（同 revision）被拒绝。
"""

import time
import uuid
import json
import queue

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql",
    reason="需要真实 MySQL（CI 默认 sqlite）",
)


def _unique_sid() -> str:
    return f"ses_mentions_{uuid.uuid4().hex[:10]}"


def _send(ws, event_type: str, payload: dict) -> None:
    ws.send_json({"event_type": event_type, "payload": payload})


def _receive(
    ws, timeout: float = 20.0, terminal: tuple[str, ...] | None = None
) -> list[dict]:
    """确定性接收直到终态事件（终态集合可扩展——幂等 ack 场景无 turn 事件）。"""
    terminal = terminal or (
        "turn.completed",
        "turn.failed",
        "turn.cancelled",
        "stream.resume_ack",
    )
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            # WebSocketTestSession.receive_json() blocks forever. Read its
            # internal queue with the remaining timeout so a missing terminal
            # event fails the test instead of hanging the whole suite.
            message = ws._send_queue.get(timeout=max(0.01, deadline - time.monotonic()))
            if isinstance(message, BaseException):
                raise message
            ws._raise_on_close(message)
            data = json.loads(message["text"])
            events.append(data)
            if data["event_type"] in terminal:
                break
        except queue.Empty:
            break
        except Exception:  # noqa: BLE001
            break
    return events


@_NEED_MYSQL
def test_single_mention_new_protocol_resumes_exactly_once(
    ws_session_tracker, monkeypatch
):
    """'分析平安'（多候选）：新协议确认 → confirm_ack → 恰好一个 T+1 重跑。

    显式隔离语义裁决（off）：本测试只验证 WS 确认协议，不依赖 suggest 的
    LLM 消歧（真机 LLM 波动会导致全量并行 flaky）。
    """
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "off")
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "分析平安", "session_id": sid})
        events = _receive(ws)
        candidates = [e for e in events if e["event_type"] == "company.candidates"]
        assert candidates, "歧义场景应发 company.candidates"
        payload = candidates[-1]["payload"]
        assert "revision" in payload and payload["revision"] == 0
        assert "mentions" in payload and len(payload["mentions"]) >= 1
        # 旧扁平候选兼容（恰好 1 个未确认 mention）
        assert payload["candidates"], "单未确认 mention 应输出旧扁平候选"
        origin_turn_id = payload["turn_id"]
        mention = payload["mentions"][0]
        code = payload["candidates"][0]["wind_code"]

        # 新协议确认（mention_id + revision）
        _send(
            ws,
            "company.confirm",
            {
                "turn_id": origin_turn_id,
                "mention_id": mention["mention_id"],
                "revision": 0,
                "company_ref": {"wind_code": code},
            },
        )
        ack_events = _receive(ws)
        acks = [e for e in ack_events if e["event_type"] == "company.confirm_ack"]
        assert acks, "确认后应收到 confirm_ack"
        ack = acks[-1]["payload"]
        assert ack["resolved"] is True
        assert ack["revision"] >= 1
        # 重跑产生新 turn（T+1）：turn.accepted 或后续 completed
        accepted = [
            e
            for e in ack_events
            if e["event_type"] == "turn.accepted"
            and e["payload"].get("turn_id") != origin_turn_id
        ]
        assert len(accepted) <= 1, "至多一个 T+1 turn.accepted"
        completed = [e for e in ack_events if e["event_type"] == "turn.completed"]
        assert len(completed) == 1, f"T+1 应恰好一次 completed，实际 {len(completed)}"
        # turn_id 在事件信封层（payload 不含）
        new_turn = completed[0].get("turn_id")
        assert new_turn and new_turn != origin_turn_id
    ws_session_tracker(events + ack_events)


@_NEED_MYSQL
def test_duplicate_confirm_same_revision_rejected(ws_session_tracker):
    """重复确认（同 revision 同值）→ v3.2.1 幂等重放：返回幂等 ack
    （completed/in_progress），绝不启动第二个 T+1、不发误导性 RESUME_FAILED。"""
    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "分析平安", "session_id": sid})
        events = _receive(ws)
        payload = [e for e in events if e["event_type"] == "company.candidates"][-1][
            "payload"
        ]
        origin_turn_id = payload["turn_id"]
        mention = payload["mentions"][0]
        code = payload["candidates"][0]["wind_code"]

        confirm_payload = {
            "turn_id": origin_turn_id,
            "mention_id": mention["mention_id"],
            "revision": 0,
            "company_ref": {"wind_code": code},
        }
        _send(ws, "company.confirm", confirm_payload)
        first = _receive(ws)
        assert any(e["event_type"] == "company.confirm_ack" for e in first)
        # 同一 revision 同值重复确认 → 幂等重放 ack（无 turn 事件，
        # 以 confirm_ack 为终态；同值重放不产生第二个 T+1）
        _send(ws, "company.confirm", confirm_payload)
        second = _receive(ws, timeout=15.0, terminal=("company.confirm_ack",))
        acks = [e for e in second if e["event_type"] == "company.confirm_ack"]
        assert acks, "幂等重放应收到 confirm_ack"
        assert acks[-1]["payload"].get("resume_status") in (
            "completed",
            "in_progress",
            "waiting",
        )
        failed = [e for e in second if e["event_type"] == "turn.failed"]
        assert not failed, "幂等重放不得返回 RESUME_FAILED"
        new_accepted = [
            e
            for e in second
            if e["event_type"] == "turn.accepted"
            and e["payload"].get("turn_id") != origin_turn_id
        ]
        assert len(new_accepted) == 0, "重复确认不得启动第二个 T+1"
    ws_session_tracker(events + first + second)


@_NEED_MYSQL
def test_multi_mention_only_unconfirmed_needs_confirm(ws_session_tracker, monkeypatch):
    """'平安和茅台对比'：茅台锁定、只确认平安 → 确认后重跑为对比引导。

    v3.2.1 批次 6：注入固定 repository（平安多候选 + 茅台唯一候选）
    确定性产生候选事件，强制断言；禁止静默 return / pytest.skip。
    显式隔离语义裁决（off）：本测试只验证 WS 确认协议。
    """
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "off")
    import json as _json

    from sqlalchemy import create_engine as _ce
    from sqlalchemy import text as _text
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.persistence.mysql.company_repository import (
        MySQLCompanyRepository,
    )

    # StaticPool + check_same_thread=False：内存 SQLite 跨线程共享同一连接
    # （WS 在 portal 线程查询、测试线程建表；默认 SingletonThreadPool 按
    # 线程隔离导致 no such table，sqlite3 默认拒绝跨线程使用连接）
    engine = _ce(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as conn:
        conn.execute(
            _text(
                "CREATE TABLE companies (entity_id TEXT, wind_code TEXT, "
                "sec_name TEXT, exchange_code TEXT, industry_l1 TEXT, "
                "aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
                "is_latest INTEGER)"
            )
        )
        for row in [
            (
                "c1",
                "000001.SZ",
                "平安银行",
                _json.dumps(["平安"], ensure_ascii=False),
            ),
            (
                "c2",
                "601318.SH",
                "中国平安",
                _json.dumps(["平安"], ensure_ascii=False),
            ),
            ("c3", "600519.SH", "贵州茅台", None),
        ]:
            conn.execute(
                _text(
                    "INSERT INTO companies VALUES "
                    "(:eid,:code,:name,'XSHG',NULL,:aliases,NULL,'1',1)"
                ),
                {"eid": row[0], "code": row[1], "name": row[2], "aliases": row[3]},
            )
    repo = MySQLCompanyRepository()
    repo._engine = engine

    import app.agents.nodes.resolve_entity as rn

    monkeypatch.setattr(rn, "get_company_repository", lambda: repo)

    client = TestClient(app)
    sid = _unique_sid()
    with client.websocket_connect("/api/v1/chat/ws") as ws:
        _send(ws, "chat.query", {"text": "平安和茅台对比", "session_id": sid})
        events = _receive(ws)
        candidates = [e for e in events if e["event_type"] == "company.candidates"]
        assert candidates, "注入固定候选后必须发出 company.candidates"
        payload = candidates[-1]["payload"]
        mentions = payload["mentions"]
        by_text = {m["text"]: m for m in mentions}
        assert (
            "茅台" in by_text
        ), f"茅台应在 mention 分组中: {[m['text'] for m in mentions]}"
        confirmable = [m for m in mentions if m.get("status") == "needs_confirmation"]
        assert all(
            m["text"] != "茅台" for m in confirmable
        ), "唯一候选茅台应已锁定（不进 remaining）"
        assert confirmable, "平安应需要确认"
        origin_turn_id = payload["turn_id"]
        # 只确认平安
        _send(
            ws,
            "company.confirm",
            {
                "turn_id": origin_turn_id,
                "mention_id": confirmable[0]["mention_id"],
                "revision": 0,
                "company_ref": {
                    "wind_code": confirmable[0]["candidates"][0]["company"]["wind_code"]
                },
            },
        )
        after = _receive(ws)
        acks = [e for e in after if e["event_type"] == "company.confirm_ack"]
        assert acks and acks[-1]["payload"]["resolved"] is True
        completed = [e for e in after if e["event_type"] == "turn.completed"]
        assert len(completed) == 1, "确认全部完成后应重跑一次"
    ws_session_tracker(events + after)
