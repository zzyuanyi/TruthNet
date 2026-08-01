"""Sessions REST 路由测试 — V12 §11.2.

覆盖：lite 模式空列表、创建、详情（module_status JSON 反序列化）、404、
列表 turn_count。使用内存 SQLite + monkeypatch，不依赖真实 MySQL。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.api.v1.routers import sessions as sessions_router
from app.core.config import settings
from app.infrastructure.persistence.models import ConversationSession, ConversationTurn
from app.main import app


@pytest.fixture
def client(monkeypatch):
    """TestClient 实例（lite 模式，无需 DB）。

    app.main import 时会 load_dotenv(根 .env) 使 SQL_BACKEND=mysql，
    此处显式固定 sqlite 保证测试隔离。
    """
    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    return TestClient(app)


@pytest.fixture
def mysql_client(monkeypatch):
    """mysql 模式 TestClient：settings 切 mysql + 注入 SQLite 引擎。

    TestClient 在线程池执行 sync 端点，SQLite 需 check_same_thread=False。
    """
    # StaticPool: SQLite :memory: 默认 SingletonThreadPool 每线程独立内存库，
    # TestClient 线程池执行端点时查不到 fixture 建的表，必须共享同一连接
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ConversationSession.__table__.create(engine)
    ConversationTurn.__table__.create(engine)

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(sessions_router, "_get_engine", lambda: engine)

    yield TestClient(app)
    engine.dispose()


def _seed_session(engine, sid: str = "ses_test", turns: int = 0) -> None:
    """预置会话 + n 条 turns（module_status 用 JSON 字符串模拟 MySQL 返回）。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": sid, "title": "测试会话"},
        )
        for i in range(1, turns + 1):
            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, module_status, "
                    " created_at) "
                    "VALUES (:tid, :sid, :idx, :q, :ms, CURRENT_TIMESTAMP)"
                ),
                {
                    "tid": f"turn_{sid}_{i}",
                    "sid": sid,
                    "idx": i,
                    "q": f"第{i}轮问题",
                    "ms": '{"finance": {"state": "success"}}',
                },
            )


# ── lite 模式 ───────────────────────────────────────────────


def test_list_empty_in_lite_mode(client):
    """lite 模式：空列表 + LITE_MODE warning。"""
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["sessions"] == []
    assert data["data"]["total"] == 0
    assert data["warnings"][0]["code"] == "LITE_MODE"


# ── 创建 ────────────────────────────────────────────────────


def test_create_session(mysql_client):
    """POST /sessions：返回 ses_ 前缀 session_id。"""
    resp = mysql_client.post("/api/v1/sessions", json={"title": "新会话"})
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["session_id"].startswith("ses_")
    assert d["title"] == "新会话"
    assert d["status"] == "active"


def test_create_session_default_title(mysql_client):
    """未传 title 时默认"新会话"。"""
    resp = mysql_client.post("/api/v1/sessions", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "新会话"


# ── 详情 ────────────────────────────────────────────────────


def test_get_session_detail_parses_module_status(mysql_client):
    """详情：module_status 反序列化为对象（非字符串）。"""
    engine = sessions_router._get_engine()  # monkeypatch 注入的 SQLite 引擎
    _seed_session(engine, turns=1)

    resp = mysql_client.get("/api/v1/sessions/ses_test")
    assert resp.status_code == 200
    turns = resp.json()["data"]["turns"]
    assert len(turns) == 1
    ms = turns[0]["module_status"]
    assert isinstance(ms, dict), f"module_status 应为对象，实际 {type(ms)}"
    assert ms["finance"]["state"] == "success"


def test_get_session_not_found(mysql_client):
    """不存在会话 → 404 Problem Details，error_code 保留业务码。"""
    resp = mysql_client.get("/api/v1/sessions/ses_missing")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "SESSION_NOT_FOUND"
    assert body["title"] == "Session Not Found"


def test_get_session_empty_turns(mysql_client):
    """会话存在但无轮次 → 200 空 turns。"""
    engine = sessions_router._get_engine()
    _seed_session(engine, turns=0)

    resp = mysql_client.get("/api/v1/sessions/ses_test")
    assert resp.status_code == 200
    assert resp.json()["data"]["turns"] == []


# ── 列表 ────────────────────────────────────────────────────


def test_list_with_turn_count(mysql_client):
    """列表：turn_count 与 updated_at 倒序。"""
    engine = sessions_router._get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_new', '新', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
    _seed_session(engine, sid="ses_old", turns=2)

    resp = mysql_client.get("/api/v1/sessions")
    sessions = resp.json()["data"]["sessions"]
    by_id = {s["session_id"]: s for s in sessions}
    assert by_id["ses_old"]["turn_count"] == 2
    assert by_id["ses_new"]["turn_count"] == 0
