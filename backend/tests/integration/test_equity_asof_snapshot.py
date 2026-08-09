"""多跳修复真库验收（8.09 审查）— 整体快照语义 + REST/Agent 口径一致（外部门禁）。

需要 TRUTHNET_RUN_EXTERNAL_TESTS=1 + MySQL/Neo4j 数据齐备。

验收口径（8.09 审查 + 8.10 修订）：
  1. as_of 快照按目标公司整体切换（退出前十大的旧股东被排除），
     不得按 (source, target) 对取最新期；
  2. as_of >= 全图最新快照期时，与不传 as_of 的节点/边/路径集合完全一致；
  3. YYYY-MM-DD 与 YYYYMMDD 返回完全相同；非法 as_of → 422；
  4. 严格 >3 层 = hop_count >= 4，真库如实记录（起点不限、目标端上市公司）：
     min_depth=3, max_depth=10 → 568 条；min_depth=4, max_depth=10 → 10 条
     （存在 10 条可验证的四跳持股路径，最大深度为四跳）；
     min_depth=5, max_depth=10 → 0 条；均 truncated=False；
  5. REST /risk 与 Chat 同期次风险等级、股权边数一致；
  6. 响应如实暴露 requested_depth/max_observed_hops/truncated/coverage_note。
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _equity(client, code: str, as_of: str | None = None) -> dict:
    url = f"/api/v1/companies/{code}/equity"
    if as_of:
        url += f"?as_of={as_of}"
    resp = client.get(url)
    assert resp.status_code == 200, resp.text[:500]
    body = resp.json()
    assert body.get("data") is not None
    return body["data"]


def _sets(data: dict) -> tuple:
    nodes = {n["id"] for n in data.get("nodes") or []}
    edges = {(e["source"], e["target"]) for e in data.get("edges") or []}
    paths = {tuple(p["node_ids"]) for p in data.get("paths") or []}
    return nodes, edges, paths


def test_equity_asof_no_duplicate_snapshot_pairs(client):
    """as_of 时点查询不得返回同一股东对的多期历史边（快照整体切换）。"""
    data = _equity(client, "600518.SH", as_of="20260331")
    edges = data.get("edges") or []
    assert edges, "应至少返回一条股权边"
    pairs = [(e.get("source"), e.get("target")) for e in edges]
    assert len(pairs) == len(
        set(pairs)
    ), f"同一 source→target 出现多期快照: {len(pairs)} vs {len(set(pairs))}"
    assert len(data.get("paths") or []) == len(
        pairs
    ), "路径数必须与唯一快照边数一致（历史重复路径不得计入）"
    # 整体快照：所有边报告期必须一致（同一目标公司同时切换快照）
    periods = {e.get("report_period") for e in edges}
    assert len(periods) == 1, f"同一目标公司应只含一个快照期，实际 {periods}"


def test_equity_asof_late_equals_no_asof(client):
    """as_of 晚于全图最新快照期 → 与不传 as_of 的节点/边/路径集合完全一致。"""
    latest = _equity(client, "600518.SH")
    asof = _equity(client, "600518.SH", as_of="20991231")
    assert _sets(latest) == _sets(
        asof
    ), "as_of 晚于最新数据时集合必须与不传 as_of 完全一致"


def test_equity_asof_format_equivalent(client):
    """2025-12-31 与 20251231 返回完全相同（适配器边界规范化）。"""
    dashed = _equity(client, "600518.SH", as_of="2025-12-31")
    compact = _equity(client, "600518.SH", as_of="20251231")
    assert _sets(dashed) == _sets(compact)


def test_equity_asof_invalid_returns_422(client):
    """无法解析的 as_of → 422（不得静默返回空图）。"""
    resp = client.get("/api/v1/companies/600518.SH/equity?as_of=abc")
    assert resp.status_code == 422, f"非法 as_of 应 422，实际 {resp.status_code}"


def test_strict_gt3_reports_10_four_hop_paths():
    """赛题口径如实记录（8.09 三轮审查修订）：起点不限（上游允许自然人/
    基金/非上市企业）、目标端为上市公司时，严格 >3（4 跳+）当前有 10 条
    可验证持股路径（曾限制两端上市公司误报为 0）；最大深度为 4 跳。"""
    import asyncio

    from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

    adapter = Neo4jEquityGraph()

    async def counts():
        d3 = await adapter.count_multi_hop_paths(
            "equity-2026Q2", min_depth=3, max_depth=10
        )
        d4 = await adapter.count_multi_hop_paths(
            "equity-2026Q2", min_depth=4, max_depth=10
        )
        d5 = await adapter.count_multi_hop_paths(
            "equity-2026Q2", min_depth=5, max_depth=10
        )
        return d3, d4, d5

    d3, d4, d5 = asyncio.run(counts())
    assert d3["count"] >= 1, "真库应存在 3 跳链（≥3 口径）"
    assert (
        d4["count"] == 10
    ), f"严格 >3（4 跳及以上）应为 10 条可验证持股路径，实际 {d4['count']}"
    assert d4["truncated"] is False
    assert d5["count"] == 0, "最大深度为 4 跳（5 跳+ 为 0）"


def test_equity_response_exposes_coverage_fields(client):
    """响应如实暴露 requested_depth/max_observed_hops/truncated/coverage_note。"""
    data = _equity(client, "600518.SH", as_of="20251231")
    assert data.get("requested_depth") == 5
    assert data.get("max_observed_hops") == 1
    assert data.get("truncated") is False
    note = data.get("coverage_note") or ""
    assert "未发现可验证的4跳及以上" in note, "严格 4 跳+ 为 0 时必须给出诚实覆盖说明"


def test_rest_and_chat_risk_level_and_equity_consistent(client):
    """REST /risk 与 Chat 同期次（2025 年报）风险等级、股权边数一致。"""
    resp = client.get("/api/v1/companies/600518.SH/risk?as_of=20251231")
    assert resp.status_code == 200, resp.text[:500]
    rest_level = resp.json()["data"].get("risk_level")

    chat = client.post(
        "/api/v1/chat",
        json={"question": "康美药业 2025 年报的综合风险等级是什么"},
    )
    assert chat.status_code == 200, chat.text[:500]
    chat_data = chat.json()["data"]
    chat_level = chat_data.get("risk_level")

    assert rest_level in {"red", "orange", "yellow", "green", "unknown"}
    assert chat_level in {"red", "orange", "yellow", "green", "unknown"}
    assert (
        chat_level == rest_level
    ), f"Chat({chat_level}) 与 REST({rest_level}) 同期次风险等级不一致"

    # 股权边数一致：chat equity_chains 数 == REST /equity 同 as_of paths 数
    equity = _equity(client, "600518.SH", as_of="20251231")
    n_rest_paths = len(equity.get("paths") or [])
    n_chat_chains = len(chat_data.get("equity_chains") or [])
    assert n_rest_paths > 0
    assert (
        n_chat_chains == n_rest_paths
    ), f"Chat 股权链({n_chat_chains}) 与 REST 股权路径({n_rest_paths})不一致"
