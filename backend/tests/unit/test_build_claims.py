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
    ExecutionPlan,
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


def _ev(
    evidence_id: str,
    source_type: str = "financial_statement",
    field_path: str | None = None,
    source_record_id: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type=source_type,
        source_title=f"{evidence_id} 来源",
        field_path=field_path or "test_field",
        source_record_id=source_record_id or f"src_{evidence_id}",
    )


def _make_state(results: ModuleResults, plan: ExecutionPlan | None = None) -> AgentState:
    return {
        "user_query": "测试",
        "company": _company(),
        "results": results,
        "plan": plan,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


# ── finance 规则 Claim ──────────────────────────────────────


def test_finance_claims_generated():
    """R1/R2 触发 + 字段证据 → 生成 Claim，evidence_ids 引用真实。

    #2：severity 与规则引擎同源（fixture 提供引擎 severity）。
    """
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered", "R2": "triggered"},
            rule_details={
                "R1": {
                    "evidence_ids": ["ev_fin_acct_rcv", "ev_fin_oper_rev"],
                    "severity": "red",
                    "explanation": "应收账款增速与营业收入增速存在显著背离",
                },
                "R2": {
                    "evidence_ids": ["ev_fin_net_profit", "ev_fin_oper_cf"],
                    "severity": "orange",
                    "explanation": "经营活动现金流与净利润严重背离",
                },
            },
            evidence=[
                _ev("ev_fin_acct_rcv", field_path="acct_rcv"),
                _ev("ev_fin_oper_rev", field_path="oper_rev"),
                _ev("ev_fin_net_profit", field_path="net_profit"),
                _ev("ev_fin_oper_cf", field_path="oper"),
            ],
        )
    )
    result = build_claims_node(_make_state(results))

    financial = [c for c in result["claims"] if c.claim_type == "financial"]
    assert len(financial) == 2
    r1 = next(c for c in financial if c.rule_id == "R1")
    # 背离结论需要应收+营收两个字段证据
    assert set(r1.evidence_ids) == {"ev_fin_acct_rcv", "ev_fin_oper_rev"}
    # #2：Claim 严重度 = 引擎真实 severity（不再硬编码 red/orange）
    assert r1.severity == "red"
    r2 = next(c for c in financial if c.rule_id == "R2")
    assert set(r2.evidence_ids) == {"ev_fin_net_profit", "ev_fin_oper_cf"}
    assert r2.severity == "orange"
    # #1：Claim 文本来自引擎 explanation（不再静态描述表）
    assert "应收账款增速与营业收入增速存在显著背离" in r1.text


def test_finance_rule_without_evidence_skipped():
    """规则触发但未产出任何证据 → 不生成该 Claim（§9.2 至少一个 Evidence）。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered", "R3": "triggered"},
            rule_details={
                "R1": {"evidence_ids": []},
                "R3": {"evidence_ids": []},
            },
            evidence=[
                _ev("ev_is_oper_rev_20260331", field_path="oper_rev")
            ],  # 不在任何规则的 evidence_ids 中
        )
    )
    result = build_claims_node(_make_state(results))
    assert result["claims"] == []


def test_multi_rule_regression():
    """R1-R7 全部触发 + 全量字段证据 → 生成 7 个 financial Claim。"""
    statuses = {f"R{i}": "triggered" for i in range(1, 8)}
    evidence = [
        _ev("ev_acct_rcv", field_path="acct_rcv"),
        _ev("ev_oper_rev", field_path="oper_rev"),
        _ev("ev_net_profit", field_path="net_profit"),
        _ev("ev_oper_cf", field_path="oper"),
        _ev("ev_monetary_cap", field_path="monetary_cap"),
        _ev("ev_borrow", field_path="borrow"),
        _ev("ev_inventories", field_path="inventories"),
        _ev("ev_oper_cost", field_path="oper_cost"),
        _ev("ev_oth_rcv", field_path="oth_rcv"),
        _ev("ev_tot_assets", field_path="tot_assets"),
        _ev("ev_core_profit", field_path="core_profit"),
    ]
    rule_details = {
        "R1": {"evidence_ids": ["ev_acct_rcv", "ev_oper_rev"]},
        "R2": {"evidence_ids": ["ev_net_profit", "ev_oper_cf"]},
        "R3": {"evidence_ids": ["ev_monetary_cap", "ev_borrow"]},
        "R4": {"evidence_ids": ["ev_inventories", "ev_oper_rev"]},
        "R5": {"evidence_ids": ["ev_oper_rev", "ev_oper_cost"]},
        "R6": {"evidence_ids": ["ev_oth_rcv", "ev_tot_assets"]},
        "R7": {"evidence_ids": ["ev_net_profit", "ev_core_profit"]},
    }
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses=statuses, rule_details=rule_details, evidence=evidence
        )
    )
    result = build_claims_node(_make_state(results))

    financial = [c for c in result["claims"] if c.claim_type == "financial"]
    assert len(financial) == 7
    # 所有 Claim 的 evidence_ids 非空且引用真实存在
    for c in financial:
        assert c.evidence_ids
        assert all(eid in {e.evidence_id for e in evidence} for eid in c.evidence_ids)
    # R1 背离结论证据覆盖应收+营收两字段
    r1 = next(c for c in financial if c.rule_id == "R1")
    assert set(r1.evidence_ids) == {"ev_acct_rcv", "ev_oper_rev"}


# ── equity Claim 证据绑定 ───────────────────────────────────


def test_equity_evidence_binding():
    """equity Claim 绑定实际证据（上游产出 ev_eq_01）。

    #3：chain_details 缺失时回退旧 chains——severity=unknown（不默认 red）。
    """
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
    assert equity[0].severity == "unknown"  # 降级载荷不得默认 red


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
                {
                    "category": "诉讼",
                    "date": "2025-01-01",
                    "sentiment": "negative",
                    "object_id": "obj_001",
                },
                {"category": "增持", "date": "2025-02-01", "sentiment": "positive"},
            ],
            evidence=[
                _ev(
                    "ann_001",
                    source_type="announcement",
                    source_record_id="obj_001",
                )
            ],
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


def test_rating_and_cluster_claims_require_canonical_evidence():
    """Rating and event-cluster facts are emitted only with resolvable evidence."""
    results = ModuleResults(
        events=EventsResult(
            rating_changes=[
                {
                    "direction": "down",
                    "institution": "测试证券",
                    "evidence_id": "ev_rating_1",
                },
                {"direction": "down", "evidence_id": "missing_rating"},
            ],
            clusters=[
                {
                    "event_cluster_id": "evtcl_1",
                    "topic": "监管处罚",
                    "sentiment": "negative",
                    "evidence_ids": ["ev_cluster_1", "missing_cluster"],
                }
            ],
            evidence=[
                _ev("ev_rating_1", source_type="research_report"),
                _ev("ev_cluster_1", source_type="announcement"),
            ],
        )
    )
    event_claims = [
        claim
        for claim in build_claims_node(_make_state(results))["claims"]
        if claim.claim_type == "event"
    ]
    assert len(event_claims) == 2
    assert {eid for claim in event_claims for eid in claim.evidence_ids} == {
        "ev_rating_1",
        "ev_cluster_1",
    }
    assert any("评级下调" in claim.text for claim in event_claims)
    assert any("监管处罚" in claim.text for claim in event_claims)


# ── evidence 汇总 ───────────────────────────────────────────


def test_evidence_collected_from_all_modules():
    """三模块 evidence 全部汇总到 state evidence。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered"},
            rule_details={
                "R1": {
                    "evidence_ids": [
                        "ev_bs_acct_rcv_20260331",
                        "ev_is_oper_rev_20260331",
                    ]
                }
            },
            evidence=[
                _ev("ev_bs_acct_rcv_20260331", field_path="acct_rcv"),
                _ev("ev_is_oper_rev_20260331", field_path="oper_rev"),
            ],
        ),
        equity=EquityResult(
            chains=[{"path": ["A"], "total_stake": 0.1}],
            evidence=[_ev("ev_eq_01", source_type="ownership_record")],
        ),
        events=EventsResult(
            timeline=[
                {
                    "category": "负面",
                    "sentiment": "negative",
                    "object_id": "src_ann_001",
                }
            ],
            evidence=[
                _ev(
                    "ann_001",
                    source_type="announcement",
                    source_record_id="src_ann_001",
                )
            ],
        ),
    )
    result = build_claims_node(_make_state(results))

    ids = {ev.evidence_id for ev in result["evidence"]}
    assert ids == {
        "ev_bs_acct_rcv_20260331",
        "ev_is_oper_rev_20260331",
        "ev_eq_01",
        "ann_001",
    }
    # 三类 Claim 全部生成且引用真实证据
    assert len(result["claims"]) == 3
    for c in result["claims"]:
        assert c.evidence_ids


def test_single_module_scope_ignores_unrequested_results():
    """异常上游混入其他模块结果时，BuildClaims 不得将其带入本轮证据链。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered"},
            rule_details={"R1": {"evidence_ids": ["ev_fin"], "severity": "red"}},
            evidence=[_ev("ev_fin")],
        ),
        equity=EquityResult(
            chains=[{"path": ["A"], "total_stake": 0.1}],
            evidence=[_ev("ev_equity", source_type="ownership_record")],
        ),
        events=EventsResult(
            timeline=[
                {
                    "category": "负面",
                    "sentiment": "negative",
                    "object_id": "src_event",
                }
            ],
            evidence=[
                _ev(
                    "ev_event",
                    source_type="announcement",
                    source_record_id="src_event",
                )
            ],
        ),
    )

    result = build_claims_node(
        _make_state(results, ExecutionPlan(requested_modules=["finance"]))
    )

    assert {claim.claim_type for claim in result["claims"]} == {"financial"}
    assert {item.evidence_id for item in result["evidence"]} == {"ev_fin"}
