"""Finance 领域模型 — V12 baseline + Phase C 规则引擎."""

from typing import Literal

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


# ── Phase C 规则引擎模型 ──────────────────────────────────────


class CurrentMetric(BaseModel):
    """规则当前指标值."""

    value: float | None = None
    unit: str = ""


class RuleResult(BaseModel):
    """单条规则计算结果 — 对齐 V12 §8.2 输出格式."""

    rule_id: str  # "R1" ~ "R7"
    rule_version: str = "1.0.0"
    rule_name: str = ""
    status: Literal[
        "triggered", "not_triggered", "not_applicable", "insufficient_data"
    ] = "not_triggered"
    severity: Literal[
        "red", "orange", "yellow", "green", "unknown"
    ] = "green"

    current: dict[str, dict] = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    industry: dict = Field(default_factory=dict)
    quality: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    warnings: list[str] = Field(default_factory=list)
