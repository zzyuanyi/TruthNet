"""AnySearch 垂类 Provider 单元测试 — Phase E 会5 B1（8/19 接入）.

覆盖：工厂注册、A 股代码提取、MCP Markdown 解析（行情/公告/三表 JSON 行）、
无代码不搜索（纯垂类定位）、HTTP/RPC 错误分类、垂直 JSON → SearchResult。
"""

from __future__ import annotations

from app.core.config import settings
from app.infrastructure.web_search import create_web_search_provider
from app.infrastructure.web_search.anysearch.provider import (
    AnySearchWebSearchProvider,
    _extract_ashare_code,
    _extract_markdown_url,
    _parse_mcp_text_results,
    _search_result_from_vertical_json,
)
from app.infrastructure.web_search.mock.provider import MockWebSearchProvider


def _run(coro):
    """同步执行 async provider.search（测试便利）。"""
    import asyncio

    return asyncio.run(coro)


# ── 工厂 ──────────────────────────────────────────────────


def test_factory_anysearch(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "anysearch")
    provider = create_web_search_provider("anysearch")
    assert isinstance(provider, AnySearchWebSearchProvider)


def test_factory_other_backends_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    assert create_web_search_provider("off") is None
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    assert isinstance(create_web_search_provider("mock"), MockWebSearchProvider)


# ── A 股代码提取 ─────────────────────────────────────────


def test_extract_code_with_exchange_suffix():
    assert _extract_ashare_code("康美药业 600518.SH 上市日期 交易所") == "600518.SH"
    assert _extract_ashare_code("贵州茅台 600519.SH 行情") == "600519.SH"
    assert _extract_ashare_code("000001.SZ 股价") == "000001.SZ"
    assert _extract_ashare_code("830799.BJ 公告") == "830799.BJ"
    assert _extract_ashare_code("600519.sh 收盘") == "600519.SH"  # 小写后缀


def test_extract_code_bare_requires_company_context():
    # 裸 6 位 + 公司语境 → 提取（默认 SH）
    assert _extract_ashare_code("分析 600519 这家公司") == "600519.SH"
    # 裸 6 位无语境（年份/数量）→ 不提取
    assert _extract_ashare_code("2025 年营收增长") == ""
    assert _extract_ashare_code("大约 600519 是什么") == ""


def test_extract_code_no_code():
    assert _extract_ashare_code("茅台最近公告") == ""
    assert _extract_ashare_code("康美药业怎么样") == ""


# ── 纯垂类：无代码不搜索 ─────────────────────────────────


def test_no_code_returns_empty_without_network(monkeypatch):
    """无 A 股代码 → 直接 []，不发任何网络请求（纯垂类定位）。"""
    provider = AnySearchWebSearchProvider()
    calls = []

    async def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("不应发起网络请求")

    monkeypatch.setattr(provider, "_vertical_search", _boom)
    assert _run(provider.search("茅台最近有什么新闻")) == []
    assert calls == []


# ── MCP Markdown 解析 ─────────────────────────────────────


def test_parse_quote_markdown():
    text = """## Search Results (2 results, 3810ms)

### 1. 600519.SH 20260818 日线行情
- {"amount":5007014.692,"change":4.9,"close":1297.99,"pct_chg":0.3789,"pe":19.7108,"trade_date":"20260818","ts_code":"600519.SH"}

### 2. 600519.SH 20260817 日线行情
- {"close":1293.09,"trade_date":"20260817","ts_code":"600519.SH"}
"""
    hits = _parse_mcp_text_results(text, "贵州茅台 600519.SH 行情", "600519.SH")
    assert len(hits) == 2
    assert hits[0].title == "600519.SH 20260818 日线行情"
    assert "close=1297.99" in hits[0].snippet
    assert "pct_chg=0.3789" in hits[0].snippet
    assert hits[0].published_at == "2026-08-18"
    assert hits[0].source == "anysearch"


def test_parse_news_markdown():
    text = """## Search Results (1 results, 900ms)

### 1. 康美药业关于股票复牌的公告
- {"title":"康美药业关于股票复牌的公告","date":"2024-01-15","url":"https://static.cninfo.com.cn/xxx","content":"康美药业股份有限公司关于股票复牌的公告…"}
"""
    hits = _parse_mcp_text_results(text, "康美药业 600518.SH 公告", "600518.SH")
    assert len(hits) == 1
    assert "复牌" in hits[0].title
    assert hits[0].url.startswith("https://")
    assert hits[0].published_at == "2024-01-15"
    assert hits[0].domain  # url 有域名


def test_parse_fundamental_markdown():
    text = """## Search Results (1 results, 1200ms)

### 1. 600519.SH 主要指标
- {"period":"2024-12-31","eps":58.36,"roe":30.41,"net_profit":86228240000,"ts_code":"600519.SH"}
"""
    hits = _parse_mcp_text_results(text, "600519.SH 财报 指标", "600519.SH")
    assert len(hits) == 1
    assert "eps=58.36" in hits[0].snippet
    assert hits[0].published_at == "2024-12-31"


def test_parse_income_markdown_full_fields():
    """利润表实测 JSON：revenue/n_income/basic_eps 全字段进 snippet。"""
    text = """## Search Results (1 results, 1424ms)

### 1. 600519.SH 20260630 利润表
- {"ann_date":"20260815","basic_eps":35.57,"end_date":"20260630","n_income":46033330566.78,"operate_profit":61411291686.27,"revenue":90703260964.48,"total_profit":61438419177.29,"ts_code":"600519.SH"}
"""
    hits = _parse_mcp_text_results(text, "贵州茅台 600519.SH 财报", "600519.SH")
    assert len(hits) == 1
    assert "revenue=90703260964.48" in hits[0].snippet
    assert "n_income=46033330566.78" in hits[0].snippet
    assert "basic_eps=35.57" in hits[0].snippet
    assert hits[0].published_at == "2026-06-30"


def test_parse_news_markdown_url_extracted():
    """公告/快讯实测：URL 在 `- **URL**:` 行，须提取到 url 字段。"""
    text = """## Search Results (1 results, 1974ms)

### 1. 贵州茅台(SH600519)股票股价_股价行情_讨论
- **URL**: https://xueqiu.com/S/SH600519
- 【贵州茅台：上半年净利润同比下降1.95%】贵州茅台(600519.SH)发布2026年半年度报告，实现营业收入907.03亿元，同比增长1.47%。
"""
    hits = _parse_mcp_text_results(text, "贵州茅台 600519.SH 快讯", "600519.SH")
    assert len(hits) == 1
    assert hits[0].url == "https://xueqiu.com/S/SH600519"
    assert hits[0].domain == "xueqiu.com"
    assert "净利润同比下降" in hits[0].snippet
    assert "**URL**" not in hits[0].snippet  # URL 行已从 snippet 清理


def test_extract_markdown_url_direct():
    assert (
        _extract_markdown_url("- **URL**: https://xueqiu.com/S/SH600519\n- 摘要")
        == "https://xueqiu.com/S/SH600519"
    )
    assert _extract_markdown_url("无 URL 文本") == ""
    assert _extract_markdown_url("见 https://example.com/a?b=1 结尾") == (
        "https://example.com/a?b=1"
    )


def test_parse_markdown_no_json_falls_back_to_text():
    text = "## Search Results (1 results)\n\n### 1. 无结构化数据\n- 只有纯文本摘要\n"
    hits = _parse_mcp_text_results(text, "q", "600519.SH")
    assert len(hits) == 1
    assert "纯文本摘要" in hits[0].snippet


def test_parse_empty_text():
    assert _parse_mcp_text_results("", "q", "600519.SH") == []
    assert _parse_mcp_text_results(None, "q", "600519.SH") == []


# ── 垂直 JSON → SearchResult ──────────────────────────────


def test_vertical_json_quote_fields():
    obj = {
        "close": 1297.99,
        "pct_chg": 0.3789,
        "pe": 19.7108,
        "trade_date": "20260818",
        "ts_code": "600519.SH",
    }
    sr = _search_result_from_vertical_json(obj, "行情", "600519.SH")
    assert sr is not None
    assert sr.published_at == "2026-08-18"
    assert "close=1297.99" in sr.snippet


def test_vertical_json_empty_obj():
    assert _search_result_from_vertical_json({}, "t", "600519.SH") is None
    assert _search_result_from_vertical_json(None, "t", "600519.SH") is None


# ── HTTP / RPC 错误分类（经 monkeypatch httpx）─────────────


def test_mcp_call_http_error_classified(monkeypatch):
    """HTTP 401 → 分类到 http_401_403，返回 []（fail-closed）。"""

    class _FakeResp:
        status_code = 401

        def json(self):
            return {"error": {"message": "unauthorized"}}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _FakeResp()

    monkeypatch.setattr(
        "app.infrastructure.web_search.anysearch.provider.httpx.AsyncClient",
        lambda timeout=None: _FakeClient(),
    )
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_http_401_403"] == 1


def test_mcp_rpc_error_returns_empty(monkeypatch):
    """JSON-RPC error → fail-closed []。"""

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "bad params"}}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _FakeResp()

    monkeypatch.setattr(
        "app.infrastructure.web_search.anysearch.provider.httpx.AsyncClient",
        lambda timeout=None: _FakeClient(),
    )
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_http_other_error"] == 1


def test_report_stats_contract():
    provider = AnySearchWebSearchProvider()
    stats = provider.report_stats()
    assert stats["web_search_provider"] == "anysearch"
    assert "web_search_vertical_requests" in stats
    assert "web_search_http_429" in stats
    # 默认零值（审查 P1-4：契约存在性断言强化）
    assert stats["web_search_http_401_403"] == 0
    assert stats["web_search_http_5xx"] == 0
    assert stats["web_search_timeout"] == 0
    assert stats["web_search_connection_error"] == 0
    assert stats["web_search_empty_real_result"] == 0
    assert stats["web_search_parse_empty"] == 0
    assert stats["web_search_not_observable"] == 0


# ── 审查 P1-4：错误路径与边界补测 ─────────────────────────


class _FakeClient:
    """可注入响应/异常的 httpx.AsyncClient 替身。"""

    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        if self._exc is not None:
            raise self._exc
        return self._resp


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _patch_client(monkeypatch, resp=None, exc=None):
    monkeypatch.setattr(
        "app.infrastructure.web_search.anysearch.provider.httpx.AsyncClient",
        lambda timeout=None: _FakeClient(resp=resp, exc=exc),
    )


def test_mcp_http_500_classified(monkeypatch):
    _patch_client(monkeypatch, resp=_FakeResp(status_code=500, payload={}))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_http_5xx"] == 1


def test_mcp_http_429_classified(monkeypatch):
    _patch_client(monkeypatch, resp=_FakeResp(status_code=429, payload={}))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_http_429"] == 1


def test_mcp_http_302_classified_as_other(monkeypatch):
    """审查 P2-3：3xx 不再落到 not_observable。"""
    _patch_client(monkeypatch, resp=_FakeResp(status_code=302, payload={}))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_http_other_error"] == 1
    assert provider.report_stats()["web_search_not_observable"] == 0


def test_mcp_timeout_classified(monkeypatch):
    import httpx

    _patch_client(monkeypatch, exc=httpx.ConnectTimeout("timeout"))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_timeout"] == 1


def test_mcp_connect_error_classified(monkeypatch):
    import httpx

    _patch_client(monkeypatch, exc=httpx.ConnectError("refused"))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_connection_error"] == 1


def test_mcp_network_error_classified(monkeypatch):
    """审查 P2-2：NetworkError 子类（RemoteProtocolError）归 connection_error。"""
    import httpx

    _patch_client(monkeypatch, exc=httpx.RemoteProtocolError("reset"))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    assert provider.report_stats()["web_search_connection_error"] == 1


def test_mcp_http_200_non_json_returns_empty(monkeypatch):
    """HTTP 200 但 body 非 JSON → fail-closed [] + parse_empty 统计。"""
    _patch_client(monkeypatch, resp=_FakeResp(status_code=200, payload="<html>"))
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []


def test_mcp_empty_text_counts_real_empty(monkeypatch):
    """MCP 返回空文本（真实空结果）→ empty_real_result 统计（审查 P1-1）。"""
    _patch_client(
        monkeypatch,
        resp=_FakeResp(
            status_code=200,
            payload={"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": ""}]}},
        ),
    )
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    stats = provider.report_stats()
    assert stats["web_search_empty_real_result"] == 1
    assert stats["web_search_parse_empty"] == 0


def test_mcp_text_no_parse_counts_parse_empty(monkeypatch):
    """MCP 返回文本但解析不出 → parse_empty 统计（审查 P1-1）。"""
    _patch_client(
        monkeypatch,
        resp=_FakeResp(
            status_code=200,
            payload={
                "jsonrpc": "2.0",
                "result": {"content": [{"type": "text", "text": "## Search Results (0)"}]},
            },
        ),
    )
    provider = AnySearchWebSearchProvider(api_key="")
    assert _run(provider.search("康美药业 600518.SH 公告")) == []
    stats = provider.report_stats()
    assert stats["web_search_parse_empty"] == 1
    assert stats["web_search_empty_real_result"] == 0


def test_search_results_truncated_to_count(monkeypatch):
    """审查 P2-1：解析后防御性截断到 count。"""
    text = "## Search Results (5 results)\n\n" + "\n".join(
        f"### {i}. t{i}\n- {{\"close\":{i},\"trade_date\":\"2026081{i}\"}}" for i in range(1, 6)
    )
    provider = AnySearchWebSearchProvider(api_key="")

    async def _fake_mcp_call(tool, args):
        return text

    monkeypatch.setattr(provider, "_mcp_call", _fake_mcp_call)
    hits = _run(provider.search("贵州茅台 600519.SH 行情", max_results=2))
    assert len(hits) == 2


def test_search_none_query_returns_empty(monkeypatch):
    """审查 P2-4：query=None 不抛异常，返回 []。"""
    provider = AnySearchWebSearchProvider(api_key="")
    monkeypatch.setattr(
        provider, "_vertical_search", lambda *a, **k: (_ for _ in ()).throw(AssertionError())
    )
    assert _run(provider.search(None)) == []


def test_search_bad_max_results_defaults(monkeypatch):
    """审查 P2-5：max_results 非数值 → 默认值不抛异常。"""
    text = "## Search Results (1)\n\n### 1. t\n- {\"close\":1,\"trade_date\":\"20260818\"}"
    provider = AnySearchWebSearchProvider(api_key="")

    async def _fake_mcp_call(tool, args):
        return text

    monkeypatch.setattr(provider, "_mcp_call", _fake_mcp_call)
    assert _run(provider.search("贵州茅台 600519.SH 行情", max_results="abc")) != []


# ── 审查 P1-2：路由分支锁死 ────────────────────────────────


def _route_sub_domain(provider, query, code="600519.SH"):
    """直连 provider._vertical_search 拿工具参数（不联网，monkeypatch _mcp_call）。"""
    import asyncio

    seen = {}

    async def _fake_mcp_call(tool, args):
        seen["args"] = args
        return "## Search Results (0)"

    # 实例级替换：_vertical_search 内 self._mcp_call 走 fake
    original = provider._mcp_call
    provider._mcp_call = _fake_mcp_call  # type: ignore[method-assign]
    try:
        asyncio.run(provider._vertical_search(query, code, 3))
    finally:
        provider._mcp_call = original  # type: ignore[method-assign]
    return seen.get("args")


def test_route_quote_for_exchange_name(monkeypatch):
    """'上交所/深交所'行情查询 → finance.quote（审查 P1-2 负向排除）。"""
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "贵州茅台 600519.SH 上交所收盘价")
    assert args["sub_domain"] == "finance.quote"


def test_route_listing_first_for_listing_announcement(monkeypatch):
    """'上市公告书' → 上市日期 flash 分支，不被 announcement 抢占（审查 P1-2）。"""
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "康美药业 600518.SH 上市公告日期")
    assert args["sub_domain"] == "finance.news"
    assert args["sub_domain_params"]["type"] == "flash"
    assert args["sub_domain_params"].get("period") == "1y"


def test_route_announcement(monkeypatch):
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "康美药业 600518.SH 最新公告")
    assert args["sub_domain"] == "finance.news"
    assert args["sub_domain_params"]["type"] == "announcement"


def test_route_fundamental_income(monkeypatch):
    """'净利润/营收' → fundamental type=income（审查 P2-11）。"""
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "贵州茅台 600519.SH 净利润")
    assert args["sub_domain"] == "finance.fundamental"
    assert args["sub_domain_params"]["type"] == "income"


def test_route_fundamental_holder(monkeypatch):
    """'股东' → fundamental type=holder（审查 P2-11）。"""
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "贵州茅台 600519.SH 十大股东")
    assert args["sub_domain"] == "finance.fundamental"
    assert args["sub_domain_params"]["type"] == "holder"


def test_route_quote_default(monkeypatch):
    provider = AnySearchWebSearchProvider(api_key="")
    args = _route_sub_domain(provider, "贵州茅台 600519.SH 今天股价")
    assert args["sub_domain"] == "finance.quote"


# ── 审查 P2-6/P2-7/P2-8/P2-9：解析边界 ─────────────────────


def test_parse_json_multiple_objects_takes_first():
    """P2-6：条目含多个 JSON 对象时取第一个，不整条丢失。"""
    from app.infrastructure.web_search.anysearch.provider import _try_parse_json_line

    body = '{"a":1} 摘要 {"b":2}'
    obj = _try_parse_json_line(body)
    assert obj == {"a": 1}


def test_extract_url_with_fullwidth_punct():
    """P2-7：URL 后跟全角逗号/中文不被吞入。"""
    from app.infrastructure.web_search.anysearch.provider import _extract_markdown_url

    assert (
        _extract_markdown_url("- **URL**: https://xueqiu.com/S/SH600519，详情见下")
        == "https://xueqiu.com/S/SH600519"
    )


def test_vertical_date_validates():
    """P2-8：非法日期返回 None。"""
    from app.infrastructure.web_search.anysearch.provider import _vertical_date

    assert _vertical_date({"trade_date": "20260818"}) == "2026-08-18"
    assert _vertical_date({"trade_date": "20261340"}) is None  # 月 13 非法
    assert _vertical_date({"date": "2024-01-15"}) == "2024-01-15"
    assert _vertical_date({"date": "not-a-date"}) is None
    assert _vertical_date({}) is None


def test_extract_code_excludes_yyyymm():
    """P2-9：YYYYMM 年份月份不作为股票代码。"""
    assert _extract_ashare_code("202501 这家公司上市了") == ""
    assert _extract_ashare_code("2026 年 01 月公司上市") == ""


def test_extract_code_suffix_not_followed_by_letter():
    """P2-10：600519.SHX 之类不匹配。"""
    assert _extract_ashare_code("600519.SHX 是什么") == ""
