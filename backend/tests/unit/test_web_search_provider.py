"""Web Search Provider 单元测试 — Phase E 会5 B1.

覆盖：Bocha 响应防御式解析、Bocha search 请求（monkeypatch httpx）、
工厂注册表与 off 语义。
"""

from __future__ import annotations

from app.core.config import settings
from app.infrastructure.web_search import create_web_search_provider
from app.infrastructure.web_search.bocha.provider import BochaWebSearchProvider
from app.infrastructure.web_search.mock.provider import MockWebSearchProvider


# ── 工厂 ──────────────────────────────────────────────────


def test_factory_off_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    assert create_web_search_provider("off") is None
    assert create_web_search_provider(None) is None  # 默认读 settings=off


def test_factory_unknown_returns_none():
    assert create_web_search_provider("unknown") is None


def test_factory_mock(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    provider = create_web_search_provider("mock")
    assert isinstance(provider, MockWebSearchProvider)


def test_factory_bocha(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "bocha")
    provider = create_web_search_provider("bocha")
    assert isinstance(provider, BochaWebSearchProvider)


# ── Bocha 响应解析 ─────────────────────────────────────────


def test_parse_standard_payload():
    payload = {
        "data": {
            "webPages": {
                "value": [
                    {
                        "name": "康美药业_百度百科",
                        "url": "https://baike.baidu.com/item/康美药业",
                        "snippet": "上市日期 2001-03-19",
                        "summary": "AI 摘要：上市日期 2001-03-19",
                        "datePublished": "2024-01-02T10:00:00Z",
                    }
                ]
            }
        }
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.title == "康美药业_百度百科"
    assert hit.url.startswith("https://baike.baidu.com")
    assert hit.domain == "baike.baidu.com"
    # snippet 优先取 summary（博查 summary=true）
    assert hit.snippet == "AI 摘要：上市日期 2001-03-19"
    assert hit.published_at == "2024-01-02"
    assert hit.source == "bocha"


def test_parse_webpages_as_direct_array():
    # 兼容：某些响应 webPages 直接是数组
    payload = {
        "data": {"webPages": [{"name": "t", "url": "https://a.com/x", "snippet": "s"}]}
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 1
    assert hits[0].title == "t"
    assert hits[0].snippet == "s"


def test_parse_malformed_returns_empty():
    assert BochaWebSearchProvider._parse_response({}) == []
    assert BochaWebSearchProvider._parse_response({"data": {}}) == []
    assert (
        BochaWebSearchProvider._parse_response(
            {"data": {"webPages": {"value": [{"bad": 1}]}}}
        )
        == []
    )
    # 全空命中是噪音，跳过（不返回空字段条目）
    assert (
        BochaWebSearchProvider._parse_response({"data": {"webPages": {"value": [{}]}}})
        == []
    )


# ── Bocha search（monkeypatch httpx）───────────────────────


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp(self._payload)


def test_bocha_search_sends_expected_request(monkeypatch):
    payload = {
        "data": {
            "webPages": {
                "value": [{"name": "t", "url": "https://a.com", "snippet": "s"}]
            }
        }
    }
    fake = _FakeClient(payload)
    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: fake,
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(
        settings, "WEB_SEARCH_BASE_URL", "https://api.bochaai.com/v1/web-search"
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_MAX_RESULTS", 5)

    provider = BochaWebSearchProvider()
    hits = _run(provider.search("康美药业 上市日期"))
    assert len(hits) == 1
    assert fake.calls, "应发起 POST 请求"
    call = fake.calls[0]
    assert call["url"] == "https://api.bochaai.com/v1/web-search"
    assert call["headers"]["Authorization"] == "Bearer test-key"
    assert call["json"]["query"] == "康美药业 上市日期"
    assert call["json"]["count"] == 5
    assert call["json"]["summary"] is True


def _run(coro):
    """同步执行 async provider.search（测试便利）。"""
    import asyncio

    return asyncio.run(coro)


def test_bocha_search_without_key_returns_empty():
    # 默认 settings.WEB_SEARCH_API_KEY="" → available=False → []
    provider = BochaWebSearchProvider(api_key="")
    assert _run(provider.search("anything")) == []
