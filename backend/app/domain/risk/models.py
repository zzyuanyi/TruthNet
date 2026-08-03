"""Risk 风险领域模型 — V12 baseline."""

from pydantic import BaseModel, Field

from app.core.enums import RiskLevel


class RiskScore(BaseModel):
    """风险评分 — V12 增强版.

    从 Prompt4 的 4 维度扩展为 V12 的多维度结构。
    """

    overall: float = Field(default=0.0, ge=0.0, le=1.0, description="综合风险 0-1")
    financial: float = Field(default=0.0, ge=0.0, le=1.0, description="财务风险 0-1")
    ownership: float = Field(default=0.0, ge=0.0, le=1.0, description="股权风险 0-1")
    sentiment: float = Field(default=0.0, ge=0.0, le=1.0, description="舆情风险 0-1")
    level: RiskLevel = Field(default=RiskLevel.LOW, description="风险等级")


class RiskFactor(BaseModel):
    """风险因子."""

    category: str = Field(..., description="风险类别")
    level: RiskLevel = Field(default=RiskLevel.LOW, description="严重程度")
    detail: str = Field(..., description="详细描述")


class CompanyRiskProfile(BaseModel):
    """公司风险画像."""

    company_id: str = Field(..., description="公司 ID")
    company_name: str = Field(..., description="公司名称")
    risk_score: RiskScore = Field(default_factory=RiskScore)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    last_updated: str = Field(default="", description="最后更新时间 (ISO 8601)")


# ══════════════════════════════════════════════════════════
# Phase C 后端任务 6/11 — 统一风险评分结构
# ══════════════════════════════════════════════════════════


class RiskSubScore(BaseModel):
    """分项风险分."""

    dimension: str
    label: str
    score: float = 0.0
    weight: float = 0.0
    contribution: float = 0.0
    status: str = "skipped"  # success / partial / skipped / failed


class RiskDataCoverage(BaseModel):
    """数据覆盖."""

    finance: bool = False
    equity: bool = False
    events: bool = False
    benchmarks: bool = False
    coverage_ratio: float = 0.0
    missing_modules: list[str] = Field(default_factory=list)


class RiskEvidence(BaseModel):
    """风险证据."""

    evidence_id: str
    source_type: str
    summary: str
    claim_ids: list[str] = Field(default_factory=list)


class RiskPatternMatch(BaseModel):
    """造假模式匹配结果."""

    pattern_id: str
    pattern_name: str
    triggered_rules: list[str] = Field(default_factory=list)
    confidence: str = "low"
    reasoning: str = ""
    partial_coverage: bool = False


class RiskOutput(BaseModel):
    """统一风险评分输出（服务层 → Router/Agent 共用）."""

    wind_code: str
    sec_name: str = ""
    as_of: str = ""
    overall_score: float = 0.0
    risk_level: str = "unknown"  # red/orange/yellow/green/unknown
    sub_scores: list[RiskSubScore] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    contributions: dict[str, float] = Field(default_factory=dict)
    strategy_version: str = "1.0.0"
    rule_set_version: str = ""
    data_coverage: RiskDataCoverage = Field(default_factory=RiskDataCoverage)
    confidence: float = 0.0
    key_contributors: list[str] = Field(default_factory=list)
    mitigating_factors: list[str] = Field(default_factory=list)
    pattern_matches: list[RiskPatternMatch] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
