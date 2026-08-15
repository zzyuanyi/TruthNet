"""财务分析 REST Schema — V12 §11.10."""

from typing import Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas.benchmarks import IndustryPercentile


class SimilarCaseSource(BaseModel):
    """相似案例的底层报表行来源（可回查证据）。"""

    source_table: str
    row_id: int | None = None  # 数据库业务表主键 id
    source_record_id: str | None = None  # 原始记录 ID，可能为空且不保证唯一
    wind_code: str
    report_period: str
    report_statement_type: str = "408006000"
    period_role: Literal["current", "prior"] = "current"  # 当前期 / 去年同期
    fields: list[str] = Field(default_factory=list)


class SimilarCase(BaseModel):
    """一条相似指标案例。

    措辞约束：只表述「指标值相似」，绝不表述为「同类造假」。
    """

    company_code: str
    company_name: str
    industry: str
    period: str
    metric: dict  # 与 SIMILAR_CASES_SCHEMA.md §3 的 metric key 对齐
    distance: float
    statement_type: Literal["observed"] = "observed"  # 陈述性质，不是报表口径
    report_statement_type: str = "408006000"  # 母公司报表口径
    sources: list[SimilarCaseSource] = Field(default_factory=list)
    evidence_ids: list[str] = Field(
        default_factory=list
    )  # optional：canonical 算法生成或为空


class SimilarCasesResult(BaseModel):
    """相似指标案例检索结果。"""

    status: Literal["ok", "empty", "error", "not_supported"]
    reason: str = ""  # empty 时="暂无相似案例"；error 时=失败原因
    cases: list[SimilarCase] = Field(default_factory=list)


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
    similar_cases: SimilarCasesResult | None = None


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
