"""综合风险 REST Schema — V12 §11.12."""

from pydantic import BaseModel, Field


class SubScore(BaseModel):
    """分项贡献分."""

    dimension: str = Field(
        ..., description="维度名: finance / equity / events / external"
    )
    label: str = Field(default="", description="中文标签")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    weight: float = Field(default=0.25, ge=0.0, le=1.0)
    contribution: float = Field(default=0.0, description="加权后贡献")
    status: str = Field(
        default="unknown", description="模块状态: success / partial / failed / skipped"
    )
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
    # Phase D #16 模式三要素（监管提示固定存在，不可被折叠/润色删除）
    phase: str = Field(default="", description="风险模式当前表现阶段（受控字符串）")
    alternative_explanation: str = Field(
        default="", description="该信号可能存在的非舞弊解释"
    )
    regulatory_hint: str = Field(
        default="", description="监管核查提示（非法律定罪结论）"
    )


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
    # 8/23 联网线索标注（见 domain/risk/models.py RiskEvidence）
    source_uri: str | None = Field(default=None, description="来源 URL（联网线索）")
    is_web: bool = Field(
        default=False, description="是否为联网搜索线索（非本地库证据）"
    )


class DerivationDataRef(BaseModel):
    evidence_id: str = Field(default="")
    source_type: str = Field(default="")
    field_path: str = Field(default="")
    period: str = Field(default="")
    value: str | None = Field(default=None)
    unit: str | None = Field(default=None)


class DerivationSignal(BaseModel):
    signal_id: str
    signal_type: str
    label: str
    severity: str = Field(default="unknown")
    explanation: str = Field(default="")
    current: dict = Field(default_factory=dict)
    industry_percentile: float | None = Field(default=None)
    data_refs: list[DerivationDataRef] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class DerivationChain(BaseModel):
    conclusion_id: str
    conclusion_type: str
    conclusion: str
    risk_level: str = Field(default="unknown")
    signals: list[DerivationSignal] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class RiskResponseData(BaseModel):
    """综合风险响应数据 — V12 §11.12."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    as_of: str | None = Field(default=None, description="数据截止日期")

    # 核心评分
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: str = Field(
        default="unknown", description="red / orange / yellow / green"
    )
    sub_scores: list[SubScore] = Field(default_factory=list)

    # 风险标签与模式
    risk_tags: list[RiskTag] = Field(default_factory=list)
    pattern_matches: list[PatternMatch] = Field(default_factory=list)
    derivation_chains: list[DerivationChain] = Field(default_factory=list)

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


class FraudConclusionData(BaseModel):
    """反欺诈结论（LLM 措辞层，数字由后端锁定，禁止 LLM 改数）。"""

    wind_code: str
    sec_name: str
    risk_level: str
    overall_score: float
    as_of: str | None = Field(default=None)
    conclusion: str = Field(default="", description="2-4 句人话结论")
    method: str = Field(default="template", description="llm | template")
    patterns: list[str] = Field(default_factory=list, description="命中的造假模式名")
    evidence_count: int = Field(default=0, description="可溯源证据条数")


class ImpactAdviceSegmentData(BaseModel):
    """Phase E 会3：分模块影响/建议段落（可溯源）。"""

    source_module: str = Field(
        default="", description="finance | equity | events | overall"
    )
    title: str = Field(default="", description="段落标题")
    detail: str = Field(default="", description="建议/结论（有数据依据）")
    evidence_ids: list[str] = Field(default_factory=list, description="可回查证据 ID")


class ImpactAdviceData(BaseModel):
    """Phase E 会3：影响与建议聚合（画像页影响建议模块数据源）。"""

    wind_code: str = Field(default="")
    sec_name: str = Field(default="")
    risk_level: str = Field(default="unknown")
    overall_score: float | None = Field(default=None)
    as_of: str = Field(default="")
    overall_advice: str = Field(default="", description="整体建议（LLM 或模板）")
    method: str = Field(default="template", description="llm | template")
    segments: list[ImpactAdviceSegmentData] = Field(default_factory=list)
    evidence_count: int = Field(default=0)
    warnings: list[str] = Field(default_factory=list)
