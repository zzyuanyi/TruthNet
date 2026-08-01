"""PersistTurn 节点单元测试 — V12 §7.2.

覆盖：SQL_BACKEND 开关、会话 upsert、turn_index 递增、字段落库、异常吞掉。
使用内存 SQLite 建 conversation 两张表，不依赖真实 MySQL。
"""

import pytest
from sqlalchemy import create_engine, text

from app.agents.nodes import persist_turn as pt
from app.agents.state import AgentState, FinalResponse, ModuleStatus, RuntimeState
from app.infrastructure.persistence.models import ConversationSession, ConversationTurn


@pytest.fixture
def sqlite_engine():
    """内存 SQLite：仅建 conversation 两张表。"""
    engine = create_engine("sqlite:///:memory:")
    ConversationSession.__table__.create(engine)
    ConversationTurn.__table__.create(engine)
    yield engine
    engine.dispose()


def _patch_mysql(monkeypatch, engine):
    """切换模块到 mysql 模式并注入 SQLite 引擎。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(pt, "_get_engine", lambda: engine)


def _make_state(
    query: str = "康美药业有风险吗",
    session_id: str = "ses_test",
    answer: str = "康美药业存在高风险信号。",
    turn_id: str = "turn_01",
) -> AgentState:
    """构造完整轮次状态。"""
    return {
        "user_query": query,
        "messages": [{"role": "user", "content": query}],
        "module_status": {
            "finance": ModuleStatus(state="success", duration_ms=120),
            "equity": ModuleStatus(state="skipped"),
        },
        "final_response": FinalResponse(answer=answer, risk_level="red"),
        "runtime": RuntimeState(
            trace_id="trace_01", session_id=session_id, turn_id=turn_id
        ),
    }


# ── no-op 开关 ──────────────────────────────────────────────


def test_noop_when_not_mysql(monkeypatch):
    """SQL_BACKEND != mysql 时不写库、返回空 messages。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "sqlite")

    def _should_not_be_called():
        raise AssertionError("sqlite 模式下不应访问数据库")

    monkeypatch.setattr(pt, "_get_engine", _should_not_be_called)
    result = pt.persist_turn_node(_make_state())
    assert result == {"messages": []}


def test_noop_without_session_id(monkeypatch, sqlite_engine):
    """无 session_id 时 no-op。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state(session_id="")
    result = pt.persist_turn_node(state)
    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one()
            == 0
        )


def test_noop_without_question(monkeypatch, sqlite_engine):
    """无问题时 no-op。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = pt.persist_turn_node(_make_state(query=""))
    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one()
            == 0
        )


# ── 首轮写入 ────────────────────────────────────────────────


def test_persist_first_turn(monkeypatch, sqlite_engine):
    """首轮：创建会话 + 写入 turn_index=1。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = pt.persist_turn_node(_make_state())

    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        session = (
            conn.execute(
                text("SELECT session_id, title, status FROM conversation_sessions")
            )
            .mappings()
            .one()
        )
        assert session["session_id"] == "ses_test"
        assert session["title"] == "康美药业有风险吗"  # question 前 30 字
        assert session["status"] == "active"

        turn = conn.execute(text("SELECT * FROM conversation_turns")).mappings().one()
        assert turn["turn_index"] == 1
        assert turn["question"] == "康美药业有风险吗"
        assert turn["answer"] == "康美药业存在高风险信号。"
        assert turn["company_code"] is None
        assert turn["trace_id"] == "trace_01"
        assert "finance" in turn["module_status"]


def test_persist_with_company_code(monkeypatch, sqlite_engine):
    """company 存在时写入 wind_code。"""
    from app.agents.state import CompanyRef

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["company"] = CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )
    pt.persist_turn_node(state)

    with sqlite_engine.connect() as conn:
        code = conn.execute(
            text("SELECT company_code FROM conversation_turns")
        ).scalar_one()
        assert code == "600518.SH"


def test_persist_second_turn_increments_index(monkeypatch, sqlite_engine):
    """第二轮：turn_index 递增为 2，不重复建会话。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state())
    pt.persist_turn_node(
        _make_state(query="它的应收账款呢", answer="应收账款增速47.2%。", turn_id="turn_02")
    )

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM conversation_sessions")
            ).scalar_one()
            == 1
        )
        indices = (
            conn.execute(
                text("SELECT turn_index FROM conversation_turns ORDER BY turn_index")
            )
            .scalars()
            .all()
        )
        assert list(indices) == [1, 2]

        # title 保持首轮
        title = conn.execute(
            text("SELECT title FROM conversation_sessions")
        ).scalar_one()
        assert title == "康美药业有风险吗"


def test_title_truncated_to_30(monkeypatch, sqlite_engine):
    """超长 question 截断为 30 字。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    long_q = "长" * 50
    pt.persist_turn_node(_make_state(query=long_q))

    with sqlite_engine.connect() as conn:
        title = conn.execute(
            text("SELECT title FROM conversation_sessions")
        ).scalar_one()
        assert len(title) == 30


# ── 异常容错 ────────────────────────────────────────────────


def test_db_error_swallowed(monkeypatch):
    """数据库异常被吞掉，不抛给 Agent 主流程。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "mysql")

    def _broken_engine():
        raise RuntimeError("db down")

    monkeypatch.setattr(pt, "_get_engine", _broken_engine)
    result = pt.persist_turn_node(_make_state())
    assert result == {"messages": []}
