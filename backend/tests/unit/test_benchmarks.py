"""行业分位计算单元测试 — Phase C 数据任务 3.

覆盖:
- 指标注册表（R1-R7 真实中间量）纯函数计算
- quantile 单调性 p05<=p25<=p50<=p75<=p95
- percentile_rank 非插值
- 样本不足 <5 不伪造分位
- 金融企业排除、分母保护不当作 0
- calculator 集成（SQLite 合成数据）
"""

import sqlite3

import pytest

from app.domain.benchmarks.calculator import (
    MIN_PEER_SAMPLE,
    aggregate_stats,
    compute_benchmark_row,
    compute_metric_values,
    eligible_companies,
    percentile_rank,
)
from app.domain.benchmarks.metric_registry import all_metrics, get_metric
from app.core.config import settings
from app.domain.finance import _fetch

PARENT = "408006000"

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

_PERIODS = ["20250331", "20250630", "20250930", "20251231", "20260331"]


@pytest.fixture
def bench_db(tmp_path, monkeypatch):
    """临时 SQLite 库（companies/bs/is/cf），指向 settings 并清空引擎缓存。"""
    db_path = tmp_path / "bench_test.db"
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


def _co(conn, code, ctype=1, industry="医药"):
    conn.execute(
        "INSERT INTO companies (wind_code, sec_name, comp_type_code, industry_l1) "
        "VALUES (?,?,?,?)",
        (code, code, ctype, industry),
    )
    conn.commit()


def _bs(conn, code, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": PARENT}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        conn.execute(
            f"INSERT INTO balance_sheet ({', '.join(_BS_COLS)}) "
            f"VALUES ({', '.join('?' for _ in _BS_COLS)})",
            [row.get(c) for c in _BS_COLS],
        )
    conn.commit()


def _is(conn, code, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": PARENT}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        conn.execute(
            f"INSERT INTO income_statement ({', '.join(_IS_COLS)}) "
            f"VALUES ({', '.join('?' for _ in _IS_COLS)})",
            [row.get(c) for c in _IS_COLS],
        )
    conn.commit()


def _cf(conn, code, fields, periods=None):
    periods = periods or _PERIODS
    for i, p in enumerate(periods):
        row = {"wind_code": code, "report_period": p, "statement_type": PARENT}
        for col, vals in fields.items():
            row[col] = vals[i] if isinstance(vals, list) else vals
        conn.execute(
            f"INSERT INTO cash_flow ({', '.join(_CF_COLS)}) "
            f"VALUES ({', '.join('?' for _ in _CF_COLS)})",
            [row.get(c) for c in _CF_COLS],
        )
    conn.commit()


def _engine(db_path=None):
    """用 monkeypatch 后的 settings.SQLITE_PATH 建引擎（与规则引擎同路径）。"""
    from sqlalchemy import create_engine

    path = db_path or settings.SQLITE_PATH
    return create_engine(f"sqlite:///{path}")


# ══════════════════════════════════════════════════════════
# 纯函数：指标计算
# ══════════════════════════════════════════════════════════


def test_r1_gap_computation():
    m = get_metric("r1_gap")
    # acct_rcv: 100→150 (+50%), oper_rev: 200→220 (+10%) → gap=40pp
    series = {
        "acct_rcv": [100, 105, 110, 120, 150],
        "oper_rev": [200, 205, 210, 215, 220],
    }
    assert m.compute_from_series(series) == pytest.approx(40.0)


def test_r1_gap_short_history_none():
    m = get_metric("r1_gap")
    series = {"acct_rcv": [100, 150], "oper_rev": [200, 220]}
    assert m.compute_from_series(series) is None


def test_r2_cf_ratio():
    m = get_metric("r2_cf_ratio")
    series = {"net_profit_excl_min_int_inc": [1e8], "net_cash_flows_oper_act": [3e7]}
    assert m.compute_from_series(series) == pytest.approx(0.3)


def test_r2_cf_ratio_zero_profit_none():
    m = get_metric("r2_cf_ratio")
    series = {"net_profit_excl_min_int_inc": [0], "net_cash_flows_oper_act": [3e7]}
    assert m.compute_from_series(series) is None


def test_r3_debt_to_assets():
    m = get_metric("r3_debt_to_assets")
    series = {
        "tot_assets": [1000.0],
        "st_borrow": [100.0],
        "lt_borrow": [50.0],
        "bonds_payable": [None],
        "non_cur_liab_due_within_1y": [None],
    }
    assert m.compute_from_series(series) == pytest.approx(0.15)


def test_r5_gross_margin():
    m = get_metric("r5_gross_margin")
    series = {"oper_rev": [100.0], "less_oper_cost": [60.0]}
    assert m.compute_from_series(series) == pytest.approx(0.4)


def test_r5_gross_margin_zero_rev_none():
    m = get_metric("r5_gross_margin")
    series = {"oper_rev": [0.0], "less_oper_cost": [60.0]}
    assert m.compute_from_series(series) is None


def test_r4_turnover_days():
    m = get_metric("r4_turnover_days")
    # inv 100,110；单季成本 (220-200)=20*4=80 年化；avg_inv=105 → 105/80*365
    series = {"inventories": [100.0, 110.0], "less_oper_cost": [200.0, 220.0]}
    days = m.compute_from_series(series)
    assert days == pytest.approx(105 / 80 * 365)


# ══════════════════════════════════════════════════════════
# 聚合统计
# ══════════════════════════════════════════════════════════


def test_quantile_monotonic():
    vals = [1.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0]
    s = aggregate_stats(vals)
    assert s["p05"] <= s["p25"] <= s["p50"] <= s["p75"] <= s["p95"]
    assert s["min_value"] == 1.0
    assert s["max_value"] == 200.0
    assert s["p50"] == 20.0
    assert s["sample_count"] == 7


def test_aggregate_empty():
    s = aggregate_stats([])
    assert s["sample_count"] == 0
    assert s["p05"] is None and s["p95"] is None


def test_percentile_rank_non_interp():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile_rank(3.0, vals) == 60.0  # 3/5 个 <= 3
    assert percentile_rank(5.0, vals) == 100.0
    assert percentile_rank(0.0, vals) == 0.0


def test_metrics_cover_all_rules():
    rule_ids = {m.rule_id for m in all_metrics()}
    # R7 对标指标已移除（官方数据无扣非净利润字段，永久零样本），仅覆盖 R1-R6
    assert rule_ids == {f"R{i}" for i in range(1, 7)}
    assert len(all_metrics()) >= 7


# ══════════════════════════════════════════════════════════
# calculator 集成（SQLite）
# ══════════════════════════════════════════════════════════


def test_eligible_companies_excludes_financial(bench_db):
    _co(bench_db, "600001.SH", ctype=1, industry="医药")
    _co(bench_db, "600002.SH", ctype=2, industry="医药")  # 银行
    _co(bench_db, "600003.SH", ctype=3, industry="医药")  # 保险
    _co(bench_db, "600004.SH", ctype=None, industry="医药")
    _co(bench_db, "600005.SH", ctype=1, industry="电子")
    engine = _engine()
    companies = eligible_companies(engine, "医药")
    assert companies == ["600001.SH"]


def test_compute_metric_values_real(bench_db):
    """同行业 5 家公司 r1_gap 计算：应收涨+营收平 → gap 高。"""
    for i, code in enumerate(
        ["600101.SH", "600102.SH", "600103.SH", "600104.SH", "600105.SH"]
    ):
        _co(bench_db, code, ctype=1, industry="医药")
        # 每家不同的 acct_rcv 增速（60, 40, 20, 10, 0 pp gap）
        ar_growth = [0.60, 0.40, 0.20, 0.10, 0.0][i]
        ar = [100e6, 100e6, 100e6, 100e6, 100e6 * (1 + ar_growth)]
        ore = [200e6, 200e6, 200e6, 200e6, 200e6]
        _bs(bench_db, code, {"acct_rcv": ar})
        _is(bench_db, code, {"oper_rev": ore})

    engine = _engine()
    m = get_metric("r1_gap")
    pairs = compute_metric_values(engine, m, "医药", "20260331")
    values = [v for _, v in pairs]
    assert len(values) == 5
    assert all(v >= 0 for v in values)
    # 确定性：重复计算一致
    pairs2 = compute_metric_values(engine, m, "医药", "20260331")
    assert pairs == pairs2


def test_benchmark_row_sample_sufficient(bench_db):
    """样本 >=5 → 返回真实分位。"""
    for i in range(6):
        code = f"60020{i}.SH"
        _co(bench_db, code, ctype=1, industry="机械")
        _is(
            bench_db,
            code,
            {
                "net_profit_excl_min_int_inc": [100e6 + i * 10] * 5,
                "oper_rev": [100e6 + i, 100e6 + i, 100e6 + i, 100e6 + i, 100e6 + i],
            },
        )
        _cf(bench_db, code, {"net_cash_flows_oper_act": [30e6 + i] * 5})
    engine = _engine()
    row = compute_benchmark_row(
        engine,
        get_metric("r2_cf_ratio"),
        "机械",
        "20260331",
        dataset_version="test-v1",
        rule_set_version="finance-rules-1.0.0",
    )
    assert row["sample_count"] >= 5
    assert row["p05"] is not None and row["p95"] is not None
    assert row["p05"] <= row["p25"] <= row["p50"] <= row["p75"] <= row["p95"]


def test_benchmark_row_insufficient_no_fabricated_percentile(bench_db):
    """样本 <5 → sample_count 明确，分位为 None，不伪造。"""
    _co(bench_db, "600301.SH", ctype=1, industry="食品饮料")
    _is(bench_db, "600301.SH", {"oper_rev": [100e6, 110e6, 120e6, 130e6, 140e6]})
    _cf(
        bench_db,
        "600301.SH",
        {"net_cash_flows_oper_act": [30e6, 33e6, 36e6, 39e6, 42e6]},
    )
    _is(
        bench_db,
        "600301.SH",
        {"net_profit_excl_min_int_inc": [50e6, 55e6, 60e6, 65e6, 70e6]},
    )
    engine = _engine()
    row = compute_benchmark_row(
        engine,
        get_metric("r2_cf_ratio"),
        "食品饮料",
        "20260331",
        dataset_version="test-v1",
        rule_set_version="finance-rules-1.0.0",
    )
    assert row["sample_count"] == 1
    assert row["sample_count"] < MIN_PEER_SAMPLE
    assert row["p05"] is None and row["p95"] is None


def test_benchmark_deterministic(bench_db):
    """同输入两次计算 → 完全一致（幂等基础）。"""
    for i in range(6):
        code = f"60040{i}.SH"
        _co(bench_db, code, ctype=1, industry="电子")
        _bs(
            bench_db,
            code,
            {
                "tot_assets": [1000e6 + i * 100] * 5,
                "monetary_cap": [100e6 + i * 10] * 5,
            },
        )
    engine = _engine()
    m = get_metric("r3_cash_to_assets")
    a = compute_metric_values(engine, m, "电子", "20260331")
    b = compute_metric_values(engine, m, "电子", "20260331")
    assert a == b
