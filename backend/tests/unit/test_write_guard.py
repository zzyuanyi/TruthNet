"""运行时写守卫单测 — 8/19 全面审查 P0（演示库零写入运行时防线，降级告警版）.

8/19 队长拍板（方案A 收敛）：守卫**不阻断**写入（fail-open 告警），
本地开发 .env 即 MYSQL_DATABASE=truthnet，阻断会破坏开发/演示启动。
断言语义：未授权写演示库 → 打印 warning（限频每 profile 一次），
不抛错、不阻断；授权/测试库/sqlite → 静默。

覆盖：
  - assert_db_writable：sqlite 静默 / mysql 非演示库静默 / 演示库未授权告警
  - validate_runtime_write_policy：lifespan 启动告警语义
  - ALLOW_DEMO_DB_WRITE=true 显式授权静默
  - 大小写不敏感（MySQL lower_case_table_names=1）
  - 限频：同 profile 只告警一次
"""

from __future__ import annotations

import logging

import pytest

from app.core import write_guard
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """每用例重置守卫相关配置与告警缓存，避免用例间污染。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "truthnet")
    monkeypatch.setattr(settings, "DEMO_DATABASE_NAME", "truthnet")
    monkeypatch.setattr(settings, "ALLOW_DEMO_DB_WRITE", False)
    monkeypatch.setattr(write_guard, "_warned_profiles", set())


def _warnings(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "app.core.write_guard"]


class TestAssertDbWritable:
    def test_mysql_demo_db_warns(self, caplog):
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()  # 不抛错
        assert _warnings(caplog), "演示库未授权应产生告警"
        assert "写守卫" in caplog.text

    def test_mysql_demo_db_case_insensitive(self, caplog):
        settings.MYSQL_DATABASE = "TRUTHNET"
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert _warnings(caplog)

    def test_mysql_test_db_silent(self, caplog):
        settings.MYSQL_DATABASE = "truthnet_test"
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert not _warnings(caplog), "测试库应静默"

    def test_mysql_other_db_silent(self, caplog):
        settings.MYSQL_DATABASE = "truthnet_restore_test"
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert not _warnings(caplog)

    def test_sqlite_silent(self, caplog):
        settings.SQL_BACKEND = "sqlite"
        settings.MYSQL_DATABASE = "truthnet"  # 即使同名也静默（无演示库语义）
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert not _warnings(caplog)

    def test_explicit_allow_demo_write_silent(self, caplog):
        settings.ALLOW_DEMO_DB_WRITE = True
        settings.MYSQL_DATABASE = "truthnet"
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert not _warnings(caplog)

    def test_custom_demo_db_name(self, caplog):
        settings.DEMO_DATABASE_NAME = "production_db"
        settings.MYSQL_DATABASE = "production_db"
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
        assert _warnings(caplog)

    def test_warn_once_per_profile(self, caplog):
        """限频：同 profile 重复调用只告警一次。"""
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable()
            write_guard.assert_db_writable()
            write_guard.assert_db_writable()
        assert len(_warnings(caplog)) == 1

    def test_explicit_engine_database_overrides_global_profile(self, caplog):
        """显式测试库 Engine 不应因全局配置指向演示库而误告警。"""
        with caplog.at_level(logging.WARNING):
            write_guard.assert_db_writable(database="truthnet_test")
        assert not _warnings(caplog)


class TestValidateRuntimeWritePolicy:
    def test_demo_db_warns_not_block(self, caplog):
        """lifespan 启动校验：告警不阻断（8/19 拍板）。"""
        with caplog.at_level(logging.WARNING):
            write_guard.validate_runtime_write_policy()  # 不抛错
        assert _warnings(caplog)

    def test_test_db_starts_ok(self, caplog):
        settings.MYSQL_DATABASE = "truthnet_test"
        with caplog.at_level(logging.WARNING):
            write_guard.validate_runtime_write_policy()
        assert not _warnings(caplog)

    def test_allow_demo_write_starts_ok(self, caplog):
        settings.ALLOW_DEMO_DB_WRITE = True
        with caplog.at_level(logging.WARNING):
            write_guard.validate_runtime_write_policy()
        assert not _warnings(caplog)

    def test_sqlite_starts_ok(self, caplog):
        settings.SQL_BACKEND = "sqlite"
        with caplog.at_level(logging.WARNING):
            write_guard.validate_runtime_write_policy()
        assert not _warnings(caplog)


class TestWriteGuardWiring:
    """写路径接线：守卫调用不破坏正常路径（sqlite 下静默执行）。"""

    def test_provenance_persist_evidence_sqlite_ok(self, monkeypatch):
        """sqlite 下 ProvenanceService 写路径不受守卫影响（零行为变更）。"""
        from sqlalchemy import create_engine, text

        from app.application.services.provenance_service import ProvenanceService

        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE evidence_refs (evidence_id TEXT PRIMARY KEY, "
                    "source_type TEXT, source_record_id TEXT, company_code TEXT, "
                    "field_path TEXT, period TEXT, value TEXT, unit TEXT, "
                    "statement_scope TEXT, source_title TEXT, dataset_version TEXT, "
                    "retrieved_at TEXT, turn_id TEXT, trace_id TEXT, module TEXT, "
                    "source_table TEXT)"
                )
            )
        settings.SQL_BACKEND = "sqlite"  # 守卫静默分支
        svc = ProvenanceService(engine=engine)
        written = svc.persist_evidence(
            [{"evidence_id": "ev_guard_1", "source_type": "announcement"}],
            trace_id="t",
            turn_id="turn",
        )
        assert written == ["ev_guard_1"]

    def test_persist_turn_node_sqlite_ok(self, monkeypatch):
        """sqlite 下 persist_turn_node 正常执行（守卫零行为变更）。"""
        import app.agents.nodes.persist_turn as pt
        from sqlalchemy import create_engine

        from app.infrastructure.persistence.models import (
            ConversationSession,
            ConversationTurn,
        )

        engine = create_engine("sqlite:///:memory:")
        ConversationSession.__table__.create(engine)
        ConversationTurn.__table__.create(engine)
        monkeypatch.setattr(pt, "_get_engine", lambda: engine)

        state = {
            "runtime": type(
                "R",
                (),
                {
                    "session_id": "ses_guard_1",
                    "trace_id": "t",
                    "turn_id": "turn_1",
                    "warnings": [],
                },
            )(),
            "user_query": "康美药业财务如何？",
            "final_response": type("F", (), {"answer": "分析结论"})(),
            "company": None,
        }
        result = pt.persist_turn_node(state)
        assert result.get("module_status", {}).get("persist_turn", {}).get("state") in (
            None,
            "ok",
            "partial",
        )
