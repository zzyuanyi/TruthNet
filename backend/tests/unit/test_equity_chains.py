"""股权链路创新闭环单元测试 — Phase D #12.

覆盖:
- equity_chains 载荷完整（chain_id/path_names/depth/final_control_pct/
  evidence_ids/risk_label/risk_level/risk_reasons/merge_explanation/source_system/as_of）
- risk_label → risk_level 单一映射
- 证据 ID 来自真实记录（非 mock/随机 UUID）
- 一致行动人合并保护：无可验证关系不擅自合并
- 无可合并关系 → 明确 warning
- 深度/比例集中的风险原因可解释
"""

from app.application.services.equity_chain_service import (
    build_equity_chains,
    map_risk_level,
)
from app.domain.equity.models import EquityEdge, OwnershipChain


def _chain(**kw):
    defaults = dict(
        path=["e1", "e2", "e3"],
        total_stake=0.5,
        depth=2,
        edge_ids=["rel_1", "rel_2"],
        final_control_pct=25.0,
        path_type="control",
        source_system="neo4j",
    )
    defaults.update(kw)
    return OwnershipChain(**defaults)


def _edge(**kw):
    defaults = dict(
        source="e1",
        target="e2",
        relation="OWNS",
        ownership_pct=50.0,
        relationship_id="rel_1",
        source_record_id="src_1",
        source_system="neo4j",
    )
    defaults.update(kw)
    return EquityEdge(**defaults)


def test_chain_load_has_all_fields():
    """equity_chains 载荷字段完整且可序列化。"""
    chains, warnings = build_equity_chains(
        company_code="600518.SH",
        chains=[_chain()],
        node_name_map={"e1": "股东甲", "e2": "中间公司", "e3": "康美药业"},
        graph_edges=[_edge()],
        top_shareholder_records=[],
        as_of="2026-03-31",
        source_system="neo4j",
    )
    assert len(chains) == 1
    d = chains[0].to_dict()
    for field in (
        "chain_id",
        "node_ids",
        "path_names",
        "edge_ids",
        "depth",
        "final_control_pct",
        "evidence_ids",
        "risk_label",
        "risk_level",
        "risk_reasons",
        "merge_explanation",
        "source_system",
        "as_of",
    ):
        assert field in d, f"缺少字段 {field}"
    assert d["path_names"] == ["股东甲", "中间公司", "康美药业"]
    assert d["depth"] == 2
    assert d["final_control_pct"] == 25.0
    assert d["source_system"] == "neo4j"
    assert d["as_of"] == "2026-03-31"


def test_evidence_ids_canonical_via_map():
    """edge_evidence_map 将 relationship_id 转 canonical ev_eq_*（可回查）。

    裸 relationship_id / source_record_id 不得出现在 evidence_ids。
    """
    chains, _ = build_equity_chains(
        company_code="600518.SH",
        chains=[_chain(edge_ids=["rel_abc123", "rel_def456"])],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[
            _edge(relationship_id="rel_abc123"),
            _edge(relationship_id="rel_def456", source="e2", target="e3"),
        ],
        top_shareholder_records=[
            {"holder_name": "A", "pct": 25.0, "source_record_id": "src_share_001"}
        ],
        edge_evidence_map={
            "rel_abc123": "ev_eq_abc123",
            "rel_def456": "ev_eq_def456",
        },
    )
    ev = chains[0].evidence_ids
    assert ev == ["ev_eq_abc123", "ev_eq_def456"], f"应全部 canonical，实际 {ev}"
    # 裸 source_record_id 不得作为证据 ID 回传（仅用于比例比对）
    assert "src_share_001" not in ev
    assert not any("mock" in e or "ev_eq_01" == e for e in ev)


def test_evidence_ids_unmapped_dropped_with_warning():
    """无法映射为 canonical 的边从 evidence_ids 丢弃，并输出 warning。"""
    chains, warnings = build_equity_chains(
        company_code="600518.SH",
        chains=[_chain(edge_ids=["rel_orphan"])],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[],
        top_shareholder_records=[],
        edge_evidence_map={},
    )
    assert chains[0].evidence_ids == [], "无法映射的边不得进入 evidence_ids"
    assert any("无法映射" in w for w in warnings), "应有无法映射 warning"


def test_risk_label_mapping_single_source():
    """risk_label → risk_level 单一映射函数。"""
    assert map_risk_level("deep_chain") == "yellow"
    assert map_risk_level("concentrated_control") == "orange"
    assert map_risk_level("multi_layer_entity") == "yellow"
    assert map_risk_level("insufficient_source") == "yellow"
    assert map_risk_level("ownership_mismatch") == "orange"
    assert map_risk_level("concerted_action") == "orange"
    assert map_risk_level("normal") == "green"
    assert map_risk_level(None) == "green"


def test_risk_reasons_explainable():
    """风险原因可解释（层级/比例/中间实体/来源覆盖）。"""
    chains, _ = build_equity_chains(
        company_code="600518.SH",
        chains=[
            _chain(depth=6, final_control_pct=60.0, path=["e%d" % i for i in range(9)])
        ],
        node_name_map={f"e{i}": f"节点{i}" for i in range(9)},
        graph_edges=[],
        top_shareholder_records=[],
    )
    c = chains[0]
    reasons = " ".join(c.risk_reasons)
    assert "层级过深" in reasons or "depth" in reasons
    assert "控制比例" in reasons


def test_no_concerted_merge_without_evidence():
    """无一致行动关系：不擅自合并，输出明确 warning。"""
    chains, warnings = build_equity_chains(
        company_code="600518.SH",
        chains=[_chain()],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[],
        top_shareholder_records=[],
        merge_groups=[],
    )
    assert chains[0].merge_explanation == ""
    assert any("一致行动" in w for w in warnings), "应有缺少一致行动关系的 warning"


def test_merge_groups_applied():
    """有可回查 merge group → 合并说明 + merged_entity_ids。"""
    chains, warnings = build_equity_chains(
        company_code="600518.SH",
        chains=[_chain()],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[],
        top_shareholder_records=[],
        merge_groups=[
            {
                "entity_id": "e1",
                "merge_key": "concerted:group_x",
                "merge_basis": "图中一致行动关系标记",
            }
        ],
    )
    assert "合并" in chains[0].merge_explanation
    assert "e1" in chains[0].merged_entity_ids
    assert chains[0].merge_key == "concerted:group_x"


def test_empty_chains_ok():
    """无控制链 → 空 equity_chains + 无一致行动 warning。"""
    chains, warnings = build_equity_chains(
        company_code="600518.SH",
        chains=[],
        node_name_map={},
        graph_edges=[],
        top_shareholder_records=[],
    )
    assert chains == []
    assert any("一致行动" in w for w in warnings)
