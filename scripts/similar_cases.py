#!/usr/bin/env python
"""任务④ — 相似历史案例检索。

按触发规则的指标，在数据库中检索指标值最接近的其他公司（同行业优先）。

核心函数 find_similar_cases(rule_id, company_code, metric_value, industry, ...)
指标口径与 backend/app/domain/finance 的规则引擎一致（母公司报表 408006000，
非金融 comp_type_code=1，R1-R7 与 financial_rules.yaml 对齐）。

用法：
  python scripts/similar_cases.py R1 600518.SH          # 检索康美药业 R1 相似案例
  python scripts/similar_cases.py --list                  # 列出各规则的指标定义
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pymysql

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
ENV = {}
for _l in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        ENV[_k.strip()] = _v.strip()

STATEMENT_TYPE = "408006000"  # 母公司报表（与规则引擎一致）


@dataclass(frozen=True)
class MetricSpec:
    rule_id: str
    rule_name: str
    label: str
    unit: str
    # 指标名 -> 计算所需的字段（与规则引擎公式一致）
    metrics: tuple[str, ...]
    # 是否需要 YoY（同比）计算
    yoy: bool = False


# R1-R7 指标定义（与 financial_rules.yaml 对齐）
METRIC_SPECS: dict[str, MetricSpec] = {
    "R1": MetricSpec("R1", "应收–营收背离", "gap", "percentage_point",
                     ("gap",), yoy=True),
    "R2": MetricSpec("R2", "现金流–利润背离", "cf_to_profit_ratio", "ratio",
                     ("cf_to_profit_ratio",)),
    "R3": MetricSpec("R3", "存贷双高", "cash_to_assets+debt_to_assets",
                     "percent", ("cash_to_assets", "debt_to_assets")),
    "R4": MetricSpec("R4", "存货–营收背离", "growth_gap", "percentage_point",
                     ("growth_gap",), yoy=True),
    "R5": MetricSpec("R5", "毛利率异常", "gross_margin", "percent",
                     ("gross_margin",)),
    "R6": MetricSpec("R6", "其他应收款关联占用", "oth_rcv_to_assets", "percent",
                     ("oth_rcv_to_assets",)),
    "R7": MetricSpec("R7", "盈利质量", "core_profit_ratio", "ratio",
                     ("core_profit_ratio",)),
}

# 指标 -> (表, 字段, 是否有 t-4Q 去年同期版本)
_METRIC_FIELDS: dict[str, tuple[str, str, bool]] = {
    "gap": ("__yoy__", "", False),  # 由 acct_rcv_yoy - oper_rev_yoy 派生
    "growth_gap": ("__yoy__", "", False),
    "cf_to_profit_ratio": ("cash_flow", "net_cash_flows_oper_act", False),
    "cash_to_assets": ("balance_sheet", "monetary_cap", False),
    "debt_to_assets": ("balance_sheet", "st_borrow", False),
    "gross_margin": ("income_statement", "oper_rev", False),
    "oth_rcv_to_assets": ("balance_sheet", "oth_rcv", False),
    "core_profit_ratio": ("income_statement", "net_profit_after_ded_nr_lp", False),
}

# 派生指标（gap/growth_gap）依赖的原始字段（当期 + 去年同期）
_DERIVED_DEP = {
    "gap": ("acct_rcv", "oper_rev"),
    "growth_gap": ("inventories", "oper_rev"),
}


def _db():
    return pymysql.connect(
        host=ENV.get("MYSQL_HOST", "localhost"),
        port=int(ENV.get("MYSQL_PORT", 3306)),
        user=ENV.get("MYSQL_USER"),
        password=ENV.get("MYSQL_PASSWORD"),
        database=ENV.get("MYSQL_DATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _prev_year(period: str) -> str:
    """去年同期报告期（如 20260331 -> 20250331）."""
    return str(int(period) - 10000)


def _load_raw(as_of: str) -> pd.DataFrame:
    """加载非金融公司最新一期的宽表数据（含去年同期用于 YoY）."""
    prev = _prev_year(as_of)
    conn = _db()
    cur = conn.cursor()
    # 当前期：三表 JOIN + companies
    cur.execute(
        """
        SELECT b.wind_code, c.sec_name, c.industry_l1,
               b.acct_rcv, b.oth_rcv, b.inventories, b.monetary_cap,
               b.st_borrow, b.lt_borrow, b.tot_assets,
               i.oper_rev, i.less_oper_cost,
               i.net_profit_excl_min_int_inc, i.net_profit_after_ded_nr_lp,
               cf.net_cash_flows_oper_act
        FROM balance_sheet b
        JOIN companies c ON b.wind_code = c.wind_code
        LEFT JOIN income_statement i
          ON b.wind_code = i.wind_code AND b.report_period = i.report_period
         AND b.statement_type = i.statement_type
        LEFT JOIN cash_flow cf
          ON b.wind_code = cf.wind_code AND b.report_period = cf.report_period
         AND b.statement_type = cf.statement_type
        WHERE b.report_period = %s AND b.statement_type = %s
          AND c.comp_type_code = 1
        """,
        (as_of, STATEMENT_TYPE),
    )
    df = pd.DataFrame(cur.fetchall())
    # 去年同期（仅 YoY 派生指标需要）
    cur.execute(
        """
        SELECT b.wind_code, b.acct_rcv, b.oth_rcv, b.inventories,
               i.oper_rev
        FROM balance_sheet b
        LEFT JOIN income_statement i
          ON b.wind_code = i.wind_code AND b.report_period = i.report_period
         AND b.statement_type = i.statement_type
        WHERE b.report_period = %s AND b.statement_type = %s
        """,
        (prev, STATEMENT_TYPE),
    )
    df_prev = pd.DataFrame(cur.fetchall())
    conn.close()

    if df.empty:
        return df

    if not df_prev.empty:
        df_prev = df_prev.rename(columns={
            "acct_rcv": "acct_rcv_prev", "oth_rcv": "oth_rcv_prev",
            "inventories": "inventories_prev", "oper_rev": "oper_rev_prev",
        })
        df = df.merge(df_prev, on="wind_code", how="left")
    else:
        for c in ["acct_rcv_prev", "oth_rcv_prev", "inventories_prev",
                  "oper_rev_prev"]:
            df[c] = None
    return df


def _compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """按指标定义计算所有公司的指标列."""
    df = df.copy()
    # YoY 派生指标
    def _yoy(cur, prev):
        return ((cur - prev) / prev * 100).where(prev.notna() & (prev != 0))

    if "acct_rcv_prev" in df.columns:
        df["acct_rcv_yoy"] = _yoy(df["acct_rcv"], df["acct_rcv_prev"])
        df["oper_rev_yoy"] = _yoy(df["oper_rev"], df["oper_rev_prev"])
        df["gap"] = df["acct_rcv_yoy"] - df["oper_rev_yoy"]
    if "inventories_prev" in df.columns:
        df["inventories_yoy"] = _yoy(df["inventories"], df["inventories_prev"])
        df["growth_gap"] = df["inventories_yoy"] - df["oper_rev_yoy"]

    # 比值类指标
    df["cf_to_profit_ratio"] = (
        df["net_cash_flows_oper_act"] / df["net_profit_excl_min_int_inc"]
    )
    df["cash_to_assets"] = df["monetary_cap"] / df["tot_assets"] * 100
    df["debt_to_assets"] = (
        (df["st_borrow"].fillna(0) + df["lt_borrow"].fillna(0))
        / df["tot_assets"] * 100
    )
    df["gross_margin"] = (
        (df["oper_rev"] - df["less_oper_cost"]) / df["oper_rev"] * 100
    )
    df["oth_rcv_to_assets"] = df["oth_rcv"] / df["tot_assets"] * 100
    df["core_profit_ratio"] = (
        df["net_profit_after_ded_nr_lp"] / df["net_profit_excl_min_int_inc"]
    )
    return df


def _company_metric(df: pd.DataFrame, company_code: str,
                    spec: MetricSpec) -> dict[str, float | None]:
    row = df[df["wind_code"] == company_code]
    if row.empty:
        return {}
    row = row.iloc[0]
    return {m: row.get(m) for m in spec.metrics}


def find_similar_cases(
    rule_id: str,
    company_code: str,
    metric_value: dict[str, float] | None = None,
    industry: str | None = None,
    as_of: str = "20260331",
    limit: int = 5,
) -> list[dict]:
    """检索与目标公司在给定规则指标上最相似的其他公司。

    Args:
        rule_id: 规则编号 R1-R7
        company_code: 当前分析股票代码（如 600518.SH）
        metric_value: 当前公司的指标值（可选；缺省时自动计算）
        industry: 当前公司行业（可选；缺省时从 companies 查）
        as_of: 报告期（YYYYMMDD）
        limit: 返回数量

    Returns:
        [{"company_code", "company_name", "industry", "period",
          "metric": {...}, "distance": float, "source": "..."}]
        样本不足时返回空列表。
    """
    spec = METRIC_SPECS.get(rule_id)
    if spec is None:
        raise ValueError(f"未知规则 {rule_id}（应为 R1-R7）")

    df = _compute_metrics(_load_raw(as_of))
    if df.empty:
        return []

    # 目标公司指标值
    if metric_value is None:
        metric_value = _company_metric(df, company_code, spec)
    if not metric_value or any(pd.isna(v) for v in metric_value.values()):
        return []

    if industry is None:
        row = df[df["wind_code"] == company_code]
        industry = row.iloc[0]["industry_l1"] if not row.empty else None

    # 排除自身，且仅保留有完整指标值的公司
    peers = df[df["wind_code"] != company_code].copy()
    for m in spec.metrics:
        peers = peers[peers[m].notna()]

    # 同行业优先；不足 limit 再扩大到全市场
    if industry and len(peers[peers["industry_l1"] == industry]) >= limit:
        peers = peers[peers["industry_l1"] == industry]
    else:
        # 同行业排前面，但允许跨行业补足
        peers["_same_ind"] = peers["industry_l1"] == industry
        peers = peers.sort_values("_same_ind", ascending=False)

    # 距离：单指标等价于 |指标差|；多指标按 IQR（四分位距）标准化后欧氏，
    # 对量纲和离群值稳健（IQR 比 std 更抗极端值）。
    def _scale(s: pd.Series) -> float:
        iqr = s.quantile(0.75) - s.quantile(0.25)
        if iqr > 0:
            return iqr
        std = s.std()
        return std if std and std > 0 else 1.0

    scales = {m: _scale(peers[m]) for m in spec.metrics}

    def _dist(row) -> float:
        s = 0.0
        for m in spec.metrics:
            d = (row[m] - metric_value[m]) / scales[m]
            s += d * d
        return s ** 0.5

    peers["_distance"] = peers.apply(_dist, axis=1)
    peers = peers.sort_values("_distance").head(limit)

    out = []
    for _, r in peers.iterrows():
        out.append({
            "company_code": r["wind_code"],
            "company_name": r["sec_name"],
            "industry": r["industry_l1"],
            "period": as_of,
            "metric": {m: (round(float(r[m]), 2) if pd.notna(r[m]) else None)
                       for m in spec.metrics},
            "distance": round(float(r["_distance"]), 4),
            "source": f"balance_sheet/income_statement/cash_flow@{as_of}",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rule_id", nargs="?", help="规则编号 R1-R7")
    ap.add_argument("company_code", nargs="?", help="股票代码，如 600518.SH")
    ap.add_argument("--as-of", default="20260331")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--list", action="store_true", help="列出规则指标定义")
    args = ap.parse_args()

    if args.list:
        for rid, s in METRIC_SPECS.items():
            print(f"{rid} {s.rule_name}: 指标={s.label} 单位={s.unit} "
                  f"公式字段={s.metrics}")
        return 0

    if not args.rule_id or not args.company_code:
        ap.print_help()
        return 1

    spec = METRIC_SPECS[args.rule_id]
    df = _compute_metrics(_load_raw(args.as_of))
    cm = _company_metric(df, args.company_code, spec)
    print(f"目标公司 {args.company_code} {spec.rule_name} 指标值: {cm}\n")

    results = find_similar_cases(
        args.rule_id, args.company_code, as_of=args.as_of, limit=args.limit
    )
    if not results:
        print("样本不足，返回空（暂无相似案例）")
        return 0
    print(f"相似历史案例 Top {len(results)}（{spec.label}）:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['company_name']} ({r['company_code']}) "
              f"[{r['industry']}] {spec.label}={r['metric']} 距离={r['distance']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
