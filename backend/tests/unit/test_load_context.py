"""LoadContext 节点单元测试 — V12 §7.2.

覆盖：SQL_BACKEND 开关、最近 N 轮回读、消息顺序、空历史、异常吞掉。
使用内存 SQLite 建 conversation 两张表，不依赖真实 MySQL。
"""

import pytest
from sqlalchemy import create_engine, text

from app.agents.nodes import load_context as lc
from app.agents.state import AgentState, RuntimeState
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
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(lc, "_get_engine", lambda: engine)


def _make_state(session_id: str = "ses_test") -> AgentState:
    return {
        "user_query": "",
        "messages": [],
        "runtime": RuntimeState(trace_id="trace_01", session_id=session_id),
    }


def _seed_turns(engine, session_id: str = "ses_test", n: int = 3) -> None:
    """预置 n 轮历史（question/answer 成对）。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"sid": session_id, "title": "历史会话"},
        )
        for i in range(1, n + 1):
            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, answer, created_at) "
                    "VALUES (:tid, :sid, :idx, :q, :a, CURRENT_TIMESTAMP)"
                ),
                {
                    "tid": f"turn_{i:02d}",
                    "sid": session_id,
                    "idx": i,
                    "q": f"第{i}轮问题",
                    "a": f"第{i}轮回答",
                },
            )


# ── no-op 开关 ──────────────────────────────────────────────


def test_noop_when_not_mysql(monkeypatch):
    """SQL_BACKEND != mysql 时不读库、返回空 messages。"""
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "sqlite")

    def _should_not_be_called():
        raise AssertionError("sqlite 模式下不应访问数据库")

    monkeypatch.setattr(lc, "_get_engine", _should_not_be_called)
    result = lc.load_context_node(_make_state())
    assert result["messages"] == []
    assert result["runtime"] is not None


def test_noop_without_session_id(monkeypatch, sqlite_engine):
    """无 session_id 时返回空。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = lc.load_context_node(_make_state(session_id=""))
    assert result["messages"] == []


# ── 历史回读 ────────────────────────────────────────────────


def test_loads_history_in_order(monkeypatch, sqlite_engine):
    """回读历史并按时间升序组装 user/assistant 消息。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turns(sqlite_engine, n=2)

    result = lc.load_context_node(_make_state())

    msgs = result["messages"]
    assert len(msgs) == 4
    assert msgs[0] == {"role": "user", "content": "第1轮问题"}
    assert msgs[1] == {"role": "assistant", "content": "第1轮回答"}
    assert msgs[2] == {"role": "user", "content": "第2轮问题"}
    assert msgs[3] == {"role": "assistant", "content": "第2轮回答"}


def test_loads_recent_n_only(monkeypatch, sqlite_engine):
    """超过回读上限时只取最近 N 轮（Phase C: 10 轮窗口）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turns(sqlite_engine, n=12)

    result = lc.load_context_node(_make_state())

    msgs = result["messages"]
    assert len(msgs) == 20  # 10 轮 × 2 条（_HISTORY_LIMIT=10）
    assert msgs[0] == {"role": "user", "content": "第3轮问题"}
    assert msgs[-1] == {"role": "assistant", "content": "第12轮回答"}


def test_empty_history(monkeypatch, sqlite_engine):
    """会话存在但无轮次时返回空 messages。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_test', '空会话', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )

    result = lc.load_context_node(_make_state())
    assert result["messages"] == []


def test_session_not_exist(monkeypatch, sqlite_engine):
    """会话不存在时返回空（不抛错）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = lc.load_context_node(_make_state(session_id="ses_missing"))
    assert result["messages"] == []


# ── 异常容错 ────────────────────────────────────────────────


def test_db_error_swallowed(monkeypatch):
    """数据库异常被吞掉，返回空消息。"""
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "mysql")

    def _broken_engine():
        raise RuntimeError("db down")

    monkeypatch.setattr(lc, "_get_engine", _broken_engine)
    result = lc.load_context_node(_make_state())
    assert result["messages"] == []
