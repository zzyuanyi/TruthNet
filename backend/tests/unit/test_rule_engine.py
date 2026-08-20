"""规则引擎单元测试 — R1–R7 真实口径 + 边界情况.

覆盖（集成验收 §7.4）:
- 每条规则正例/反例; 缺字段; 零分母; NaN/None; 重复报告期;
- 合并+母公司同时存在（应取合并）; 仅母公司（降级+warning）; 单期;
- 多期趋势; 未来/错序日期（as_of 过滤）; RuleResult 序列化; Agent 接入。
全部基于 SQLite 合成数据，不访问 MySQL/网络/模型下载。
"""

import os
import sqlite3
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.agents.nodes.finance import finance_node
from app.agents.state import AgentState, CompanyRef, ExecutionPlan, RuntimeState
from app.core.config import settings
from app.domain.finance import _fetch
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_engine import evaluate_all_rules
from app.domain.finance.rule_r1 import evaluate_r1
from app.domain.finance.rule_r2 import evaluate_r2
from app.domain.finance.rule_r3 import evaluate_r3
from app.domain.finance.rule_r4 import evaluate_r4
from app.domain.finance.rule_r5 import evaluate_r5
from app.domain.finance.rule_r7 import evaluate_r7
from app.domain.finance.rule_utils import single_quarter_by_period

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


def test_r1_threshold_change_in_yaml_takes_effect(rule_db, tmp_path, monkeypatch):
    """#11: modifying the YAML thresholds changes runtime rule behavior."""
    from app.domain.finance import financial_rule_config

    conn = rule_db
    _insert_company(conn, "CFG_R1")
    ar = _seq(100_000_000, [0.05, 0.05, 0.15, 0.60])
    ore = _seq(200_000_000, [0.0, 0.0, 0.0, -0.20])
    _insert_bs(conn, "CFG_R1", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "CFG_R1", PARENT, {"oper_rev": ore})

    source = Path(financial_rule_config.__file__).with_name("financial_rules.yaml")
    config_path = tmp_path / "financial_rules.yaml"
    config_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(financial_rule_config, "_FINANCIAL_RULES_FILE", config_path)
    financial_rule_config.clear_financial_rule_config_cache()

    assert evaluate_r1("CFG_R1", "20260331").severity == "red"

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    for key in raw["rules"]["R1"]["thresholds"]:
        raw["rules"]["R1"]["thresholds"][key] = 10_000
    previous_mtime = config_path.stat().st_mtime_ns
    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    os.utime(
        config_path,
        ns=(previous_mtime + 1_000_000, previous_mtime + 1_000_000),
    )
    assert config_path.stat().st_mtime_ns != previous_mtime

    assert evaluate_r1("CFG_R1", "20260331").status == "not_triggered"


def test_r1_missing_intermediate_period_does_not_pair_by_index(rule_db):
    """R1 字段缺期时，不能把不同报告期按数组下标拼接。"""
    conn = rule_db
    _insert_company(conn, "PERIOD_R1")
    periods_ar = [
        "20240331",
        "20240630",
        "20240930",
        "20241231",
        "20250331",
        "20250630",
    ]
    periods_rev = [
        "20240331",
        "20240930",
        "20241231",
        "20250331",
        "20250630",
    ]
    _insert_bs(
        conn,
        "PERIOD_R1",
        PARENT,
        {"acct_rcv": [100e6, 110e6, 120e6, 130e6, 140e6, 200e6]},
        periods=periods_ar,
    )
    _insert_is(
        conn,
        "PERIOD_R1",
        PARENT,
        {"oper_rev": [100e6, 120e6, 130e6, 140e6, 150e6]},
        periods=periods_rev,
    )

    result = evaluate_r1("PERIOD_R1", "20250630", periods=8)

    assert result.status in ("triggered", "not_triggered")
    # 20250630 没有 20240630 的营收，不能把 20250630 的应收与其他营收期次配对；
    # 因而选择较早的完整同比对，结果应来自 20250331/20240331。
    assert result.current["acct_rcv_growth"]["value"] == pytest.approx(40.0)
    assert result.current["oper_rev_growth"]["value"] == pytest.approx(40.0)


def test_r5_missing_period_does_not_shift_cost_into_revenue_period(rule_db):
    """R5 各字段按 report_period 对齐，缺期不得整体左移。"""
    conn = rule_db
    _insert_company(conn, "PERIOD_R5")
    revenue_periods = [
        "20240331",
        "20240630",
        "20240930",
        "20241231",
        "20250331",
        "20250630",
    ]
    _insert_is(
        conn,
        "PERIOD_R5",
        PARENT,
        {
            "oper_rev": [100e6] * 6,
            "less_oper_cost": [90e6, None, 90e6, 90e6, 90e6, 10e6],
        },
        periods=revenue_periods,
    )

    result = evaluate_r5("PERIOD_R5", "20250630", periods=8)

    assert result.current["gross_margin"]["value"] == pytest.approx(90.0)


def test_financial_rule_switch_returns_explicit_not_applicable(tmp_path, monkeypatch):
    """#11: a disabled rule is explicit and does not query financial data."""
    from app.domain.finance import financial_rule_config

    source = Path(financial_rule_config.__file__).with_name("financial_rules.yaml")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    raw["rules"]["R2"]["enabled"] = False
    config_path = tmp_path / "financial_rules.yaml"
    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr(financial_rule_config, "_FINANCIAL_RULES_FILE", config_path)
    financial_rule_config.clear_financial_rule_config_cache()

    result = evaluate_r2("NO_DATABASE_ACCESS", "20260331")

    assert result.status == "not_applicable"
    assert result.severity == "unknown"
    assert result.warnings == ["RULE_DISABLED"]


def test_financial_rule_config_rejects_missing_threshold(tmp_path):
    """#11: invalid YAML fails closed instead of using hidden defaults."""
    from app.domain.finance.financial_rule_config import load_financial_rules

    source = Path(__file__).parents[2] / "app/domain/finance/financial_rules.yaml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    del raw["rules"]["R7"]["thresholds"]["cash_divergence_pp"]
    config_path = tmp_path / "invalid_financial_rules.yaml"
    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        load_financial_rules(config_path)


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
    # P1-3（第二轮审查修订）：借款分项必须完整（lt 缺失时下界未触发 →
    # insufficient_data 而非绿色），此测试验证双低时正常 not_triggered
    _insert_bs(
        conn,
        "600009.SH",
        PARENT,
        {
            "tot_assets": assets,
            "monetary_cap": [a * 0.05 for a in assets],
            "st_borrow": [a * 0.03 for a in assets],
            "lt_borrow": [a * 0.03 for a in assets],
        },
    )
    r = evaluate_r3("600009.SH", "20260331")
    assert r.status == "not_triggered"


# ══════════════════════════════════════════════════════════
# 口径: 固定母公司报表（408006000），不读取合并报表
# ══════════════════════════════════════════════════════════


def test_parent_fixed_even_when_consolidated_exists(rule_db):
    conn = rule_db
    _insert_company(conn, "600010.SH")
    # 同时存在合并(999 触发)与母公司(100 同步增长不触发)：必须只读母公司 408006000
    ar_cons = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore_cons = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600010.SH", CONSOLIDATED, {"acct_rcv": ar_cons})
    _insert_is(conn, "600010.SH", CONSOLIDATED, {"oper_rev": ore_cons})
    # 母公司口径不触发（同步增长）
    ar_par = _seq(100_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600010.SH", PARENT, {"acct_rcv": ar_par})
    _insert_is(conn, "600010.SH", PARENT, {"oper_rev": ore_cons})

    r = evaluate_r1("600010.SH", "20260331")
    # 固定母公司口径，绝不因合并报表存在而切换为 consolidated
    assert r.quality["statement_scope"] == "parent_company"
    assert r.quality["statement_type"] == PARENT


def test_fetch_series_uses_parent_even_when_consolidated_higher(rule_db):
    """合并表数值更高也必须被忽略：fetch_series 只返回母公司 408006000 的值。"""
    conn = rule_db
    _insert_company(conn, "600020.SH")
    # 合并表 acct_rcv = 999，母公司 = 100
    _insert_bs(
        conn,
        "600020.SH",
        CONSOLIDATED,
        {"acct_rcv": [999, 999, 999, 999, 999, 999, 999, 999]},
        periods=[
            "20250331",
            "20250630",
            "20250930",
            "20251231",
            "20260331",
            "20260331",
            "20260331",
            "20260331",
        ],
    )
    _insert_bs(
        conn,
        "600020.SH",
        PARENT,
        {"acct_rcv": [100, 110, 120, 130, 140, 150, 160, 170]},
    )
    sr = _fetch.fetch_series("600020.SH", "acct_rcv", 8, "20260331")
    assert sr.statement_type == PARENT
    assert sr.scope == "parent_company"
    assert sr.values and all(v < 999 for v in sr.values), "不得读取合并口径 999"


def test_consolidated_only_returns_insufficient_with_warning(rule_db):
    conn = rule_db
    _insert_company(conn, "600011.SH")
    # 只有合并报表，无母公司报表：不得降级使用合并数据
    ar_cons = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore_cons = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    _insert_bs(conn, "600011.SH", CONSOLIDATED, {"acct_rcv": ar_cons})
    _insert_is(conn, "600011.SH", CONSOLIDATED, {"oper_rev": ore_cons})

    r = evaluate_r1("600011.SH", "20260331")
    assert r.status == "insufficient_data"
    assert r.quality["statement_scope"] == "parent_company"
    assert r.quality["statement_type"] == PARENT
    assert r.quality["coverage"] == 0.0
    assert any("缺少母公司报表" in w for w in r.warnings), f"warnings={r.warnings}"
    assert not any("降级" in w for w in r.warnings)


def test_parent_only_no_degrade_warning(rule_db):
    conn = rule_db
    _insert_company(conn, "600012.SH")
    ar = _seq(100_000_000, [0.1, 0.1, 0.5, 0.8])
    ore = _seq(200_000_000, [0.1, 0.1, 0.1, 0.1])
    # 仅母公司口径
    _insert_bs(conn, "600012.SH", PARENT, {"acct_rcv": ar})
    _insert_is(conn, "600012.SH", PARENT, {"oper_rev": ore})

    r = evaluate_r1("600012.SH", "20260331")
    assert r.quality["statement_scope"] == "parent_company"
    assert r.quality["statement_type"] == PARENT
    # 不得出现口径切换 warning 文案
    assert not any("降级" in w for w in r.warnings), f"warnings={r.warnings}"


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
# 公司类型 Gate: 1→执行；2/3/4→不适用；NULL/非法→insufficient
# ══════════════════════════════════════════════════════════


def test_company_type_gate_financial_excluded(rule_db):
    """comp_type_code=2/3/4 → 全部规则 not_applicable + excluded_financial。"""
    conn = rule_db
    for code, ctype in [
        ("600030.SH", 2),
        ("600031.SH", 3),
        ("600032.SH", 4),
    ]:
        _insert_company(conn, code, comp_type=ctype)
        results = evaluate_all_rules(code, "20260331")
        for r in results.values():
            assert r.status == "not_applicable", f"{code} {r.rule_id} {r.status}"
            assert r.quality["company_type_status"] == "excluded_financial"
            assert r.quality["statement_scope"] == "parent_company"
            assert r.quality["statement_type"] == PARENT
            assert any("COMPANY_TYPE_FINANCIAL_EXCLUDED" == w for w in r.warnings)


def test_company_type_gate_null_is_insufficient(rule_db):
    """comp_type_code=NULL → 全部规则 insufficient_data，绝不当作非金融。"""
    conn = rule_db
    _insert_company(conn, "600033.SH", comp_type=None)
    results = evaluate_all_rules("600033.SH", "20260331")
    for r in results.values():
        assert r.status == "insufficient_data", f"{r.rule_id} {r.status}"
        assert r.severity == "unknown"
        assert r.quality["company_type_status"] == "unknown"
        assert r.quality["statement_scope"] == "parent_company"
        assert r.quality["statement_type"] == PARENT
        assert r.quality["coverage"] == 0.0
        assert "COMPANY_TYPE_UNKNOWN" in r.warnings


def test_company_type_gate_invalid_is_insufficient(rule_db):
    """comp_type_code 非法（如 7）→ insufficient_data。"""
    conn = rule_db
    _insert_company(conn, "600034.SH", comp_type=7)
    results = evaluate_all_rules("600034.SH", "20260331")
    for r in results.values():
        assert r.status == "insufficient_data"
        assert r.quality["company_type_status"] == "unknown"


def test_r4_short_history_no_index_error(rule_db):
    """R4 仅 3 期数据（无 t-4Q）→ insufficient_data，不抛 IndexError。"""
    conn = rule_db
    _insert_company(conn, "600036.SH")
    _insert_bs(
        conn,
        "600036.SH",
        PARENT,
        {"inventories": [1e8, 1.1e8, 1.2e8]},
        periods=_PERIODS[-3:],
    )
    _insert_is(
        conn,
        "600036.SH",
        PARENT,
        {"oper_rev": [2e8, 2.1e8, 2.2e8]},
        periods=_PERIODS[-3:],
    )
    r = evaluate_r4("600036.SH", "20260331")
    assert r.status == "insufficient_data"
    assert r.quality["statement_scope"] == "parent_company"


def test_single_quarter_by_period_requires_adjacent_quarter():
    """缺 Q1 时 Q2 不得拿上一条跨年累计值盲减。"""
    values = [100.0, 260.0]
    periods = ["20231231", "20240630"]

    assert single_quarter_by_period(values, periods) == [None, None]


def test_r4_turnover_missing_previous_inventory_is_unknown(rule_db):
    """R4 周转天数缺相邻季度存货时跳过，不把 None 当 0 参与计算。"""
    conn = rule_db
    _insert_company(conn, "600038.SH")
    periods = [
        "20240331",
        "20240630",
        "20240930",
        "20241231",
        "20250331",
        "20250630",
    ]
    _insert_bs(
        conn,
        "600038.SH",
        PARENT,
        {"inventories": [1e8, 1e8, 1e8, 1e8, None, 1e8]},
        periods=periods,
    )
    _insert_is(
        conn,
        "600038.SH",
        PARENT,
        {
            "oper_rev": [2e8, 2e8, 2e8, 2e8, 2e8, 2e8],
            "less_oper_cost": [5e7, 9e7, 13e7, 17e7, 5e7, 9e7],
        },
        periods=periods,
    )

    r = evaluate_r4("600038.SH", "20250630")

    assert "inventory_turnover_days" not in r.current
    assert r.quality["turnover_calculable"] is False


def test_r5_missing_current_cost_does_not_become_full_margin(rule_db):
    """R5 当期成本缺失不得按 0 计算成 100% 毛利率并触发 red。"""
    conn = rule_db
    _insert_company(conn, "600039.SH")
    _insert_is(
        conn,
        "600039.SH",
        PARENT,
        {
            "oper_rev": [1e8, 1e8, 1e8, 1e8, 1e8],
            "less_oper_cost": [9e7, 9e7, 9e7, 9e7, None],
        },
    )

    r = evaluate_r5("600039.SH", "20260331")

    assert r.status == "insufficient_data"
    assert r.severity != "red"
    assert "gross_margin" not in r.current


def test_r7_orange_without_core_ratio_no_type_error(rule_db):
    """R7 扣非字段缺失（简化版）触发 orange → 不抛 TypeError，quality 固定母公司口径。"""
    conn = rule_db
    _insert_company(conn, "600037.SH")
    # 简化版：net_profit 有、扣非字段全 NULL；营收/现金背离触发 orange
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    rev = [1e8, 1e8, 1e8, 1e8, 1e8]  # 增速 0
    cf = [1e8, 1.3e8, 1.6e8, 2.0e8, 2.5e8]  # 增速 >30%
    _insert_is(
        conn,
        "600037.SH",
        PARENT,
        {
            "net_profit_excl_min_int_inc": np,
            "oper_rev": rev,
            "net_profit_after_ded_nr_lp": [None] * 5,
        },
    )
    _insert_cf(conn, "600037.SH", PARENT, {"net_cash_flows_oper_act": cf})
    r = evaluate_r7("600037.SH", "20260331")
    assert r.status in (
        "triggered",
        "not_triggered",
        "insufficient_data",
        "not_applicable",
    )
    assert r.quality["statement_scope"] == "parent_company"


def test_all_statuses_carry_parent_scope_quality(rule_db):
    """triggered / not_triggered / insufficient_data 均携带母公司口径 quality。"""
    conn = rule_db
    _insert_company(conn, "600035.SH")
    # R2 触发数据
    np = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
    cf = [-5e7, -6e7, -7e7, -8e7, -9e7]
    _insert_is(conn, "600035.SH", PARENT, {"net_profit_excl_min_int_inc": np})
    _insert_cf(conn, "600035.SH", PARENT, {"net_cash_flows_oper_act": cf})
    results = evaluate_all_rules("600035.SH", "20260331")
    for r in results.values():
        assert r.quality, f"{r.rule_id} quality 为空"
        assert r.quality["statement_scope"] == "parent_company"
        assert r.quality["statement_type"] == PARENT
        assert r.quality["company_type_status"] == "known_non_financial"


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


def test_align_by_period_offsets():
    """P2-3：错位期次对齐——下标拼接会错配，对齐后各期值正确。"""
    from app.domain.finance._fetch import SeriesResult, align_by_period

    cash_sr = SeriesResult(values=[100, 200], periods=["20240331", "20241231"])
    assets_sr = SeriesResult(values=[1000, None], periods=["20240331", "20250630"])
    aligned = align_by_period(cash=cash_sr, assets=assets_sr)

    assert list(aligned.keys()) == ["20240331", "20241231", "20250630"]
    assert aligned["20240331"] == {"cash": 100, "assets": 1000}
    assert aligned["20241231"] == {"cash": 200, "assets": None}  # 该期无资产
    assert aligned["20250630"] == {"cash": None, "assets": None}  # 该期无现金


def test_r3_aligned_history_no_fake_zero(monkeypatch, rule_db):
    """P2-3：R3 history——分母缺失跳过、不制造零值、升序真实期次。

    核验修订：此前未插入测试数据，history=[] 空循环假通过；现补真实数据，
    断言 history 非空且每点期次真实升序。
    """
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [100, 120, 140, 160, 200, 220],
            "tot_assets": [1000, 1000, 1000, 1000, 1000, 1000],
            "st_borrow": [150, 160, 170, 180, 200, 210],
            "lt_borrow": [100, 100, 100, 100, 100, 100],
        },
        periods=[
            "20250331",
            "20250630",
            "20250930",
            "20251231",
            "20260331",
            "20260930",
        ],
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    assert r.status != "insufficient_data"
    assert len(r.history or []) >= 2, "插入数据后 history 不得为空（假通过）"
    for point in r.history:
        assert point["period"] not in ("", "nan")
        assert point["period"].isdigit()
        assert (
            point["period"].endswith("0331")
            or point["period"].endswith("1231")
            or point["period"].endswith("0630")
            or point["period"].endswith("0930")
        )
    periods = [p["period"] for p in r.history]
    assert periods == sorted(periods)


def test_r3_aligned_current_uses_core_period(rule_db):
    """P2-3（核验修订）：辅助字段（less_fin_exp，income 表）比核心字段多一期
    → current 取核心字段（cash/assets）最后共同期 20251231，不因并集最后一期
    20260331 核心缺失而错误 insufficient_data（并集最后一期假阴性）。

    balance_sheet 只到 20251231（最近 2 期 cash/assets 有值，通过早期检查）；
    income_statement 多出 20260331 的 less_fin_exp → 并集最后一期 = 20260331。
    """
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    core_periods = ["20241231", "20250331", "20250630", "20250930", "20251231"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [100, 120, 140, 160, 200],
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [150, 160, 170, 180, 200],
            "lt_borrow": [100, 100, 100, 100, 100],
        },
        periods=core_periods,
    )
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"less_fin_exp": [30, 30, 30, 30, 30, 30]},  # 辅助字段多出 20260331
        periods=core_periods + ["20260331"],
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    assert r.status != "insufficient_data"
    # current 基于 20251231：200/1000=20%，(200+100)/1000=30% → 双高
    assert r.current["cash_to_assets"]["value"] == 20.0
    assert r.current["debt_to_assets"]["value"] == 30.0


def test_r3_single_borrow_missing_lower_bound_not_triggered_is_insufficient(
    rule_db,
):
    """P1-3（第二轮审查修订）：单个借款分项缺失且下界未触发双高 → 必须返回
    insufficient_data——缺失项可能使真实负债越过阈值，不能给绿色。
    实测曾误报 green：cash 20% + st 10% + lt 未知。"""
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20241231", "20250331", "20250630", "20250930", "20251231"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [200, 200, 200, 200, 200],
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [100, 100, 100, 100, 100],  # 下界 10% < 20% 未触发
            "lt_borrow": [None, None, None, None, None],
        },
        periods=periods,
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    assert r.status == "insufficient_data"
    assert "borrow_field_missing" in (r.quality or {})
    assert r.quality["borrow_field_missing"] == ["lt_borrow"]


def test_r3_single_borrow_missing_lower_bound_triggered_conservative(rule_db):
    """P1-3（第二轮审查修订）：单个借款分项缺失但下界已触发双高 → 保守触发
    + borrow_partial 标记（真实负债只会更高，不漏报）。"""
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20241231", "20250331", "20250630", "20250930", "20251231"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [200, 200, 200, 200, 200],
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [250, 250, 250, 250, 250],  # 下界 25% > 20% 触发
            "lt_borrow": [None, None, None, None, None],
        },
        periods=periods,
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    assert r.status == "triggered"
    assert r.quality.get("borrow_partial") is True
    assert r.quality.get("borrow_field_missing") == ["lt_borrow"]


def test_r3_prev_looks_back_core_and_borrow_valid(rule_db):
    """P1-3（第二轮审查修订）：前期趋势比较向前查找"核心字段共同有效 + 借款
    至少一项有效"的最近期次——直接取并集上一期（20250930 借款缺失）会
    静默跳过持续扩大判断（severity 停在 orange），回退后应判 red。"""
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20241231", "20250331", "20250630", "20250930", "20251231"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [160, 160, 160, 160, 200],  # current 20%
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [180, 180, 180, None, 260],  # 20250930 缺 st
            "lt_borrow": [0, 0, 0, None, 0],  # 20250930 借款全缺失（st/lt 均 None）
        },
        periods=periods,
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    # current 20251231: cash 20% + debt 26% 双高 → 持续扩大检查回退到
    # 20250630（cash 16% + debt 18%）→ 20>16 且 26>18 → red
    assert r.status == "triggered"
    assert r.severity == "red"


def test_r6_aligned_current_correct_under_misaligned_periods(rule_db):
    """P2-3（核验修订）：期次错位下 current 取核心字段（oth_rcv/assets）
    共同有效期的数据，按下标拼接会取错值。"""
    from app.domain.finance.rule_r6 import evaluate_r6

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20241231", "20250331", "20250630", "20250930", "20251231", "20260331"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "oth_rcv": [5e8, 6e8, None, 8e8, 10e8, 12e8],  # 缺 20250630
            "tot_assets": [1e10, 1e10, 1e10, 1e10, 1e10, 1e10],
            "acct_rcv": [5e9, 5e9, 5e9, 5e9, 5e9, 5e9],
        },
        periods=periods,
    )
    r = evaluate_r6("TEST", "20260331", periods=8)
    assert r.status != "insufficient_data"
    # current = 20260331：12e8/1e10 = 12.0%
    assert r.current["oth_rcv_to_assets"]["value"] == 12.0


def test_r6_yoy_none_not_zero(rule_db):
    """P1-3（核验修订）：去年同期缺失 → 同比为 None（不是 0%），
    current 省略该指标，explanation 不格式化 None。"""
    from app.domain.finance.rule_r6 import evaluate_r6

    _insert_company(rule_db, "TEST", comp_type=1)
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "oth_rcv": [10e8, 11e8, 15e8],  # 无前一年同月日期次（≥1 万分母保护）
            "tot_assets": [1e10, 1e10, 1e10],
            "acct_rcv": [5e9, 5e9, 5e9],
        },
        periods=["20250630", "20250930", "20251231"],
    )
    r = evaluate_r6("TEST", "20260331", periods=8)
    assert r.status != "insufficient_data"
    assert "oth_rcv_yoy" not in r.current  # 缺失不输出 0%
    assert "0.0%" not in (r.explanation or "")


def test_r6_yoy_uses_prev_year_same_period(rule_db):
    """P1-3（核验修订）：同比取前一年同月日期次（20251231 vs 20241231），
    不是并集数组下标 -5（错位时可能取到不同月日）。"""
    from app.domain.finance.rule_r6 import evaluate_r6

    _insert_company(rule_db, "TEST", comp_type=1)
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "oth_rcv": [5e8, 6e8, 7e8, 8e8, 10e8],  # 10e8 vs 5e8 → +100%
            "tot_assets": [1e10, 1e10, 1e10, 1e10, 1e10],
            "acct_rcv": [5e9, 5e9, 5e9, 5e9, 5e9],
        },
        periods=["20241231", "20250331", "20250630", "20250930", "20251231"],
    )
    r = evaluate_r6("TEST", "20260331", periods=8)
    assert r.status != "insufficient_data"
    assert r.current["oth_rcv_yoy"]["value"] == 100.0


def test_prev_year_period_exact_only():
    """P1-3（第二轮审查修订）：同比必须只接受精确 YYYY-1+MMDD。

    20251231 配合 20231231（缺 20241231）时不得回退——两年前变化
    不能被当成同比。
    """
    from app.domain.finance._fetch import prev_year_period

    assert prev_year_period("20251231", ["20241231", "20251231"]) == "20241231"
    # 精确去年同期缺失 → None（不得回退 20231231）
    assert prev_year_period("20251231", ["20231231", "20251231"]) is None
    assert prev_year_period("20250331", ["20250331"]) is None
    assert prev_year_period("20250331", ["20240331", "20250331"]) == "20240331"


def test_r2_aligned_does_not_pair_misaligned_periods(rule_db):
    """P1-1（第二轮审查修订）：R2 判定全部消费对齐结果——最新共同期现金流为
    正、仅下一期现金流为负时，不得把下一期现金流与上一期利润配成
    consecutive negative（旧下标拼接会误判 red）。"""
    from app.domain.finance.rule_r2 import evaluate_r2

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20250331", "20250630", "20250930", "20251231", "20260331"]
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"net_profit_excl_min_int_inc": [1e8, 1e8, 1e8, 1e8, 1e8]},
        periods=periods,
    )
    # 现金流：20260331 无数据（错位），20251231 为负
    _insert_cf(
        rule_db,
        "TEST",
        PARENT,
        {"net_cash_flows_oper_act": [1e8, 1e8, -1e8, 1e8, None]},
        periods=periods,
    )
    r = evaluate_r2("TEST", "20260331", periods=8)
    # 对齐窗口最近 4 期 = [20250630, 20250930, 20251231, 20260331]
    # cf = [1e8, -1e8, 1e8, None] → 无连续负现金流；current(20260331) cf=None
    assert r.status != "insufficient_data"
    assert r.severity != "red"  # 旧下标拼接会把 -1e8 与下一期利润配对成负流
    assert r.current["consec_neg_cf"]["value"] < 2


def test_r2_common_period_window_detects_risk(rule_db):
    """P1-1（第三轮审查修订）：R2 按共同有效期判定——利润到 20241231、
    现金流多出 20250331（单边数据不参与），共同期前连续 3 期正利润负
    现金流 → 应 red。旧逻辑 current 取并集最后一期（利润 None）→ green 漏报。"""
    from app.domain.finance.rule_r2 import evaluate_r2

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20240331", "20240630", "20240930", "20241231", "20250331"]
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"net_profit_excl_min_int_inc": [1e8, 1e8, 1e8, 1e8, None]},
        periods=periods,
    )
    _insert_cf(
        rule_db,
        "TEST",
        PARENT,
        {"net_cash_flows_oper_act": [-5e7, -5e7, -5e7, -5e7, -5e7]},
        periods=periods,
    )
    r = evaluate_r2("TEST", "20260331", periods=8)
    assert r.status == "triggered"
    assert r.severity == "red"  # 共同期窗口内连续 3 期负现金流 + 当前负
    assert r.current["consec_neg_cf"]["value"] >= 3


def test_r2_missing_period_breaks_consecutive(rule_db):
    """P1-1（第三轮审查修订）：窗口内缺失期打断连续负现金流（不跨期累计）。"""
    from app.domain.finance.rule_r2 import evaluate_r2

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20240331", "20240630", "20240930", "20241231", "20250331"]
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"net_profit_excl_min_int_inc": [1e8, 1e8, 1e8, 1e8, 1e8]},
        periods=periods,
    )
    # cf 中间缺 20240930 → 负现金流被分成两段（各 1 期），不得累计为 3
    _insert_cf(
        rule_db,
        "TEST",
        PARENT,
        {"net_cash_flows_oper_act": [-5e7, -5e7, None, -5e7, -5e7]},
        periods=periods,
    )
    r = evaluate_r2("TEST", "20260331", periods=8)
    # 缺失打断后重新累计：20241231+20250331 连续 2 期（非 3 期跨期累计）
    assert r.current["consec_neg_cf"]["value"] == 2
    assert r.severity != "red"  # 2 期不满足 red（需 >=3）


def test_r3_partial_no_implied_rate_no_red(rule_db):
    """P1-2（第三轮审查修订）：partial（借款缺失）时不计算隐含利率、不升级
    red——下界负债会高估利率（实测下界 6.67% vs 真实 3.33%）。"""
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20241231", "20250331", "20250630", "20250930", "20251231"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [300, 300, 300, 300, 300],
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [300, 300, 300, 300, 300],  # 下界 30%
            "lt_borrow": [None, None, None, None, None],  # 未知
        },
        periods=periods,
    )
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"less_fin_exp": [20, 20, 20, 20, 20]},
        periods=periods,
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    assert r.status == "triggered"  # 下界双高 → 保守触发
    assert r.severity == "orange"  # 上限 orange，不升 red
    assert "implied_interest_rate" not in r.current  # 不计算隐含利率
    assert r.quality.get("borrow_partial") is True
    assert r.quality.get("implied_rate_calculable") is False


def test_r2_missing_whole_quarter_resets_consecutive(rule_db):
    """P1-1（第四轮审查修订）：整季缺失（两张表均无 20240630）时，
    20240331/20240930/20241231 不是连续季度，连续负现金流不得累计为 3——
    需要报告期相邻校验。"""
    from app.domain.finance.rule_r2 import evaluate_r2

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20240331", "20240930", "20241231"]  # 缺 20240630
    _insert_is(
        rule_db,
        "TEST",
        PARENT,
        {"net_profit_excl_min_int_inc": [1e8, 1e8, 1e8]},
        periods=periods,
    )
    _insert_cf(
        rule_db,
        "TEST",
        PARENT,
        {"net_cash_flows_oper_act": [-5e7, -5e7, -5e7]},
        periods=periods,
    )
    r = evaluate_r2("TEST", "20260331", periods=8)
    # 20240930 与 20241231 是相邻季度（consec=2），但跨 20240630 的
    # 20240331 不得与之累计为 3 → 相邻校验生效，不误判 red
    assert r.current["consec_neg_cf"]["value"] == 2
    assert r.severity != "red"


def test_r3_prev_borrow_incomplete_skips_trend_red(rule_db):
    """P1-1（第四轮审查修订）：趋势 red 要求前期 st/lt 都完整——前期 lt
    缺失时用下界判断"持续扩大"会误升 red（真实负债可能反而下降），
    应跳过趋势升级保留 orange。"""
    from app.domain.finance.rule_r3 import evaluate_r3

    _insert_company(rule_db, "TEST", comp_type=1)
    periods = ["20240331", "20240630", "20240930", "20241231", "20250331"]
    _insert_bs(
        rule_db,
        "TEST",
        PARENT,
        {
            "monetary_cap": [240, 240, 240, 250, 260],  # 24%→25%→26%
            "tot_assets": [1000, 1000, 1000, 1000, 1000],
            "st_borrow": [200, 200, 200, 200, 260],
            "lt_borrow": [100, 100, 100, None, 150],  # 前期 20241231 lt 缺失
        },
        periods=periods,
    )
    r = evaluate_r3("TEST", "20260331", periods=8)
    # current(20250331) 借款完整 26%+41%；prev(20241231) lt 缺失 →
    # 下界 20% 显示"持续扩大"——但真实负债可能下降，不得升 red
    assert r.status == "triggered"
    assert r.severity == "orange"
    assert r.quality.get("borrow_partial") is False  # 当前期借款完整


def test_next_quarter_validates_full_quarter_end_date():
    """P2（第五轮审查修订）：next_quarter 必须校验完整季度末日期，
    不能只看月份——20240330 月份为 3 但不是季度末（0331），应返回 None。
    （8.11 C5：提取到公共 period.next_quarter，R2 与 CV-NUM-01 共用）"""
    from app.domain.finance.period import next_quarter

    assert next_quarter("20240331") == "20240630"
    assert next_quarter("20241231") == "20250331"
    assert next_quarter("20250630") == "20250930"
    assert next_quarter("20250930") == "20251231"
    # 月份正确但日期不是季度末 → None
    assert next_quarter("20240330") is None
    assert next_quarter("20241230") is None
    assert next_quarter("20250929") is None
    # 非季度末月份 → None
    assert next_quarter("20250115") is None
    # 非法格式 → None
    assert next_quarter("") is None
    assert next_quarter("2024") is None
