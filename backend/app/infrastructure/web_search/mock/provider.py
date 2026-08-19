"""Mock Web Search Provider — Phase E 会5.

实现 WebSearchProvider Port 协议。
不调用真实搜索引擎；按注入的预设命中返回，或空列表。
用于：本地开发、CI 测试、off 一致性对照。
"""

from __future__ import annotations

from app.application.ports.web_search_provider import SearchResult


class MockWebSearchProvider:
    """Mock Web Search Provider.

    返回预设命中（通过构造参数注入，测试用）；默认空列表。
    """

    def __init__(self, hits: list[dict] | None = None):
        self._hits = hits or []

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        """返回预设命中（截断到 max_results）。"""
        results = [SearchResult(**{**h, "source": "mock"}) for h in self._hits]
        if max_results:
            results = results[:max_results]
        return results
