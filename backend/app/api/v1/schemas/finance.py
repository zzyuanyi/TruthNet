"""财务分析 REST Schema — V12 §11.10."""

from pydantic import BaseModel, Field

from app.api.v1.schemas.benchmarks import IndustryPercentile


class FinanceRuleItem(BaseModel):
    """单条规则结果 — 对齐 V12 RuleResult."""

    rule_id: str = Field(..., description="规则 ID (R1-R7)")
    rule_version: str = Field(default="1.0.0")
    rule_name: str = Field(default="", description="规则中文名")
    status: str = Field(
        default="not_triggered",
        description="triggered / not_triggered / not_applicable / insufficient_data",
    )
    severity: str = Field(
        default="green", description="red / orange / yellow / green / unknown"
    )
    current: dict[str, dict] = Field(
        default_factory=dict,
        description="当前指标值，如 {'应收账款同比': {'value': 35.2, 'unit': '%'}}",
    )
    history: list[dict] = Field(default_factory=list, description="历史序列，每期一条")
    industry: dict = Field(
        default_factory=dict,
        description="行业分位（旧结构，deprecated——请使用 industry_metrics）",
        deprecated=True,
    )
    industry_metrics: list[IndustryPercentile] = Field(
        default_factory=list,
        description="行业分位指标（typed：rule_id/metric_id/p50/p75/p95/company_percentile）",
    )
    quality: dict = Field(default_factory=dict, description="数据质量标记")
    explanation: str = Field(default="", description="LLM 解读文本")
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IndustryBenchmark(BaseModel):
    """行业对标 — V12 §11.10."""

    industry_l1: str = Field(default="", description="一级行业")
    peer_count: int = Field(default=0, description="同行业公司数")
    percentile: dict[str, float | None] = Field(
        default_factory=dict,
        description="各指标的分位值，如 {'R1_receivable_yoy': 75.0}",
    )
    warnings: list[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    """数据质量."""

    periods_available: int = Field(default=0, description="可用期数")
    periods_requested: int = Field(default=8, description="请求期数")
    statement_scope: str = Field(default="parent_company", description="报表口径")
    gaps: list[str] = Field(default_factory=list, description="数据缺失期间")
    warnings: list[str] = Field(default_factory=list)


class FinanceResponseData(BaseModel):
    """财务分析响应数据 — V12 §11.10."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    risk_level: str = Field(
        default="unknown", description="风险等级: red / orange / yellow / green"
    )
    rules: list[FinanceRuleItem] = Field(default_factory=list)
    industry_benchmark: IndustryBenchmark = Field(default_factory=IndustryBenchmark)
    data_quality: DataQuality = Field(default_factory=DataQuality)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
