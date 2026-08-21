"""indicator_semantics 服务单元测试 — v3.3.3 批次 A（方案 §8.1）。

表征目标（方案 §2.1/§2.3/§4.3）：
  - 「存货周转情况」绝不退化为「存货」(inventories)；
  - 「毛利率」识别为 r5_gross_margin；
  - 最长、最具体语义优先，匹配结果与词表输入顺序无关；
  - unsupported 精确短语与指标短语同表竞争，不被短词抢占；
  - 环比不得冒充同比（方案 §8.1）。
"""

from app.application.services.indicator_semantics import (
    resolve_indicator_semantics,
)


def test_inventory_turnover_question_routes_r4_turnover_days():
    """方案 §2.1 P1：存货周转情况 → r4_turnover_days，绝不 inventories。"""
    result = resolve_indicator_semantics("回到康美，存货周转情况如何")
    assert result.metric_ids == ["r4_turnover_days"]
    assert result.executable is True
    assert result.reason == ""


def test_inventory_turnover_days_exact():
    result = resolve_indicator_semantics("存货周转天数")
    assert result.metric_ids == ["r4_turnover_days"]
    assert result.confidence in ("exact", "alias")


def test_inventory_balance_still_inventories():
    """方案 §8.1：「存货是多少」仍是基础指标 inventories。"""
    result = resolve_indicator_semantics("存货是多少")
    assert result.metric_ids == ["inventories"]
    assert result.executable is True


def test_gross_margin_question_routes_r5_gross_margin():
    """方案 §2.3 P1：毛利率正常吗 → r5_gross_margin。"""
    result = resolve_indicator_semantics("毛利率正常吗")
    assert result.metric_ids == ["r5_gross_margin"]
    assert result.executable is True


def test_sales_gross_margin_alias():
    """官方语料 session 5/turn 9 同类表达：销售毛利率 → r5_gross_margin。"""
    result = resolve_indicator_semantics("2024财年第1季度销售毛利率是多少")
    assert result.metric_ids == ["r5_gross_margin"]


def test_revenue_growth_suffix():
    result = resolve_indicator_semantics("营业收入增速")
    assert result.metric_ids == ["operating_revenue_growth"]
    assert result.operation == "yoy_growth"


def test_receivable_growth_suffix():
    result = resolve_indicator_semantics("应收账款增速")
    assert result.metric_ids == ["accounts_receivable_growth"]


def test_mom_modifier_never_pretends_yoy():
    """方案 §8.1：营收环比 → 环比形态，不能冒充同比。"""
    result = resolve_indicator_semantics("营收环比")
    assert result.metric_ids == ["operating_revenue_mom"]
    assert result.operation == "mom"
    assert "growth" not in result.metric_ids[0]


def test_unsupported_turnover_rate_not_hijacked_by_short_word():
    """方案 §4.3：unsupported 精确短语与指标短语同表竞争。"""
    result = resolve_indicator_semantics("存货周转率是多少")
    assert result.executable is False
    assert result.reason == "unsupported"
    assert result.metric_ids == []
    assert result.matched_texts == ["存货周转率"]


def test_receivable_turnover_rate_unsupported():
    result = resolve_indicator_semantics("应收账款周转率")
    assert result.executable is False
    assert result.reason == "unsupported"


def test_longest_match_independent_of_table_order():
    """方案 §4.3/批次 A 完成标准：长短词匹配与输入顺序无关。"""
    long_query = "存货周转天数比存货更具体"
    assert resolve_indicator_semantics(long_query).metric_ids == ["r4_turnover_days"]
    assert resolve_indicator_semantics(long_query).metric_ids == (
        resolve_indicator_semantics(long_query).metric_ids
    )
    # 同一 query 重复解析结果稳定；「营业收入」(4字) 长于「毛利率」(3字)，
    # 最长匹配优先 → operating_revenue_growth
    first = resolve_indicator_semantics("毛利率和营业收入增速哪个更值得关注")
    second = resolve_indicator_semantics("毛利率和营业收入增速哪个更值得关注")
    assert first.metric_ids == second.metric_ids
    assert first.metric_ids == ["operating_revenue_growth"]


def test_sales_margin_longer_than_margin():
    """销售毛利率 > 毛利率：长词优先。"""
    result = resolve_indicator_semantics("销售毛利率如何")
    assert result.metric_ids == ["r5_gross_margin"]
    assert result.matched_texts == ["销售毛利率"]


def test_r5_modifier_not_faked_as_yoy():
    """批次 A 保守口径：r5 毛利率暂无同比能力，修饰词不得伪造。"""
    result = resolve_indicator_semantics("毛利率同比变化")
    assert result.executable is False
    assert result.reason == "modifier_unsupported"


def test_no_match_returns_none_confidence():
    result = resolve_indicator_semantics("今天天气怎么样")
    assert result.metric_ids == []
    assert result.executable is False
    assert result.confidence == "none"
    assert result.reason == "no_match"


def test_latest_quarter_period_hint():
    result = resolve_indicator_semantics("最新季度毛利率")
    assert result.metric_ids == ["r5_gross_margin"]
    assert result.period_hint == "latest_quarter"


def test_net_assets_is_mapped_to_parent_company_balance_sheet_field():
    result = resolve_indicator_semantics("公司2023年净资产是多少")
    assert result.metric_ids == ["net_assets"]
    assert result.executable is True


def test_known_market_metrics_are_honestly_unsupported_without_llm():
    """官方题型中的未覆盖资金/分红指标不得落入综合诊断。"""
    for query in (
        "恒生电子今天的主力净买入额是多少",
        "昨天贵州茅台的融资买入额是多少",
        "贵州茅台的融券卖出量是多少",
    ):
        result = resolve_indicator_semantics(query)
        assert result.executable is False
        assert result.reason == "unsupported"


# ── 8/17 方案 §5.7 接线：受约束 LLM 指标 fallback ─────────────


def test_no_match_off_mode_zero_llm(monkeypatch):
    """off 模式（生产默认）：LLM fallback 零调用，保持确定性。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "off")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    result = resolve_indicator_semantics("摊薄EPS是多少")
    assert result.reason == "no_match"
    assert calls == []


def test_no_match_mock_backend_zero_llm(monkeypatch):
    """mock 环境：LLM fallback 零调用。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    result = resolve_indicator_semantics("摊薄EPS是多少")
    assert result.reason == "no_match"
    assert calls == []


def test_llm_unsupported_indicator_honest(monkeypatch):
    """LLM 判定为指标但不在能力集 → 诚实 unsupported（任意变体覆盖）。"""
    from app.application.services.indicator_semantics import _IndicatorLLMOutput
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    output = _IndicatorLLMOutput(
        is_indicator=True, metric_phrase="股息率", reason="unsupported"
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: output
    )
    result = resolve_indicator_semantics("贵州茅台摊薄EPS是多少")
    assert result.executable is False
    assert result.reason == "unsupported"
    assert result.confidence == "llm"


def test_llm_not_indicator_keeps_no_match(monkeypatch):
    """LLM 判定非指标问法 → 保持 no_match（不误判）。"""
    from app.application.services.indicator_semantics import _IndicatorLLMOutput
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    output = _IndicatorLLMOutput(
        is_indicator=False, metric_phrase="", reason="not_indicator"
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: output
    )
    result = resolve_indicator_semantics("今天天气怎么样")
    assert result.reason == "no_match"
    assert result.confidence == "none"


def test_llm_mapped_uses_deterministic_canonical(monkeypatch):
    """LLM 判 mapped：canonical 仍由确定性词表决定（防 LLM 编造 ID）。"""
    from app.application.services.indicator_semantics import _IndicatorLLMOutput
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    output = _IndicatorLLMOutput(
        is_indicator=True, metric_phrase="销售毛利率", reason="mapped"
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: output
    )
    result = resolve_indicator_semantics("销售毛利率是多少")
    assert result.executable is True
    assert result.metric_ids == ["r5_gross_margin"]
    assert result.confidence in ("exact", "alias")


def test_llm_fallback_trigger_guard_zero_call(monkeypatch):
    """触发守卫：无数值问法词（多少/率/额…）→ 不调 LLM。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    result = resolve_indicator_semantics("康美和茅台对比")
    assert result.reason == "no_match"
    assert calls == []
