"""AnySearch 行情快照查询与字段级诚实降级。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.application.ports.web_search_provider import SearchResult
from app.application.services.web_search_service import web_search

MARKET_FIELD_LABELS: dict[str, str] = {
    "close": "收盘价",
    "pct_chg": "涨跌幅",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "pre_close": "昨收价",
    "turnover_rate": "换手率",
    "pe": "市盈率",
    "pb": "市净率",
    "pe_ttm": "滚动市盈率",
    "dividend_yield": "股息率",
    "total_mv": "总市值",
    "circ_mv": "流通市值",
    "amount": "成交额",
    "volume": "成交量",
}

# AnySearch finance.quote 沿用 A 股日线常用字段单位。
_FIELD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pe_ttm", ("滚动市盈率", "市盈率ttm", "市盈率 ttm", "pe_ttm", "ttm")),
    ("dividend_yield", ("股息率", "股息")),
    ("circ_mv", ("流通市值",)),
    ("total_mv", ("总市值", "市值")),
    ("turnover_rate", ("换手率",)),
    (
        "pct_chg",
        (
            "涨跌幅",
            "涨幅",
            "跌幅",
            "是涨还是跌",
            "涨还是跌",
            "股价波动",
            "市场表现",
            "近期表现",
            "近期走势",
            "最近走势",
            "今日表现",
            "今天表现",
            "表现如何",
            "表现怎么样",
        ),
    ),
    ("pre_close", ("昨收价", "前收盘价", "昨收")),
    ("open", ("开盘价", "开盘", "今开价", "今开")),
    ("high", ("最高价",)),
    ("low", ("最低价",)),
    ("amount", ("成交额",)),
    ("volume", ("成交量",)),
    ("pe", ("市盈率", "pe")),
    ("pb", ("市净率", "pb")),
    ("close", ("收盘价", "最新价", "当前市价", "现价", "股价", "行情")),
)

_HISTORY_RANGE_RE = re.compile(
    r"(?:近|过去|最近)\s*(?:一|二|三|四|五|六|七|八|九|十|半|\d+)\s*"
    r"(?:个)?(?:交易日|日|天|周|月|季度|年)"
)
_HISTORY_CUES = (
    "历史",
    "年内",
    "今年以来",
    "区间",
    "阶段最高",
    "阶段最低",
    "近期表现",
    "近期走势",
    "最近走势",
    "股价波动",
)
_PAIR_RE = re.compile(r"(?:^|\s)([a-z_]+)=([^\s]+)")
_DATE_RE = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")
_MIN_HISTORY_SPAN_DAYS = {
    "7d": 5,
    "30d": 24,
    "90d": 72,
    "180d": 144,
    "1y": 300,
    "5y": 1500,
}


@dataclass(frozen=True)
class MarketQuoteResult:
    status: Literal["ok", "no_data", "field_missing", "history_required"]
    field: str
    value: Decimal | None = None
    raw_value: str = ""
    trade_date: str = ""
    period_start: str = ""
    hit: SearchResult | None = None


def detect_market_quote_field(query: str) -> str | None:
    """识别单个可由 finance.quote 回答的行情字段。"""
    normalized = (query or "").lower()
    for field, aliases in _FIELD_PATTERNS:
        if any(alias in normalized for alias in aliases):
            return field
    return None


def requires_market_history(query: str) -> bool:
    """判断问题是否需要完整历史序列，避免用单日快照冒充区间结果。"""
    text = query or ""
    return bool(_HISTORY_RANGE_RE.search(text)) or any(
        cue in text for cue in _HISTORY_CUES
    )


def _history_period(query: str) -> str:
    text = query or ""
    if "今年以来" in text or "近一年" in text or "最近一年" in text:
        return "1y"
    if "近半年" in text or "最近半年" in text:
        return "180d"
    if "近三月" in text or "近3月" in text or "最近三个月" in text:
        return "90d"
    if "近一季度" in text or "近季度" in text:
        return "90d"
    if any(cue in text for cue in ("近一周", "近1周", "最近一周", "近7日", "近7天")):
        return "7d"
    if "近一月" in text or "近一个月" in text or "最近一个月" in text:
        return "30d"
    return "30d"


def query_market_quote(
    *, sec_name: str, wind_code: str, field: str, user_query: str
) -> MarketQuoteResult:
    """查询最新行情快照；目标字段缺失时不使用相邻字段替代。"""
    if field not in MARKET_FIELD_LABELS:
        return MarketQuoteResult(status="field_missing", field=field)
    historical = requires_market_history(user_query)
    period = _history_period(user_query) if historical else ""
    query = f"{sec_name} {wind_code} {MARKET_FIELD_LABELS[field]} 行情"
    if period:
        query += f" period={period}"
    hits = web_search(query, max_results=10)
    snapshots = [
        snapshot
        for hit in hits
        if (snapshot := _snapshot_from_hit(hit))[0] and snapshot[1]
    ]
    snapshots.sort(key=lambda item: item[0], reverse=True)
    if not snapshots:
        return MarketQuoteResult(status="no_data", field=field)

    if historical:
        if len(snapshots) < 2 or not _history_covers_period(snapshots, period):
            return MarketQuoteResult(status="history_required", field=field)
        if field == "pct_chg":
            first_close = snapshots[-1][1].get("close")
            last_close = snapshots[0][1].get("close")
            if not first_close or not last_close:
                return MarketQuoteResult(status="history_required", field=field)
            try:
                value = (Decimal(last_close) / Decimal(first_close) - 1) * 100
            except (InvalidOperation, ZeroDivisionError):
                return MarketQuoteResult(status="history_required", field=field)
            return MarketQuoteResult(
                status="ok",
                field=field,
                value=value,
                raw_value=f"{value:.4f}",
                trade_date=snapshots[0][0],
                period_start=snapshots[-1][0],
                hit=snapshots[0][2],
            )
        if field == "high":
            candidates = [item for item in snapshots if item[1].get("high")]
            if not candidates:
                return MarketQuoteResult(status="history_required", field=field)
            trade_date, values, hit = max(
                candidates, key=lambda item: Decimal(item[1]["high"])
            )
            raw_value = values["high"]
        else:
            trade_date, values, hit = snapshots[0]
            raw_value = values.get(field, "")
    else:
        trade_date, values, hit = snapshots[0]
        raw_value = values.get(field, "")
    if not raw_value:
        return MarketQuoteResult(
            status="field_missing", field=field, trade_date=trade_date, hit=hit
        )
    try:
        value = Decimal(raw_value.replace(",", ""))
    except InvalidOperation:
        return MarketQuoteResult(
            status="field_missing", field=field, trade_date=trade_date, hit=hit
        )
    return MarketQuoteResult(
        status="ok",
        field=field,
        value=value,
        raw_value=raw_value,
        trade_date=trade_date,
        period_start=snapshots[-1][0] if historical else "",
        hit=hit,
    )


def format_market_value(field: str, value: Decimal) -> str:
    """按 AnySearch finance.quote 契约格式化行情值。"""
    if field in ("close", "open", "high", "low", "pre_close"):
        return f"{value:,.2f}元"
    if field in ("pct_chg", "turnover_rate", "dividend_yield"):
        return f"{_trim_decimal(value, 4)}%"
    if field in ("pe", "pb", "pe_ttm"):
        return f"{_trim_decimal(value, 4)}倍"
    if field in ("total_mv", "circ_mv"):
        return f"{_trim_decimal(value / Decimal('10000'), 2)}亿元"
    return _trim_decimal(value, 4)


def _snapshot_from_hit(hit: SearchResult) -> tuple[str, dict[str, str], SearchResult]:
    values = {
        match.group(1): match.group(2).strip("，。;,.")
        for match in _PAIR_RE.finditer(hit.snippet or "")
        if match.group(1) in MARKET_FIELD_LABELS
        or match.group(1) in {"dv_ratio", "dv_ttm"}
        or match.group(1) == "trade_date"
    }
    if "dividend_yield" not in values:
        values["dividend_yield"] = values.get("dv_ratio") or values.get("dv_ttm", "")
    # AnySearch finance.quote 使用 vol，应用层统一称为 volume。
    vol_match = re.search(r"(?:^|\s)vol=([^\s]+)", hit.snippet or "")
    if vol_match and "volume" not in values:
        values["volume"] = vol_match.group(1).strip("，。;,.")
    trade_date = _normalize_date(values.get("trade_date", "") or hit.published_at or "")
    return trade_date, values, hit


def _normalize_date(raw: str) -> str:
    text = str(raw or "").strip()
    if not _DATE_RE.fullmatch(text):
        return ""
    digits = text.replace("-", "")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def _history_covers_period(
    snapshots: list[tuple[str, dict[str, str], SearchResult]], period: str
) -> bool:
    """确认返回序列覆盖请求区间，避免用最近少量样本冒充完整历史。"""
    from datetime import date

    dates = []
    for trade_date, _, _ in snapshots:
        try:
            dates.append(date.fromisoformat(trade_date))
        except ValueError:
            continue
    if len(dates) < 2:
        return False
    minimum_span = _MIN_HISTORY_SPAN_DAYS.get(period)
    if minimum_span is None:
        return True
    return (max(dates) - min(dates)).days >= minimum_span


def _trim_decimal(value: Decimal, places: int) -> str:
    rendered = f"{value:,.{places}f}"
    return rendered.rstrip("0").rstrip(".")
