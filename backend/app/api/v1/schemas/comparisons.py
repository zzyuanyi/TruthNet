"""跨公司对比 REST Schema — V12 §11.14."""

from typing import Any

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
    statement_scope: str = Field(default="parent_company", description="报表口径")


class CompanyIndicator(BaseModel):
    """单公司单指标值."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    value: float | None = Field(default=None)
    unit: str = Field(default="")
    period: str = Field(default="", description="该数值对应的报告期 YYYYMMDD")
    severity: str = Field(default="green")
    status: str = Field(default="not_triggered")


class IndicatorCompare(BaseModel):
    """单指标跨公司对比."""

    indicator: str = Field(..., description="指标/规则 ID")
    label: str = Field(default="", description="中文标签")
    companies: list[CompanyIndicator] = Field(default_factory=list)
    period: str = Field(default="", description="共同报告期 YYYYMMDD")
    difference: float | None = Field(default=None, description="两家公司差值 A-B")
    difference_unit: str = Field(default="", description="差值单位")


class RuleMetricValue(BaseModel):
    """单指标值（⑥：RuleResult.current 多指标字典展开，不做单一值压缩）."""

    key: str = Field(..., description="指标 key（current 字典键）")
    label: str = Field(default="", description="中文标签（D2 元数据）")
    value: Any = Field(default=None, description="指标值（数字/布尔/字符串/空）")
    unit: str = Field(default="", description="单位（current 或 D2 元数据）")
    risk_direction: str = Field(default="neutral", description="风险方向（D2 元数据）")


class TriggeredRuleDetail(BaseModel):
    """单条触发规则详情（⑥：值/方向/单位/证据规则级，兼容旧 triggered_rules）."""

    rule_id: str = Field(..., description="规则 ID（R1..R7）")
    label: str = Field(default="", description="规则中文名称（D2 元数据）")
    status: str = Field(default="not_triggered", description="规则状态")
    severity: str = Field(default="green", description="严重等级")
    as_of: str = Field(default="", description="分析期间 YYYYMMDD")
    metrics: list[RuleMetricValue] = Field(default_factory=list)
    evidence_ids: list[str] = Field(
        default_factory=list, description="规则级 evidence（已落库可回查）"
    )
    explanation: str = Field(default="", description="规则解释")


class CompanyRiskSummary(BaseModel):
    """公司风险摘要（对比用） — Phase C 任务 13 扩展 coverage/evidence."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="")
    industry_l1: str = Field(default="")
    risk_level: str = Field(default="unknown")
    overall_score: float = Field(default=0.0)
    triggered_rules: list[str] = Field(default_factory=list)
    triggered_rule_details: list[TriggeredRuleDetail] = Field(
        default_factory=list, description="触发规则详情（⑥，含指标值/方向/证据）"
    )
    pattern_matches: list[str] = Field(default_factory=list)
    coverage: float = Field(default=0.0, description="数据覆盖 (0-1)")
    evidence_ids: list[str] = Field(default_factory=list)
    partial: bool = Field(default=False, description="单家公司分析失败/部分")


class ComparisonsResponseData(BaseModel):
    """跨公司对比响应数据 — V12 §11.14 + Phase C 任务 13."""

    period: str = Field(default="", description="对比期间")
    statement_scope: str = Field(default="parent_company")
    companies: list[CompanyRiskSummary] = Field(default_factory=list)
    indicators: list[IndicatorCompare] = Field(default_factory=list)
    financial_indicators: list[IndicatorCompare] = Field(
        default_factory=list,
        description="标准财报科目对比：营业收入、净利润、现金流及资产负债等",
    )
    dataset_version: str = Field(default="")
    warnings: list[str] = Field(default_factory=list)
