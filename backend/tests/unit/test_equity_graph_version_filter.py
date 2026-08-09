import asyncio

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


def test_multi_hop_count_has_versioned_and_all_version_modes():
    driver = _Driver([{"cnt": 14}])
    adapter = _adapter(driver)

    versioned = asyncio.run(adapter.count_multi_hop_paths("equity-2026Q2", min_depth=3))
    assert versioned == 14
    _, params = driver.calls[-1]
    assert params["gv"] == "equity-2026Q2"
    assert params["all_versions"] is False

    all_versions = asyncio.run(
        adapter.count_multi_hop_paths(min_depth=3, all_versions=True)
    )
    assert all_versions == 14
    _, params = driver.calls[-1]
    assert params["all_versions"] is True
