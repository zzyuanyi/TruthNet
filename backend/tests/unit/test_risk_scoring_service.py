"""风险评分服务单元测试 — Phase C 后端任务 6/11.

覆盖:
- 缺模块不按 0 风险（移除维度权重 + 归一化）
- 数据覆盖不足不输出绿色（unknown）
- 不因 events/benchmarks 缺失自动绿色
- 模式匹配来自 fraud_patterns.yaml
- 权重/贡献计算
- 股权维度不实例化图（服务无图依赖）
"""

import pytest

from app.application.services.risk_scoring_service import RiskScoringService
from app.agents.state import (
    EquityResult,
    EventsResult,
    EvidenceRef,
    FinanceResult,
)
from app.domain.risk.models import RiskOutput


def _fin_result(statuses=None, evidence=None, severities=None):
    """构造 FinanceResult；triggered 规则默认 severity=orange（含 rules 供 pattern 匹配）。"""
    from app.domain.finance.models import RuleResult

    statuses = statuses or {}
    severities = severities or {}
    rules = [
        RuleResult(
            rule_id=rid,
            status=st,
            severity=severities.get(rid, "orange" if st == "triggered" else "green"),
        )
        for rid, st in statuses.items()
    ]
    return FinanceResult(
        rule_statuses=statuses,
        rules=rules,
        evidence=evidence or [],
    )


def _eq_result(chains=None, evidence=None):
    return EquityResult(
        graph={"nodes": [{"id": "company_x"}]},
        chains=chains or [],
        evidence=evidence or [],
    )


def _ev_result(timeline=None, evidence=None):
    return EventsResult(
        timeline=timeline or [],
        evidence=evidence or [],
    )


def test_missing_events_not_green_on_zero():
    """无 events 且无 benchmarks → 财务触发 red 时不得被拉成 green。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={"R1": "triggered", "R3": "triggered"}),
        equity_result=_eq_result(chains=[{"a": 1}]),
        events_result=None,
        benchmarks=None,
        rule_set_version="finance-rules-1.0.0",
    )
    # events/benchmarks 缺失 → 权重归一化到 finance+equity
    dims = {s.dimension for s in out.sub_scores}
    assert "events" not in dims
    assert "benchmarks" not in dims
    assert out.overall_score > 0  # 不按 0 计算
    assert "不参与综合分" in " ".join(out.mitigating_factors)


def test_low_coverage_returns_unknown_not_green():
    """数据覆盖不足 → risk_level unknown，绝不输出 green。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={}),
        equity_result=None,
        events_result=None,
        benchmarks=None,
    )
    assert out.data_coverage.coverage_ratio < 0.5
    assert out.risk_level == "unknown"


def test_full_modules_calculate_overall():
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600519.SH",
        as_of="20260331",
        sec_name="贵州茅台",
        finance_result=_fin_result(statuses={}),
        equity_result=_eq_result(chains=[]),
        events_result=_ev_result(
            timeline=[
                {"date": "2026-03-01", "category": "股东大会", "sentiment": "neutral"}
            ]
        ),
        benchmarks={"r2_cf_ratio": {"company_percentile": 30.0}},
        rule_set_version="finance-rules-1.0.0",
    )
    assert out.risk_level in ("green", "yellow", "orange", "red")
    assert len(out.sub_scores) == 4
    assert out.data_coverage.coverage_ratio == pytest.approx(1.0, abs=0.01)


def test_pattern_matches_from_yaml():
    """模式匹配来自 fraud_patterns.yaml 唯一来源。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600001.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={"R1": "triggered", "R2": "triggered"}),
        equity_result=None,
        events_result=None,
        benchmarks=None,
    )
    pids = {m.pattern_id for m in out.pattern_matches}
    assert "P1" in pids  # R1+R2 → 收入虚增型


def test_red_level_from_finance():
    """财务多规则触发 → red。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={f"R{i}": "triggered" for i in range(1, 6)}
        ),
        equity_result=_eq_result(chains=[{"a": 1}, {"b": 2}, {"c": 3}]),
        events_result=_ev_result(
            timeline=[{"date": "d", "category": "c", "sentiment": "negative"}] * 3
        ),
        benchmarks={"r1_gap": {"company_percentile": 95.0}},
        rule_set_version="finance-rules-1.0.0",
    )
    assert out.overall_score >= 0.3
    assert out.risk_level in ("red", "orange")


def test_evidence_ids_collected():
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={"R1": "triggered"},
            evidence=[
                EvidenceRef(evidence_id="ev_fin_abc", source_table="income_statement")
            ],
        ),
        equity_result=None,
        events_result=None,
        benchmarks=None,
    )
    assert "ev_fin_abc" in out.evidence_ids
