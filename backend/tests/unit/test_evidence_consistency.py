"""Claim–Evidence 全局一致性测试 — 后端任务 4.

核心不变量:
    all claim.evidence_ids ⊆ all evidence.evidence_id
覆盖:
- 真实规则引擎 → finance_node → build_claims 链路中无悬空引用；
- 无 evidence 的 Claim 不被生成；
- 不存在硬编码的假证据 ID（如 ev_ev_01）；
- 同一轮无重复 Claim。
"""

import sqlite3

import pytest

from app.agents.nodes.build_claims import build_claims_node
from app.agents.nodes.finance import finance_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    EquityResult,
    EventsResult,
    ExecutionPlan,
    EvidenceRef,
    ModuleResults,
    RuntimeState,
)
from app.core.config import settings
from app.domain.finance import _fetch

PARENT = "408006000"
_PERIODS = ["20250331", "20250630", "20250930", "20251231", "20260331"]


@pytest.fixture
def finance_db(tmp_path, monkeypatch):
    """合成 SQLite 库：触发 R1 + R2 + R6 的公司数据."""
    db_path = tmp_path / "evid.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE companies (wind_code TEXT PRIMARY KEY, sec_name TEXT, "
        "comp_type_code INTEGER, industry_l1 TEXT)"
    )
    conn.execute(
        "CREATE TABLE balance_sheet (id INTEGER PRIMARY KEY, wind_code TEXT, "
        "report_period TEXT, statement_type TEXT, monetary_cap REAL, acct_rcv REAL, "
        "oth_rcv REAL, inventories REAL, tot_assets REAL, st_borrow REAL, lt_borrow REAL, "
        "bonds_payable REAL, non_cur_liab_due_within_1y REAL, tot_cur_assets REAL, "
        "tot_cur_liab REAL, tot_liab REAL, tot_shrhldr_eqy_incl_min_int REAL)"
    )
    conn.execute(
        "CREATE TABLE income_statement (id INTEGER PRIMARY KEY, wind_code TEXT, "
        "report_period TEXT, statement_type TEXT, oper_rev REAL, tot_oper_rev REAL, "
        "less_oper_cost REAL, less_selling_dist_exp REAL, less_gerl_admin_exp REAL, "
        "less_fin_exp REAL, oper_profit REAL, tot_profit REAL, "
        "net_profit_excl_min_int_inc REAL, net_profit_after_ded_nr_lp REAL)"
    )
    conn.execute(
        "CREATE TABLE cash_flow (id INTEGER PRIMARY KEY, wind_code TEXT, "
        "report_period TEXT, statement_type TEXT, net_cash_flows_oper_act REAL, "
        "net_cash_flows_inv_act REAL, net_cash_flows_fnc_act REAL, free_cash_flow REAL)"
    )
    conn.execute(
        "INSERT INTO companies (wind_code, sec_name, comp_type_code, industry_l1) "
        "VALUES ('600518.SH', '康美药业', 1, '医药')"
    )
    # R1 触发：应收暴增、营收下滑
    ar = [1e8, 1.05e8, 1.1e8, 1.25e8, 1.85e8]
    ore = [2e8, 2e8, 2e8, 2e8, 1.6e8]
    # R2 触发：净利为正、现金流为负
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    cf = [-5e7, -6e7, -7e7, -8e7, -9e7]
    for i, p in enumerate(_PERIODS):
        conn.execute(
            "INSERT INTO balance_sheet (wind_code, report_period, statement_type, "
            "acct_rcv, oth_rcv, tot_assets, monetary_cap, st_borrow) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("600518.SH", p, PARENT, ar[i], 5e7, 1e9, 3e8, 2e8),
        )
        conn.execute(
            "INSERT INTO income_statement (wind_code, report_period, statement_type, "
            "oper_rev, net_profit_excl_min_int_inc, less_oper_cost) "
            "VALUES (?,?,?,?,?,?)",
            ("600518.SH", p, PARENT, ore[i], np[i], 1.2e8),
        )
        conn.execute(
            "INSERT INTO cash_flow (wind_code, report_period, statement_type, "
            "net_cash_flows_oper_act) VALUES (?,?,?,?)",
            ("600518.SH", p, PARENT, cf[i]),
        )
    conn.commit()

    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db_path))
    monkeypatch.setattr(_fetch, "_ENGINES", {})
    yield conn
    conn.close()


def _state_with(company_code: str = "600518.SH") -> AgentState:
    return {
        "user_query": "康美有风险吗",
        "company": CompanyRef(
            entity_id=f"company_{company_code.replace('.', '_')}",
            wind_code=company_code,
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["finance", "equity", "events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def _finance_results(state):
    out = finance_node(state)
    return out["results"].finance


def test_global_claim_evidence_consistency(finance_db):
    """all claim.evidence_ids ⊆ all evidence.evidence_id."""
    state = _state_with()
    fin = _finance_results(state)
    results = ModuleResults(
        finance=fin,
        equity=EquityResult(
            chains=[{"path": ["马兴田", "康美药业"], "total_stake": 0.32}],
            evidence=[
                EvidenceRef(evidence_id="ev_eq_01", source_type="ownership_record")
            ],
        ),
        events=EventsResult(
            timeline=[{"category": "诉讼", "sentiment": "negative"}],
            evidence=[EvidenceRef(evidence_id="ann_001", source_type="announcement")],
        ),
    )
    state["results"] = results
    out = build_claims_node(state)

    claims = out["claims"]
    evidence_ids = {ev.evidence_id for ev in out["evidence"]}

    # 不变量: 每个 Claim 的证据 ID 都必须存在于 evidence 集合中
    for c in claims:
        assert c.evidence_ids, f"Claim {c.claim_id} 无证据"
        assert all(
            eid in evidence_ids for eid in c.evidence_ids
        ), f"Claim {c.claim_id} 存在悬空证据引用: {c.evidence_ids} ⊄ {evidence_ids}"

    # 无假证据 ID
    for eid in evidence_ids:
        assert eid != "ev_ev_01"


def test_finance_triggered_rules_have_evidence(finance_db):
    """触发规则对应的财务 Claim 必须引用真实财务证据。"""
    state = _state_with()
    fin = _finance_results(state)
    assert any(
        s == "triggered" for s in fin.rule_statuses.values()
    ), "测试数据未触发规则"

    results = ModuleResults(finance=fin)
    state["results"] = results
    out = build_claims_node(state)

    financial_claims = [c for c in out["claims"] if c.claim_type == "financial"]
    fin_ev_ids = {ev.evidence_id for ev in fin.evidence}
    for c in financial_claims:
        assert (
            set(c.evidence_ids) <= fin_ev_ids
        ), f"财务 Claim {c.claim_id} 引用非财务证据 {c.evidence_ids}"


def test_no_duplicate_claims_same_turn(finance_db):
    """同一轮输出无重复 Claim（reducer 拼接不翻倍）。"""
    state = _state_with()
    fin = _finance_results(state)
    state["results"] = ModuleResults(finance=fin)
    out1 = build_claims_node(state)
    # 第二次调用使用不同 state 实例（模拟新轮），不应与首轮拼接翻倍
    state2 = dict(state)
    out2 = build_claims_node(state2)
    claim_ids1 = {c.claim_id for c in out1["claims"]}
    claim_ids2 = {c.claim_id for c in out2["claims"]}
    assert claim_ids1 == claim_ids2  # 无累积翻倍
    assert len(out2["claims"]) == len(out1["claims"])
