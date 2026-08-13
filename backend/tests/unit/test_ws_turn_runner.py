"""WsTurnRunner 单元测试 — Phase D #5/#6/#10 turn 执行.

使用可控 fake graph（模拟 astream_events 输出），确定性验证：
- module.started 在节点执行前发送
- module.completed 在节点返回后发送
- answer.delta 来自 generate_answer 实时分段（DeltaSink）
- 协作式取消：当前节点结束、下一节点不启动、turn.cancelled 恰好一次
- 单终态：completed / cancelled / failed 互斥
- accepted 后立即取消
- generate_answer 前取消
"""

import asyncio

from app.application.services.ws_session_manager import (
    WsSession,
    WsSessionManager,
    ActiveTurn,
)
from app.application.services.ws_turn_runner import run_turn
from app.agents.state import (
    CompanyRef,
    ExecutionPlan,
    FinalResponse,
    ModuleResults,
    RuntimeState,
)


class _FakeGraph:
    """模拟 LangGraph.astream_events 输出（可控节点序列）。

    与真实 LangGraph 一致：逐节点 start → end 交错；
    每次 on_chain_end 时，若当前节点是 generate_answer，
    则通过 sink push 实时分段（模拟真流式）。
    resolve_entity / plan_modules 产出各自的输出（供 runner 推导可执行模块）。
    """

    def __init__(
        self,
        node_names: list[str],
        final_state: dict,
        *,
        company: object = None,
        requested_modules: list[str] | None = None,
    ):
        self._nodes = node_names
        self._final = final_state
        self._company = company
        self._requested = requested_modules

    async def astream_events(self, state, version="v2"):
        from app.agents.delta_sink import get_sink

        for name in self._nodes:
            yield {"event": "on_chain_start", "name": name, "data": {}}
            out = self._final
            if name == "resolve_entity":
                out = {"company": self._company}
            elif name == "plan_modules":
                out = {"plan": _FakePlan(self._requested or [])}
            if name == "generate_answer":
                sink = get_sink(state["runtime"].turn_id)
                if sink is not None:
                    sink.push("结论段。")
                    sink.push("信号摘要段。")
            yield {"event": "on_chain_end", "name": name, "data": {"output": out}}
        # 根链结束 → 完整最终 state
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": self._final},
        }


class _FakePlan:
    """最小 ExecutionPlan 桩（requested_modules 可读）。"""

    def __init__(self, requested_modules: list[str]):
        self.requested_modules = requested_modules


def _make_turn(session: WsSession, turn_id="turn_1") -> ActiveTurn:
    return session.turns[turn_id]


def _run_events(events: list[tuple[str, dict]]) -> list[str]:
    return [et for et, _ in events]


def _state(question="问题", turn_id="turn_1"):
    return {
        "messages": [],
        "user_query": question,
        "company": None,
        "plan": None,
        "module_status": {},
        "results": ModuleResults(),
        "evidence": [],
        "claims": [],
        "final_response": FinalResponse(
            answer="结论段。信号摘要段。", risk_level="yellow"
        ),
        "runtime": RuntimeState(trace_id="tr", session_id="ses", turn_id=turn_id),
    }


def _build_emit():
    events: list[tuple[str, dict]] = []

    async def emit(et: str, payload: dict) -> None:
        events.append((et, payload))

    return events, emit


def _build_state(state: dict):
    def build():
        return dict(state)

    return build


async def _run(
    graph,
    state,
    turn,
    session,
    emit,
    build_state,
):
    result = await run_turn(
        session=session,
        turn=turn,
        graph=graph,
        question=state["user_query"],
        emit=emit,
        build_state=build_state,
    )
    return result


def test_turn_completed_emits_module_and_delta():
    """正常完成：module.started/completed + answer.delta + turn.completed。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        state = _state()
        company = object()
        state["company"] = company
        state["plan"] = ExecutionPlan(
            intent="simple_query", requested_modules=["finance"]
        )
        graph = _FakeGraph(
            [
                "load_context",
                "plan_modules",
                "finance",
                "generate_answer",
                "persist_turn",
            ],
            state,
            company=company,
            requested_modules=["finance"],
        )
        events, emit = _build_emit()
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "completed"
        ets = [e[0] for e in events]
        assert "module.started" in ets and "module.completed" in ets
        assert "answer.delta" in ets
        assert "artifact.upsert" in ets
        assert "turn.completed" in ets
        # delta 来自真实分段（非拆句）：拼接即最终答案
        deltas = [e[1]["text"] for e in events if e[0] == "answer.delta"]
        assert "".join(deltas) == state["final_response"].answer

    asyncio.run(scenario())


def test_turn_completed_exposes_intent():
    """WS 终态透出意图，供前端选择分析或会话展示模式。"""

    async def scenario():
        manager = WsSessionManager()
        session = manager.get_or_create_session("ses")
        turn = manager.start_turn(session, "turn_1", "你好")
        state = _state(question="你好")
        state["plan"] = ExecutionPlan(intent="chitchat", requested_modules=[])
        graph = _FakeGraph(
            ["load_context", "plan_modules", "generate_answer", "persist_turn"],
            state,
            requested_modules=[],
        )
        events, emit = _build_emit()

        result = await _run(graph, state, turn, session, emit, _build_state(state))

        assert result.outcome == "completed"
        completed = next(
            payload for name, payload in events if name == "turn.completed"
        )
        assert completed["intent"] == "chitchat"
        assert all(name != "artifact.upsert" for name, _ in events)

    asyncio.run(scenario())


def test_cancel_after_accepted():
    """accepted 后立即取消：turn.cancelled，无 module / completed。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        turn.token.request_cancel()  # 启动前已取消
        state = _state()
        graph = _FakeGraph(
            [
                "load_context",
                "plan_modules",
                "finance",
                "generate_answer",
                "persist_turn",
            ],
            state,
            requested_modules=["finance"],
        )
        events, emit = _build_emit()
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "cancelled"
        ets = [e[0] for e in events]
        assert ets == ["turn.cancelled"]
        assert "module.started" not in ets
        assert "turn.completed" not in ets

    asyncio.run(scenario())


def test_cancel_during_execution_stops_next_node():
    """执行中取消：当前节点结束，下一节点不启动，turn.cancelled 一次。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        state = _state()

        # 在 finance 完成后取消（当前节点结束）
        async def emit(et, payload):
            if et == "module.completed" and payload.get("module") == "finance":
                turn.token.request_cancel()
            events.append((et, payload))

        events: list[tuple[str, dict]] = []
        graph = _FakeGraph(
            [
                "load_context",
                "plan_modules",
                "finance",
                "equity",
                "generate_answer",
                "persist_turn",
            ],
            state,
            requested_modules=["finance", "equity"],
        )
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "cancelled"
        ets = [e[0] for e in events]
        assert "turn.cancelled" in ets
        # finance 后 equity 不启动（当前节点结束即停止）
        equity_start = any(
            e[0] == "module.started" and e[1].get("module") == "equity" for e in events
        )
        assert equity_start is False
        assert ets.count("turn.cancelled") == 1
        assert "turn.completed" not in ets

    asyncio.run(scenario())


def test_cancel_before_generate_answer_no_delta():
    """generate_answer 前取消：无 answer.delta，无 turn.completed。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        state = _state()

        async def emit(et, payload):
            if et == "module.completed" and payload.get("module") == "equity":
                turn.token.request_cancel()
            events.append((et, payload))

        events: list[tuple[str, dict]] = []
        graph = _FakeGraph(
            [
                "load_context",
                "plan_modules",
                "finance",
                "equity",
                "generate_answer",
                "persist_turn",
            ],
            state,
            requested_modules=["finance", "equity"],
        )
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "cancelled"
        ets = [e[0] for e in events]
        assert "answer.delta" not in ets
        assert "turn.completed" not in ets
        assert ets.count("turn.cancelled") == 1

    asyncio.run(scenario())


def test_single_terminal_event():
    """恰好一个终态事件（completed 场景）。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        state = _state()
        graph = _FakeGraph(
            ["plan_modules", "generate_answer", "persist_turn"],
            state,
            requested_modules=[],
        )
        events, emit = _build_emit()
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "completed"
        terminals = [
            e[0]
            for e in events
            if e[0] in ("turn.completed", "turn.cancelled", "turn.failed")
        ]
        assert len(terminals) == 1
        assert terminals == ["turn.completed"]

    asyncio.run(scenario())


def test_no_final_response_fails():
    """无 final_response → turn.failed。"""

    async def scenario():
        m = WsSessionManager()
        s = m.get_or_create_session("ses")
        turn = m.start_turn(s, "turn_1", "问题")
        state = _state()
        state["final_response"] = None
        graph = _FakeGraph(
            ["plan_modules", "persist_turn"],
            state,
            requested_modules=[],
        )
        events, emit = _build_emit()
        result = await _run(graph, state, turn, s, emit, _build_state(state))
        assert result.outcome == "no_response"
        ets = [e[0] for e in events]
        assert "turn.failed" in ets
        assert "turn.completed" not in ets

    asyncio.run(scenario())


def test_company_candidates_event_and_pending_confirmation():
    async def scenario():
        from app.application.services.ws_session_manager import session_manager

        local_manager = WsSessionManager()
        session = local_manager.get_or_create_session("ses")
        turn = local_manager.start_turn(session, "turn_1", "分析平安")
        state = _state(question="分析平安")
        state["plan"] = ExecutionPlan(
            intent="company_disambiguation", requested_modules=[]
        )
        state["company_candidates"] = [
            CompanyRef(
                entity_id="company_000001_SZ",
                wind_code="000001.SZ",
                sec_name="平安银行",
                exchange="XSHE",
            )
        ]
        graph = _FakeGraph(
            ["plan_modules", "generate_answer", "persist_turn"],
            state,
            requested_modules=[],
        )
        events, emit = _build_emit()
        result = await _run(graph, state, turn, session, emit, _build_state(state))
        assert result.outcome == "completed"
        candidate_events = [
            payload for name, payload in events if name == "company.candidates"
        ]
        assert candidate_events[0]["candidates"][0]["wind_code"] == "000001.SZ"
        pending = session_manager.get_pending_disambiguation(session)
        assert pending["question"] == "分析平安"
        assert pending["candidates"][0]["wind_code"] == "000001.SZ"

    asyncio.run(scenario())
