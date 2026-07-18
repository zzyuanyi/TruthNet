"""Graph Port Contract 测试 — NetworkX 和 Neo4j 共享接口."""

import pytest

from app.application.ports.equity_graph import EquityGraphPort
from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph


class TestGraphPortContract:
    """NetworkX 满足 EquityGraphPort."""

    def test_adapter_satisfies_port(self):
        graph = NetworkXEquityGraph()
        assert isinstance(graph, EquityGraphPort)

    @pytest.mark.asyncio
    async def test_get_graph(self):
        graph = NetworkXEquityGraph()
        result = await graph.get_graph("600519", depth=3)
        assert result.company_id == "600519"
        assert len(result.nodes) >= 1

    @pytest.mark.asyncio
    async def test_get_control_chains(self):
        graph = NetworkXEquityGraph()
        chains = await graph.get_control_chains("600519")
        assert isinstance(chains, list)

    @pytest.mark.asyncio
    async def test_check_connection(self):
        graph = NetworkXEquityGraph()
        assert await graph.check_connection() is True
