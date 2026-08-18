"""Bocha Web Search Provider — Phase E 会5 B1.

对接博查（Bocha）Web Search API：`WEB_SEARCH_BASE_URL`
（默认 https://api.bochaai.com/v1/web-search）。
- 国产、中文友好、国内直连；专为 AI/LLM 检索设计。
- **未真机验证**（需 API key）；API 契约封装在本模块内，拿到 key 后按
  真实响应微调，不影响其余模块（抽象隔离，provider 可换）。

解析用防御式写法：不同时期响应字段可能有增减，缺失字段取空串/None；
snippet 优先取 summary（博查 summary=true 返回 AI 摘要），
回退 snippet/description。
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from app.application.ports.web_search_provider import SearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class BochaWebSearchProvider:
    """Bocha（博查）Web Search Provider."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.WEB_SEARCH_API_KEY
        self._base_url = (
            base_url if base_url is not None else settings.WEB_SEARCH_BASE_URL
        )
        self._timeout = (
            timeout if timeout is not None else settings.WEB_SEARCH_TIMEOUT_SECONDS
        )
        self._available = bool(self._api_key)
        if not self._available:
            logger.warning("Bocha: API key 未配置，Provider 不可用（返回空结果）")

    @property
    def provider_name(self) -> str:
        return "bocha"

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        """联网搜索；无 key / 异常 / 无结果 → 空列表（调用方诚实降级）。"""
        if not self._available:
            return []
        count = max_results or settings.WEB_SEARCH_MAX_RESULTS
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._base_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "summary": True,
                        "count": count,
                    },
                )
                resp.raise_for_status()
                return self._parse_response(resp.json())
        except Exception as exc:  # noqa: BLE001 — 联网失败返回空，调用方诚实降级
            logger.warning("Bocha: 搜索失败（query=%r）: %s", query, exc)
            return []

    @staticmethod
    def _parse_response(payload: dict) -> list[SearchResult]:
        """防御式解析博查响应（不同时期字段可能有增减）。"""
        data = payload.get("data") or {}
        web_pages = data.get("webPages") or {}
        if isinstance(web_pages, list):
            # 兼容：某些响应 webPages 直接是数组
            value = web_pages
        elif isinstance(web_pages, dict):
            value = web_pages.get("value")
        else:
            value = []
        if not isinstance(value, list):
            value = []
        out: list[SearchResult] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("name") or "")
            snippet = str(
                item.get("summary")
                or item.get("snippet")
                or item.get("description")
                or ""
            )
            # 空命中（无可解析内容）跳过，不返回噪音
            if not (url or title or snippet):
                continue
            out.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    domain=_hostname(url),
                    published_at=_as_date(item.get("datePublished")),
                    source="bocha",
                )
            )
        return out


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:  # noqa: BLE001
        return ""


def _as_date(value) -> str | None:
    """归一化到 YYYY-MM-DD；空值/解析失败 → None。"""
    if not value:
        return None
    return str(value)[:10]
