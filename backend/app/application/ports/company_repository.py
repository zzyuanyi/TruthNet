"""CompanyRepository Port — V12 baseline.

定义公司数据访问接口，不依赖具体数据库。
"""

from typing import Protocol, runtime_checkable

from app.domain.company.models import CompanyRecord, CompanySearchResult


@runtime_checkable
class CompanyRepository(Protocol):
    """公司数据仓库接口.

    lite: SQLiteAdapter
    full: MySQLAdapter
    """

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司.

        匹配质量排序：精确代码 > 精确名称 > 受限前缀/包含。
        """
        ...

    async def get_by_code(self, code: str) -> CompanyRecord | None:
        """按股票代码获取公司（支持 600518 / 600518.SH / 600518_SH）。"""
        ...

    async def get_by_entity_id(self, entity_id: str) -> CompanyRecord | None:
        """按内部实体 ID 获取公司."""
        ...

    async def list_all(self, limit: int = 100) -> list[CompanyRecord]:
        """列出所有公司."""
        ...
