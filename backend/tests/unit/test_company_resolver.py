"""CompanyResolver 单元测试 — Phase C 任务 14.

使用 SQLite fixture adapter（CI 自包含），覆盖代码规范化、名称搜索、
单字符拒绝、唯一命中判定。
"""

import pytest

from app.application.services.company_resolver import CompanyResolver
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


@pytest.fixture
def resolver():
    return CompanyResolver(repo=SQLiteCompanyRepository())


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
