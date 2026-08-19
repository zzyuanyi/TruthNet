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
    def __init__(self, payload, status_code: int = 200, headers: dict | None = None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload, status_code: int = 200, headers: dict | None = None):
        self._payload = payload
        self._status_code = status_code
        self._headers = headers or {}
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp(self._payload, self._status_code, self._headers)


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


# ── 官方契约 / 兼容变体（8/19 审查）────────────────────────


def test_parse_official_top_level_webpages_contract():
    """官方 SearchResponse 形状：webPages 在顶层（部分镜像/历史响应）。"""
    payload = {
        "_type": "SearchResponse",
        "queryContext": {"originalQuery": "康美药业 600518.SH 上市日期 交易所"},
        "webPages": {
            "webSearchUrl": "",
            "totalEstimatedMatches": 100,
            "value": [
                {
                    "name": "康美药业_百度百科",
                    "url": "https://baike.baidu.com/item/康美药业",
                    "snippet": "上市日期 2001-03-19",
                    "datePublished": "2024-01-02T10:00:00Z",
                }
            ],
        },
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 1
    assert hits[0].title == "康美药业_百度百科"
    assert hits[0].snippet == "上市日期 2001-03-19"
    assert hits[0].published_at == "2024-01-02"


def test_parse_legacy_data_webpages_still_compatible():
    """官方 `data.webPages.value` 契约（当前官方响应）仍兼容。"""
    payload = {
        "code": 200,
        "log_id": "d71841ad20095f61",
        "msg": None,
        "data": {
            "_type": "SearchResponse",
            "webPages": {
                "value": [
                    {
                        "name": "贵州茅台_百度百科",
                        "url": "https://baike.baidu.com/item/贵州茅台",
                        "snippet": "上市日期 2001-08-27",
                    }
                ]
            },
        },
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 1
    assert hits[0].title == "贵州茅台_百度百科"


def test_parse_top_level_webpages_value_empty():
    assert BochaWebSearchProvider._parse_response({"webPages": {"value": []}}) == []
    assert BochaWebSearchProvider._parse_response({"webPages": {}}) == []
    assert (
        BochaWebSearchProvider._parse_response({"data": {"webPages": {"value": []}}})
        == []
    )


def test_parse_webpages_missing_returns_empty():
    assert BochaWebSearchProvider._parse_response({"data": {}}) == []
    assert BochaWebSearchProvider._parse_response({}) == []
    assert BochaWebSearchProvider._parse_response({"webPages": None}) == []
    assert BochaWebSearchProvider._parse_response({"data": {"webPages": None}}) == []


def test_parse_malformed_value_returns_empty():
    payload = {"data": {"webPages": {"value": "not-a-list"}}}
    assert BochaWebSearchProvider._parse_response(payload) == []
    payload = {"webPages": {"value": [{"no": "usable fields"}]}}
    assert BochaWebSearchProvider._parse_response(payload) == []


def test_parse_summary_absent_falls_back_to_snippet():
    """summary 缺失 → 回退 snippet（再回退 description）。"""
    payload = {
        "data": {
            "webPages": {
                "value": [
                    {
                        "name": "t",
                        "url": "https://a.com/1",
                        "snippet": "上市日期 2001-03-19",
                    }
                ]
            }
        }
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 1
    assert hits[0].snippet == "上市日期 2001-03-19"
    payload = {
        "data": {
            "webPages": {
                "value": [
                    {"name": "t", "url": "https://a.com/2", "description": "desc 内容"}
                ]
            }
        }
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert hits[0].snippet == "desc 内容"


def test_parse_partial_missing_url_title_snippet():
    """url/title/snippet 部分缺失 → 不抛异常，可解析字段照常。"""
    payload = {
        "data": {
            "webPages": {
                "value": [
                    {"url": "https://a.com/x"},  # 无 title/snippet
                    {"name": "只有标题", "snippet": "上市日期 2001-03-19"},  # 无 url
                ]
            }
        }
    }
    hits = BochaWebSearchProvider._parse_response(payload)
    assert len(hits) == 2
    assert hits[0].url == "https://a.com/x"
    assert hits[1].title == "只有标题"
    assert hits[1].domain == ""


# ── HTTP 错误分类诊断（8/19 审查）──────────────────────────


def test_http_401_returns_empty_and_counts_auth(monkeypatch):
    fake = _FakeClient({}, status_code=401)
    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: fake,
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["http_401_403"] == 1


def test_http_403_returns_empty_and_counts_auth(monkeypatch):
    fake = _FakeClient({}, status_code=403)
    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: fake,
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["http_401_403"] == 1


def test_http_429_returns_empty_and_counts_rate_limit(monkeypatch):
    fake = _FakeClient({}, status_code=429, headers={"Retry-After": "60"})
    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: fake,
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["http_429"] == 1


def test_http_5xx_returns_empty_and_counts_server_error(monkeypatch):
    for code in (500, 502, 503):
        fake = _FakeClient({}, status_code=code)
        monkeypatch.setattr(
            "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
            lambda timeout=None: fake,
        )
        monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
        provider = BochaWebSearchProvider()
        assert _run(provider.search("q")) == []
        assert provider._stats["http_5xx"] == 1


def test_timeout_counts_and_returns_empty(monkeypatch):
    import httpx

    class _TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            raise httpx.ConnectTimeout("connect timeout")

    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: _TimeoutClient(),
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["timeout"] == 1


def test_connection_error_counts_and_returns_empty(monkeypatch):
    import httpx

    class _ConnClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: _ConnClient(),
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["connection_error"] == 1


def test_real_empty_vs_parse_empty_observable(monkeypatch):
    """HTTP 200 + 空 value → 归入 empty_real_result（真实空结果可诊断）。"""
    fake = _FakeClient({"data": {"webPages": {"value": []}}}, status_code=200)
    monkeypatch.setattr(
        "app.infrastructure.web_search.bocha.provider.httpx.AsyncClient",
        lambda timeout=None: fake,
    )
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", "test-key")
    provider = BochaWebSearchProvider()
    assert _run(provider.search("q")) == []
    assert provider._stats["empty_real_result"] == 1
    assert provider._stats["parse_empty"] == 1  # 解析同样产出空
