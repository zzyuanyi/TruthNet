"""Phase C 母公司口径一致性测试.

覆盖:
- finance_node 统一口径说明（SCOPE_NOTE）恰好一次，顺序稳定；
- 财务 Evidence source_type=408006000、source_title 含"母公司报表"；
- build_claims 财务 Claim 携带母公司范围 limitations；
- REST _build_chat_response warnings 透传（恰好一次）；
- 无重复/无"降级"文案。
"""

import sqlite3

import pytest

from app.agents.nodes.build_claims import build_claims_node
from app.agents.nodes.finance import finance_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    ExecutionPlan,
    ModuleResults,
    ModuleStatus,
    RuntimeState,
)
from app.core.config import settings
from app.domain.finance import _fetch
from app.domain.finance.parent_scope import SCOPE_NOTE

PARENT = "408006000"
_PERIODS = ["20250331", "20250630", "20250930", "20251231", "20260331"]


@pytest.fixture
def finance_db(tmp_path, monkeypatch):
    """合成 SQLite 库：R1 触发 + R5 触发的公司数据（非金融）。"""
    db_path = tmp_path / "parent_scope.db"
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
            ("600518.SH", p, PARENT, ore[i], 1e8, 1.2e8),
        )
        conn.execute(
            "INSERT INTO cash_flow (wind_code, report_period, statement_type, "
            "net_cash_flows_oper_act) VALUES (?,?,?,?)",
            ("600518.SH", p, PARENT, -5e7),
        )
    conn.commit()

    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db_path))
    monkeypatch.setattr(_fetch, "_ENGINES", {})
    yield conn
    conn.close()


def _state_with() -> AgentState:
    return {
        "user_query": "康美有风险吗",
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def test_scope_note_exactly_once(finance_db):
    """FinanceResult.warnings 中统一口径说明恰好一次。"""
    out = finance_node(_state_with())
    fin = out["results"].finance
    assert fin is not None
    assert fin.warnings.count(SCOPE_NOTE) == 1, f"warnings={fin.warnings}"


def test_finance_evidence_parent_scope(finance_db):
    """财务 Evidence 标记母公司报表（statement_scope=parent_company，source_title 含母公司报表）。"""
    out = finance_node(_state_with())
    fin = out["results"].finance
    ev = fin.evidence
    assert ev, "应产出财务 Evidence"
    for e in ev:
        assert e.source_type == "financial_statement", f"source_type={e.source_type}"
        assert e.statement_scope == "parent_company", f"scope={e.statement_scope}"
        assert "母公司报表" in e.source_title, f"source_title={e.source_title}"


def test_financial_claim_parent_scope_limitation(finance_db):
    """财务 Claim 的 limitations 包含母公司范围限制。"""
    state = _state_with()
    fin = finance_node(state)["results"].finance
    state["results"] = ModuleResults(finance=fin)
    out = build_claims_node(state)
    financial = [c for c in out["claims"] if c.claim_type == "financial"]
    assert financial, "应产出财务 Claim"
    for c in financial:
        assert any(
            "母公司报表" in lim for lim in c.limitations
        ), f"{c.claim_id} limitations={c.limitations}"


def test_warning_order_stable_across_runs(finance_db):
    """重复运行 warning 顺序稳定（非 set 随机）。"""
    w1 = list(finance_node(_state_with())["results"].finance.warnings)
    w2 = list(finance_node(_state_with())["results"].finance.warnings)
    assert w1 == w2
    # 无重复项
    assert len(w1) == len(set(w1))


def test_no_degrade_warning_in_finance(finance_db):
    """Finance warnings 不含口径切换 warning 文案。"""
    fin = finance_node(_state_with())["results"].finance
    for w in fin.warnings:
        assert "降级" not in w
        assert "合并报表优先" not in w


def test_rest_chat_warnings_propagate_finance(finance_db):
    """REST _build_chat_response 将 Finance 口径说明透传到 API warnings 且恰好一次。"""
    from app.api.v1.routers.chat import _build_chat_response

    state = _state_with()
    fin = finance_node(state)["results"].finance
    state["results"] = ModuleResults(finance=fin)
    state["module_status"] = {"finance": ModuleStatus(state="success")}
    resp = _build_chat_response(state, trace_id="trace-1")
    warnings = list(resp.data.warnings)
    assert warnings.count(SCOPE_NOTE) == 1, f"warnings={warnings}"


def test_rest_pure_equity_no_finance_warning(finance_db):
    """纯股权/纯事件请求（finance 未执行）→ 不产生母公司口径 warning。"""
    from app.api.v1.routers.chat import _build_chat_response

    state: AgentState = {
        "user_query": "只看股权",
        "company": CompanyRef(
            entity_id="company_x",
            wind_code="600000.SH",
            sec_name="X",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["equity"]),
        "module_status": {"equity": ModuleStatus(state="success")},
        "results": ModuleResults(finance=None),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    resp = _build_chat_response(state, trace_id="trace-2")
    assert all(SCOPE_NOTE not in w for w in resp.data.warnings)
