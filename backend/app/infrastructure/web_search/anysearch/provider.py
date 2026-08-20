"""AnySearch Provider — Phase E 会5 B1（8/19 接入）.

定位：
本项目是财报反欺诈智能问答，联网搜索优先用于补充 A 股结构化金融数据
（上市日期、公告、三表、行情）；带 A 股代码时走 MCP finance 垂直域。
无 A 股代码时，可走 REST /v1/search 通用入口，但必须经过相关性 Gate，
低相关结果 fail-closed → []，不直接接入回答链。

对接 AnySearch（https://anysearch.com）MCP 端点（垂直搜索唯一可靠路径）：
- `POST https://api.anysearch.com/mcp`（JSON-RPC 2.0, method="tools/call"）
- 中文金融数据只能走这里（REST /v1/search 的垂直参数实测无效/被忽略；
  且通用中文搜索质量差——调研文档
  `竞赛管理/docs/reference/AnySearch-API规范.md`，2026-08-19 实测）。

本 provider 只实现 finance 垂直域三子域：
- finance.quote        → 行情（close/pct_chg/pe/trade_date...）
- finance.news         → 公告/快讯（type=announcement 公告、type=flash 中文快讯）
- finance.fundamental  → 三表/指标（type=indicator/income/balance/cashflow/holder）

路由：从 query 提取 A 股代码（600519.SH / 000001.SZ / 830799.BJ），
有代码按查询意图选 finance 子域；无代码 → REST 通用搜索 + 相关性过滤。
所有失败路径 fail-closed → []（与 bocha provider 同语义）。

认证：Authorization: Bearer <as_sk_xxx>（可选，匿名可用但限流低）。
Key 注册：免费，一个邮箱即可（POST /v1/auth/email/register，见调研文档 §2.4）。
错误分类统计：401/403、429、5xx、timeout、连接错误、真实空 vs 解析空。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from urllib.parse import urlparse

import httpx

from app.application.ports.web_search_provider import SearchResult
from app.core.config import settings

logger = logging.getLogger(__name__)

# A 股代码：600519.SH / 000001.SZ / 830799.BJ / 430047.BJ（含 688 科创板）
_A_SHARE_CODE_RE = re.compile(
    r"(?<!\d)(\d{6})\.(SH|SZ|BJ)(?![\dA-Za-z])", re.IGNORECASE
)
# 裸 6 位数字（无交易所后缀）不作为强信号——需公司语境辅助，避免误判年份
_BARE_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
# 裸码误判负向过滤：形如 YYYYMM（年份+月份）的数字不是股票代码
_YYYYMM_RE = re.compile(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])$")

# 意图 cue（垂直子域选择）
# 审查 P1-2（8/19）："交易所"裸词会误命中"上交所/深交所"行情查询，
# 改为负向排除——先检查"上交所/深交所"（交易所非"上/深"开头时才是上市意图）。
_ANNOUNCEMENT_CUES = (
    "公告",
    "舆情",
    "新闻",
    "快讯",
    "披露",
    "处罚",
    "调查",
    "评级",
    "高管",
    "薪酬",
    "首发",
    "发行价",
)
_LISTING_CUES = ("上市", "挂牌", "什么时候上市", "何时上市", "ipo")
_EXCHANGE_NAME_QUOTE_CUES = ("上交所", "深交所", "北交所")  # 交易所名 = 行情语境
# "上市公告"语义 = 上市日期/公告历史，优先上市日期分支（P1-2：含"公告"的
# "上市公告书/上市公告日"不应被 announcement 抢占）
_LISTING_FIRST_CUES = ("上市公告", "上市日期", "什么时候上市", "何时上市")
_FUNDAMENTAL_CUES = ("财报", "三表", "营收", "净利润", "毛利率", "资产负债", "现金流", "指标", "股东")
# 其余带代码 → finance.quote（行情）

# finance.fundamental 子类型细分（P2-11：按 cue 映射 holder/cashflow/balance）
_FUNDAMENTAL_HOLDER_CUES = ("股东", "十大股东", "持股")
_FUNDAMENTAL_CASHFLOW_CUES = ("现金流", "现金流量")
_FUNDAMENTAL_BALANCE_CUES = ("资产负债", "资产负债表", "总资产", "总负债")
_FUNDAMENTAL_INCOME_CUES = ("营收", "营业收入", "净利润", "利润表", "毛利率")

# MCP 端点与客户端标识
_MCP_ENDPOINT = "https://api.anysearch.com/mcp"
_REST_SEARCH_ENDPOINT = "https://api.anysearch.com/v1/search"
_DEFAULT_CLIENT_HEADER = "truthnet/1.0"

# MCP 文本解析：单条 JSON 行最长截断（垂直行情 JSON 字段多，600 字符足够下游）
_SNIPPET_MAX = 600
# flash/announcement 默认只返回最近 1d；上市日期查询显式放宽窗口
# （P1-3：历史上市信息需长窗口，取值对齐 quote 的 period 可选值）
_FLASH_PERIOD = "1y"
_QUOTE_PERIOD_RE = re.compile(r"(?:^|\s)period=(7d|14d|30d|90d|180d|1y|5y)(?:\s|$)")


class AnySearchWebSearchProvider:
    """AnySearch A 股垂类 Provider（MCP finance 垂直域，纯垂类）."""

    def __init__(
        self,
        api_key: str | None = None,
        mcp_endpoint: str | None = None,
        timeout: float | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.ANYSEARCH_API_KEY
        self._mcp_endpoint = mcp_endpoint or _MCP_ENDPOINT
        self._timeout = (
            timeout if timeout is not None else settings.WEB_SEARCH_TIMEOUT_SECONDS
        )
        self._stats_lock = threading.Lock()
        self._stats = self._fresh_stats()

    @staticmethod
    def _fresh_stats() -> dict:
        return {
            "requests": 0,
            "vertical_requests": 0,
            "general_requests": 0,
            "http_401_403": 0,
            "http_429": 0,
            "http_5xx": 0,
            "http_other_error": 0,
            "timeout": 0,
            "connection_error": 0,
            "empty_real_result": 0,
            "parse_empty": 0,
            "relevance_filtered": 0,
            "not_observable": 0,
        }

    def _stat_inc(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    def report_stats(self) -> dict:
        """运行统计（供报告诊断；与 bocha 契约一致 + 垂类分流）。"""
        with self._stats_lock:
            return {
                "web_search_provider": "anysearch",
                "web_search_requests": self._stats["requests"],
                "web_search_vertical_requests": self._stats["vertical_requests"],
                "web_search_general_requests": self._stats["general_requests"],
                "web_search_http_401_403": self._stats["http_401_403"],
                "web_search_http_429": self._stats["http_429"],
                "web_search_http_5xx": self._stats["http_5xx"],
                "web_search_http_other_error": self._stats["http_other_error"],
                "web_search_timeout": self._stats["timeout"],
                "web_search_connection_error": self._stats["connection_error"],
                "web_search_empty_real_result": self._stats["empty_real_result"],
                "web_search_parse_empty": self._stats["parse_empty"],
                "web_search_relevance_filtered": self._stats["relevance_filtered"],
                "web_search_not_observable": self._stats["not_observable"],
            }

    @property
    def provider_name(self) -> str:
        return "anysearch"

    # ── 对外入口（WebSearchProvider Port）──────────────────

    async def search(
        self, query: str | None, max_results: int | None = None
    ) -> list[SearchResult]:
        """AnySearch 搜索；异常/无结果/低相关 → 空列表（诚实降级）。

        有 A 股代码：MCP finance 垂直域；无代码：REST 通用搜索 + 相关性 Gate。
        """
        self._stat_inc("requests")
        query = query or ""
        code = _extract_ashare_code(query)
        count = _safe_max_results(max_results)
        if not code:
            return await self._general_search(query, count)
        return await self._vertical_search(query, code, count)

    # ── REST 通用搜索 ───────────────────────────────────────

    async def _general_search(self, query: str, count: int) -> list[SearchResult]:
        """REST /v1/search 通用搜索；低相关结果过滤后返回。"""
        self._stat_inc("general_requests")
        if not (query or "").strip():
            return []
        payload = {
            "query": query,
            "format": "json",
            "max_results": count,
        }
        if _contains_cjk(query):
            payload.update({"zone": "cn", "language": "zh"})
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    _REST_SEARCH_ENDPOINT,
                    headers=self._headers(),
                    json=payload,
                )
            if resp.status_code != 200:
                raise _AnySearchHTTPError(resp.status_code)
            data = resp.json()
            code = data.get("code") if isinstance(data, dict) else None
            if code not in (None, 0, 200):
                raise _AnySearchRPCError(str(data.get("message") or data.get("msg") or code))
        except _AnySearchHTTPError as exc:
            self._classify_http(exc.status_code)
            return []
        except _AnySearchRPCError as exc:
            self._stat_inc("http_other_error")
            logger.warning("AnySearch REST 错误: %s", str(exc)[:200])
            return []
        except httpx.TimeoutException:
            self._stat_inc("timeout")
            logger.warning("AnySearch 通用搜索超时（query=%r）", query)
            return []
        except (httpx.ConnectError, httpx.NetworkError, httpx.ProtocolError) as exc:
            self._stat_inc("connection_error")
            logger.warning("AnySearch 通用搜索连接失败（query=%r）: %s", query, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            self._stat_inc("not_observable")
            logger.warning(
                "AnySearch 通用搜索未知异常（query=%r）: %s", query, str(exc)[:300]
            )
            return []

        hits = _parse_rest_results(data)
        if not hits:
            raw_results = (((data or {}).get("data") or {}).get("results") or [])
            if raw_results:
                self._stat_inc("parse_empty")
            else:
                self._stat_inc("empty_real_result")
            return []
        relevant = _filter_relevant_results(query, hits)
        if not relevant:
            self._stat_inc("relevance_filtered")
        return relevant[:count]

    # ── MCP 垂类搜索 ────────────────────────────────────────

    async def _vertical_search(
        self, query: str, code: str, count: int
    ) -> list[SearchResult]:
        """MCP finance 垂直域：按意图选 quote/news/fundamental。"""
        self._stat_inc("vertical_requests")
        ql = (query or "").lower()
        # 路由优先级（审查 P1-2 修正）：
        # 1. 上市日期/上市公告（listing 语义）优先——"上市公告书"不被公告抢占
        # 2. 公告/舆情 → finance.news announcement
        # 3. 上交所/深交所/北交所 → 行情语境（交易所名 = 行情，不是上市意图）
        # 4. 财报/指标/股东 → finance.fundamental（按 cue 细分 type）
        # 5. 其余 → finance.quote 行情
        if any(cue in ql for cue in _LISTING_FIRST_CUES) or any(
            cue in ql for cue in _LISTING_CUES
        ):
            # 上市日期：finance 域无结构化 listing_date 字段（8/19 探测结论），
            # 改走中文快讯（flash）——快讯文本/官网内容可能含「上市/挂牌」信息，
            # 由下游 extract_listing_date_from_hits 的语义关键字窗口解析；
            # period 放宽到 _FLASH_PERIOD（P1-3：默认 1d 取不到历史上市信息）。
            tool_args = {
                "query": query,
                "domain": "finance",
                "sub_domain": "finance.news",
                "sub_domain_params": {
                    "type": "flash",
                    "symbol": "",
                    "cn_code": code,
                    "period": _FLASH_PERIOD,
                },
                "max_results": count,
            }
        elif any(cue in ql for cue in _ANNOUNCEMENT_CUES):
            tool_args = {
                "query": query,
                "domain": "finance",
                "sub_domain": "finance.news",
                "sub_domain_params": {
                    "type": "announcement",
                    "symbol": "",
                    "cn_code": code,
                },
                "max_results": count,
            }
        elif any(cue in ql for cue in _EXCHANGE_NAME_QUOTE_CUES):
            tool_args = {
                "query": query,
                "domain": "finance",
                "sub_domain": "finance.quote",
                "sub_domain_params": {
                    "type": "stock",
                    "symbol": "",
                    "cn_code": code,
                },
                "max_results": count,
            }
        elif any(cue in ql for cue in _FUNDAMENTAL_CUES):
            ftype = _fundamental_type(ql)
            tool_args = {
                "query": query,
                "domain": "finance",
                "sub_domain": "finance.fundamental",
                "sub_domain_params": {
                    "type": ftype,
                    "symbol": "",
                    "cn_code": code,
                },
                "max_results": count,
            }
        else:
            period_match = _QUOTE_PERIOD_RE.search(ql)
            tool_args = {
                "query": query,
                "domain": "finance",
                "sub_domain": "finance.quote",
                "sub_domain_params": {
                    "type": "stock",
                    "symbol": "",
                    "cn_code": code,
                    **({"period": period_match.group(1)} if period_match else {}),
                },
                "max_results": count,
            }
        try:
            text = await self._mcp_call("search", tool_args)
        except _AnySearchHTTPError as exc:
            self._classify_http(exc.status_code)
            return []
        except _AnySearchRPCError as exc:
            self._stat_inc("http_other_error")
            logger.warning("AnySearch RPC 错误: %s", str(exc)[:200])
            return []
        except httpx.TimeoutException:
            self._stat_inc("timeout")
            logger.warning("AnySearch 垂类搜索超时（query=%r）", query)
            return []
        except (httpx.ConnectError, httpx.NetworkError, httpx.ProtocolError) as exc:
            # P2-2：传输层失败统一归 connection_error——NetworkError 子类
            # （ReadError/WriteError/CloseError）+ ProtocolError（RemoteProtocolError
            # /LocalProtocolError，TLS 中断/对端断连）与 ConnectError 同属
            # 连接失败（httpx 异常树：TransportError → Timeout/Network/Protocol）。
            self._stat_inc("connection_error")
            logger.warning("AnySearch 垂类搜索连接失败（query=%r）: %s", query, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            self._stat_inc("not_observable")
            logger.warning(
                "AnySearch 垂类搜索未知异常（query=%r）: %s", query, str(exc)[:300]
            )
            return []
        hits = _parse_mcp_text_results(text, query, code)
        if not hits:
            # P1-1：区分「服务端真无结果」与「有文本但解析不出」——
            # 空文本 = 真实空结果；非空但 0 命中 = 解析失败（统计契约与 bocha 对齐）
            if not (text or "").strip():
                self._stat_inc("empty_real_result")
            else:
                self._stat_inc("parse_empty")
        # P2-1：解析后防御性截断到 count（服务端可能返回多于请求数）
        return hits[:count]

    async def _mcp_call(self, tool_name: str, arguments: dict) -> str:
        """MCP tools/call；返回 content[0].text（渲染后的 Markdown/JSON 文本）。"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._mcp_endpoint, headers=self._headers(), json=payload
            )
            # P2-3：3xx/4xx/5xx 一律按 HTTP 错误分类（httpx 默认不跟随重定向，
            # 302/301 响应体非 JSON，若放过会误记 not_observable）
            if resp.status_code != 200:
                raise _AnySearchHTTPError(resp.status_code)
            data = resp.json()
            if "error" in data:
                raise _AnySearchRPCError(
                    str(data["error"].get("message", "unknown"))
                )
            result = data.get("result") or {}
            for part in result.get("content") or []:
                if part.get("type") == "text":
                    return str(part.get("text") or "")
            return ""

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Anysearch-Client": _DEFAULT_CLIENT_HEADER,
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _classify_http(self, status_code: int) -> None:
        """HTTP 状态分类统计（垂类失败共用）。"""
        if status_code in (401, 403):
            self._stat_inc("http_401_403")
        elif status_code == 429:
            self._stat_inc("http_429")
        elif status_code >= 500:
            self._stat_inc("http_5xx")
        else:
            self._stat_inc("http_other_error")
        logger.warning("AnySearch: HTTP %s（垂类搜索）", status_code)


class _AnySearchHTTPError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class _AnySearchRPCError(Exception):
    pass


# ── 解析纯函数（可单测）────────────────────────────────────


def _extract_ashare_code(query: str) -> str:
    """从 query 提取 A 股代码（600519.SH / 000001.SZ / 830799.BJ）。

    优先带交易所后缀的 6 位代码；无后缀时需公司语境辅助
    （避免把年份/数量误判为股票代码，P2-9：形如 YYYYMM 的年份月份排除）。
    """
    m = _A_SHARE_CODE_RE.search(query or "")
    if m:
        return f"{m.group(1)}.{m.group(2).upper()}"
    m2 = _BARE_CODE_RE.search(query or "")
    if (
        m2
        and not _YYYYMM_RE.fullmatch(m2.group(1))
        and any(cue in (query or "") for cue in ("股", "公司", "上市", "行情"))
    ):
        return f"{m2.group(1)}.SH"  # 无后缀默认 SH（可被垂直域修正）
    return ""


def _safe_max_results(max_results: int | None) -> int:
    """max_results 防御式归一（P2-5）：None/非数值/越界 → 默认 5，上限 10。"""
    try:
        if max_results is None:
            return max(1, min(int(settings.WEB_SEARCH_MAX_RESULTS), 10))
        return max(1, min(int(max_results), 10))
    except (TypeError, ValueError):
        return max(1, min(int(settings.WEB_SEARCH_MAX_RESULTS), 10))


def _fundamental_type(ql: str) -> str:
    """fundamental 子类型按 cue 细分（P2-11：股东/现金流/资产负债/营收 → 对应报表）。"""
    if any(cue in ql for cue in _FUNDAMENTAL_HOLDER_CUES):
        return "holder"
    if any(cue in ql for cue in _FUNDAMENTAL_CASHFLOW_CUES):
        return "cashflow"
    if any(cue in ql for cue in _FUNDAMENTAL_BALANCE_CUES):
        return "balance"
    if any(cue in ql for cue in _FUNDAMENTAL_INCOME_CUES):
        return "income"
    return "indicator"


def _parse_mcp_text_results(
    text: str, query: str, code: str
) -> list[SearchResult]:
    """MCP 垂类搜索结果（Markdown 文本）→ SearchResult 列表。

    MCP search 返回渲染 Markdown：`### N. <标题>\n- {"json":...}`——
    垂直行情/公告/三表数据以 JSON 行内嵌。解析策略：
    1. 逐条 `### N. ` 标题 + 下一行 JSON 对象 → 结构化字段；
    2. 无 `###` 结构时，全文正则提取 JSON 对象行；
    3. 全部失败 → 把整体文本作为单条 snippet（保底，防丢信息）。
    """
    if not text:
        return []
    out: list[SearchResult] = []
    for title, body in _split_mcp_entries(text):
        obj = _try_parse_json_line(body)
        if obj:
            sr = _search_result_from_vertical_json(obj, title, code)
            if sr is not None:
                out.append(sr)
                continue
        if body.strip():
            # 非结构化条目：从 Markdown 提取 URL（`- **URL**: https://...` 行，
            # 公告/快讯实测格式），并清理 URL 行后作为 snippet
            url = _extract_markdown_url(body)
            snippet = "\n".join(
                line for line in body.splitlines() if "**URL**" not in line
            ).strip()
            out.append(
                SearchResult(
                    title=title or query,
                    url=url,
                    snippet=snippet[:_SNIPPET_MAX],
                    domain=_hostname(url),
                    published_at=None,
                    source="anysearch",
                )
            )
    if out:
        return out
    cleaned = text.strip()
    # 空结果计数头（"## Search Results (0)"）不是有效条目 → 真实空结果
    if _is_empty_results_header(cleaned):
        return []
    if cleaned:
        return [
            SearchResult(
                title=query,
                url="",
                snippet=cleaned[:_SNIPPET_MAX],
                domain="",
                published_at=None,
                source="anysearch",
            )
        ]
    return []


def _parse_rest_results(payload: dict) -> list[SearchResult]:
    """REST /v1/search 结构化结果 → SearchResult。

    AnySearch REST 实测结构：`data.results[{title,url,snippet,content}]`；
    兼容历史字段 name/summary/description。content 可能很长，只作为 snippet
    兜底截断，不把整页内容塞进证据链。
    """
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, list):
        return []
    out: list[SearchResult] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("link") or "")
        title = str(item.get("title") or item.get("name") or "")
        snippet = str(
            item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("content")
            or ""
        )
        if not (url or title or snippet):
            continue
        out.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet[:_SNIPPET_MAX],
                domain=_hostname(url),
                published_at=None,
                source="anysearch",
            )
        )
    return out


_GENERIC_QUERY_WORDS = (
    "行业",
    "产业",
    "市场",
    "公司",
    "企业",
    "技术",
    "趋势",
    "发展",
    "现状",
    "近期",
    "最新",
    "观点",
    "研报",
    "报告",
    "分析",
    "研究",
    "情况",
    "影响",
    "风险",
    "机会",
    "如何",
    "怎么样",
    "是什么",
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _query_relevance_terms(query: str) -> list[str]:
    """提取保守相关性词：去掉通用泛词后保留主体词/代码/英文词。"""
    q = (query or "").strip().lower()
    terms = [m.group(0) for m in _TOKEN_RE.finditer(q)]
    cjk_text = re.sub(r"[^\u4e00-\u9fff]+", " ", q)
    for word in _GENERIC_QUERY_WORDS:
        cjk_text = cjk_text.replace(word, " ")
    for run in _CJK_RUN_RE.findall(cjk_text):
        if len(run) >= 2:
            terms.append(run)
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            deduped.append(term)
    return deduped


def _filter_relevant_results(
    query: str, hits: list[SearchResult]
) -> list[SearchResult]:
    """通用搜索相关性 Gate。

    中文通用搜索实测容易跑偏；若能提取主体词，则每条结果必须命中至少一个
    主体词。提不出主体词时不额外过滤，交给上游 off/限流/业务降级。
    """
    terms = _query_relevance_terms(query)
    if not terms:
        return hits
    relevant: list[SearchResult] = []
    for hit in hits:
        haystack = f"{hit.title}\n{hit.snippet}\n{hit.url}".lower()
        if any(term in haystack for term in terms):
            relevant.append(hit)
    return relevant


_EMPTY_RESULTS_HEADER_RE = re.compile(r"^##\s*Search Results\s*\(\s*0\s*\)", re.IGNORECASE)


def _is_empty_results_header(text: str) -> bool:
    """MCP 空结果计数头（`## Search Results (0 results)`）→ 真实空结果。"""
    return bool(_EMPTY_RESULTS_HEADER_RE.match(text or ""))


def _split_mcp_entries(text: str) -> list[tuple[str, str]]:
    """把 MCP Markdown 切成 (标题, 正文) 列表。

    `### N. <title>`（带序号）开新条目；`## 分组标题`（无序号，如
    "## Search Results (N results)"）是分组头，直接丢弃不产出条目；
    无标题的连续段落归入前一条目。
    """
    entries: list[tuple[str, str]] = []
    current_title = ""
    current_body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*#{1,6}\s*\d+\.\s*(.*)$", line)
        if m:
            if current_title or any(b.strip() for b in current_body):
                entries.append((current_title, "\n".join(current_body).strip()))
            current_title = m.group(1).strip()
            current_body = []
        elif re.match(r"^\s*##\s", line):
            continue  # 分组头（无序号）丢弃：`## Search Results (N)` 是结果计数头
        else:
            current_body.append(line)
    if current_title or any(b.strip() for b in current_body):
        entries.append((current_title, "\n".join(current_body).strip()))
    return entries


def _try_parse_json_line(body: str) -> dict | None:
    """从条目正文提取第一个 JSON 对象；失败 → None。

    P2-6：回退分支用 JSONDecoder().raw_decode 逐位置尝试，避免贪婪正则
    `{.*}` 在"一条目含多个 JSON 对象"时整条丢失。
    """
    for line in body.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            continue
    # 回退：正文内嵌 JSON（raw_decode 取第一个完整对象）
    decoder = json.JSONDecoder()
    for i, ch in enumerate(body or ""):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(body[i:])
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            continue
    return None


# URL 终止字符集：半角 + 全角标点（P2-7：\S+ 会吞入全角逗号/中文）
_URL_TERMINATORS = ".,;:)]}，。！？；：、」』）】"
# URL 字符类：非空白且非全角标点/中文（避免 \S+ 吞入紧贴中文）
_URL_CHARS = r"[^\s，。！？；：、」』）】<>\[\]\"']"
_URL_LINE_RE = re.compile(rf"\*\*URL\*\*:\s*(https?://{_URL_CHARS}+)")


def _extract_markdown_url(body: str) -> str:
    """从 Markdown 条目提取 URL（`- **URL**: https://...` 行，公告/快讯实测）。

    URL 行可能换行（`- **URL**: https://...\n- 摘要`），取首个 http(s) 链接；
    字符类排除全角标点/中文（P2-7），URL 后紧跟「，详情」等不被吞入。
    """
    m = _URL_LINE_RE.search(body or "")
    if m:
        return m.group(1).rstrip(_URL_TERMINATORS)
    m2 = re.search(rf"https?://{_URL_CHARS}+", body or "")
    if m2:
        return m2.group(0).rstrip(_URL_TERMINATORS)
    return ""


def _search_result_from_vertical_json(
    obj: dict, title: str, code: str
) -> SearchResult | None:
    """垂直域 JSON → SearchResult。

    - finance.quote 行情：close/pct_chg/pe/trade_date...
    - finance.news 公告：title/date/url/description...
    - finance.fundamental：报表/指标字段
    snippet 组装关键字段（供下游 snippet/title 解析）；trade_date/date 作为
    published_at（垂直域结构化日期，非网页发布时间，语义安全）。
    """
    if not isinstance(obj, dict) or not obj:
        return None
    url = str(obj.get("url") or obj.get("link") or "")
    item_title = str(obj.get("title") or obj.get("name") or title or code)
    snippet = str(
        obj.get("snippet")
        or obj.get("description")
        or obj.get("summary")
        or ""
    )
    if not snippet:
        parts = []
        for key in (
            # quote 行情
            "trade_date",
            "close",
            "pct_chg",
            "open",
            "high",
            "low",
            "pre_close",
            "pe",
            "pb",
            "pe_ttm",
            "turnover_rate",
            "total_mv",
            "circ_mv",
            "vol",
            "volume",
            "amount",
            # income 利润表（8/19 探测实测字段）
            "end_date",
            "revenue",
            "n_income",
            "operate_profit",
            "total_profit",
            "basic_eps",
            "diluted_eps",
            "ann_date",
            # balance 资产负债表
            "total_assets",
            "total_liab",
            "total_hldr_eqy_exc_min_int",
            # cashflow 现金流
            "n_cashflow_act",
            "n_cashflow_inv",
            "n_cash_flows_fnc_act",
            # indicator 指标
            "roe",
            "grossprofit_margin",
            "netprofit_margin",
            "debt_to_assets",
            "period",
            "eps",
            "net_profit",
            # news/公告通用
            "date",
            "content",
        ):
            if key in obj and obj[key] not in (None, "", "null"):
                parts.append(f"{key}={obj[key]}")
        snippet = " ".join(parts)[:_SNIPPET_MAX]
    if not (url or snippet or item_title):
        return None
    return SearchResult(
        title=item_title,
        url=url,
        snippet=snippet,
        domain=_hostname(url),
        published_at=_vertical_date(obj),
        source="anysearch",
    )


def _vertical_date(obj: dict) -> str | None:
    """垂直域结构化日期 → 'YYYY-MM-DD'（trade_date=YYYYMMDD / date / end_date）。

    P2-8：8 位纯数字校验月/日合法性（20261340 → None）；ISO 格式只接受
    YYYY-MM-DD 前缀且校验日期合法；其余返回 None（不输出脏日期）。
    """
    raw = (
        obj.get("trade_date")
        or obj.get("end_date")
        or obj.get("ann_date")
        or obj.get("date")
        or obj.get("period")
        or ""
    )
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) == 8 and s.isdigit():
        try:
            year, month, day = int(s[0:4]), int(s[4:6]), int(s[6:8])
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return None
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:  # noqa: BLE001
            return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:  # noqa: BLE001
        return ""
