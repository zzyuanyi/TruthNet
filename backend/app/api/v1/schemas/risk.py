"""综合风险 REST Schema — V12 §11.12."""

from pydantic import BaseModel, Field


class SubScore(BaseModel):
    """分项贡献分."""
    dimension: str = Field(..., description="维度名: finance / equity / events / external")
    label: str = Field(default="", description="中文标签")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    weight: float = Field(default=0.25, ge=0.0, le=1.0)
    contribution: float = Field(default=0.0, description="加权后贡献")
    status: str = Field(default="unknown", description="模块状态: success / partial / failed / skipped")
    warning: str | None = Field(default=None)


class RiskTag(BaseModel):
    """风险标签."""
    tag: str = Field(..., description="标签名")
    category: str = Field(default="", description="来源类别")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PatternMatch(BaseModel):
    """造假模式匹配结果."""
    pattern_id: str = Field(..., description="模式 ID，如 P1")
    pattern_name: str = Field(..., description="模式中文名")
    triggered_rules: list[str] = Field(default_factory=list)
    confidence: str = Field(default="medium", description="high / medium / low")
    reasoning: str = Field(default="", description="匹配理由")


class MitigatingFactor(BaseModel):
    """缓解因素."""
    factor: str = Field(..., description="因素描述")
    category: str = Field(default="", description="类别")
    weight: float = Field(default=0.0, description="影响权重")


class DataCoverage(BaseModel):
    """数据覆盖."""
    finance: bool = Field(default=False)
    equity: bool = Field(default=False)
    events: bool = Field(default=False)
    benchmarks: bool = Field(default=False)
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_modules: list[str] = Field(default_factory=list)


class RiskEvidence(BaseModel):
    """风险证据引用."""
    evidence_id: str = Field(..., description="证据 ID")
    source_type: str = Field(default="", description="来源类型")
    claim_ids: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="证据摘要")


class RiskResponseData(BaseModel):
    """综合风险响应数据 — V12 §11.12."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    as_of: str | None = Field(default=None, description="数据截止日期")

    # 核心评分
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: str = Field(default="unknown", description="red / orange / yellow / green")
    sub_scores: list[SubScore] = Field(default_factory=list)

    # 风险标签与模式
    risk_tags: list[RiskTag] = Field(default_factory=list)
    pattern_matches: list[PatternMatch] = Field(default_factory=list)

    # 置信度与覆盖
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="综合置信度")
    data_coverage: DataCoverage = Field(default_factory=DataCoverage)

    # 缓解因素
    mitigating_factors: list[MitigatingFactor] = Field(default_factory=list)

    # 策略版本
    strategy_version: str = Field(default="1.0.0")
    rule_set_version: str = Field(default="finance-rules-1.0.0")

    # 证据
    evidence: list[RiskEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
