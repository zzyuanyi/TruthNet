from datetime import date

import pytest

from app.agents.nodes.generate_answer import _answer_indicator
from app.agents.nodes.plan_modules import detect_indicator, plan_modules_node
from app.agents.state import CompanyRef, ExecutionPlan, RuntimeState
from app.application.services.indicator_query_service import (
    IndicatorObservation,
    IndicatorQueryResult,
    query_indicator,
    query_indicator_cagr,
    query_indicator_trend,
    query_quarter_mom,
    query_quarter_value,
)
from app.domain.finance._fetch import SeriesResult


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_603180_SH",
        wind_code="603180.SH",
        sec_name="金牌家居",
        exchange="XSHG",
    )


def test_detect_indicator_and_diagnostic_guard():
    assert detect_indicator("金牌家居的资产负债率是多少") == "debt_to_assets"
    assert detect_indicator("金牌家居的总资产") == "total_assets"
    assert detect_indicator("金牌家居的应收账款周转率") == "unsupported"
    assert detect_indicator("分析金牌家居的资产负债率风险") is None


def test_indicator_plan_keeps_requested_period():
    out = plan_modules_node(
        {
            "user_query": "金牌家居 2024 年报的资产负债率是多少",
            "company": _company(),
            "request_context": None,
        }
    )
    plan = out["plan"]
    assert plan.intent == "indicator"
    assert plan.indicator == "debt_to_assets"
    assert plan.requested_modules == []
    assert plan.as_of == date(2024, 12, 31)
    assert plan.as_of_kind == "report_period"


def test_query_indicator_requires_same_exact_period(monkeypatch):
    data = {
        "tot_liab": SeriesResult([40.0], periods=["20241231"]),
        "tot_assets": SeriesResult([100.0], periods=["20241231"]),
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_indicator(
        "603180.SH", "debt_to_assets", as_of="20241231", require_exact_period=True
    )
    assert result.status == "ok"
    assert result.period == "20241231"
    assert result.value == 40.0

    missing = query_indicator(
        "603180.SH", "debt_to_assets", as_of="20250930", require_exact_period=True
    )
    assert missing.status == "insufficient_data"


def test_answer_indicator_is_short_and_traceable(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="debt_to_assets",
            label="资产负债率",
            period="20241231",
            value=40.0,
            unit="percent",
            observations=[
                IndicatorObservation("tot_liab", "balance_sheet", 40.0),
                IndicatorObservation("tot_assets", "balance_sheet", 100.0),
            ],
        ),
    )
    state = {
        "company": _company(),
        "plan": ExecutionPlan(
            intent="indicator",
            indicator="debt_to_assets",
            as_of=date(2024, 12, 31),
            as_of_kind="report_period",
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_indicator(state, "debt_to_assets")
    answer = out["final_response"].answer
    assert "资产负债率为 40.00%（2024-12-31，母公司口径）" in answer
    assert len(answer.splitlines()) <= 2
    assert len(out["evidence"]) == 2
    assert all(item.evidence_id.startswith("ev_fin_") for item in out["evidence"])
    assert out["claims"][0].evidence_ids == [
        item.evidence_id for item in out["evidence"]
    ]


def test_answer_unsupported_indicator_is_honest():
    out = _answer_indicator(
        {"company": _company(), "runtime": RuntimeState(turn_id="t")},
        "unsupported",
    )
    assert "该指标暂未覆盖" in out["final_response"].answer
    assert out["claims"] == []
    assert out["evidence"] == []


# ── 2026-08-12 三轮审查修订批 2：后缀路由 / 严格同比 / 双期间 ──


def test_detect_indicator_growth_and_mom_suffixes():
    """先基础指标、后环同比；无指标不误判。"""
    assert detect_indicator("金牌家居的资产负债率同比") == "debt_to_assets_growth"
    assert detect_indicator("金牌家居的营收增速") == "operating_revenue_growth"
    assert detect_indicator("金牌家居的应收账款环比") == "accounts_receivable_mom"
    assert detect_indicator("金牌家居环比怎么样") is None
    assert detect_indicator("金牌家居的经营现金流同比") == "operating_cash_flow_growth"
    assert detect_indicator("金牌家居的存货同比") == "inventories_growth"


def test_detect_indicator_colloquial_words():
    """口语词映射 + "分析"不再阻断指标短答。"""
    assert detect_indicator("金牌家居的营收") == "operating_revenue"
    assert detect_indicator("金牌家居的负债率") == "debt_to_assets"
    assert detect_indicator("金牌家居的现金流") == "operating_cash_flow"
    assert detect_indicator("分析一下金牌家居的资产负债率") == "debt_to_assets"
    # 诊断词（异常/原因）仍路由到诊断分支
    assert detect_indicator("分析金牌家居资产负债率异常的原因") is None


def test_query_indicator_mom_returns_labeled_unsupported():
    """环比 → 带 label 的 unsupported（非裸值，供文案显示指标名）。"""
    result = query_indicator("603180.SH", "operating_revenue_mom")
    assert result.status == "unsupported"
    assert result.label == "营业收入"
    assert result.indicator == "operating_revenue_mom"


def test_query_indicator_yoy_growth_strict(monkeypatch):
    """严格同比：精确去年同期；双期间 observations；label 含同比增速。"""
    data = {
        "oper_rev": SeriesResult(
            [1.0e8, 1.1e8, 1.21e8],
            periods=["20231231", "20241231", "20251231"],
        ),
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_indicator(
        "603180.SH",
        "operating_revenue_growth",
        as_of="20251231",
        require_exact_period=True,
    )
    assert result.status == "ok"
    assert result.value == 10.0  # (121-110)/110 * 100
    assert result.period == "20251231"
    assert result.comparison_period == "20241231"
    assert result.label == "营业收入同比增速"
    assert [o.period for o in result.observations] == ["20251231", "20241231"]

    # 去年同期缺失 → insufficient_data（不回退两年前）
    missing = query_indicator(
        "603180.SH",
        "operating_revenue_growth",
        as_of="20250331",
        require_exact_period=True,
    )
    assert missing.status == "insufficient_data"


def test_query_indicator_yoy_growth_negative_and_default_latest(monkeypatch):
    """负增长正确 + 非 require_exact 取最近期。"""
    data = {
        "net_profit_excl_min_int_inc": SeriesResult(
            [2.0e8, 1.0e8], periods=["20241231", "20251231"]
        ),
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_indicator("603180.SH", "net_profit_growth")
    assert result.status == "ok"
    assert result.value == -50.0
    assert result.comparison_period == "20241231"


def test_query_indicator_growth_two_field_unsupported(monkeypatch):
    """双字段指标（资产负债率）增速 → unsupported。"""
    result = query_indicator("603180.SH", "debt_to_assets_growth")
    assert result.status == "unsupported"
    assert result.label == "资产负债率"


def test_query_indicator_cagr_rejects_inconsistent_annual_source(monkeypatch):
    """年报远低于同年三季报时不输出看似精确的错误 CAGR。"""
    data = SeriesResult(
        [100.0, 60.0, 90.0, 110.0, 1.0],
        periods=["20231231", "20240930", "20241231", "20250930", "20251231"],
    )
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda *args, **kwargs: data,
    )
    result = query_indicator_cagr("603180.SH", "operating_revenue", years=3)
    assert result.status == "insufficient_data"
    assert result.value is None


def test_query_indicator_rejects_inconsistent_annual_revenue(monkeypatch):
    """年度累计营收为零但同年三季报有值时，不把零展示成真实营收。"""
    data = SeriesResult(
        [110.0, 0.0],
        periods=["20250930", "20251231"],
    )
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda *args, **kwargs: data,
    )
    result = query_indicator("600606.SH", "operating_revenue")
    assert result.status == "insufficient_data"
    assert result.value is None


def test_query_indicator_rejects_zero_revenue_placeholder(monkeypatch):
    data = SeriesResult([0.0], periods=["20251231"])
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda *args, **kwargs: data,
    )
    result = query_indicator("600606.SH", "operating_revenue")
    assert result.status == "insufficient_data"
    assert result.value is None


def test_registry_metric_trend_reuses_period_evaluator(monkeypatch):
    data = {
        "oper_rev": SeriesResult(
            [100.0, 110.0, 120.0],
            periods=["20231231", "20241231", "20251231"],
        ),
        "less_oper_cost": SeriesResult(
            [60.0, 66.0, 84.0],
            periods=["20231231", "20241231", "20251231"],
        ),
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    rows = query_indicator_trend("603180.SH", "r5_gross_margin")
    assert [row.period for row in rows] == ["20231231", "20241231", "20251231"]
    assert [row.value for row in rows] == [0.4, 0.4, 0.3]


def test_query_quarter_value_subtracts_same_year_cumulative_prior(monkeypatch):
    data = {
        "net_profit_excl_min_int_inc": SeriesResult(
            [10.0, 25.0, 55.0, 100.0],
            periods=["20250331", "20250630", "20250930", "20251231"],
        )
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_quarter_value("603180.SH", "net_profit")
    assert result.status == "ok"
    assert result.period == "20251231"
    assert result.value == 45.0


def test_query_indicator_growth_denominator_protection(monkeypatch):
    """yoy_growth 分母绝对值 <1 万 → insufficient_data。"""
    data = {
        "inventories": SeriesResult([8000.0, 9000.0], periods=["20241231", "20251231"]),
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_indicator(
        "603180.SH",
        "inventories_growth",
        as_of="20251231",
        require_exact_period=True,
    )
    assert result.status == "insufficient_data"


def test_answer_indicator_growth_dual_evidence(monkeypatch):
    """增速分支：正负文案 + 双期间两条 evidence（id/period 各自正确）。"""
    from app.agents.nodes.generate_answer import _answer_indicator

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="accounts_receivable_growth",
            label="应收账款同比增速",
            period="20251231",
            value=-8.5,
            unit="percent",
            observations=[
                IndicatorObservation(
                    "acct_rcv", "balance_sheet", 1.83e8, period="20251231"
                ),
                IndicatorObservation(
                    "acct_rcv", "balance_sheet", 2.0e8, period="20241231"
                ),
            ],
            comparison_period="20241231",
        ),
    )
    state = {
        "company": _company(),
        "plan": ExecutionPlan(
            intent="indicator",
            indicator="accounts_receivable_growth",
            as_of=date(2025, 12, 31),
            as_of_kind="report_period",
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_indicator(state, "accounts_receivable_growth")
    answer = out["final_response"].answer
    assert "同比下降 8.50%" in answer
    assert "2025-12-31 较 2024-12-31" in answer
    assert len(out["evidence"]) == 2
    ids = [item.evidence_id for item in out["evidence"]]
    assert len(set(ids)) == 2  # 双期间 evidence_id 不同
    assert [item.period for item in out["evidence"]] == ["20251231", "20241231"]
    assert out["claims"][0].evidence_ids == ids


def test_answer_indicator_positive_growth_text(monkeypatch):
    """正增速文案：同比增长。"""
    from app.agents.nodes.generate_answer import _answer_indicator

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="operating_revenue_growth",
            label="营业收入同比增速",
            period="20251231",
            value=8.5,
            unit="percent",
            observations=[
                IndicatorObservation(
                    "oper_rev", "income_statement", 1.08e8, period="20251231"
                ),
                IndicatorObservation(
                    "oper_rev", "income_statement", 1.0e8, period="20241231"
                ),
            ],
            comparison_period="20241231",
        ),
    )
    state = {
        "company": _company(),
        "plan": ExecutionPlan(
            intent="indicator",
            indicator="operating_revenue_growth",
            as_of=date(2025, 12, 31),
            as_of_kind="report_period",
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_indicator(state, "operating_revenue_growth")
    assert "同比增长 8.50%" in out["final_response"].answer


def test_answer_indicator_quarter_mom(monkeypatch):
    """单季度环比走真实计算结果，不再主动降级为 unsupported。"""
    from app.agents.nodes.generate_answer import _answer_indicator

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_quarter_mom",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="operating_revenue_quarter_mom",
            label="单季度营业收入环比增长率",
            period="20250331",
            comparison_period="20241231",
            value=50.0,
            unit="percent",
            observations=[
                IndicatorObservation(
                    "oper_rev", "income_statement", 45.0, period="20250331"
                ),
                IndicatorObservation(
                    "oper_rev", "income_statement", 30.0, period="20241231"
                ),
            ],
        ),
    )
    out = _answer_indicator(
        {
            "company": _company(),
            "plan": ExecutionPlan(
                intent="indicator",
                indicator="operating_revenue_mom",
                answer_operation="quarter_mom",
            ),
            "runtime": RuntimeState(turn_id="t"),
        },
        "operating_revenue_mom",
    )
    answer = out["final_response"].answer
    assert "单季度营业收入环比增长率为 50.00%" in answer
    assert "2025-03-31" in answer


def test_query_quarter_mom_crosses_year_boundary(monkeypatch):
    data = {
        "oper_rev": SeriesResult(
            [70_000_000.0, 100_000_000.0, 45_000_000.0],
            periods=["20240930", "20241231", "20250331"],
        )
    }
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda _code, field, periods, as_of: data[field],
    )
    result = query_quarter_mom("603180.SH", "operating_revenue")
    assert result.status == "ok"
    assert result.period == "20250331"
    assert result.comparison_period == "20241231"
    assert result.value == pytest.approx(50.0)
    assert [item.value for item in result.observations] == [45_000_000.0, 30_000_000.0]


# ── v3.3.3 批次 B：registry 指标查询适配（方案 §5.3）────────────


def _fake_series(field_name):
    """两期升序假序列：2024Q3 / 2024A。"""
    data = {
        "inventories": [("20240930", 100.0), ("20241231", 120.0)],
        "less_oper_cost": [("20240930", 300.0), ("20241231", 320.0)],
        "oper_rev": [("20240930", 500.0), ("20241231", 520.0)],
    }
    pairs = data[field_name]
    return SeriesResult(periods=[p for p, _ in pairs], values=[v for _, v in pairs])


def test_query_metric_registry_gross_margin(monkeypatch):
    """批次 B：r5_gross_margin 经 registry 公式查询，ratio → percent。"""
    from app.application.services.indicator_query_service import query_metric

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda code, field, periods=8, as_of="": _fake_series(field),
    )
    result = query_metric("603180.SH", "r5_gross_margin")
    assert result.status == "ok"
    assert result.indicator == "r5_gross_margin"
    assert result.label == "毛利率"
    assert result.unit == "percent"
    assert result.period == "20241231"
    # registry 公式先 round((520-320)/520, 4)=0.3846，adapter ×100 → 38.46
    assert result.value == pytest.approx(38.46, abs=1e-6)
    assert {obs.field_path for obs in result.observations} == {
        "oper_rev",
        "less_oper_cost",
    }
    assert len(result.observations) == 2  # periods=1 → 每字段最新期 1 条


def test_query_metric_registry_turnover_days(monkeypatch):
    """批次 B：r4_turnover_days 经 registry 公式查询（不复制公式）。

    收口批次 A：经 metric_evaluator 按报告期对齐；结果期 observations
    只含目标期字段值（期间一致契约，方案 §2.1）。
    """
    from app.application.services.indicator_query_service import query_metric

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda code, field, periods=8, as_of="": _fake_series(field),
    )
    result = query_metric("603180.SH", "r4_turnover_days")
    assert result.status == "ok"
    assert result.unit == "days"
    # 20241231（Q4）：单季成本=320-300=20；avg_inv=(120+100)/2=110；年化=80
    assert result.value == pytest.approx(110 / 80 * 365, abs=1e-3)
    assert result.period == "20241231"
    # 结果期 observations：2 字段 × 目标期 1 条（期间一致契约）
    assert len(result.observations) == 2
    assert all(obs.period == result.period for obs in result.observations)
    # 可计算期间：Q4 可算（Q3 因缺前一期存货不可算）
    assert result.available_periods == ["20241231"]


def test_query_metric_registry_explicit_period_no_fallback(monkeypatch):
    """收口批次 A（方案 §2.2）：显式目标期不可计算时不 fallback。"""
    from app.application.services.indicator_query_service import query_metric

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda code, field, periods=8, as_of="": _fake_series(field),
    )
    result = query_metric(
        "603180.SH", "r5_gross_margin", as_of="20231231", require_exact_period=True
    )
    assert result.status == "insufficient_data"
    assert result.period == "20231231"
    assert result.available_periods == ["20240930", "20241231"]
    assert "目标期" in result.warnings[0]


def test_query_metric_registry_insufficient_data(monkeypatch):
    """批次 B：无序列数据 → insufficient_data（不伪造）。"""
    from app.application.services.indicator_query_service import query_metric

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.fetch_series",
        lambda code, field, periods=8, as_of="": SeriesResult(periods=[], values=[]),
    )
    result = query_metric("603180.SH", "r4_turnover_days")
    assert result.status == "insufficient_data"
    assert result.label == "存货周转天数"


def test_answer_indicator_registry_metric_emits_executed_metric(monkeypatch):
    """批次 B：成功指标短答返回 executed_metric（供 persist 落库）。"""
    from app.agents.nodes.generate_answer import _answer_indicator

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_registry_metric",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="r5_gross_margin",
            label="毛利率",
            period="20241231",
            value=38.46,
            unit="percent",
            observations=[
                IndicatorObservation(
                    "oper_rev", "income_statement", 520.0, period="20241231"
                ),
                IndicatorObservation(
                    "less_oper_cost",
                    "income_statement",
                    320.0,
                    period="20241231",
                ),
            ],
        ),
    )
    state = {
        "company": _company(),
        "plan": ExecutionPlan(intent="indicator", indicator="r5_gross_margin"),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_indicator(state, "r5_gross_margin")
    assert "38.46%" in out["final_response"].answer
    assert out["executed_metric"] == {
        "metric_id": "r5_gross_margin",
        "period": "20241231",
        "unit": "percent",
        "status": "ok",
        "company_code": "603180.SH",
    }
    assert len(out["claims"]) == 1
    assert len(out["evidence"]) == 2
