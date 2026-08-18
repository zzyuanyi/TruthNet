"""Phase E 会2 — equity_insight_service 测试.

覆盖：
- 交叉持股（2 环/3 环）检测与解读、环去重（旋转等价）；
- 隐含持股链（depth≥2）解读与可回查 evidence；
- 无环/无链 → 空列表；空图 → 空列表；
- 措辞区分 path_type（持股 vs 控制）。
"""

from app.application.services.equity_insight_service import build_equity_insights
from app.domain.equity.models import (
    EquityEdge,
    EquityGraph,
    EquityNode,
    OwnershipChain,
)


def _node(nid: str, label: str) -> EquityNode:
    return EquityNode(id=nid, label=label, type="company")


def _edge(src: str, tgt: str, rid: str) -> EquityEdge:
    return EquityEdge(
        source=src,
        target=tgt,
        relation="holds",
        ownership_pct=30.0,
        relationship_id=rid,
        source_system="neo4j",
    )


def _chain(
    path: list[str], edge_ids: list[str], pct: float, path_type: str = "ownership"
) -> OwnershipChain:
    return OwnershipChain(
        path=path,
        total_stake=pct / 100.0,
        depth=len(edge_ids),
        edge_ids=edge_ids,
        final_control_pct=pct,
        path_type=path_type,
        source_system="neo4j",
    )


_EMAP = {
    "r1": "ev_eq_r1",
    "r2": "ev_eq_r2",
    "r3": "ev_eq_r3",
    "r4": "ev_eq_r4",
    "r5": "ev_eq_r5",
}


def _names() -> dict[str, str]:
    return {"A": "甲公司", "B": "乙公司", "C": "丙公司", "T": "目标公司", "X": "X公司"}


def test_cross_holding_two_cycle():
    """A→B→A 相互持股 → 交叉持股解读（可回查证据）。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("A", "甲公司"), _node("B", "乙公司")],
        edges=[_edge("A", "B", "r1"), _edge("B", "A", "r2")],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
    )
    cross = [i for i in insights if i.insight_type == "cross_holding"]
    assert len(cross) == 1
    ins = cross[0]
    assert "交叉持股" in ins.title
    assert "甲公司" in ins.detail and "乙公司" in ins.detail
    assert set(ins.evidence_ids) == {"ev_eq_r1", "ev_eq_r2"}
    assert ins.risk_level == "yellow"


def test_cross_holding_three_cycle():
    """A→B→C→A 环形持股 → 环形持股解读。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("A", "甲公司"), _node("B", "乙公司"), _node("C", "丙公司")],
        edges=[_edge("A", "B", "r1"), _edge("B", "C", "r2"), _edge("C", "A", "r3")],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
    )
    cross = [i for i in insights if i.insight_type == "cross_holding"]
    assert len(cross) == 1
    assert "环形持股" in cross[0].title
    assert len(cross[0].evidence_ids) == 3


def test_cycle_rotation_dedup():
    """环的旋转等价去重：A→B→A 与 B→A→B 只产出一条。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("A", "甲公司"), _node("B", "乙公司")],
        edges=[_edge("A", "B", "r1"), _edge("B", "A", "r2")],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
    )
    cross = [i for i in insights if i.insight_type == "cross_holding"]
    assert len(cross) == 1


def test_no_cycle_no_chain_returns_empty():
    """无环无链 → 空列表（不编造解读）。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("A", "甲公司"), _node("B", "乙公司")],
        edges=[_edge("A", "B", "r1")],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
    )
    assert insights == []


def test_empty_graph_returns_empty():
    assert (
        build_equity_insights(
            graph=None, node_name_map={}, edge_evidence_map={}, company_code="600000.SH"
        )
        == []
    )
    graph = EquityGraph(company_id="T", source_system="neo4j")
    assert (
        build_equity_insights(
            graph=graph,
            node_name_map={},
            edge_evidence_map={},
            company_code="600000.SH",
        )
        == []
    )


def test_implicit_chain_interpretation():
    """X→Y→T 间接持股链 → 解读说明中间层与穿透难度。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[
            _node("X", "X公司"),
            _node("Y", "Y公司"),
            _node("T", "目标公司"),
        ],
        edges=[_edge("X", "Y", "r1"), _edge("Y", "T", "r2")],
        control_chains=[
            _chain(["X", "Y", "T"], ["r1", "r2"], 20.0),
        ],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
        target_name="目标公司",
    )
    implicit = [i for i in insights if i.insight_type == "implicit_chain"]
    assert len(implicit) == 1
    ins = implicit[0]
    assert "间接持股" in ins.title
    assert "1 层中间实体" in ins.detail or "Y公司" in ins.detail
    assert set(ins.evidence_ids) == {"ev_eq_r1", "ev_eq_r2"}
    # 2 层链 → 正常（观察项）
    assert ins.risk_level == "green"


def test_implicit_deep_chain_yellow():
    """3 层以上隐含链 → 提醒级。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node(f"N{i}", f"主体{i}") for i in range(4)],
        edges=[
            _edge("N0", "N1", "r1"),
            _edge("N1", "N2", "r2"),
            _edge("N2", "N3", "r3"),
        ],
        control_chains=[_chain(["N0", "N1", "N2", "N3"], ["r1", "r2", "r3"], 15.0)],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map={},
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
        target_name="N3",
    )
    implicit = [i for i in insights if i.insight_type == "implicit_chain"]
    assert len(implicit) == 1
    assert implicit[0].risk_level == "yellow"


def test_implicit_control_wording():
    """path_type=control 时措辞为"控制"，ownership 为"持股"。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("X", "X公司"), _node("Y", "Y公司"), _node("T", "目标公司")],
        edges=[_edge("X", "Y", "r1"), _edge("Y", "T", "r2")],
        control_chains=[
            _chain(["X", "Y", "T"], ["r1", "r2"], 51.0, path_type="control"),
        ],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
        target_name="目标公司",
    )
    implicit = [i for i in insights if i.insight_type == "implicit_chain"]
    assert len(implicit) == 1
    assert "间接控制" in implicit[0].title


def test_direct_chain_not_implicit():
    """单跳直接持股（depth=1）不产出 implicit_chain。"""
    graph = EquityGraph(
        company_id="T",
        nodes=[_node("X", "X公司"), _node("T", "目标公司")],
        edges=[_edge("X", "T", "r1")],
        control_chains=[_chain(["X", "T"], ["r1"], 60.0)],
        source_system="neo4j",
    )
    insights = build_equity_insights(
        graph=graph,
        node_name_map=_names(),
        edge_evidence_map=_EMAP,
        company_code="600000.SH",
        target_name="目标公司",
    )
    implicit = [i for i in insights if i.insight_type == "implicit_chain"]
    assert implicit == []
