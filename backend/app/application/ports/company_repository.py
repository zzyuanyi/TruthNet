"""CompanyRepository Port — V12 baseline.

定义公司数据访问接口，不依赖具体数据库。
"""

from typing import Protocol, runtime_checkable

from app.domain.company.models import CompanyRef, CompanySearchResult


@runtime_checkable
class CompanyRepository(Protocol):
    """公司数据仓库接口.

    lite: SQLiteAdapter
    full: MySQLAdapter
    """

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司."""
        ...

    async def get_by_code(self, code: str) -> CompanyRef | None:
        """按股票代码获取公司."""
        ...

    async def list_all(self, limit: int = 100) -> list[CompanyRef]:
        """列出所有公司."""
        ...
