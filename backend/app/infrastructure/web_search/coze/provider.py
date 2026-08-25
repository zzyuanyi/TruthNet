"""Coze Web Search Provider — 平台托管联网搜索（coze-coding-dev-sdk）.

数据源为平台内置 SearchClient（沙箱预置、免 Key），归一化到统一
SearchResult 契约，镜像 bocha provider 的防御式写法：
- 任何异常 fail-closed 返回 []（不抛给守卫服务）；
- snippet 优先 AI summary（信息密度高），回退 snippet；
- domain 从 url 解析；published_at 透传 publish_time（可空）。
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.application.ports.web_search_provider import SearchResult

logger = logging.getLogger(__name__)


class CozeWebSearchProvider:
    """平台托管 Web Search Provider（coze-coding-dev-sdk，后端专用）."""

    def __init__(self) -> None:
        # SDK 预置在沙箱环境，导入失败视为不可用（fail-closed）
        try:
            from coze_coding_dev_sdk import SearchClient

            self._client = SearchClient()
        except Exception:
            logger.warning("Coze: SDK 初始化失败，Provider 不可用", exc_info=True)
            self._client = None

    @property
    def provider_name(self) -> str:
        return "coze"

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        """联网搜索：真实调用 SearchClient；失败/空结果返回 []."""
        if self._client is None:
            return []
        count = max_results if max_results is not None else 5
        try:
            response = self._client.web_search(query=query, count=count)
        except Exception:
            logger.warning("Coze: 联网搜索失败，fail-closed 返回空", exc_info=True)
            return []

        results: list[SearchResult] = []
        for item in response.web_items or []:
            url = getattr(item, "url", "") or ""
            snippet = (
                getattr(item, "summary", None) or getattr(item, "snippet", "") or ""
            )
            results.append(
                SearchResult(
                    title=getattr(item, "title", "") or "",
                    url=url,
                    snippet=snippet,
                    domain=urlparse(url).netloc if url else "",
                    published_at=getattr(item, "publish_time", None),
                    source=self.provider_name,
                )
            )
        return results
