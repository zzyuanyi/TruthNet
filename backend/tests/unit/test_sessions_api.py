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
from app.infrastructure.persistence.models import (
    Claim,
    ClaimEvidenceLink,
    ConversationSession,
    ConversationTurn,
    EventCluster,
    EventClusterSource,
    EvidenceRef,
    RatingChange,
)
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
    # 建全量会话/证据表（DELETE 级联路径依赖：links → claims → evidence）
    for tbl in (
        ConversationSession,
        ConversationTurn,
        EvidenceRef,
        Claim,
        ClaimEvidenceLink,
        EventCluster,
        EventClusterSource,
        RatingChange,
    ):
        tbl.__table__.create(engine)

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
    resp = mysql_client.post(
        "/api/v1/sessions", json={"title": "新会话", "user_id": "user_a"}
    )
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["session_id"].startswith("ses_")
    assert d["user_id"] == "user_a"
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


def test_get_session_returns_panel_data(mysql_client):
    """详情：turn 返回 panel_data（v7 历史面板恢复，对齐审计 P1-3）.

    旧数据 panel_data=None 时同样 200（不伪造风险等级）。
    """
    engine = sessions_router._get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_panel', '面板', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, panel_data, created_at) "
                "VALUES ('turn_panel_1', 'ses_panel', 1, '问题', "
                ":pd, CURRENT_TIMESTAMP)"
            ),
            {
                "pd": '{"risk_level": "red", "triggered_rules": '
                '[{"rule_id": "R1", "rule_name": "应收-营收背离", '
                '"evidence_ids": []}], "key_metrics": {}, "follow_ups": []}'
            },
        )

    resp = mysql_client.get("/api/v1/sessions/ses_panel")
    assert resp.status_code == 200
    turns = resp.json()["data"]["turns"]
    assert len(turns) == 1
    panel = turns[0]["panel_data"]
    assert isinstance(panel, dict), f"panel_data 应为对象，实际 {type(panel)}"
    assert panel["risk_level"] == "red"
    assert panel["triggered_rules"][0]["rule_name"] == "应收-营收背离"

    # 旧数据（无 panel_data）→ None，不崩溃
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, created_at) "
                "VALUES ('turn_panel_2', 'ses_panel', 2, '旧轮次', "
                "CURRENT_TIMESTAMP)"
            )
        )
    resp2 = mysql_client.get("/api/v1/sessions/ses_panel")
    assert resp2.status_code == 200
    turns2 = resp2.json()["data"]["turns"]
    assert len(turns2) == 2
    assert turns2[1]["panel_data"] is None


def test_get_session_returns_response_metadata(mysql_client):
    engine = sessions_router._get_engine()
    _seed_session(engine, sid="ses_meta", turns=0)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, response_meta, created_at) "
                "VALUES ('turn_meta', 'ses_meta', 1, '问题', :meta, CURRENT_TIMESTAMP)"
            ),
            {
                "meta": '{"intent":"diagnose","follow_ups":["继续"],'
                '"supporting_evidence_ids":["ev_1"],'
                '"requested_period_text":"2025年报"}'
            },
        )
    turn = mysql_client.get("/api/v1/sessions/ses_meta").json()["data"]["turns"][0]
    assert turn["intent"] == "diagnose"
    assert turn["follow_ups"] == ["继续"]
    assert turn["supporting_evidence_ids"] == ["ev_1"]
    assert turn["requested_period_text"] == "2025年报"


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


def test_list_sessions_paginates_with_total(mysql_client):
    engine = sessions_router._get_engine()
    for index in range(3):
        _seed_session(engine, sid=f"ses_page_{index}", turns=0)
    data = mysql_client.get("/api/v1/sessions?limit=2&offset=1").json()["data"]
    assert len(data["sessions"]) == 2
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 1


def test_sessions_are_filtered_by_user_id(mysql_client):
    """列表/详情按 user_id 隔离；NULL 历史会话只归默认用户。"""
    engine = sessions_router._get_engine()
    with engine.begin() as conn:
        for sid, user_id in (("ses_a", "user_a"), ("ses_b", "user_b")):
            conn.execute(
                text(
                    "INSERT INTO conversation_sessions "
                    "(session_id, user_id, title, status, created_at, updated_at) "
                    "VALUES (:sid, :uid, :title, 'active', CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                ),
                {"sid": sid, "uid": user_id, "title": sid},
            )

    data_a = mysql_client.get("/api/v1/sessions?user_id=user_a").json()["data"]
    assert [s["session_id"] for s in data_a["sessions"]] == ["ses_a"]

    assert mysql_client.get("/api/v1/sessions/ses_b?user_id=user_a").status_code == 404
    assert mysql_client.get("/api/v1/sessions/ses_b?user_id=user_b").status_code == 200


# ── 删除（级联 + 全局证据保护回归）─────────────────────────


def _seed_delete_scenario(engine) -> None:
    """预置删除场景：1 会话 1 turn + 4 类证据.

    - ev_local:   仅 turn 关联（→ 删除）
    - ev_claim:   被本会话 Claim 引用（Claim 随 turn 删除后无引用 → 删除）
    - ev_rating:  被 rating_changes 引用（全局资产 → 保留，turn_id 置 NULL）
    - ev_cluster: 被 event_cluster_sources 引用（全局资产 → 保留，turn_id 置 NULL）
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_del', '待删', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, created_at) "
                "VALUES ('turn_del', 'ses_del', 1, '问题', CURRENT_TIMESTAMP)"
            )
        )
        for eid in ("ev_local", "ev_claim", "ev_rating", "ev_cluster"):
            conn.execute(
                text(
                    "INSERT INTO evidence_refs "
                    "(evidence_id, source_type, source_record_id, turn_id, "
                    " dataset_version, retrieved_at) "
                    "VALUES (:e, 'financial_statement', :e, 'turn_del', "
                    " 'mock-v12', CURRENT_TIMESTAMP)"
                ),
                {"e": eid},
            )
        conn.execute(
            text(
                "INSERT INTO claims "
                "(claim_id, turn_id, text, severity, verification_status, "
                " generated_at) "
                "VALUES ('claim_1', 'turn_del', '断言', 'high', 'verified', "
                "CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claim_evidence_links "
                "(claim_id, evidence_id, relation_type, sequence_no, created_at) "
                "VALUES ('claim_1', 'ev_claim', 'supports', 0, CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO rating_changes "
                "(rating_change_id, wind_code, quarter, institution, "
                " current_rating, direction, evidence_id, dataset_version) "
                "VALUES ('rc_1', '600518', '2024Q1', 'test', '买入', 'up', "
                " 'ev_rating', 'mock-v12')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO event_clusters "
                "(event_cluster_id, entity_id, wind_code, topic, summary, "
                " cluster_method, start_date, end_date, event_count, sentiment, "
                " cluster_version, dataset_version, created_at) "
                "VALUES ('ec_1', 'e1', '600518', '主题', '', 'v1', "
                " '2024-01-01', '2024-01-02', 1, 'negative', 'v1', 'mock-v12', "
                " CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO event_cluster_sources "
                "(event_cluster_id, source_type, source_record_id, evidence_id, "
                " sequence_no) "
                "VALUES ('ec_1', 'announcement', 'src_1', 'ev_cluster', 0)"
            )
        )


def test_delete_session_soft_deletes_and_preserves_audit_chain(mysql_client):
    """DELETE /sessions/{id}：软删除，不物理删除 turns/claims/evidence。

    物理级联清理由 SessionCleanupService.cleanup_session 在 TTL/脚本中执行；
    REST 删除只隐藏会话并保留审计链。
    """
    engine = sessions_router._get_engine()
    _seed_delete_scenario(engine)

    resp = mysql_client.delete("/api/v1/sessions/ses_del")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"deleted": True, "session_id": "ses_del"}

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, metadata FROM conversation_sessions WHERE session_id='ses_del'"
            )
        ).first()
        assert row[0] == "archived"
        import json

        meta = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        assert meta["deleted_at"]
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar() == 1
        )
        assert conn.execute(text("SELECT COUNT(*) FROM claims")).scalar() == 1
        assert (
            conn.execute(text("SELECT COUNT(*) FROM claim_evidence_links")).scalar()
            == 1
        )
        assert conn.execute(text("SELECT COUNT(*) FROM evidence_refs")).scalar() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM rating_changes")).scalar() == 1
        assert (
            conn.execute(text("SELECT COUNT(*) FROM event_cluster_sources")).scalar()
            == 1
        )
    assert mysql_client.get("/api/v1/sessions/ses_del").status_code == 404


def test_delete_empty_session(mysql_client):
    """零轮次会话也可删除（曾因 turn_rows 为空误判 404）。"""
    engine = sessions_router._get_engine()
    _seed_session(engine, sid="ses_empty", turns=0)

    resp = mysql_client.delete("/api/v1/sessions/ses_empty")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"deleted": True, "session_id": "ses_empty"}
    with engine.connect() as conn:
        status = conn.execute(
            text(
                "SELECT status FROM conversation_sessions WHERE session_id='ses_empty'"
            )
        ).scalar()
        assert status == "archived"


def test_purge_expired_soft_deleted_sessions(mysql_client):
    """TTL 到期后，软删除会话可由清理服务物理删除。"""
    from datetime import datetime, timezone
    import json

    from app.application.services.session_cleanup_service import SessionCleanupService

    engine = sessions_router._get_engine()
    with engine.begin() as conn:
        for sid, deleted_at in (
            ("ses_old_deleted", "2026-01-01T00:00:00+00:00"),
            ("ses_recent_deleted", "2026-08-18T00:00:00+00:00"),
        ):
            conn.execute(
                text(
                    "INSERT INTO conversation_sessions "
                    "(session_id, title, status, metadata, created_at, updated_at) "
                    "VALUES (:sid, :title, 'archived', :meta, CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                ),
                {
                    "sid": sid,
                    "title": sid,
                    "meta": json.dumps({"deleted_at": deleted_at}),
                },
            )

    stats = SessionCleanupService(engine=engine).purge_expired_soft_deleted(
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
        ttl_days=30,
    )
    assert stats["scanned"] == 2
    assert stats["purged"] == 1
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text("SELECT session_id FROM conversation_sessions ORDER BY session_id")
            )
            .scalars()
            .all()
        )
    assert rows == ["ses_recent_deleted"]


def test_delete_session_not_found(mysql_client):
    """不存在的会话 → 404 SESSION_NOT_FOUND。"""
    resp = mysql_client.delete("/api/v1/sessions/ses_missing")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "SESSION_NOT_FOUND"


def _seed_cross_session_scenario(engine) -> None:
    """跨会话共享证据场景（事故核心场景回归）。

    ev_shared 的 turn_id 属于被删会话 A，但被保留会话 B 的 Claim 引用：
    - 删除 A 前曾无条件删除 ev_shared → B 的 Claim 失去证据链接（P1 事故）
    - 现在应保留 ev_shared、保留 B 的 link，并将 turn_id 置 NULL
    """
    with engine.begin() as conn:
        # 会话 A（将被删除）
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_del', '待删', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, created_at) "
                "VALUES ('turn_del', 'ses_del', 1, '问题', CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO evidence_refs "
                "(evidence_id, source_type, source_record_id, turn_id, "
                " dataset_version, retrieved_at) "
                "VALUES ('ev_shared', 'financial_statement', 'src_shared', "
                " 'turn_del', 'mock-v12', CURRENT_TIMESTAMP)"
            )
        )
        # 会话 B（保留），其 Claim 引用 ev_shared
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_keep', '保留', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, created_at) "
                "VALUES ('turn_keep', 'ses_keep', 1, '问题', CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claims "
                "(claim_id, turn_id, text, severity, verification_status, "
                " generated_at) "
                "VALUES ('claim_keep', 'turn_keep', '保留会话的断言', 'medium', "
                " 'verified', CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claim_evidence_links "
                "(claim_id, evidence_id, relation_type, sequence_no, created_at) "
                "VALUES ('claim_keep', 'ev_shared', 'supports', 0, CURRENT_TIMESTAMP)"
            )
        )


def test_hard_cleanup_preserves_cross_session_shared_evidence(mysql_client):
    """硬清理服务：删 A 后保留 ev_shared + B 的 link，turn_id 置 NULL。

    回归（P1 事故根因）：物理清理共享 evidence_refs 后，外键级联删除
    其他 Claim 的 links，曾导致保留会话的证据链断裂。
    """
    from app.application.services.session_cleanup_service import SessionCleanupService

    engine = sessions_router._get_engine()
    _seed_cross_session_scenario(engine)

    stats = SessionCleanupService(engine=engine).cleanup_session("ses_del")
    assert stats["session_deleted"] is True

    with engine.connect() as conn:
        # 会话 A 已删，B 保留
        sessions = (
            conn.execute(text("SELECT session_id FROM conversation_sessions"))
            .scalars()
            .all()
        )
        assert sessions == ["ses_keep"]
        # ev_shared 保留且 turn_id 置 NULL
        rows = conn.execute(
            text("SELECT evidence_id, turn_id FROM evidence_refs")
        ).all()
        assert rows == [("ev_shared", None)]
        # B 的 link 与 Claim 完好（未被级联误删）
        assert (
            conn.execute(text("SELECT COUNT(*) FROM claim_evidence_links")).scalar()
            == 1
        )
        assert conn.execute(text("SELECT COUNT(*) FROM claims")).scalar() == 1
        # 无指向已删 turn 的无效引用
        invalid = conn.execute(
            text(
                "SELECT COUNT(*) FROM evidence_refs e "
                "LEFT JOIN conversation_turns t ON e.turn_id = t.turn_id "
                "WHERE e.turn_id IS NOT NULL AND t.turn_id IS NULL"
            )
        ).scalar()
        assert invalid == 0
