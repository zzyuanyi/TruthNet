"""股权穿透 REST Schema — V12 §11."""

from pydantic import BaseModel, Field


class EquityNodeDTO(BaseModel):
    """股权图谱节点."""

    id: str = Field(..., description="节点唯一标识")
    entity_id: str = Field(default="", description="实体 ID")
    name: str = Field(..., description="节点显示名称")
    entity_type: str = Field(default="entity", description="实体类型")
    wind_code: str | None = Field(default=None, description="Wind 代码")
    match_confidence: float | None = Field(default=None, description="匹配置信度")
    risk_level: str | None = Field(default=None, description="风险等级")
    mock: bool = Field(default=False, description="是否为 mock 数据")


class EquityEdgeDTO(BaseModel):
    """股权图谱边."""

    id: str = Field(default="", description="边标识")
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation_type: str = Field(default="OWNS", description="关系类型")
    ownership_pct: float | None = Field(default=None, description="持股比例 (%)")
    control_pct: float | None = Field(default=None, description="控制权比例 (%)")
    valid_from: str | None = Field(default=None, description="有效期起")
    valid_to: str | None = Field(default=None, description="有效期止")
    source_id: str | None = Field(default=None, description="数据来源")
    match_confidence: float | None = Field(default=None, description="匹配置信度")


class EquityPathDTO(BaseModel):
    """控制链路径."""

    path_id: str = Field(default="", description="路径 ID")
    node_ids: list[str] = Field(default_factory=list, description="路径节点 ID 序列")
    edge_ids: list[str] = Field(default_factory=list, description="路径边 ID 序列")
    depth: int = Field(default=0, description="路径深度")
    final_control_pct: float | None = Field(
        default=None, description="最终控制比例 (0-1)"
    )
    path_type: str = Field(default="control", description="路径类型")


class TargetCompanyDTO(BaseModel):
    """目标公司."""

    entity_id: str = Field(default="", description="实体 ID")
    wind_code: str = Field(default="", description="Wind 代码")
    name: str = Field(default="", description="公司名称")


class EquityResponseData(BaseModel):
    """股权穿透响应数据."""

    target: TargetCompanyDTO = Field(default_factory=TargetCompanyDTO)
    nodes: list[EquityNodeDTO] = Field(default_factory=list)
    edges: list[EquityEdgeDTO] = Field(default_factory=list)
    paths: list[EquityPathDTO] = Field(default_factory=list)
    as_of: str | None = Field(default=None, description="数据截止日期")
    graph_version: str = Field(default="", description="图数据版本")
    partial: bool = Field(default=False, description="是否为部分结果")
    warnings: list[str] = Field(default_factory=list)
