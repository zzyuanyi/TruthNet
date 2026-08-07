"""WS 终态与 janitor 生命周期回归测试 — Phase D #12 修复补充.

覆盖：
  - run_turn 已抢占终态后抛异常 → 路由层（chat._run_ws_turn 外层 except）
    不得补发第二个 turn.failed（单终态完整性，B1 补齐项）；
  - lifespan janitor：启动后周期调用，shutdown 后停止且不挂起。
"""

import asyncio
import time
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _test_session_id() -> str:
    return f"ses_term_{uuid.uuid4().hex[:10]}"


def test_router_no_second_terminal_after_claim(monkeypatch):
    """run_turn 已 claim 终态后抛异常 → 路由层不补发 turn.failed。"""

    async def scenario():
        import app.api.v1.routers.chat as chat_mod
        from app.application.services.ws_session_manager import session_manager

        sid = _test_session_id()
        session = session_manager.get_or_create_session(sid)
        turn = session_manager.start_turn(session, f"turn_{sid}", "问题")
        # 模拟 run_turn 已抢占终态（例如已发送 turn.completed / cancelled）
        assert session_manager.claim_terminal_event(session, turn.turn_id) is True

        emitted: list[dict] = []

        async def _emit(_sid: str, event: dict) -> None:
            emitted.append(event)

        def _env(event_type, payload, *, sid, trace_id="", turn_id=""):
            return {
                "event_type": event_type,
                "payload": payload,
                "session_id": sid,
                "turn_id": turn_id,
                "sequence": 1,
            }

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated post-terminal failure")

        monkeypatch.setattr(chat_mod, "run_turn", _boom)
        monkeypatch.setattr(chat_mod, "_get_graph", lambda: None)

        await chat_mod._run_ws_turn(
            session_id=sid,
            turn_id=turn.turn_id,
            question="q",
            trace_id="t",
            _envelope=_env,
            _emit=_emit,
        )
        session_manager.close_session(sid)

        failed = [e for e in emitted if e["event_type"] == "turn.failed"]
        assert failed == [], f"已 claim 终态后不得补发 turn.failed：{failed}"

    asyncio.run(scenario())


def test_router_emits_single_failed_without_claim(monkeypatch):
    """run_turn 异常且终态未 claim → 路由层恰好补发一次 turn.failed。"""

    async def scenario():
        import app.api.v1.routers.chat as chat_mod
        from app.application.services.ws_session_manager import session_manager

        sid = _test_session_id()
        session = session_manager.get_or_create_session(sid)
        turn = session_manager.start_turn(session, f"turn_{sid}", "问题")

        emitted: list[dict] = []

        async def _emit(_sid: str, event: dict) -> None:
            emitted.append(event)

        def _env(event_type, payload, *, sid, trace_id="", turn_id=""):
            return {
                "event_type": event_type,
                "payload": payload,
                "session_id": sid,
                "turn_id": turn_id,
                "sequence": 1,
            }

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("pre-terminal failure")

        monkeypatch.setattr(chat_mod, "run_turn", _boom)
        monkeypatch.setattr(chat_mod, "_get_graph", lambda: None)

        await chat_mod._run_ws_turn(
            session_id=sid,
            turn_id=turn.turn_id,
            question="q",
            trace_id="t",
            _envelope=_env,
            _emit=_emit,
        )
        session_manager.close_session(sid)

        failed = [e for e in emitted if e["event_type"] == "turn.failed"]
        assert len(failed) == 1, f"终态未 claim 时应恰好补发一次 failed：{emitted}"

    asyncio.run(scenario())


def test_lifespan_janitor_runs_and_stops(monkeypatch):
    """lifespan janitor：周期调用；shutdown 后停止、不挂起。"""
    from app.application.services.ws_session_manager import session_manager

    calls = {"n": 0}
    orig_janitor = session_manager.janitor

    def _counting_janitor():
        calls["n"] += 1
        return {"expired_events": 0, "expired_sessions": 0}

    monkeypatch.setattr(session_manager, "janitor", _counting_janitor)
    monkeypatch.setattr(settings, "WS_JANITOR_INTERVAL_SECONDS", 0.05)

    with TestClient(app) as client:
        assert client.get("/api/v1/healthz").status_code == 200
        time.sleep(0.25)  # 覆盖多个 janitor 周期
        assert calls["n"] >= 2, f"janitor 应被周期调用，实际 {calls['n']} 次"

    # shutdown 后停止（不再调用），且不挂起（with 已正常退出）
    n_after_exit = calls["n"]
    time.sleep(0.15)
    assert calls["n"] == n_after_exit, "shutdown 后 janitor 不得继续调用"
    monkeypatch.setattr(session_manager, "janitor", orig_janitor)
