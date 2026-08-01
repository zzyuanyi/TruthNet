"""BuildClaims 节点单元测试 — V12 §9.2.

覆盖：三类 Claim 证据绑定（finance/equity/events）、无证据不生成、
多规则触发回归、evidence 汇总。
"""

from app.agents.nodes.build_claims import build_claims_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    EquityResult,
    EventsResult,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
    RuntimeState,
)


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


def _ev(evidence_id: str, source_type: str = "financial_statement") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type=source_type,
        source_title=f"{evidence_id} 来源",
        field_path="test_field",
    )


def _make_state(results: ModuleResults) -> AgentState:
    return {
        "user_query": "测试",
        "company": _company(),
        "results": results,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


# ── finance 规则 Claim ──────────────────────────────────────


def test_finance_claims_generated():
    """R1/R2 触发 + 匹配证据 → 生成 Claim，evidence_ids 引用真实。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered", "R2": "triggered"},
            evidence=[
                _ev("ev_bs_01"),
                _ev("ev_is_01"),
                _ev("ev_cf_01"),
                _ev("ev_is_02"),
            ],
        )
    )
    result = build_claims_node(_make_state(results))

    financial = [c for c in result["claims"] if c.claim_type == "financial"]
    assert len(financial) == 2
    r1 = next(c for c in financial if c.rule_id == "R1")
    # 背离结论需要应收+营收两个字段证据
    assert r1.evidence_ids == ["ev_bs_01", "ev_is_01"]
    assert r1.severity == "red"
    r2 = next(c for c in financial if c.rule_id == "R2")
    assert r2.evidence_ids == ["ev_cf_01", "ev_is_02"]


def test_finance_rule_without_evidence_skipped():
    """规则触发但无匹配证据 → 不生成该 Claim（§9.2 至少一个 Evidence）。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered", "R3": "triggered"},
            evidence=[_ev("ev_is_01")],  # 只有 R5 用的 IS 证据，R1/R3 的 BS/CF 缺失
        )
    )
    result = build_claims_node(_make_state(results))
    assert result["claims"] == []


def test_multi_rule_regression():
    """R1-R7 全部触发 + 全量证据 → 生成 7 个 financial Claim。"""
    statuses = {f"R{i}": "triggered" for i in range(1, 8)}
    evidence = [
        _ev("ev_bs_01"),
        _ev("ev_is_01"),
        _ev("ev_cf_01"),
        _ev("ev_is_02"),
        _ev("ev_bs_02"),
        _ev("ev_bs_03"),
    ]
    results = ModuleResults(
        finance=FinanceResult(rule_statuses=statuses, evidence=evidence)
    )
    result = build_claims_node(_make_state(results))

    financial = [c for c in result["claims"] if c.claim_type == "financial"]
    assert len(financial) == 7
    # 所有 Claim 的 evidence_ids 非空且引用真实存在
    for c in financial:
        assert c.evidence_ids
        assert all(
            eid
            in {"ev_bs_01", "ev_is_01", "ev_cf_01", "ev_is_02", "ev_bs_02", "ev_bs_03"}
            for eid in c.evidence_ids
        )
    # R1 背离结论证据覆盖应收+营收两字段
    r1 = next(c for c in financial if c.rule_id == "R1")
    assert set(r1.evidence_ids) == {"ev_bs_01", "ev_is_01"}


# ── equity Claim 证据绑定 ───────────────────────────────────


def test_equity_evidence_binding():
    """equity Claim 绑定实际证据（上游产出 ev_eq_01）。"""
    results = ModuleResults(
        equity=EquityResult(
            chains=[{"path": ["马兴田", "康美实业", "康美药业"], "total_stake": 0.301}],
            evidence=[_ev("ev_eq_01", source_type="ownership_record")],
        )
    )
    result = build_claims_node(_make_state(results))

    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1
    assert equity[0].evidence_ids == ["ev_eq_01"]
    assert "马兴田" in equity[0].text


def test_equity_without_evidence_skipped():
    """chains 存在但 evidence 为空 → 不生成 equity Claim。"""
    results = ModuleResults(
        equity=EquityResult(chains=[{"path": ["A"], "total_stake": 0.5}], evidence=[])
    )
    result = build_claims_node(_make_state(results))
    assert all(c.claim_type != "equity" for c in result["claims"])


# ── events Claim 证据绑定 ───────────────────────────────────


def test_events_evidence_binding():
    """负面事件 Claim 绑定 ann_* 真实证据（回归：不再硬编码 ev_ev_01）。"""
    results = ModuleResults(
        events=EventsResult(
            timeline=[
                {"category": "诉讼", "date": "2025-01-01", "sentiment": "negative"},
                {"category": "增持", "date": "2025-02-01", "sentiment": "positive"},
            ],
            evidence=[_ev("ann_001", source_type="announcement")],
        )
    )
    result = build_claims_node(_make_state(results))

    events = [c for c in result["claims"] if c.claim_type == "event"]
    assert len(events) == 1
    assert events[0].evidence_ids == ["ann_001"]
    assert "ev_ev_01" not in events[0].evidence_ids
    # 文本反映负面事件数量与负面类别（增持等非负面类别不列入）
    assert "1项负面事件（诉讼）" in events[0].text
    assert "增持" not in events[0].text


def test_events_without_negative_skipped():
    """timeline 全为中性/正面 → 不生成风险 Claim（P1-3 回归）。"""
    results = ModuleResults(
        events=EventsResult(
            timeline=[
                {"category": "增持", "sentiment": "positive"},
                {"category": "中标", "sentiment": "neutral"},
            ],
            evidence=[_ev("ann_001", source_type="announcement")],
        )
    )
    result = build_claims_node(_make_state(results))
    assert all(c.claim_type != "event" for c in result["claims"])


def test_events_without_evidence_skipped():
    """存在负面事件但 evidence 为空 → 不生成 events Claim。"""
    results = ModuleResults(
        events=EventsResult(
            timeline=[{"category": "负面", "sentiment": "negative"}], evidence=[]
        )
    )
    result = build_claims_node(_make_state(results))
    assert all(c.claim_type != "event" for c in result["claims"])


# ── evidence 汇总 ───────────────────────────────────────────


def test_evidence_collected_from_all_modules():
    """三模块 evidence 全部汇总到 state evidence。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered"},
            evidence=[_ev("ev_bs_01"), _ev("ev_is_01")],
        ),
        equity=EquityResult(
            chains=[{"path": ["A"], "total_stake": 0.1}],
            evidence=[_ev("ev_eq_01", source_type="ownership_record")],
        ),
        events=EventsResult(
            timeline=[{"category": "负面", "sentiment": "negative"}],
            evidence=[_ev("ann_001", source_type="announcement")],
        ),
    )
    result = build_claims_node(_make_state(results))

    ids = {ev.evidence_id for ev in result["evidence"]}
    assert ids == {"ev_bs_01", "ev_is_01", "ev_eq_01", "ann_001"}
    # 三类 Claim 全部生成且引用真实证据
    assert len(result["claims"]) == 3
    for c in result["claims"]:
        assert c.evidence_ids
