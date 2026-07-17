"""Equity 股权领域模型 — V12 baseline."""

from pydantic import BaseModel, Field


class EquityNode(BaseModel):
    """股权图谱节点."""

    id: str = Field(..., description="节点唯一标识")
    label: str = Field(..., description="节点显示名称")
    type: str = Field(
        ..., description="节点类型: company / person / entity / controller"
    )
    depth: int = Field(default=0, description="从目标公司起算的深度")


class EquityEdge(BaseModel):
    """股权图谱边."""

    source: str = Field(..., description="起始节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation: str = Field(default="holds", description="关系类型")
    stake_ratio: float | None = Field(None, ge=0.0, le=1.0, description="持股比例")


class OwnershipChain(BaseModel):
    """控制链."""

    path: list[str] = Field(..., description="路径节点 ID 序列")
    total_stake: float = Field(default=0.0, ge=0.0, le=1.0, description="累计持股")
    depth: int = Field(default=0, description="链路深度")


class EquityGraph(BaseModel):
    """股权图谱."""

    company_id: str = Field(..., description="目标公司 ID")
    nodes: list[EquityNode] = Field(default_factory=list)
    edges: list[EquityEdge] = Field(default_factory=list)
    control_chains: list[OwnershipChain] = Field(default_factory=list)
