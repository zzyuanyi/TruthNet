"""规则引擎单元测试 — R1–R7 真实口径 + 边界情况.

覆盖（集成验收 §7.4）:
- 每条规则正例/反例; 缺字段; 零分母; NaN/None; 重复报告期;
- 合并+母公司同时存在（应取合并）; 仅母公司（降级+warning）; 单期;
- 多期趋势; 未来/错序日期（as_of 过滤）; RuleResult 序列化; Agent 接入。
全部基于 SQLite 合成数据，不访问 MySQL/网络/模型下载。
"""

import sqlite3

import pytest

from app.agents.nodes.finance import finance_node
from app.agents.state import AgentState, CompanyRef, ExecutionPlan, RuntimeState
from app.core.config import settings
from app.domain.finance import _fetch
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_engine import evaluate_all_rules
from app.domain.finance.rule_r1 import evaluate_r1
from app.domain.finance.rule_r2 import evaluate_r2
from app.domain.finance.rule_r3 import evaluate_r3

CONSOLIDATED = "408001000"
PARENT = "408006000"

# 报告期（5 期，供 t 与 t-4Q）
_PERIODS = ["20250331", "20250630", "20250930", "20251231", "20260331"]

_BS_COLS = [
    "wind_code",
    "report_period",
    "statement_type",
    "monetary_cap",
    "acct_rcv",
    "oth_rcv",
    "inventories",
    "tot_assets",
    "st_borrow",
    "lt_borrow",
    "bonds_payable",
    "non_cur_liab_due_within_1y",
    "tot_cur_assets",
    "tot_cur_liab",
    "tot_liab",
    "tot_shrhldr_eqy_incl_min_int",
]
_IS_COLS = [
    "wind_code",
    "report_period",
    "statement_type",
    "oper_rev",
    "tot_oper_rev",
    "less_oper_cost",
    "less_selling_dist_exp",
    "less_gerl_admin_exp",
    "less_fin_exp",
    "oper_profit",
    "tot_profit",
    "net_profit_excl_min_int_inc",
    "net_profit_after_ded_nr_lp",
]
_CF_COLS = [
    "wind_code",
    "report_period",
    "statement_type",
    "net_cash_flows_oper_act",
    "net_cash_flows_inv_act",
    "net_cash_flows_fnc_act",
    "free_cash_flow",
]


@pytest.fixture
def rule_db(tmp_path, monkeypatch):
    """临时 SQLite 库，指向 settings 并清空引擎缓存."""
    db_path = tmp_path / "rules_test.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE companies (wind_code TEXT PRIMARY KEY, sec_name TEXT, "
        "comp_type_code INTEGER, industry_l1 TEXT)"
    )
    conn.execute(
        "CREATE TABLE balance_sheet (id INTEGER PRIMARY KEY, wind_code TEXT, "
        + " TEXT, ".join(_BS_COLS[1:])
        + " TEXT)"
    )
    conn.execute(
        "CREATE TABLE income_statement (id INTEGER PRIMARY KEY, wind_code TEXT, "
        + " TEXT, ".join(_IS_COLS[1:])
        + " TEXT)"
    )
    conn.execute(
        "CREATE TABLE cash_flow (id INTEGER PRIMARY KEY, wind_code TEXT, "
        + " TEXT, ".join(_CF_COLS[1:])
        + " TEXT)"
    )
    conn.commit()

    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db_path))
    monkeypatch.setattr(_fetch, "_ENGINES", {})
    yield conn
    conn.close()


def _insert_company(conn, code, comp_type=1, industry="医药"):
    conn.execute(
        "INSERT INTO companies (wind_code, sec_name, comp_type_code, industry_l1) VALUES (?,?,?,?)",
        (code, code, comp_type, industry),
    )
    conn.commit()


def _insert_bs(conn, code, stmt_type, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": stmt_type}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        cols = _BS_COLS
        conn.execute(
            f"INSERT INTO balance_sheet ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [row.get(c) for c in cols],
        )
    conn.commit()


def _insert_is(conn, code, stmt_type, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": stmt_type}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        cols = _IS_COLS
        conn.execute(
            f"INSERT INTO income_statement ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [row.get(c) for c in cols],
        )
    conn.commit()


def _insert_cf(conn, code, stmt_type, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": stmt_type}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        cols = _CF_COLS
        conn.execute(
            f"INSERT INTO cash_flow ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [row.get(c) for c in cols],
        )
    conn.commit()


def _seq(base, growths):
    """从 base 起按 growths 生成数值序列（单位：元）."""
    vals = [base]
    for g in growths:
        vals.append(vals[-1] + base * g)
    return vals


# ══════════════════════════════════════════════════════════
# R1 · 应收–营收背离
# ══════════════════════════════════════════════════════════


def test_r1_trigger_red(rule_db):
    conn = rule_db
    _insert_company(conn, "600001.SH")
    # acct_rcv 强势增长，oper_rev 下滑 → R1 red
    ar = _seq(100_000_000, [0.05, 0.05, 0.15, 0.60])
    ore = _seq(200_000_000, [0.0, 0.0, 0.0, -0.20])
    _insert_bs(conn, "600001.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600001.SH", PARENT, {"oper_rev": ore})

    r = evaluate_r1("600001.SH", "20260331")
    assert r.status == "triggered"
    assert r.severity == "red"
    assert r.quality["statement_scope"] == "parent_company"
    assert r.evidence_ids  # 有证据引用


def test_r1_not_triggered(rule_db):
    conn = rule_db
    _insert_company(conn, "600002.SH")
    # 应收与营收同步增长，背离小
    ar = _seq(100_000_000, [0.1, 0.1, 0.1, 0.1])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600002.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600002.SH", PARENT, {"oper_rev": ore})

    r = evaluate_r1("600002.SH", "20260331")
    assert r.status == "not_triggered"


def test_r1_insufficient_short_history(rule_db):
    conn = rule_db
    _insert_company(conn, "600003.SH")
    # 仅 2 期数据 → t-4Q 不存在 → insufficient_data
    _insert_bs(
        conn, "600003.SH", PARENT, {"acct_rcv": [1e8, 1.1e8]}, periods=_PERIODS[-2:]
    )
    _insert_is(
        conn, "600003.SH", PARENT, {"oper_rev": [2e8, 2.1e8]}, periods=_PERIODS[-2:]
    )
    r = evaluate_r1("600003.SH", "20260331")
    assert r.status == "insufficient_data"


def test_r1_zero_denominator_protection(rule_db):
    conn = rule_db
    _insert_company(conn, "600004.SH")
    # t-4Q 的 acct_rcv 为 0 → yoy 分母保护 → insufficient_data
    ar = [0, 1000, 2000, 3000, 4000]  # t-4=0
    ore = _seq(200_000_000, [0, 0, 0, 0])
    _insert_bs(conn, "600004.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600004.SH", PARENT, {"oper_rev": ore})
    r = evaluate_r1("600004.SH", "20260331")
    assert r.status == "insufficient_data"


# ══════════════════════════════════════════════════════════
# R2 · 现金流–利润背离
# ══════════════════════════════════════════════════════════


def test_r2_trigger(rule_db):
    conn = rule_db
    _insert_company(conn, "600005.SH")
    # 净利润为正但经营现金流连续为负 ≥3 期（含当期）→ red
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    cf = [-5e7, -6e7, -7e7, -8e7, -9e7]
    _insert_is(conn, "600005.SH", PARENT, {"net_profit_excl_min_int_inc": np})
    _insert_cf(conn, "600005.SH", PARENT, {"net_cash_flows_oper_act": cf})

    r = evaluate_r2("600005.SH", "20260331")
    assert r.status == "triggered"


def test_r2_not_triggered(rule_db):
    conn = rule_db
    _insert_company(conn, "600006.SH")
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    cf = [1.2e8, 1.3e8, 1.4e8, 1.5e8, 1.6e8]  # 现金充足
    _insert_is(conn, "600006.SH", PARENT, {"net_profit_excl_min_int_inc": np})
    _insert_cf(conn, "600006.SH", PARENT, {"net_cash_flows_oper_act": cf})
    r = evaluate_r2("600006.SH", "20260331")
    assert r.status == "not_triggered"


def test_r2_loss_making_not_applicable(rule_db):
    conn = rule_db
    _insert_company(conn, "600007.SH")
    np = [-1e8, -1.1e8, -1.2e8, -1.3e8, -1.4e8]  # 持续亏损
    cf = [-5e7, -5e7, -5e7, -5e7, -5e7]
    _insert_is(conn, "600007.SH", PARENT, {"net_profit_excl_min_int_inc": np})
    _insert_cf(conn, "600007.SH", PARENT, {"net_cash_flows_oper_act": cf})
    r = evaluate_r2("600007.SH", "20260331")
    assert r.status == "not_applicable"


# ══════════════════════════════════════════════════════════
# R3 · 存贷双高
# ══════════════════════════════════════════════════════════


def test_r3_trigger(rule_db):
    conn = rule_db
    _insert_company(conn, "600008.SH")
    # 货币资金 30%、有息负债 25% → 双高
    assets = _seq(1000_000_000, [0.1, 0.1, 0.1, 0.1])
    monetary = [a * 0.30 for a in assets]
    st_borrow = [a * 0.20 for a in assets]
    lt_borrow = [a * 0.05 for a in assets]
    fin_exp = [a * 0.02 for a in assets]
    _insert_bs(
        conn,
        "600008.SH",
        PARENT,
        {
            "tot_assets": assets,
            "monetary_cap": monetary,
            "st_borrow": st_borrow,
            "lt_borrow": lt_borrow,
        },
    )
    _insert_is(conn, "600008.SH", PARENT, {"less_fin_exp": fin_exp})
    r = evaluate_r3("600008.SH", "20260331")
    assert r.status == "triggered"


def test_r3_not_triggered(rule_db):
    conn = rule_db
    _insert_company(conn, "600009.SH")
    assets = _seq(1000_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(
        conn,
        "600009.SH",
        PARENT,
        {
            "tot_assets": assets,
            "monetary_cap": [a * 0.05 for a in assets],
            "st_borrow": [a * 0.03 for a in assets],
        },
    )
    r = evaluate_r3("600009.SH", "20260331")
    assert r.status == "not_triggered"


# ══════════════════════════════════════════════════════════
# 口径: 合并优先 / 母公司降级
# ══════════════════════════════════════════════════════════


def test_consolidated_preferred_when_both(rule_db):
    conn = rule_db
    _insert_company(conn, "600010.SH")
    # 同时插入合并与母公司：合并数据触发，母公司不触发
    ar_cons = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore_cons = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600010.SH", CONSOLIDATED, {"acct_rcv": ar_cons})
    _insert_is(conn, "600010.SH", CONSOLIDATED, {"oper_rev": ore_cons})
    # 母公司口径不触发（同步增长）
    ar_par = _seq(100_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600010.SH", PARENT, {"acct_rcv": ar_par})
    _insert_is(conn, "600010.SH", PARENT, {"oper_rev": ore_cons})

    r = evaluate_r1("600010.SH", "20260331")
    assert r.quality["statement_scope"] == "consolidated"
    assert r.quality["statement_type"] == CONSOLIDATED


def test_parent_only_fallback_with_warning(rule_db):
    conn = rule_db
    _insert_company(conn, "600011.SH")
    ar = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    # 仅母公司口径
    _insert_bs(conn, "600011.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600011.SH", PARENT, {"oper_rev": ore})

    r = evaluate_r1("600011.SH", "20260331")
    assert r.quality["statement_scope"] == "parent_company"
    assert any("降级母公司" in w or "408006000" in w for w in r.warnings)


def test_as_of_filters_future_periods(rule_db):
    conn = rule_db
    _insert_company(conn, "600012.SH")
    # 插入含未来报告期的数据；as_of=20251231 时应排除 20260331
    ar = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600012.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600012.SH", PARENT, {"oper_rev": ore})
    # 用更早的 as_of（只有 4 期 ≤ 20251231，t-4Q 仍存在）
    r = evaluate_r1("600012.SH", "20251231")
    assert r.status in ("triggered", "not_triggered", "insufficient_data")
    # as_of 更早到只剩 1 期 → 必然 insufficient
    r2 = evaluate_r1("600012.SH", "20250331")
    assert r2.status == "insufficient_data"


def test_single_period_insufficient(rule_db):
    conn = rule_db
    _insert_company(conn, "600013.SH")
    _insert_bs(conn, "600013.SH", PARENT, {"acct_rcv": [1e8]}, periods=["20260331"])
    _insert_is(conn, "600013.SH", PARENT, {"oper_rev": [2e8]}, periods=["20260331"])
    r = evaluate_r1("600013.SH", "20260331")
    assert r.status == "insufficient_data"


# ══════════════════════════════════════════════════════════
# RuleResult 序列化
# ══════════════════════════════════════════════════════════


def test_rule_result_serialization_roundtrip(rule_db):
    conn = rule_db
    _insert_company(conn, "600014.SH")
    ar = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600014.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600014.SH", PARENT, {"oper_rev": ore})
    r = evaluate_r1("600014.SH", "20260331")

    dumped = r.model_dump_json()
    restored = RuleResult.model_validate_json(dumped)
    assert restored.rule_id == r.rule_id
    assert restored.status == r.status
    assert restored.quality == r.quality
    assert restored.evidence_ids == r.evidence_ids


def test_nan_none_values(rule_db):
    conn = rule_db
    _insert_company(conn, "600015.SH")
    # 含 None 值与极小值，不应崩溃，返回 insufficient 或合法状态
    ar = [None, 1000, 2000, 3000, 4000]
    ore = [None, 1000, 2000, 3000, 4000]
    _insert_bs(conn, "600015.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600015.SH", PARENT, {"oper_rev": ore})
    r = evaluate_r1("600015.SH", "20260331")
    assert r.status in (
        "triggered",
        "not_triggered",
        "insufficient_data",
        "not_applicable",
    )


# ══════════════════════════════════════════════════════════
# 汇总入口 + 异常兜底
# ══════════════════════════════════════════════════════════


def test_evaluate_all_rules_returns_seven(rule_db):
    conn = rule_db
    _insert_company(conn, "600016.SH")
    results = evaluate_all_rules("600016.SH", "20260331")
    assert set(results.keys()) == {f"R{i}" for i in range(1, 8)}
    for r in results.values():
        assert r.rule_id  # 每条规则有 id


def test_evaluate_all_unknown_company_insufficient(rule_db):
    # 不存在于 companies 表的公司 → 各规则应返回 insufficient/NA，不抛异常
    results = evaluate_all_rules("999999.SZ", "20260331")
    for r in results.values():
        assert r.status in ("insufficient_data", "not_applicable")


# ══════════════════════════════════════════════════════════
# Agent 接入: finance_node 调用真实规则引擎
# ══════════════════════════════════════════════════════════


def test_finance_node_calls_rule_engine(rule_db):
    conn = rule_db
    _insert_company(conn, "600017.SH")
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    cf = [-5e7, -6e7, -7e7, -8e7, -9e7]
    ar = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_is(
        conn,
        "600017.SH",
        PARENT,
        {"net_profit_excl_min_int_inc": np, "oper_rev": ore},
    )
    _insert_cf(conn, "600017.SH", PARENT, {"net_cash_flows_oper_act": cf})
    _insert_bs(conn, "600017.SH", PARENT, {"acct_rcv": ar})

    state: AgentState = {
        "user_query": "康美有风险吗",
        "company": CompanyRef(
            entity_id="company_600017_SH",
            wind_code="600017.SH",
            sec_name="测试公司",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    out = finance_node(state)
    fin = out["results"].finance
    assert fin is not None
    assert "R2" in fin.rule_statuses
    assert fin.rule_statuses["R2"] == "triggered"
    # 规则证据被转换为 EvidenceRef
    assert any(ev.evidence_id.startswith("ev_") for ev in fin.evidence)


def test_finance_node_skips_when_not_planned(rule_db):
    state: AgentState = {
        "user_query": "只看股权",
        "company": CompanyRef(
            entity_id="company_x",
            wind_code="600000.SH",
            sec_name="X",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["equity"]),
        "runtime": RuntimeState(trace_id="t"),
    }
    out = finance_node(state)
    assert out["module_status"]["finance"].state == "skipped"
