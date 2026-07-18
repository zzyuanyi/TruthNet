"""Finance 领域模型 — V12 baseline.

财务报表数据模型。本轮只建骨架，不实现完整财务规则。
"""

from pydantic import BaseModel, Field


class FinancialItem(BaseModel):
    """财务报表科目."""

    item_name: str = Field(..., description="科目名称，如'营业收入'")
    item_value: float | None = Field(None, description="金额（亿元）")
    unit: str = Field(default="亿元", description="单位")
    report_type: str = Field(
        ..., description="报表类型: balance_sheet / income / cash_flow"
    )
    fiscal_year: int = Field(..., description="财年")
    fiscal_period: str = Field(default="FY", description="期间: Q1/Q2/Q3/Q4/FY")


class FinanceWarning(BaseModel):
    """财务预警项."""

    category: str = Field(..., description="预警类别，如'营收勾稽'")
    level: str = Field(default="low", description="严重程度: low/medium/high/critical")
    detail: str = Field(..., description="预警详情")
    related_items: list[str] = Field(default_factory=list, description="相关科目")
