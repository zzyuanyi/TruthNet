"""Port 协议和 Mock Adapter 单元测试."""

import pytest

from app.application.ports.company_repository import CompanyRepository
from app.application.ports.equity_graph import EquityGraphPort
from app.application.ports.llm_provider import LLMProvider
from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph
from app.infrastructure.llm.mock.provider import MockLLMProvider
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


class TestCompanyRepositoryPort:
    """CompanyRepository Port 协议测试."""

    def test_sqlite_adapter_implements_protocol(self):
        adapter = SQLiteCompanyRepository()
        assert isinstance(adapter, CompanyRepository)

    @pytest.mark.asyncio
    async def test_mock_search(self):
        adapter = SQLiteCompanyRepository()
        result = await adapter.search("茅台")
        assert result.total >= 0
        if result.total > 0:
            assert result.companies[0].code == "600519"

    @pytest.mark.asyncio
    async def test_mock_get_by_code(self):
        adapter = SQLiteCompanyRepository()
        c = await adapter.get_by_code("600519")
        assert c is not None
        assert c.name == "贵州茅台酒股份有限公司"

    @pytest.mark.asyncio
    async def test_mock_get_by_code_not_found(self):
        adapter = SQLiteCompanyRepository()
        c = await adapter.get_by_code("999999")
        assert c is None

    @pytest.mark.asyncio
    async def test_mock_list_all(self):
        adapter = SQLiteCompanyRepository()
        companies = await adapter.list_all()
        assert len(companies) > 0


class TestEquityGraphPort:
    """EquityGraphPort 协议测试."""

    def test_networkx_adapter_implements_protocol(self):
        adapter = NetworkXEquityGraph()
        assert isinstance(adapter, EquityGraphPort)

    @pytest.mark.asyncio
    async def test_networkx_check_connection(self):
        adapter = NetworkXEquityGraph()
        assert await adapter.check_connection() is True

    @pytest.mark.asyncio
    async def test_networkx_get_graph(self):
        adapter = NetworkXEquityGraph()
        graph = await adapter.get_graph("600519", depth=3)
        assert graph.company_id == "600519"
        assert len(graph.nodes) > 0

    @pytest.mark.asyncio
    async def test_networkx_get_control_chains(self):
        adapter = NetworkXEquityGraph()
        chains = await adapter.get_control_chains("600519", max_depth=5)
        assert isinstance(chains, list)


class TestLLMProviderPort:
    """LLMProvider Port 协议测试."""

    def test_mock_adapter_implements_protocol(self):
        adapter = MockLLMProvider()
        assert isinstance(adapter, LLMProvider)

    @pytest.mark.asyncio
    async def test_mock_provider_name(self):
        adapter = MockLLMProvider()
        assert adapter.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_mock_check_connection(self):
        adapter = MockLLMProvider()
        assert await adapter.check_connection() is True

    @pytest.mark.asyncio
    async def test_mock_chat_returns_string(self):
        adapter = MockLLMProvider()
        result = await adapter.chat([{"role": "user", "content": "测试问题"}])
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Mock" in result

    @pytest.mark.asyncio
    async def test_mock_chat_stream(self):
        adapter = MockLLMProvider()
        chunks = []
        async for chunk in adapter.chat_stream(
            [{"role": "user", "content": "测试问题"}]
        ):
            chunks.append(chunk)
        assert len(chunks) > 0
        full = "".join(chunks)
        assert "Mock" in full
