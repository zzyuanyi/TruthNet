"""Equity 股权领域模型 — V12 baseline + Phase C (真实 Neo4j 契约).

Phase C 约定：
  - ownership_pct 对外统一为 0–100（百分数）。
  - 每条边绑定 Neo4j 稳定 relationship_id，作为证据定位的 source_record_id。
  - 股权路径（持股或控制关系，随 path_type 区分）携带 edge_ids，
    路径中的每条边可经 relationship_id 定位。
"""

from pydantic import BaseModel, Field


class EquityNode(BaseModel):
    """股权图谱节点."""

    id: str = Field(..., description="节点唯一标识")
    label: str = Field(..., description="节点显示名称")
    type: str = Field(
        ..., description="节点类型: company / person / entity / controller"
    )
    depth: int = Field(default=0, description="从目标公司起算的深度")
    entity_id: str = Field(default="", description="实体 ID（与 MySQL 对齐）")
    wind_code: str | None = Field(default=None, description="Wind 代码（适用时）")
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )
    mock: bool = Field(default=False, description="是否为 mock 数据")


class EquityEdge(BaseModel):
    """股权图谱边."""

    source: str = Field(..., description="起始节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation: str = Field(default="holds", description="关系类型")
    # 持股比例（0-1，兼容旧字段）
    stake_ratio: float | None = Field(
        None, ge=0.0, le=1.0, description="持股比例 (0-1)"
    )
    # 持股比例（0-100，Phase C 对外规范字段）
    ownership_pct: float | None = Field(None, description="持股比例 (%) 0-100")
    # 证据定位字段
    relationship_id: str | None = Field(default=None, description="Neo4j 关系稳定 ID")
    source_record_id: str | None = Field(default=None, description="来源记录 ID")
    report_period: str | None = Field(default=None, description="报告期")
    ann_dt: str | None = Field(default=None, description="公告日期")
    as_of: str | None = Field(default=None, description="时点")
    is_latest: bool = Field(default=True, description="是否最新快照")
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )
    mock: bool = Field(default=False, description="是否为 mock 数据")

    def effective_ownership_pct(self) -> float | None:
        """规范持股比例（0-100）.

        优先返回 ownership_pct；缺失时由 stake_ratio 推算，禁止重复乘 100。
        """
        if self.ownership_pct is not None:
            return self.ownership_pct
        if self.stake_ratio is not None:
            return round(self.stake_ratio * 100, 4)
        return None


class OwnershipChain(BaseModel):
    """股权路径（持股或控制关系，随 path_type 区分）."""

    path: list[str] = Field(..., description="路径节点 ID 序列")
    total_stake: float = Field(
        default=0.0, ge=0.0, le=1.0, description="累计持股 (0-1)"
    )
    depth: int = Field(default=0, description="链路深度")
    edge_ids: list[str] = Field(
        default_factory=list, description="路径边 relationship_id 序列"
    )
    final_control_pct: float | None = Field(
        default=None, description="最终控制比例 (%) 0-100"
    )
    # 8.09 四轮审查：默认 ownership（持股关系）——十大股东链路是持股路径，
    # 只有存在明确控制证据才标记 control，不得默认断言控制
    path_type: str = Field(
        default="ownership", description="路径类型: ownership/control"
    )
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )

    def effective_control_pct(self) -> float | None:
        """规范控制比例（0-100）."""
        if self.final_control_pct is not None:
            return self.final_control_pct
        return round(self.total_stake * 100, 4)


class EquityGraph(BaseModel):
    """股权图谱."""

    company_id: str = Field(..., description="目标公司 ID")
    nodes: list[EquityNode] = Field(default_factory=list)
    edges: list[EquityEdge] = Field(default_factory=list)
    control_chains: list[OwnershipChain] = Field(default_factory=list)
    graph_version: str | None = Field(default=None, description="图数据版本")
    dataset_version: str | None = Field(default=None, description="数据集版本")
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )
    # ── 多跳诚实覆盖说明（8.09 审查新增）──
    requested_depth: int = Field(
        default=0, description="请求穿透深度（hop_count 口径）"
    )
    max_observed_hops: int = Field(
        default=0, description="实际观测到的最大跳数（len(edge_ids) 口径）"
    )
    truncated: bool = Field(
        default=False, description="路径结果超过限制被截断（非精确全集）"
    )
    coverage_note: str = Field(
        default="",
        description="覆盖说明：严格 4 跳+ 为 0 时如实说明，不推断现实不存在",
    )
