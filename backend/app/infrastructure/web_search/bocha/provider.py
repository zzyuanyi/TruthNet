"""Bocha Web Search Provider — Phase E 会5 B1.

对接博查（Bocha）Web Search API：`WEB_SEARCH_BASE_URL`
（默认 https://api.bochaai.com/v1/web-search）。
- 国产、中文友好、国内直连；专为 AI/LLM 检索设计。
- 官方契约（2026-08-19 联网核验）：`POST {base}/v1/web-search`，
  响应根结构 `{code, log_id, msg, data}`，结果位于 **`data.webPages.value`**；
  兼容历史/变体：顶层 `webPages.value` 与 `webPages` 直接为数组。
- 常见错误码：400 请求错误 / 401 Key 无效 / 403 余额不足 / 429 请求频繁 /
  500 服务器错误（用 `log_id` 调试）。

解析用防御式写法：不同时期响应字段可能有增减，缺失字段取空串/None；
snippet 优先取 summary（博查 summary=true 返回 AI 摘要），
回退 snippet/description。

诊断（8/19 审查）：真实 Provider 区分 401/403（key/auth）、429（provider
限流，尽量透出 Retry-After）、5xx（provider server）、timeout、连接错误、
真实空结果 vs 解析空；日志不含完整 API Key。调用方保持 fail-closed → []。
"""

from __future__ import annotations

import logging
import threading
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
        self._stats_lock = threading.Lock()
        self._stats = self._fresh_stats()

    @staticmethod
    def _fresh_stats() -> dict:
        return {
            "requests": 0,
            "http_401_403": 0,
            "http_429": 0,
            "http_5xx": 0,
            "http_other_error": 0,
            "timeout": 0,
            "connection_error": 0,
            "empty_real_result": 0,
            "parse_empty": 0,
            "not_observable": 0,
        }

    def _stat_inc(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    def report_stats(self) -> dict:
        """运行统计（供报告诊断；空真结果与失败可区分）。"""
        with self._stats_lock:
            return {
                "web_search_provider": "bocha",
                "web_search_requests": self._stats["requests"],
                "web_search_http_401_403": self._stats["http_401_403"],
                "web_search_http_429": self._stats["http_429"],
                "web_search_http_5xx": self._stats["http_5xx"],
                "web_search_http_other_error": self._stats["http_other_error"],
                "web_search_timeout": self._stats["timeout"],
                "web_search_connection_error": self._stats["connection_error"],
                "web_search_empty_real_result": self._stats["empty_real_result"],
                "web_search_parse_empty": self._stats["parse_empty"],
                "web_search_not_observable": self._stats["not_observable"],
            }

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
        self._stat_inc("requests")
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
                hits = self._classify_and_parse(resp, query)
                if not hits:
                    # 到达这里：HTTP 200 但结果为空（真实无结果，或解析出空）
                    if resp.status_code == 200:
                        self._stat_inc("empty_real_result")
                return hits
        except httpx.TimeoutException:
            self._stat_inc("timeout")
            logger.warning("Bocha: 联网超时（query=%r）", query)
            return []
        except httpx.ConnectError as exc:
            self._stat_inc("connection_error")
            logger.warning("Bocha: 连接失败（query=%r）: %s", query, exc)
            return []
        except httpx.NetworkError as exc:
            self._stat_inc("connection_error")
            logger.warning("Bocha: 网络错误（query=%r）: %s", query, exc)
            return []
        except Exception as exc:  # noqa: BLE001 — 未知异常，fail-closed 返回空
            self._stat_inc("not_observable")
            logger.warning("Bocha: 未知异常（query=%r）: %s", query, exc)
            return []

    def _classify_and_parse(self, resp: httpx.Response, query: str) -> list:
        """按 HTTP 状态分类解析；非 200 → 记统计、诊断日志、返回 []。"""
        code = int(getattr(resp, "status_code", 0) or 0)
        if code in (401, 403):
            self._stat_inc("http_401_403")
            # 不打印 key；只提示检查配置
            logger.error(
                "Bocha: 认证/配额失败（HTTP %s），请检查 WEB_SEARCH_API_KEY 与账户余额",
                code,
            )
            return []
        if code == 429:
            self._stat_inc("http_429")
            retry_after = resp.headers.get("Retry-After") if resp.headers else None
            logger.warning(
                "Bocha: 被限流（HTTP 429）%s",
                f"Retry-After={retry_after}" if retry_after else "",
            )
            return []
        if code >= 500:
            self._stat_inc("http_5xx")
            logger.warning("Bocha: 服务端错误 HTTP %s（query=%r）", code, query)
            return []
        if code != 200:
            self._stat_inc("http_other_error")
            logger.warning("Bocha: 未预期 HTTP %s（query=%r）", code, query)
            return []
        payload = resp.json()
        hits = self._parse_response(payload)
        if not hits:
            self._stat_inc("parse_empty")
        return hits

    @staticmethod
    def _parse_response(payload: dict) -> list[SearchResult]:
        """防御式解析博查响应（不同时期字段可能有增减）。

        官方契约：`data.webPages.value`；兼容顶层 `webPages.value` 变体；
        webPages 直接为数组时兼容。空命中（无可解析内容）跳过。
        """
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            web_pages = data.get("webPages")
        else:
            web_pages = None
        if web_pages is None and isinstance(payload, dict):
            # 顶层 webPages 变体（某些镜像/历史响应）
            web_pages = payload.get("webPages")
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
