"""Web Search 守卫服务单元测试 — Phase E 会5 B1.

覆盖：off 门（默认零副作用）、mock 命中、缓存去重、限流、超时。
"""

from __future__ import annotations

import time

import pytest

from app.application.ports.web_search_provider import SearchResult
from app.application.services import web_search_service
from app.application.services.web_search_service import (
    _reset_for_tests,
    web_search,
)
from app.core.config import settings
from app.infrastructure.web_search.mock.provider import MockWebSearchProvider


@pytest.fixture(autouse=True)
def _clean_state():
    """每个测试前重置缓存与限流状态。"""
    _reset_for_tests()
    yield
    _reset_for_tests()


class _CountingProvider:
    """统计 search 调用次数（缓存去重验证用）。"""

    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "counting"

    async def search(self, query: str, max_results: int | None = None) -> list:
        self.calls += 1
        return [
            SearchResult(
                title=query, url="https://x.test/1", snippet="s", source="counting"
            )
        ]


class _SleepingProvider:
    """超时验证用：search 阻塞 sleep_seconds 秒。"""

    def __init__(self, sleep_seconds: float = 1.0):
        self.sleep_seconds = sleep_seconds

    @property
    def provider_name(self) -> str:
        return "sleepy"

    async def search(self, query: str, max_results: int | None = None) -> list:
        import asyncio

        await asyncio.sleep(self.sleep_seconds)
        return [SearchResult(title=query, url="https://x.test/1", snippet="s")]


# ── off 门 ────────────────────────────────────────────────


def test_off_default_returns_empty_no_side_effects(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    assert web_search("康美药业 上市日期") == []
    # off 路径零副作用：不创建 provider、不写缓存
    assert web_search_service._cache == {}


# ── mock 命中 ─────────────────────────────────────────────


def test_mock_backend_returns_hits(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    hits = [
        {
            "title": "康美药业_百度百科",
            "url": "https://baike.baidu.com/x",
            "snippet": "上市日期 2001-03-19",
        }
    ]
    monkeypatch.setattr(
        web_search_service, "_create_provider", lambda: MockWebSearchProvider(hits)
    )
    result = web_search("康美药业 上市日期")
    assert len(result) == 1
    assert result[0].title == "康美药业_百度百科"
    assert result[0].source == "mock"


def test_mock_empty_hits(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    monkeypatch.setattr(
        web_search_service, "_create_provider", lambda: MockWebSearchProvider()
    )
    assert web_search("无结果查询") == []


# ── 缓存去重 ──────────────────────────────────────────────


def test_cache_dedup_same_query(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _CountingProvider()
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)
    first = web_search("康美药业 上市日期")
    second = web_search("康美药业 上市日期")  # 命中缓存，不重复联网
    assert first and second == first
    assert counting.calls == 1


def test_cache_keyed_by_query(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _CountingProvider()
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)
    web_search("query-a")
    web_search("query-b")  # 不同 query → 重新联网
    assert counting.calls == 2


# ── 8/19 审查：空/失败结果缓存语义 ─────────────────────────


def test_nonempty_result_cached_indefinitely(monkeypatch):
    """非空结果进程内常驻：同 query 重复调用不再联网。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _CountingProvider()
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)
    web_search("有结果查询")
    assert counting.calls == 1
    # 手动把缓存时间拨回很久之前，非空结果仍应命中缓存（常驻）
    with web_search_service._cache_lock:
        web_search_service._cache["有结果查询"] = (
            web_search_service._cache["有结果查询"][0],
            0.0,
        )
    web_search("有结果查询")
    assert counting.calls == 1, "非空结果不应因时间过期而重新联网"


class _EmptyCountingProvider:
    """统计 search 调用次数，返回空列表（空缓存语义验证用）。"""

    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "empty-counting"

    async def search(self, query: str, max_results: int | None = None) -> list:
        self.calls += 1
        return []


def test_empty_result_expires_after_short_ttl(monkeypatch):
    """空/失败结果短 TTL：过期后同 query 可重新联网（不永久污染缓存）。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _EmptyCountingProvider()
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)
    assert web_search("空结果查询") == []
    assert counting.calls == 1
    # 空结果超过 TTL → 过期，重新联网
    with web_search_service._cache_lock:
        web_search_service._cache["空结果查询"] = ([], 0.0)
    assert web_search("空结果查询") == []
    assert counting.calls == 2, "空结果短 TTL 过期后应重新联网（不永久缓存失败）"


def test_empty_result_cached_within_ttl(monkeypatch):
    """空结果在短 TTL 窗口内 → 命中缓存，不重复联网（同 turn 防重复空搜）。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _EmptyCountingProvider()
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)
    assert web_search("空结果查询") == []
    assert web_search("空结果查询") == []  # TTL 内命中缓存
    assert counting.calls == 1


# ── 限流 ──────────────────────────────────────────────────


def test_rate_limit_blocks_when_budget_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    monkeypatch.setattr(settings, "WEB_SEARCH_RATE_LIMIT_RPM", 1)  # 每分钟 1 次
    monkeypatch.setattr(
        web_search_service, "_create_provider", lambda: MockWebSearchProvider()
    )
    assert web_search("q1") == []  # 空命中也占一次请求
    # 预算耗尽（同一分钟内）→ 第二次请求被限流，返回 []
    assert web_search("q2") == []


def test_rate_limit_recovers_after_refill(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    monkeypatch.setattr(settings, "WEB_SEARCH_RATE_LIMIT_RPM", 1)
    monkeypatch.setattr(
        web_search_service, "_create_provider", lambda: MockWebSearchProvider()
    )
    assert web_search("q1") == []
    assert web_search("q2") == []  # 限流
    # 手动把令牌桶回填时间拨回 60 秒前 → 令牌恢复
    web_search_service._rate_meta["last_refill"] -= 61.0
    assert web_search("q3") == []  # 恢复后放行（空命中，仍是 []）


# ── 超时 ──────────────────────────────────────────────────


def test_timeout_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    monkeypatch.setattr(
        web_search_service, "_create_provider", lambda: _SleepingProvider(1.0)
    )
    started = time.monotonic()
    assert web_search("慢查询", timeout=0.05) == []
    assert time.monotonic() - started < 0.5  # 超时快速返回，不傻等 1s
