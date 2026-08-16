"""股权链路创新闭环单元测试 — Phase D #12.

覆盖:
- equity_chains 载荷完整（chain_id/path_names/depth/final_control_pct/
  evidence_ids/risk_label/risk_level/risk_reasons/merge_explanation/source_system/as_of）
- risk_label → risk_level 单一映射
- 证据 ID 来自真实记录（非 mock/随机 UUID）
- 一致行动人合并保护：无可验证关系不擅自合并
- 无可合并关系 → 明确 warning
- 深度/比例集中的风险原因可解释
- Lite/NetworkX 路径 path_type 契约（REST 与 Chat 一致，wind code 规范化）
"""

import pytest

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
        # 8.09 四轮审查：path_type 必须透传（下游按此措辞）
        "path_type",
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
    assert d["path_type"] == "control"
    assert d["source_system"] == "neo4j"
    assert d["as_of"] == "2026-03-31"


def test_path_type_ownership_default_and_wording():
    """8.09 四轮审查：path_type 默认透传 ownership，比例集中措辞为
    "最终持股比例集中"（不得断言控制权集中）。"""
    from app.domain.equity.models import OwnershipChain

    default_chain = OwnershipChain(
        path=["e1", "e2", "e3"],
        total_stake=0.6,
        depth=2,
        edge_ids=["rel_1", "rel_2"],
        final_control_pct=60.0,
    )  # 无 path_type → 默认 ownership
    chains, _ = build_equity_chains(
        company_code="600518.SH",
        chains=[default_chain],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[],
        top_shareholder_records=[],
        source_system="neo4j",
    )
    d = chains[0].to_dict()
    assert d["path_type"] == "ownership"
    assert d["risk_label"] == "concentrated_control"  # 60% 仍触发风险标签
    assert any(
        "最终持股比例 60.0% 集中" in r for r in d["risk_reasons"]
    ), f"ownership 路径比例集中措辞应为'最终持股'，实际 {d['risk_reasons']}"

    control_chain = _chain(final_control_pct=60.0)  # path_type="control"
    chains2, _ = build_equity_chains(
        company_code="600518.SH",
        chains=[control_chain],
        node_name_map={"e1": "A", "e2": "B", "e3": "C"},
        graph_edges=[],
        top_shareholder_records=[],
        source_system="neo4j",
    )
    reasons2 = chains2[0].to_dict()["risk_reasons"]
    assert any(
        "最终控制比例 60.0% 集中" in r for r in reasons2
    ), f"control 路径保留'最终控制'措辞，实际 {reasons2}"


def test_networkx_lite_paths_are_ownership():
    """8.09 五轮审查：NetworkX/Lite 适配器路径 path_type=ownership——Lite
    内置图同样是持股路径语义，不得标记 control。"""
    from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph

    adapter = NetworkXEquityGraph()
    graph = adapter._get_graph_sync("600518", depth=3)
    assert graph.control_chains, "Lite 图应返回内置持股路径"
    assert all(
        c.path_type == "ownership" for c in graph.control_chains
    ), "Lite 路径必须全部为 ownership"


@pytest.mark.parametrize(
    "wind_code",
    ["600518", "600518.SH", "600518.XSHG"],
)
def test_networkx_lite_wind_code_normalized(wind_code):
    """8.09 七轮审查：NetworkX 边界必须规范化 Wind Code——裸码 / .SH /
    .XSHG 解析为同一内部键并返回相同两条路径（曾只认裸码导致真实
    Resolver 返回 600518.SH 时查空图，Lite 实际不可用）。"""
    from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph

    graph = NetworkXEquityGraph()._get_graph_sync(wind_code, depth=3)
    assert (
        len(graph.control_chains) == 2
    ), f"{wind_code} 应返回相同两条持股路径，实际 {len(graph.control_chains)} 条"
    assert all(
        c.path_type == "ownership" for c in graph.control_chains
    ), "Lite 路径必须全部为 ownership"
    first = graph.control_chains[0]
    assert (
        first.path[0] == "600518"
    ), f"路径必须以目标公司结尾/开头一致，实际 {first.path}"


def test_rest_and_chat_equity_path_types_consistent_lite(monkeypatch):
    """8.09 六轮/七轮审查：Lite profile 下 REST /equity（真实格式 wind_code）
    与 Chat（直接调 equity_node）两侧 path_type 全部 ownership 且数量一致。

    契约固化，防某一入口漏传；不再手工复制节点转换逻辑。
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "GRAPH_BACKEND", "networkx")
    # Resolver 返回真实格式（带后缀）——曾用裸码掩盖 Lite 缺陷
    from app.application.services.company_resolver import CompanyRecord

    class _FakeResolver:
        async def resolve(self, code):
            return CompanyRecord(
                entity_id="company_600518_SH",
                wind_code="600518.SH",
                sec_name="康美药业",
                exchange_code="XSHG",
            )

    monkeypatch.setattr("app.api.v1.routers.equity.CompanyResolver", _FakeResolver)

    # REST 侧：/equity → paths 与 equity_chains 的 path_type
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/companies/600518.SH/equity")
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()["data"]
        assert data["paths"], "Lite 应返回内置股权路径（真实格式 wind_code）"
        assert all(
            p["path_type"] == "ownership" for p in data["paths"]
        ), f"REST paths 必须全部 ownership: {[p['path_type'] for p in data['paths']]}"
        assert all(
            ch["path_type"] == "ownership" for ch in data["equity_chains"]
        ), "REST equity_chains 必须全部 ownership"

    # Chat 侧：直接调用 equity_node（不复制生产转换逻辑）
    from datetime import date

    from app.agents.nodes.equity import equity_node
    from app.agents.state import CompanyRef, ExecutionPlan, RuntimeState

    state = {
        "user_query": "康美药业股权结构",
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(
            intent="equity",
            requested_modules=["equity"],
            as_of=date(2026, 3, 31),
        ),
        "runtime": RuntimeState(
            trace_id="t_lite_test",
            session_id="s_lite_test",
            turn_id="t_lite_test",
        ),
    }
    out = equity_node(state)
    chain_details = out["results"].equity.chain_details or []
    assert chain_details, "Chat equity_node 应产出链路载荷"
    assert all(
        cd.get("path_type") == "ownership" for cd in chain_details
    ), f"Chat chain_details 必须全部 ownership: {chain_details}"
    assert len(chain_details) == len(
        data["equity_chains"]
    ), "REST 与 Chat 链路数量应一致"


def test_equity_path_dto_defaults_ownership():
    """8.09 六轮审查：EquityPathDTO 默认 path_type=ownership（OpenAPI/手工
    构造不默认断言控制）。"""
    from app.api.v1.schemas.equity import EquityPathDTO

    dto = EquityPathDTO()
    assert dto.path_type == "ownership"
    assert (
        "最终持股或控制比例"
        in EquityPathDTO.model_fields["final_control_pct"].description
    )


def test_deep_ownership_chain_wording_and_pdf_label_map():
    """8.09 六轮审查：深层 ownership 链原因措辞为"持股关系"；
    PDF 风险标签中文映射保留兼容键。"""
    from app.application.services.report_service import _RISK_LABEL_CN

    # 深层 ownership 链 → "持股关系难以穿透核实"
    from app.application.services.equity_chain_service import build_equity_chains
    from app.domain.equity.models import OwnershipChain

    deep = OwnershipChain(
        path=[f"e{i}" for i in range(9)],
        total_stake=0.1,
        depth=6,
        edge_ids=["rel_1"] * 6,
        final_control_pct=10.0,
        path_type="ownership",
    )
    chains, _ = build_equity_chains(
        company_code="600518.SH",
        chains=[deep],
        node_name_map={f"e{i}": f"节点{i}" for i in range(9)},
        graph_edges=[],
        top_shareholder_records=[],
        source_system="neo4j",
    )
    reasons = " ".join(chains[0].risk_reasons)
    assert "持股关系难以穿透核实" in reasons, f"深层 ownership 措辞，实际 {reasons}"
    assert "控制关系难以穿透核实" not in reasons

    # PDF 中文标签映射（保留内部英文键，渲染为中文）
    assert _RISK_LABEL_CN["concentrated_control"] == "持股比例集中"
    assert _RISK_LABEL_CN["deep_chain"] == "链路层级过深"
    assert _RISK_LABEL_CN["normal"] == "正常"


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
    # 2026-08-16 口径校准：集中持股降为 yellow（观察项，非独立中高危信号）
    assert map_risk_level("concentrated_control") == "yellow"
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
