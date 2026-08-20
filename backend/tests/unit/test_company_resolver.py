"""CompanyResolver 单元测试 — Phase C 任务 14.

使用 SQLite fixture adapter（CI 自包含），覆盖代码规范化、名称搜索、
单字符拒绝、唯一命中判定。
"""

import pytest

from app.domain.company.models import CompanyRecord
from app.application.services.company_resolver import (
    CompanyResolver,
    get_company_repository,
)
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


@pytest.fixture
def resolver():
    return CompanyResolver(repo=SQLiteCompanyRepository())


class _AliasRepository:
    """最小仓库夹具：验证别名归一化后按规范名查询。"""

    def __init__(self):
        self.record = CompanyRecord(
            entity_id="company_601601_SH",
            wind_code="601601.SH",
            sec_name="中国太保",
        )

    async def get_by_code(self, code):
        return self.record if code == "中国太保" else None

    async def get_by_entity_id(self, entity_id):
        return None

    async def search(self, query, limit=10):
        raise AssertionError("精确俗称应在 search 前归一化")


def test_factory_caches_repository_by_backend(monkeypatch):
    """中间验收 P2-1：同一 backend 重复调用返回同一实例（Engine 复用，
    长对话不再每轮新建连接池）。"""
    from app.application.services import company_resolver as cr

    monkeypatch.setattr(cr.settings, "SQL_BACKEND", "sqlite")
    cr._repo_cache.clear()
    r1 = get_company_repository()
    r2 = get_company_repository()
    assert r1 is r2


def test_factory_cache_separated_by_backend(monkeypatch):
    """中间验收 P2-1：backend 切换后使用独立缓存实例。"""
    from app.application.services import company_resolver as cr

    monkeypatch.setattr(cr.settings, "SQL_BACKEND", "sqlite")
    cr._repo_cache.clear()
    r_sqlite = get_company_repository()
    monkeypatch.setattr(cr.settings, "SQL_BACKEND", "mysql")
    r_mysql = get_company_repository()
    assert r_sqlite is not r_mysql
    assert type(r_mysql).__name__ == "MySQLCompanyRepository"
    cr._repo_cache.clear()


@pytest.mark.asyncio
async def test_resolve_by_digits(resolver):
    c = await resolver.resolve("600518")
    assert c is not None
    assert c.wind_code == "600518.SH"
    assert c.entity_id == "company_600518_SH"


@pytest.mark.asyncio
async def test_resolve_by_full_wind_code(resolver):
    c = await resolver.resolve("600518.SH")
    assert c is not None
    assert c.sec_name == "康美药业"


@pytest.mark.asyncio
async def test_resolve_by_underscore_code(resolver):
    c = await resolver.resolve("600518_SH")
    assert c is not None
    assert c.wind_code == "600518.SH"


@pytest.mark.asyncio
async def test_resolve_by_name(resolver):
    c = await resolver.resolve("贵州茅台")
    assert c is not None
    assert c.wind_code == "600519.SH"


@pytest.mark.asyncio
async def test_resolve_by_market_alias():
    c = await CompanyResolver(repo=_AliasRepository()).resolve("太平洋保险")
    assert c is not None
    assert c.sec_name == "中国太保"
    assert c.wind_code == "601601.SH"


@pytest.mark.asyncio
async def test_resolve_single_char_rejected(resolver):
    assert await resolver.resolve("茅") is None
    assert await resolver.resolve("A") is None


@pytest.mark.asyncio
async def test_resolve_unknown_none(resolver):
    assert await resolver.resolve("999999") is None
    assert await resolver.resolve("") is None


@pytest.mark.asyncio
async def test_resolve_by_entity_id(resolver):
    c = await resolver.resolve("company_600518_SH")
    assert c is not None
    assert c.entity_id == "company_600518_SH"


@pytest.mark.asyncio
async def test_search_exact_code_priority(resolver):
    result = await resolver.repo.search("600519", limit=5)
    assert result.total >= 1
    assert result.companies[0].wind_code == "600519.SH"
