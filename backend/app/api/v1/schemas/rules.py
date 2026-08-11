"""规则定义只读 Schema — D2（2026-08-11）.

只读返回规则展示元数据（名称/描述/指标/参数/判定说明）+ 实际阈值值。
展示元数据来自 financial_rules.yaml metadata 段（人工维护），
阈值来自同一 YAML 的 rules 段（运行时事实来源）。
"""

from pydantic import BaseModel, Field


class RuleMetricMetaDTO(BaseModel):
    """单指标展示元数据（与运行时 current 的 key 对应）。"""

    key: str = Field(..., description="指标 key（RuleResult.current 的键）")
    label: str = Field(..., description="中文标签")
    unit: str = Field(default="", description="单位")
    formula: str = Field(default="", description="计算公式说明")
    risk_direction: str = Field(default="neutral", description="风险方向")


class RuleParameterMetaDTO(BaseModel):
    """单阈值参数展示元数据。"""

    key: str = Field(..., description="阈值 key（YAML thresholds 的键）")
    unit: str = Field(default="", description="单位")
    description: str = Field(default="", description="说明")
    value: float | int | None = Field(
        default=None, description="实际阈值值（来自 YAML rules 段）"
    )


class RuleConditionsDTO(BaseModel):
    """各严重等级的判定说明（人工维护文本，非代码反推）。"""

    red: str = Field(default="", description="红色等级判定说明")
    orange: str = Field(default="", description="橙色等级判定说明")
    yellow: str = Field(default="", description="黄色等级判定说明")


class RuleDefinitionDTO(BaseModel):
    """单条规则完整定义（展示 + 阈值）。"""

    rule_id: str = Field(..., description="规则 ID（R1..R7）")
    name: str = Field(..., description="规则中文名称")
    description: str = Field(default="", description="规则描述")
    enabled: bool = Field(..., description="是否启用")
    thresholds: dict[str, float] = Field(default_factory=dict, description="实际阈值值")
    metrics: list[RuleMetricMetaDTO] = Field(default_factory=list)
    parameters: list[RuleParameterMetaDTO] = Field(default_factory=list)
    conditions: RuleConditionsDTO = Field(default_factory=RuleConditionsDTO)


class RulesDefinitionsData(BaseModel):
    """GET /api/v1/rules/definitions 响应数据."""

    version: str = Field(..., description="规则文件版本")
    execution_version: str = Field(
        default="1.0.0", description="规则执行版本（R1-R7 输出/Claim 统一来源，v3.5）"
    )
    rules: list[RuleDefinitionDTO] = Field(default_factory=list)
    evaluation_config_hash: str = Field(
        ..., description="仅覆盖 enabled+thresholds 的 hash（风险缓存失效键）"
    )
    definition_hash: str = Field(
        ..., description="覆盖完整展示元数据的 hash（规则页版本识别）"
    )
    source: str = Field(
        default="financial_rules.yaml", description="规则元数据来源文件"
    )
