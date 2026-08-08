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


def test_same_session_rejects_second_active_turn():
    from app.application.services.ws_session_manager import WsSessionManager

    manager = WsSessionManager()
    session = manager.get_or_create_session("ses_same")
    first = manager.start_turn_if_idle(session, "turn_1", "问题一")
    second = manager.start_turn_if_idle(session, "turn_2", "问题二")
    assert first is not None
    assert second is None
    manager.remove_turn(session, "turn_1")
    assert manager.start_turn_if_idle(session, "turn_2", "问题二") is not None


def test_company_confirm_replays_original_question_with_selected_company(monkeypatch):
    """候选确认必须以新 turn 携带选中公司继续原问题，而不是只回确认文案。"""
    import app.api.v1.routers.chat as chat_mod
    from app.application.services.ws_session_manager import session_manager

    sid = _test_session_id()
    resumed: list[tuple[str, str]] = []

    async def fake_run_ws_turn(
        *,
        session_id,
        turn_id,
        question,
        trace_id,
        request_context,
        accepted_at,
        _envelope,
        _emit,
    ):
        assert accepted_at > 0
        session = session_manager.get_session(session_id)
        assert session is not None
        try:
            if request_context is None:
                candidates = [
                    {"wind_code": "000001.SZ", "sec_name": "平安银行"},
                    {"wind_code": "601318.SH", "sec_name": "中国平安"},
                ]
                session_manager.set_pending_disambiguation(
                    session,
                    {
                        "turn_id": turn_id,
                        "question": question,
                        "as_of": "20251231",
                        "candidates": candidates,
                    },
                )
                await _emit(
                    session_id,
                    _envelope(
                        "company.candidates",
                        {"turn_id": turn_id, "candidates": candidates},
                        sid=session_id,
                        trace_id=trace_id,
                        turn_id=turn_id,
                    ),
                )
            else:
                resumed.append((question, request_context.company_code))
            if session_manager.claim_terminal_event(session, turn_id):
                await _emit(
                    session_id,
                    _envelope(
                        "turn.completed",
                        {"answer": "ok"},
                        sid=session_id,
                        trace_id=trace_id,
                        turn_id=turn_id,
                    ),
                )
        finally:
            session_manager.remove_turn(session, turn_id)

    monkeypatch.setattr(chat_mod, "_run_ws_turn", fake_run_ws_turn)

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/chat/ws?session_id={sid}") as ws:
            ws.send_json(
                {
                    "event_type": "chat.query",
                    "payload": {"text": "分析平安", "session_id": sid},
                }
            )
            first_events = []
            while (
                not first_events or first_events[-1]["event_type"] != "turn.completed"
            ):
                first_events.append(ws.receive_json())

            first_turn_id = next(
                event["turn_id"]
                for event in first_events
                if event["event_type"] == "turn.accepted"
            )
            assert any(
                event["event_type"] == "company.candidates" for event in first_events
            )

            ws.send_json(
                {
                    "event_type": "company.confirm",
                    "payload": {
                        "company_ref": "000001.SZ",
                        "session_id": sid,
                        "turn_id": first_turn_id,
                    },
                }
            )
            second_events = []
            while (
                not second_events or second_events[-1]["event_type"] != "turn.completed"
            ):
                second_events.append(ws.receive_json())

    assert resumed == [("分析平安", "000001.SZ")]
    second_turn_id = next(
        event["turn_id"]
        for event in second_events
        if event["event_type"] == "turn.accepted"
    )
    assert second_turn_id != first_turn_id


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
