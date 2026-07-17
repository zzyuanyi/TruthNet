"""FinanceRepository Port — V12 baseline.

定义财务数据访问接口，不依赖具体数据库。
"""

from typing import Protocol, runtime_checkable

from app.domain.finance.models import FinancialItem, FinanceWarning


@runtime_checkable
class FinanceRepository(Protocol):
    """财务数据仓库接口.

    lite: SQLiteAdapter
    full: MySQLAdapter
    """

    async def get_items(
        self,
        company_code: str,
        fiscal_year: int,
        report_type: str | None = None,
    ) -> list[FinancialItem]:
        """获取财务报表科目."""
        ...

    async def get_warnings(
        self, company_code: str, fiscal_year: int
    ) -> list[FinanceWarning]:
        """获取财务预警."""
        ...
