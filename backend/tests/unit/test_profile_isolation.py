"""连接配置 profile 隔离测试 — v3.3.3 收口残余批次（审查 P1，2026-08-14）。

验证：同一 backend 下切换 host/port/database/user 后，Repository 与
NameIndexProvider 的**实例及其 Engine 均不得复用**——否则旧库名称会被
缓存到新 profile 下、旧库连接被新 profile 复用（静默读错库）。

审查复现场景：
    MYSQL_DATABASE=db_one -> provider A
    MYSQL_DATABASE=db_two -> provider B
    旧实现：same_provider=True、profile_key=新库、engine_reused=True
    修复后：same_provider=False、profile_key/Engine 绑定各自捕获库
"""

import pytest

from app.application.services import company_resolver as cr
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_factory_state():
    from app.domain.finance import _fetch

    cr._repo_cache.clear()
    cr._name_provider_cache.clear()
    _fetch._ENGINES.clear()
    yield
    cr._repo_cache.clear()
    cr._name_provider_cache.clear()
    _fetch._ENGINES.clear()


class _DummyEngine:
    """记录 dispose 的假 Engine（不触碰数据库）。"""

    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


# ── NameIndexProvider 工厂 ─────────────────────────────────


def test_name_provider_isolated_by_database(monkeypatch):
    """审查复现场景：同 backend 切换 database 不得复用实例。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    p1 = cr.get_company_name_index_provider()
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
    p2 = cr.get_company_name_index_provider()
    assert p1 is not p2
    assert p1.profile_key.endswith("db_one")
    assert p2.profile_key.endswith("db_two")
    # 切回 db_one 复用同一实例（正常缓存语义不变）
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    assert cr.get_company_name_index_provider() is p1


def test_name_provider_engine_bound_to_construction_profile(monkeypatch):
    """实例创建后切换 settings，Engine 仍绑定创建时的数据库。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    p1 = cr.get_company_name_index_provider()
    e1 = p1._get_engine()
    try:
        assert e1.url.database == "db_one"
        monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
        assert p1._get_engine() is e1  # 旧实例不重建 Engine
        assert e1.url.database == "db_one"  # 也不偷换库
        p2 = cr.get_company_name_index_provider()
        assert p2 is not p1
        assert p2._engine is None
        e2 = p2._get_engine()
        try:
            assert e2 is not e1
            assert e2.url.database == "db_two"
        finally:
            e2.dispose()
    finally:
        e1.dispose()


def test_name_provider_isolated_by_user_and_host(monkeypatch):
    """MySQL key 至少包含 backend/user/host/port/database。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_USER", "user_a")
    p1 = cr.get_company_name_index_provider()
    monkeypatch.setattr(settings, "MYSQL_USER", "user_b")
    p2 = cr.get_company_name_index_provider()
    assert p1 is not p2
    monkeypatch.setattr(settings, "MYSQL_HOST", "other-host")
    p3 = cr.get_company_name_index_provider()
    assert p3 is not p2


def test_name_provider_sqlite_key_includes_path(monkeypatch):
    """SQLite key 包含 SQLITE_PATH，不同 db 文件不共用 profile。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", "data/a.db")
    p1 = cr.get_company_name_index_provider()
    monkeypatch.setattr(settings, "SQLITE_PATH", "data/b.db")
    p2 = cr.get_company_name_index_provider()
    assert p1 is not p2
    assert p1.profile_key == "sqlite:data/a.db"
    assert p2.profile_key == "sqlite:data/b.db"


# ── Repository 工厂 ────────────────────────────────────────


def test_repository_isolated_by_database(monkeypatch):
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    r1 = cr.get_company_repository()
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
    r2 = cr.get_company_repository()
    assert r1 is not r2


def test_repository_engine_bound_to_construction_profile(monkeypatch):
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    r1 = cr.get_company_repository()
    e1 = r1._get_engine()
    try:
        assert e1.url.database == "db_one"
        monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
        r2 = cr.get_company_repository()
        assert r2 is not r1
        assert r2._engine is None
        e2 = r2._get_engine()
        try:
            assert e2 is not e1
            assert e2.url.database == "db_two"
            assert e1.url.database == "db_one"
        finally:
            e2.dispose()
    finally:
        e1.dispose()


def test_repository_sqlite_isolated_by_path(monkeypatch):
    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", "data/a.db")
    r1 = cr.get_company_repository()
    monkeypatch.setattr(settings, "SQLITE_PATH", "data/b.db")
    r2 = cr.get_company_repository()
    assert r1 is not r2
    assert r1._db_path == "data/a.db"
    assert r2._db_path == "data/b.db"


def test_repository_same_profile_reuses_instance(monkeypatch):
    """同 profile 重复调用仍复用实例（既有 P2-1 语义不回归）。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "truthnet")
    r1 = cr.get_company_repository()
    r2 = cr.get_company_repository()
    assert r1 is r2


# ── 审查 P2：切库时 dispose 其他 profile 的旧 Engine ──────────


def test_provider_other_profile_engine_disposed_on_switch(monkeypatch):
    """切换 profile 时，旧 profile 实例的 Engine 被 dispose（连接池不滞留）。"""
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    p1 = cr.get_company_name_index_provider()
    dummy = _DummyEngine()
    p1._engine = dummy
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
    p2 = cr.get_company_name_index_provider()
    assert p2 is not p1
    assert dummy.disposed is True  # 旧 profile 连接池已释放
    # 切回 db_one 复用同一实例（Engine 懒重建，实例不失效）
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    assert cr.get_company_name_index_provider() is p1


def test_repository_other_profile_engine_disposed_on_switch(monkeypatch):
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    r1 = cr.get_company_repository()
    dummy = _DummyEngine()
    r1._engine = dummy
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
    cr.get_company_repository()
    assert dummy.disposed is True


def test_fetch_engine_profile_keyed(monkeypatch):
    """审查 P2：_fetch._get_engine 按完整 profile key 缓存，不按 backend。"""
    from app.domain.finance import _fetch

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    assert _fetch._engine_profile_key(settings).endswith(":db_one")
    e1 = _fetch._get_engine()
    try:
        monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
        assert _fetch._engine_profile_key(settings).endswith(":db_two")
        e2 = _fetch._get_engine()
        try:
            assert e2 is not e1
            assert e1.url.database == "db_one"
            assert e2.url.database == "db_two"
        finally:
            e2.dispose()
    finally:
        e1.dispose()


def test_fetch_engine_disposes_other_profiles(monkeypatch):
    """切换 profile 建立新 Engine 时，旧 profile Engine 被 dispose。"""
    from app.domain.finance import _fetch

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_one")
    key_one = _fetch._engine_profile_key(settings)
    dummy = _DummyEngine()
    _fetch._ENGINES[key_one] = dummy
    monkeypatch.setattr(settings, "MYSQL_DATABASE", "db_two")
    engine = _fetch._get_engine()
    try:
        assert dummy.disposed is True
        assert engine.url.database == "db_two"
        # 旧 key 条目保留但 Engine 已 dispose（懒重建语义）
        assert _fetch._ENGINES[key_one] is dummy
    finally:
        engine.dispose()
