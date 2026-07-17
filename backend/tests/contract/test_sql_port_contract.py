"""SQL Port Contract 测试 — SQLite 和 MySQL 共享接口."""

import pytest

from app.application.ports.company_repository import CompanyRepository
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


class TestSQLPortContract:
    """SQLite CompanyRepository 满足 CompanyRepository Port."""

    def test_adapter_satisfies_port(self):
        repo = SQLiteCompanyRepository()
        assert isinstance(repo, CompanyRepository)

    @pytest.mark.asyncio
    async def test_search_by_code(self):
        repo = SQLiteCompanyRepository()
        c = await repo.get_by_code("600519")
        assert c is not None
        assert c.code == "600519"
        assert c.name == "贵州茅台酒股份有限公司"

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        repo = SQLiteCompanyRepository()
        result = await repo.search("茅台")
        assert result.total >= 1
        assert result.companies[0].code == "600519"

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        repo = SQLiteCompanyRepository()
        result = await repo.search("")
        assert result.total >= 1

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        repo = SQLiteCompanyRepository()
        c = await repo.get_by_code("999999")
        assert c is None

    @pytest.mark.asyncio
    async def test_list_all(self):
        repo = SQLiteCompanyRepository()
        companies = await repo.list_all()
        assert len(companies) >= 4
