"""风险评分服务单元测试 — Phase C 后端任务 6/11.

覆盖:
- 缺模块不按 0 风险（移除维度权重 + 归一化）
- 数据覆盖不足不输出绿色（unknown）
- 不因 events/benchmarks 缺失自动绿色
- 模式匹配来自 fraud_patterns.yaml
- 权重/贡献计算
- 股权维度不实例化图（服务无图依赖）
"""

import asyncio

import pytest

from app.application.services.risk_scoring_service import RiskScoringService
from app.agents.state import (
    EquityResult,
    EventsResult,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
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
        # WARN-1-1 修订后 statuses={} 视为"未返回任何规则状态"(skipped)；
        # 用可判定状态保留"全模块评分"原意图
        finance_result=_fin_result(statuses={"R1": "not_triggered"}),
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


def test_equity_chain_signal_sets_risk_level_floor():
    """An orange canonical equity chain must not produce an overall green level."""
    svc = RiskScoringService()
    equity = EquityResult(
        graph={"nodes": [{"id": "company_x"}]},
        chains=[{"path": ["a", "b"]}],
        chain_details=[{"risk_level": "orange"}],
    )
    out = svc.score(
        wind_code="600518.SH",
        as_of="20251231",
        finance_result=_fin_result(statuses={}),
        equity_result=equity,
        events_result=_ev_result(
            timeline=[{"sentiment": "neutral", "title": "常规公告"}]
        ),
        benchmarks={"r1_gap": {"company_percentile": 20.0}},
    )
    assert out.risk_level == "orange"
    assert any("最高有效叶子信号" in warning for warning in out.warnings)


def test_rating_and_cluster_data_participate_without_announcements():
    """Ratings/clusters keep event coverage and risk when the timeline is empty."""
    svc = RiskScoringService()
    events = EventsResult(
        timeline=[],
        rating_changes=[{"direction": "down"}],
        clusters=[{"sentiment": "negative", "topic": "诉讼"}],
    )
    out = svc.score(
        wind_code="600518.SH",
        as_of="20251231",
        finance_result=_fin_result(statuses={}),
        equity_result=_eq_result(chains=[]),
        events_result=events,
        benchmarks={"r1_gap": {"company_percentile": 20.0}},
    )
    assert out.data_coverage.events is True
    assert out.risk_level in {"orange", "red"}


def test_router_assembly_reuses_agent_module_nodes(monkeypatch):
    """The /risk service must not maintain a second, partial module assembly."""
    from app.agents.nodes import cross_validate, equity, events, finance, risk
    from app.application.services.company_resolver import CompanyRecord
    from app.application.services.risk_scoring_service import assemble_and_score

    calls: list[str] = []

    async def resolve(_code):
        return CompanyRecord(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange_code="XSHG",
        )

    def finance_stub(state):
        calls.append("finance")
        return {"results": ModuleResults(finance=FinanceResult())}

    def equity_stub(state):
        calls.append("equity")
        assert state["results"].finance is not None
        return {"results": ModuleResults(equity=EquityResult())}

    def events_stub(state):
        calls.append("events")
        return {"results": ModuleResults(events=EventsResult())}

    def cross_stub(state):
        calls.append("cross_validate")
        return {"cross_validation": None}

    expected = RiskOutput(
        wind_code="600518.SH",
        sec_name="康美药业",
        as_of="20251231",
        risk_level="yellow",
    )

    def risk_stub(state):
        calls.append("risk")
        assert state["results"].finance is not None
        assert state["results"].equity is not None
        assert state["results"].events is not None
        assert state["plan"].as_of.strftime("%Y%m%d") == "20251231"
        return {"risk_output": expected}

    monkeypatch.setattr(
        "app.application.services.company_resolver.resolve_company", resolve
    )
    monkeypatch.setattr(finance, "finance_node", finance_stub)
    monkeypatch.setattr(equity, "equity_node", equity_stub)
    monkeypatch.setattr(events, "events_node", events_stub)
    monkeypatch.setattr(cross_validate, "cross_validate_node", cross_stub)
    monkeypatch.setattr(risk, "risk_node", risk_stub)
    out = asyncio.run(assemble_and_score("600518.SH", "20251231"))
    assert out is expected
    assert calls == ["finance", "equity", "events", "cross_validate", "risk"]


def test_risk_failure_path_in_compiled_graph():
    """P1 回归：RiskScoringService.score 异常时，risk 失败状态经 reducer 合并。

    必须通过编译后的 LangGraph 执行——module_status 的 reducer
    （{**a, **b}）只在合并时触发；直接调用 risk_node() 测不出值形态错误
    （失败路径曾返回裸 ModuleStatus，导致整个 graph 中断）。
    """
    from unittest.mock import patch

    from langgraph.graph import END, StateGraph

    from app.agents.nodes.risk import risk_node
    from app.agents.state import (
        AgentState,
        CompanyRef,
        ModuleResults,
        ModuleStatus,
        RuntimeState,
    )

    def _pass_through(state: dict) -> dict:
        return {"user_query": state.get("user_query", "")}

    g = StateGraph(AgentState)
    g.add_node("risk", risk_node)
    g.add_node("end", _pass_through)
    g.set_entry_point("risk")
    g.add_edge("risk", "end")
    g.add_edge("end", END)
    compiled = g.compile()

    state = {
        "user_query": "康美有风险吗",
        "company": CompanyRef(
            entity_id="600518.SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="SH",
        ),
        "results": ModuleResults(),
        "module_status": {"finance": ModuleStatus(state="success")},
        "runtime": RuntimeState(trace_id="t1", session_id="s1", turn_id="t1"),
        "pattern_matches": [],
    }
    with patch.object(RiskScoringService, "score", side_effect=RuntimeError("failed")):
        result = compiled.invoke(state)

    assert result["module_status"]["risk"].state == "failed"
    assert (
        result["module_status"]["finance"].state == "success"
    ), "失败路径不得破坏既有模块状态"
    assert result["risk_output"] is None


# ── WARN-1-1（核验修订）：财务完全不可判断 → 聚合层不得输出"正常" ──


def test_all_finance_insufficient_returns_unknown_not_green():
    """7 条规则全部 insufficient/not_applicable → 财务 partial → 无其他明确
    黄色以上叶子信号时综合等级必须 unknown，绝不输出 green"正常"。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={f"R{i}": "insufficient_data" for i in range(1, 6)}
        ),
        equity_result=_eq_result(chains=[]),
        events_result=_ev_result(
            timeline=[{"sentiment": "neutral", "title": "常规公告"}]
        ),
        benchmarks={"r1_gap": {"company_percentile": 30.0}},
    )
    assert out.risk_level == "unknown"
    assert "finance" in out.data_coverage.missing_modules
    assert any("综合等级标记 unknown" in w for w in out.warnings)
    assert any("财务" in f for f in out.mitigating_factors)
    # 财务维度不得按"有数据无风险"参与权重
    assert not any(s.dimension == "finance" for s in out.sub_scores)


def test_mixed_finance_statuses_keeps_finance_dimension():
    """部分规则可判定 + 部分 insufficient → 财务维度仍有效，不因个别规则
    数据不足丢弃整个财务维度（康美 as_of=20260331 实测场景）。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={
                "R1": "not_triggered",
                "R2": "insufficient_data",
                "R3": "not_triggered",
                "R4": "not_applicable",
            }
        ),
        equity_result=_eq_result(chains=[]),
        events_result=None,
        benchmarks=None,
    )
    fin_subs = [s for s in out.sub_scores if s.dimension == "finance"]
    assert fin_subs and fin_subs[0].status == "success"
    assert "finance" not in out.data_coverage.missing_modules
    assert out.risk_level != "unknown"  # 财务维度有效 → 正常评分


def test_finance_partial_keeps_equity_red_signal():
    """财务完全不可判断但股权已有 red 信号 → 保留 red 并提示财务覆盖不足，
    不得统一覆盖成 unknown（不得漏报明确风险）。"""
    equity = EquityResult(
        graph={"nodes": [{"id": "company_x"}]},
        chains=[{"path": ["a", "b"]}],
        chain_details=[{"risk_level": "red"}],
    )
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={f"R{i}": "insufficient_data" for i in range(1, 6)}
        ),
        equity_result=equity,
        events_result=None,
        benchmarks=None,
    )
    assert out.risk_level == "red"
    assert any("财务规则未参与评分" in w for w in out.warnings)
    assert not any("综合等级标记 unknown" in w for w in out.warnings)


# ── 8.09 二轮审查：补充反例（skipped / 零权重覆盖 / 布尔一致）──


def test_finance_skipped_empty_statuses_returns_unknown():
    """二轮审查反例：finance.rule_statuses={}（skipped，未返回任何规则状态）
    时不得输出 green"正常"——关键维度保护必须覆盖 partial 之外的状态。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={}),
        equity_result=_eq_result(chains=[]),
        events_result=_ev_result(
            timeline=[{"sentiment": "neutral", "title": "常规公告"}]
        ),
        benchmarks={"r1_gap": {"company_percentile": 30.0}},
    )
    assert out.data_coverage.coverage_ratio == pytest.approx(0.6, abs=0.01)
    assert (
        out.risk_level == "unknown"
    ), f"财务 skipped 且无明确风险信号时必须 unknown，实际 {out.risk_level}"
    assert "finance" in out.data_coverage.missing_modules


def test_all_dimensions_unavailable_keeps_coverage_info():
    """二轮审查反例：全维度不可用时覆盖信息不得丢失
    （曾实测 coverage_ratio=0 / missing_modules=[] / mitigating_factors=[]）。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={}),
        equity_result=None,
        events_result=None,
        benchmarks=None,
    )
    assert out.risk_level == "unknown"
    assert out.data_coverage.coverage_ratio == 0.0
    assert "finance" in out.data_coverage.missing_modules
    assert "equity" in out.data_coverage.missing_modules
    assert any("全部维度均不可用" in f for f in out.mitigating_factors)
    assert any("无法评分" in w for w in out.warnings)


def test_coverage_bools_match_missing_modules():
    """二轮审查：覆盖布尔与 missing_modules 同源（全部按 status==success），
    不得出现 coverage.equity=true 但 missing_modules 含 equity 的矛盾。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(statuses={}),
        equity_result=_eq_result(chains=[]),
        events_result=None,
        benchmarks=None,
    )
    assert out.data_coverage.equity is True
    assert out.data_coverage.events is False
    assert out.data_coverage.benchmarks is False
    assert "events" in out.data_coverage.missing_modules
    assert "benchmarks" in out.data_coverage.missing_modules
    assert "equity" not in out.data_coverage.missing_modules


# ── 8.11：真实证据类型与摘要 ────────────────────────────────


def test_risk_evidence_real_types_and_deduped():
    """8.11：证据按真实类型/摘要返回（字段期次值），重复 ID 只保留一次。"""
    svc = RiskScoringService()
    fin_ev = EvidenceRef(
        evidence_id="ev_fin_1",
        source_type="financial_statement",
        source_record_id="bs_1",
        field_path="资产负债率",
        period="20251231",
        value="0.47",
        module="finance",
    )
    ann_ev = EvidenceRef(
        evidence_id="ev_ann_1",
        source_type="announcement",
        source_record_id="ann_1",
        source_title="关于股权质押的公告",
        module="events",
    )
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={"R1": "triggered"},
            evidence=[fin_ev, fin_ev],  # 重复 ID
        ),
        equity_result=_eq_result(chains=[{"a": 1}]),
        events_result=_ev_result(evidence=[ann_ev]),
        rule_set_version="finance-rules-1.0.0",
    )
    evs = {e.evidence_id: e for e in out.evidence}
    assert set(evs) == {"ev_fin_1", "ev_ann_1"}, "重复 ID 只保留一次"
    assert evs["ev_fin_1"].source_type == "financial_statement"
    assert evs["ev_fin_1"].summary == "资产负债率 20251231: 0.47"
    assert evs["ev_ann_1"].source_type == "announcement"
    assert evs["ev_ann_1"].summary == "关于股权质押的公告"


def test_risk_evidence_summary_fallbacks():
    """8.11：无 title 用 excerpt；字段缺失时用模块兜底文案，不伪造类型。"""
    svc = RiskScoringService()
    out: RiskOutput = svc.score(
        wind_code="600518.SH",
        as_of="20260331",
        finance_result=_fin_result(
            statuses={"R1": "triggered"},
            evidence=[
                EvidenceRef(
                    evidence_id="ev_x_1",
                    source_type="",
                    source_record_id="r1",
                    source_excerpt="某摘要",
                    module="events",
                ),
                EvidenceRef(
                    evidence_id="ev_x_2",
                    source_type="ownership_record",
                    source_record_id="r2",
                    module="equity",
                ),
            ],
        ),
        equity_result=_eq_result(chains=[{"a": 1}]),
        rule_set_version="finance-rules-1.0.0",
    )
    by_id = {e.evidence_id: e for e in out.evidence}
    assert by_id["ev_x_1"].summary == "某摘要"
    assert by_id["ev_x_1"].source_type == ""  # 空值保留，Router 侧转 unknown
    assert by_id["ev_x_2"].summary == "finance 模块证据"
    assert by_id["ev_x_2"].source_type == "ownership_record"
