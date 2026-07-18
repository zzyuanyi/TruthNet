"""SQLite FinanceRepository Adapter — lite profile.

实现 FinanceRepository Port 协议。
Mock 实现，后续接入真实 SQLite。
"""

from app.domain.finance.models import FinancialItem, FinanceWarning


class SQLiteFinanceRepository:
    """SQLite 财务仓库 — lite profile (mock)."""

    async def get_items(
        self,
        company_code: str,
        fiscal_year: int,
        report_type: str | None = None,
    ) -> list[FinancialItem]:
        """获取财务报表科目 (mock)."""
        return [
            FinancialItem(
                item_name="营业收入",
                item_value=1505.60,
                report_type="income",
                fiscal_year=fiscal_year,
            ),
            FinancialItem(
                item_name="销售商品收到的现金",
                item_value=1652.35,
                report_type="cash_flow",
                fiscal_year=fiscal_year,
            ),
        ]

    async def get_warnings(
        self, company_code: str, fiscal_year: int
    ) -> list[FinanceWarning]:
        """获取财务预警 (mock)."""
        return [
            FinanceWarning(
                category="营收勾稽",
                level="low",
                detail="营收与现金流入匹配良好",
            ),
        ]
