"""AnySearch 行情字段级查询测试。"""

from decimal import Decimal

from app.application.ports.web_search_provider import SearchResult
from app.application.services import market_quote_service as service


def _hit(date: str, snippet: str) -> SearchResult:
    return SearchResult(
        title=f"600519.SH {date} 日线行情",
        snippet=snippet,
        published_at=f"{date[:4]}-{date[4:6]}-{date[6:]}",
        source="anysearch",
    )


def test_detect_market_quote_fields():
    assert service.detect_market_quote_field("贵州茅台今天股价") == "close"
    assert service.detect_market_quote_field("恒生电子换手率") == "turnover_rate"
    assert service.detect_market_quote_field("东吴证券总市值") == "total_mv"
    assert service.detect_market_quote_field("东吴证券今日成交额") == "amount"
    assert service.detect_market_quote_field("东吴证券今日成交量") == "volume"
    assert service.detect_market_quote_field("平安银行今日是涨还是跌") == "pct_chg"
    assert service.detect_market_quote_field("平安银行的当前市价") == "close"
    assert service.detect_market_quote_field("雷柏科技近期走势") == "pct_chg"


def test_query_market_quote_selects_latest_snapshot(monkeypatch):
    monkeypatch.setattr(
        service,
        "web_search",
        lambda query, **kwargs: [
            _hit("20260819", "trade_date=20260819 close=1307.88"),
            _hit("20260820", "trade_date=20260820 close=1291.5 pct_chg=-1.2524"),
        ],
    )

    result = service.query_market_quote(
        sec_name="贵州茅台",
        wind_code="600519.SH",
        field="close",
        user_query="贵州茅台今天股价",
    )

    assert result.status == "ok"
    assert result.trade_date == "2026-08-20"
    assert result.value == Decimal("1291.5")


def test_volume_uses_anysearch_vol_field_and_not_amount(monkeypatch):
    monkeypatch.setattr(
        service,
        "web_search",
        lambda query, **kwargs: [
            _hit(
                "20260820",
                "trade_date=20260820 amount=3280474.226 vol=230690.17",
            )
        ],
    )

    result = service.query_market_quote(
        sec_name="东吴证券",
        wind_code="601555.SH",
        field="volume",
        user_query="东吴证券今日成交量",
    )

    assert result.status == "ok"
    assert result.value == Decimal("230690.17")


def test_historical_range_does_not_use_daily_snapshot(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "web_search",
        lambda query, **kwargs: (
            calls.append(query) or [_hit("20260820", "close=110")]
        ),
    )

    result = service.query_market_quote(
        sec_name="中兴通讯",
        wind_code="000063.SZ",
        field="pct_chg",
        user_query="中兴通讯的近一月涨跌幅",
    )

    assert result.status == "history_required"
    assert len(calls) == 1
    assert "period=30d" in calls[0]


def test_history_period_preserves_week_and_three_month_ranges(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "web_search",
        lambda query, **kwargs: (
            calls.append(query) or [_hit("20260820", "close=110")]
        ),
    )
    for query, expected in (("近一周涨跌幅", "7d"), ("近3月涨跌幅", "90d")):
        service.query_market_quote(
            sec_name="中兴通讯",
            wind_code="000063.SZ",
            field="pct_chg",
            user_query=query,
        )
        assert f"period={expected}" in calls[-1]


def test_historical_pct_change_uses_first_and_last_close(monkeypatch):
    monkeypatch.setattr(
        service,
        "web_search",
        lambda query, **kwargs: [
            _hit("20260820", "trade_date=20260820 close=110"),
            _hit("20260720", "trade_date=20260720 close=100"),
        ],
    )
    result = service.query_market_quote(
        sec_name="中兴通讯",
        wind_code="000063.SZ",
        field="pct_chg",
        user_query="中兴通讯近一月涨跌幅",
    )
    assert result.status == "ok"
    assert result.value == Decimal("10")
    assert result.trade_date == "2026-08-20"
    assert result.period_start == "2026-07-20"


def test_market_value_units_are_formatted_from_quote_contract():
    assert service.format_market_value("close", Decimal("1291.5")) == "1,291.50元"
    assert service.format_market_value("turnover_rate", Decimal("0.2026")) == "0.2026%"
    assert service.format_market_value("total_mv", Decimal("161448038.64")) == (
        "16,144.8亿元"
    )
    assert service.format_market_value("amount", Decimal("3280474.226")) == (
        "3,280,474.226"
    )
