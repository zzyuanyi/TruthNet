from datetime import date

from app.agents.nodes.generate_answer import _answer_indicator
from app.agents.nodes.plan_modules import detect_indicator, plan_modules_node
from app.agents.state import CompanyRef, ExecutionPlan, RuntimeState
from app.application.services.indicator_query_service import (
    IndicatorObservation,
    IndicatorQueryResult,
    query_indicator,
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
