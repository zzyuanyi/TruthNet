"""跨公司对比 REST Schema — V12 §11.14."""

from pydantic import BaseModel, Field


class ComparisonRequest(BaseModel):
    """跨公司对比请求体 — V12 §11.14."""

    company_codes: list[str] = Field(
        ..., min_length=2, max_length=5, description="对比公司代码列表"
    )
    period: str = Field(default="2026Q2", description="对比期间")
    indicators: list[str] = Field(
        default_factory=lambda: ["R1", "R2", "R3"],
        description="对比指标列表",
    )
    statement_scope: str = Field(
        default="parent_company", description="报表口径"
    )


class CompanyIndicator(BaseModel):
    """单公司单指标值."""
    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    value: float | None = Field(default=None)
    unit: str = Field(default="")
    severity: str = Field(default="green")
    status: str = Field(default="not_triggered")


class IndicatorCompare(BaseModel):
    """单指标跨公司对比."""
    indicator: str = Field(..., description="指标/规则 ID")
    label: str = Field(default="", description="中文标签")
    companies: list[CompanyIndicator] = Field(default_factory=list)


class CompanyRiskSummary(BaseModel):
    """公司风险摘要（对比用）."""
    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="")
    industry_l1: str = Field(default="")
    risk_level: str = Field(default="unknown")
    overall_score: float = Field(default=0.0)
    triggered_rules: list[str] = Field(default_factory=list)
    pattern_matches: list[str] = Field(default_factory=list)


class ComparisonsResponseData(BaseModel):
    """跨公司对比响应数据 — V12 §11.14."""

    period: str = Field(default="", description="对比期间")
    statement_scope: str = Field(default="parent_company")
    companies: list[CompanyRiskSummary] = Field(default_factory=list)
    indicators: list[IndicatorCompare] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
