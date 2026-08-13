"""Neo4j 股权图：graph_version 过滤 + as_of 快照分支 + 多跳统计（8.09 审查）。

快照过滤在 Cypher 查询阶段完成（is_latest 快路径 / 历史时点整体快照 map），
本文件用 mock driver 验证：
  - 查询分支选择（is_latest vs 目标公司快照期 map）
  - as_of 规范化与非法期次拒绝
  - 深度统一（OwnershipChain.depth == len(edge_ids)）
  - count_multi_hop_paths 的 min_depth/max_depth 语义、节点序列去重、
    封顶 truncated
快照过滤的实际行为由真库集成测试 test_equity_asof_snapshot.py 覆盖。
"""

import asyncio

import pytest

from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph


class _Driver:
    def __init__(self, records=None):
        self.records = [] if records is None else records
        self.calls = []

    def execute_query(self, query, params):
        self.calls.append((query, params))
        return self.records, None, None


def _adapter(driver):
    adapter = Neo4jEquityGraph.__new__(Neo4jEquityGraph)
    adapter._available = True
    adapter._driver = driver
    return adapter


def test_get_graph_filters_and_reports_requested_version(monkeypatch):
    driver = _Driver()
    adapter = _adapter(driver)
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")

    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")

    query, params = driver.calls[0]
    assert "rel.graph_version = $graph_version" in query
    assert params["graph_version"] == "equity-2026Q2"
    assert graph.graph_version == "equity-2026Q2"


def test_async_get_graph_forwards_version(monkeypatch):
    adapter = _adapter(_Driver())
    captured = {}

    def fake_sync(company_code, **kwargs):
        captured.update(kwargs)
        from app.domain.equity.models import EquityGraph

        return EquityGraph(company_id=company_code)

    monkeypatch.setattr(adapter, "_get_graph_sync", fake_sync)
    asyncio.run(adapter.get_graph("600518.SH", graph_version="equity-2026Q2"))
    assert captured["graph_version"] == "equity-2026Q2"


# ── 8.09 审查：as_of 快照分支（整体快照语义，过滤在 Cypher 层） ──


class _FakeRel:
    """模拟 Neo4j 关系：同 (source, target, type) 不同报告期 = 不同快照边。"""

    type = "OWNS"

    def __init__(self, rel_id, src, tgt, period):
        self.start_node = {"entity_id": src}
        self.end_node = {"entity_id": tgt}
        self._props = {
            "relationship_id": rel_id,
            "ownership_pct": "10.000000",
            "report_period": period,
            "is_latest": True,
            "mock": False,
        }

    def get(self, key, default=None):
        return self._props.get(key, default)


class _FakePath:
    """模拟 Neo4j path（8.09 三轮审查：nodes 从 target 开始）。

    真实语义（upstream 查询 (target)<-[:OWNS]-(o1)<-[:OWNS]-(o2)...）：
      path.nodes = [target, o1, o2, ...]
      path.relationships[i].start_node = nodes[i+1]（股东），
      path.relationships[i].end_node = nodes[i]（被持股公司）。
    """

    def __init__(self, rels):
        self._rels = rels
        self.nodes = (
            [rels[0].end_node] + [rel.start_node for rel in rels] if rels else []
        )

    @property
    def relationships(self):
        return self._rels


def _records_for_asof() -> list[dict]:
    """单条路径（一条边）的 mock 返回结构。"""
    rel = _FakeRel("rel_2025", "S", "T", "20251231")
    return [{"target": {"entity_id": "T"}, "path": _FakePath([rel])}]


def _asof_adapter(monkeypatch, latest_snapshot: str, snapshot_map: dict):
    """构造 as_of 分支 mock：latest_snapshot + 快照 map 都 monkeypatch。"""
    adapter = _adapter(_Driver(_records_for_asof()))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    monkeypatch.setattr(adapter, "_latest_snapshot_period", lambda gv: latest_snapshot)
    monkeypatch.setattr(adapter, "_snapshot_periods", lambda gv, asof: snapshot_map)
    return adapter


def test_asof_historical_uses_target_snapshot_map(monkeypatch):
    """as_of < 全图最新快照期 → 历史时点分支：按目标公司快照期 map 过滤。"""
    adapter = _asof_adapter(
        monkeypatch, latest_snapshot="20260331", snapshot_map={"company_T": "20251231"}
    )

    adapter._get_graph_sync(
        "600518.SH", depth=3, as_of="20251231", graph_version="equity-2026Q2"
    )
    query, params = adapter._driver.calls[-1]
    assert (
        "rel.report_period = $latest_periods[endNode(rel).entity_id]" in query
    ), "历史时点必须按目标公司整体快照期过滤"
    assert params["latest_periods"] == {"company_T": "20251231"}


def test_asof_latest_or_future_uses_is_latest(monkeypatch):
    """as_of >= 全图最新快照期 → is_latest 快路径（与不传 as_of 完全一致）。"""
    adapter = _asof_adapter(monkeypatch, latest_snapshot="20260331", snapshot_map={})

    adapter._get_graph_sync(
        "600518.SH", depth=3, as_of="20260331", graph_version="equity-2026Q2"
    )
    query, _ = adapter._driver.calls[-1]
    assert "rel.is_latest = true" in query
    assert "latest_periods" not in query


def test_asof_normalized_before_snapshot_lookup(monkeypatch):
    """8.09 审查：YYYY-MM-DD / YYYYQn 在适配器边界统一规范化为 YYYYMMDD。"""
    adapter = _adapter(_Driver(_records_for_asof()))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    captured = {}
    monkeypatch.setattr(adapter, "_latest_snapshot_period", lambda gv: "20260331")
    monkeypatch.setattr(
        adapter, "_snapshot_periods", lambda gv, asof: captured.update(asof=asof) or {}
    )

    adapter._get_graph_sync(
        "600518.SH", depth=3, as_of="2025-12-31", graph_version="equity-2026Q2"
    )
    assert captured.get("asof") == "20251231", "YYYY-MM-DD 应规范化为 20251231"


def test_asof_invalid_raises_value_error(monkeypatch):
    """无法解析的 as_of 必须抛错（REST 层转 422），不得静默返回空图。"""
    adapter = _asof_adapter(monkeypatch, latest_snapshot="20260331", snapshot_map={})
    with pytest.raises(ValueError, match="INVALID_AS_OF"):
        adapter._get_graph_sync(
            "600518.SH", depth=3, as_of="not-a-period", graph_version="equity-2026Q2"
        )


def test_path_depth_equals_edge_count(monkeypatch):
    """8.09 审查：OwnershipChain.depth == len(edge_ids)（hop_count 口径）。"""
    rel1 = _FakeRel("rel_a", "S1", "T", "20251231")
    rel2 = _FakeRel("rel_b", "S2", "S1", "20251231")
    records = [{"target": {"entity_id": "T"}, "path": _FakePath([rel1, rel2])}]
    adapter = _adapter(_Driver(records))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")

    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")
    assert len(graph.control_chains) == 1
    chain = graph.control_chains[0]
    assert (
        chain.depth == 2 == len(chain.edge_ids)
    ), f"depth({chain.depth}) 必须等于边数({len(chain.edge_ids)})"
    assert chain.depth == len(chain.path) - 1


def test_path_nodes_ordered_along_real_direction(monkeypatch):
    """8.09 三轮审查：多跳节点序列按真实持股方向组装（最上游→最下游），
    且每条 edge[i] 满足 source==node[i]、target==node[i+1]。

    曾按关系遍历顺序追加 start_node 导致节点序列与边错位。
    """
    rel1 = _FakeRel("rel_a", "S1", "T", "20251231")  # S1 持股 T
    rel2 = _FakeRel("rel_b", "S2", "S1", "20251231")  # S2 持股 S1
    records = [{"target": {"entity_id": "T"}, "path": _FakePath([rel1, rel2])}]
    adapter = _adapter(_Driver(records))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")

    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")
    chain = graph.control_chains[0]
    assert chain.path == [
        "S2",
        "S1",
        "T",
    ], f"节点序列应按真实方向 S2→S1→T，实际 {chain.path}"
    assert chain.edge_ids == [
        "rel_b",
        "rel_a",
    ], f"边序列应同步反转，实际 {chain.edge_ids}"
    edge_by_id = {e.relationship_id: e for e in graph.edges}
    for i, eid in enumerate(chain.edge_ids):
        e = edge_by_id[eid]
        assert e.source == chain.path[i], f"edge[{i}] source 应为 {chain.path[i]}"
        assert e.target == chain.path[i + 1], f"edge[{i}] target 应为 {chain.path[i+1]}"


def test_path_type_is_ownership_not_control(monkeypatch):
    """8.09 三轮审查：十大股东链路默认 path_type=ownership（基金/少数持股
    不等于实际控制，不得一律标记 control）。"""
    rel = _FakeRel("rel_2025", "S", "T", "20251231")
    records = [{"target": {"entity_id": "T"}, "path": _FakePath([rel])}]
    adapter = _adapter(_Driver(records))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")
    assert graph.control_chains[0].path_type == "ownership"


def test_duplicate_node_sequences_collapsed():
    """同一节点序列对应多条路径 → 只计一次（防御性去重）。"""
    rel1 = _FakeRel("rel_a", "S", "T", "20251231")
    rel2 = _FakeRel("rel_b", "S", "T", "20241231")
    records = [
        {"target": {"entity_id": "T"}, "path": _FakePath([rel1])},
        {"target": {"entity_id": "T"}, "path": _FakePath([rel2])},
    ]
    adapter = _adapter(_Driver(records))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")
    assert len(graph.control_chains) == 1


def test_truncated_flag_set_when_over_200(monkeypatch):
    """LIMIT 201：存在第 201 条 → truncated=true（截断是显式的，不是静默）。"""
    rels = [_FakeRel(f"rel_{i}", f"S{i}", "T", "20251231") for i in range(201)]
    records = [{"target": {"entity_id": "T"}, "path": _FakePath([r])} for r in rels]
    adapter = _adapter(_Driver(records))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    graph = adapter._get_graph_sync("600518.SH", depth=3, graph_version="equity-2026Q2")
    assert graph.truncated is True
    assert len(graph.control_chains) == 200
    assert graph.max_observed_hops == 1


def test_coverage_note_when_no_4hop_chains(monkeypatch):
    """严格 4 跳+ 为 0 → 诚实覆盖说明（不推断不存在更深关系）。"""
    rel = _FakeRel("rel_2025", "S", "T", "20251231")
    records = [{"target": {"entity_id": "T"}, "path": _FakePath([rel])}]
    adapter = _adapter(_Driver(records))
    monkeypatch.setattr(adapter, "_resolve_wind_code", lambda code: "600518.SH")
    graph = adapter._get_graph_sync("600518.SH", depth=5, graph_version="equity-2026Q2")
    assert graph.coverage_note != ""
    assert "未发现可验证的4跳及以上" in graph.coverage_note
    assert graph.max_observed_hops == 1
    assert graph.requested_depth == 5


# ── 8.09 审查：count_multi_hop_paths（min/max 深度 + 去重 + 截断） ──


def test_multi_hop_count_has_versioned_and_all_version_modes():
    driver = _Driver([{"cnt": 14}])
    adapter = _adapter(driver)

    versioned = asyncio.run(adapter.count_multi_hop_paths("equity-2026Q2"))
    assert versioned == {"count": 14, "truncated": False}
    query, params = driver.calls[-1]
    assert "*3..10" in query  # 8.09：默认 min_depth=3, max_depth=10（不再 ..4 截断）
    assert "count(DISTINCT [n IN nodes(p) | n.entity_id])" in query
    # 8.09 三轮审查：只要求目标端是上市公司（b.wind_code <> ''），
    # 上游允许任意真实 Entity（自然人/基金/非上市企业）
    assert "b.wind_code <> ''" in query
    assert (
        "a.wind_code <> ''" not in query
    ), "起点不得限制为上市公司（会漏掉自然人→壳公司→上市公司链路）"
    assert params["gv"] == "equity-2026Q2"
    assert params["all_versions"] is False

    all_versions = asyncio.run(adapter.count_multi_hop_paths(all_versions=True))
    assert all_versions == {"count": 14, "truncated": False}
    _, params = driver.calls[-1]
    assert params["all_versions"] is True


def test_multi_hop_strict_gt3_uses_min_depth_4_max_10():
    """赛题口径固化：严格 >3 层股权链（4 跳+）验收传 (min_depth=4, max_depth=10)
    → Cypher *4..10（统计 4 跳及以上，不统计 3 跳链）。"""
    driver = _Driver([{"cnt": 0}])
    adapter = _adapter(driver)

    asyncio.run(
        adapter.count_multi_hop_paths("equity-2026Q2", min_depth=4, max_depth=10)
    )
    query, params = driver.calls[-1]
    assert "*4..10" in query
    assert params["gv"] == "equity-2026Q2"


def test_multi_hop_exact_4_uses_4_4():
    """精确 4 跳（验收对照）→ (min_depth=4, max_depth=4) → Cypher *4..4。"""
    driver = _Driver([{"cnt": 0}])
    adapter = _adapter(driver)
    asyncio.run(
        adapter.count_multi_hop_paths("equity-2026Q2", min_depth=4, max_depth=4)
    )
    query, _ = driver.calls[-1]
    assert "*4..4" in query


def test_multi_hop_invalid_depth_range_raises():
    adapter = _adapter(_Driver())
    with pytest.raises(ValueError, match="INVALID_DEPTH_RANGE"):
        asyncio.run(
            adapter.count_multi_hop_paths("equity-2026Q2", min_depth=5, max_depth=3)
        )
    with pytest.raises(ValueError, match="INVALID_DEPTH_RANGE"):
        asyncio.run(
            adapter.count_multi_hop_paths("equity-2026Q2", min_depth=0, max_depth=3)
        )
    with pytest.raises(ValueError, match="INVALID_DEPTH_RANGE"):
        asyncio.run(
            adapter.count_multi_hop_paths("equity-2026Q2", min_depth=3, max_depth=11)
        )


def test_multi_hop_cap_reports_truncated_not_silent():
    """计数封顶 10000：截断时返回 truncated=true，不把截断值当精确值。"""
    driver = _Driver([{"cnt": 15000}])
    adapter = _adapter(driver)
    result = asyncio.run(adapter.count_multi_hop_paths("equity-2026Q2"))
    assert result == {"count": 10000, "truncated": True}


def test_snapshot_cache_ttl_expires(monkeypatch):
    """8.09 三轮审查：快照缓存带 TTL——同一 graph_version 下重建图后，
    超过 TTL 的缓存必须重新查询，不能一直读旧快照映射。"""
    from app.infrastructure.graph.neo4j import equity_graph as eg

    driver = _Driver([{"latest": "20251231"}])
    adapter = _adapter(driver)
    monkeypatch.setattr(eg, "_LATEST_SNAPSHOT_CACHE", {})
    monkeypatch.setattr(eg, "_SNAPSHOT_MAP_CACHE", {})

    now = [1000.0]
    monkeypatch.setattr(eg.time, "monotonic", lambda: now[0])

    assert adapter._latest_snapshot_period("equity-2026Q2") == "20251231"
    assert len(driver.calls) == 1  # 首次查询

    # TTL 内命中缓存
    now[0] += 100
    assert adapter._latest_snapshot_period("equity-2026Q2") == "20251231"
    assert len(driver.calls) == 1  # 未重新查询

    # 超过 TTL → 重新查询
    now[0] += 300
    assert adapter._latest_snapshot_period("equity-2026Q2") == "20251231"
    assert len(driver.calls) == 2  # TTL 过期后重新查询
