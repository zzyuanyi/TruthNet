"""股权穿透 REST Schema — V12 §11 + Phase C 真实图谱契约."""

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
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )


class EquityEdgeDTO(BaseModel):
    """股权图谱边."""

    id: str = Field(default="", description="边标识（relationship_id）")
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation_type: str = Field(default="OWNS", description="关系类型")
    ownership_pct: float | None = Field(default=None, description="持股比例 (%) 0-100")
    control_pct: float | None = Field(default=None, description="控制权比例 (%)")
    valid_from: str | None = Field(default=None, description="有效期起")
    valid_to: str | None = Field(default=None, description="有效期止")
    source_id: str | None = Field(default=None, description="数据来源")
    match_confidence: float | None = Field(default=None, description="匹配置信度")
    # Phase C: 证据定位字段
    relationship_id: str | None = Field(default=None, description="Neo4j 关系稳定 ID")
    source_record_id: str | None = Field(default=None, description="来源记录 ID")
    report_period: str | None = Field(default=None, description="报告期")
    ann_dt: str | None = Field(default=None, description="公告日期")
    is_latest: bool = Field(default=True, description="是否最新快照")
    mock: bool = Field(default=False, description="是否为 mock 数据")
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )


class EquityPathDTO(BaseModel):
    """股权路径（持股或控制关系，随 path_type 区分）."""

    path_id: str = Field(default="", description="路径 ID")
    node_ids: list[str] = Field(default_factory=list, description="路径节点 ID 序列")
    edge_ids: list[str] = Field(
        default_factory=list, description="路径边 relationship_id 序列"
    )
    depth: int = Field(default=0, description="路径深度")
    final_control_pct: float | None = Field(
        default=None, description="最终持股或控制比例 (%) 0-100"
    )
    # 8.09 五轮审查：默认 ownership（持股关系）；control 仅在存在明确
    # 控制证据时使用——手工构造/OpenAPI 消费不再默认断言控制
    path_type: str = Field(
        default="ownership", description="路径类型: ownership/control"
    )
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )


class TargetCompanyDTO(BaseModel):
    """目标公司（来自 MySQL 真实画像）."""

    entity_id: str = Field(default="", description="实体 ID")
    wind_code: str = Field(default="", description="Wind 代码")
    name: str = Field(default="", description="公司名称")


class EquityChainDTO(BaseModel):
    """正式股权链路载荷 — Phase D #12.

    每条链含 chain_id/path_names/depth/final_control_pct/evidence_ids/
    risk_label/risk_level/risk_reasons/merge_explanation/source_system/as_of。
    原 V12 `paths` 保留兼容，新增 `equity_chains` 字段供前端链路卡消费。
    """

    chain_id: str = Field(default="", description="链路 ID")
    node_ids: list[str] = Field(default_factory=list, description="节点 ID 序列")
    path_names: list[str] = Field(default_factory=list, description="节点名称序列")
    edge_ids: list[str] = Field(
        default_factory=list, description="边 relationship_id 序列"
    )
    depth: int = Field(default=0, description="链路深度")
    final_control_pct: float | None = Field(
        default=None, description="最终控制比例 (%)"
    )
    # 8.09 四轮审查：链路类型——ownership（持股关系，默认）/ control（有
    # 明确控制证据）；下游按此措辞，不得一律称"控制"
    path_type: str = Field(
        default="ownership", description="链路类型: ownership/control"
    )
    evidence_ids: list[str] = Field(
        default_factory=list, description="真实证据 ID（可回查）"
    )
    risk_label: str = Field(default="normal", description="风险标签（规范映射键）")
    risk_level: str = Field(
        default="green", description="风险等级 red/orange/yellow/green"
    )
    risk_reasons: list[str] = Field(default_factory=list, description="可解释风险原因")
    merge_explanation: str = Field(default="", description="一致行动人合并说明")
    merged_entity_ids: list[str] = Field(
        default_factory=list, description="合并实体 ID"
    )
    merge_key: str = Field(default="", description="合并依据键")
    merge_basis: str = Field(default="", description="合并依据说明")
    source_system: str = Field(default="unknown", description="数据来源")
    as_of: str = Field(default="", description="数据截止日期")


class EquityInsightDTO(BaseModel):
    """Phase E 会2：隐含关系解读（交叉持股/隐含持股链）。

    每条含结构化检测结果 + 可回查证据；画像页/对话直接渲染 detail。
    """

    insight_id: str = Field(default="", description="洞察 ID")
    insight_type: str = Field(default="", description="cross_holding | implicit_chain")
    title: str = Field(default="", description="标题")
    detail: str = Field(default="", description="解读文案（有数据依据）")
    entity_ids: list[str] = Field(default_factory=list, description="涉及节点 ID")
    entity_names: list[str] = Field(default_factory=list, description="涉及节点名称")
    path: list[str] = Field(default_factory=list, description="节点路径（名称）")
    edge_ids: list[str] = Field(default_factory=list, description="边 relationship_id")
    evidence_ids: list[str] = Field(
        default_factory=list, description="可回查 canonical 证据 ID"
    )
    risk_level: str = Field(default="green", description="风险等级")


class DownstreamRiskSignalDTO(BaseModel):
    """8/23 会1 深化：下游主体风险信号（负面公告/负面事件簇）。

    有信号才填充；信号来源为负面公告库（announcements sentiment=
    negative）与负面事件簇（event_clusters sentiment=negative）。
    """

    kind: str = Field(default="", description="信号类型: announcement/event_cluster")
    title: str = Field(default="", description="信号标题（公告标题/事件主题）")
    date: str = Field(default="", description="信号日期（公告日/事件起始日）")
    evidence_id: str = Field(default="", description="可回查证据 ID（空=无）")


class DownstreamRelationDTO(BaseModel):
    """8/23 会1 深化：下游（子公司/被投资企业）直接持股关系."""

    entity_id: str = Field(default="", description="被投资方实体 ID")
    wind_code: str = Field(default="", description="被投资方证券代码（如为上市公司）")
    sec_name: str = Field(default="", description="被投资方名称")
    ownership_pct: float | None = Field(default=None, description="直接持股比例 (%)")
    relation: str = Field(default="OWNS", description="关系类型")
    # 8/23 上下游风险信号：上市公司子公司有负面记录 → red；无 → green；
    # 非上市公司（无 wind_code）→ unknown（公开数据未覆盖）
    risk_level: str = Field(default="unknown", description="风险等级 red/green/unknown")
    risk_signals: list[DownstreamRiskSignalDTO] = Field(
        default_factory=list, description="负面风险信号列表（最多 3 条）"
    )


class EquityResponseData(BaseModel):
    """股权穿透响应数据."""

    target: TargetCompanyDTO = Field(default_factory=TargetCompanyDTO)
    nodes: list[EquityNodeDTO] = Field(default_factory=list)
    edges: list[EquityEdgeDTO] = Field(default_factory=list)
    paths: list[EquityPathDTO] = Field(default_factory=list)
    # Phase D #12: 正式链路载荷（含风险标签/证据/合并说明）
    equity_chains: list[EquityChainDTO] = Field(default_factory=list)
    # Phase E 会2: 隐含关系解读（交叉持股/隐含持股链）
    equity_insights: list[EquityInsightDTO] = Field(default_factory=list)
    as_of: str | None = Field(default=None, description="数据截止日期")
    graph_version: str = Field(default="", description="图数据版本")
    source_system: str = Field(
        default="unknown", description="数据来源: neo4j/networkx"
    )
    partial: bool = Field(default=False, description="是否为部分结果")
    warnings: list[str] = Field(default_factory=list)
    # ── 多跳诚实覆盖说明（8.09 审查新增）──
    requested_depth: int = Field(
        default=0, description="请求穿透深度（hop_count 口径）"
    )
    max_observed_hops: int = Field(
        default=0, description="实际观测最大跳数（len(edge_ids) 口径）"
    )
    truncated: bool = Field(
        default=False, description="路径结果超过限制被截断（非精确全集）"
    )
    coverage_note: str = Field(
        default="",
        description="覆盖说明：严格 4 跳+ 为 0 时如实说明，不推断不存在更深关系",
    )
    # 8/23 会1 深化：下游（子公司/被投资企业）——独立字段（不混入穿透图）
    downstream_relations: list[DownstreamRelationDTO] = Field(
        default_factory=list, description="下游直接持股关系（截断展示前 50 条）"
    )
    downstream_total: int = Field(default=0, description="下游总数（截断前真实数量）")
