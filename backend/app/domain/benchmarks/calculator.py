"""行业分位计算器 — Phase C 数据任务 3.

职责：
- 按行业 × 报告期批量计算各指标（metric）的公司值
- 聚合分布统计（mean/std/min/p05/p25/p50/p75/p95/max/sample_count）
- 计算公司值百分位（percentile_rank，RULES_SPEC §1.3 非插值）

约束：
- 固定母公司报表口径（statement_type=408006000，SQL 注入）
- 只用 comp_type_code=1（非金融）；金融/NULL 类型排除
- 排除 NULL/非法值；分母保护缺失样本不计入（不当作 0）
- 计算确定性、幂等（同输入同输出）
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.benchmarks.metric_registry import MetricSpec, field_table
from app.domain.finance.statement_type import PARENT_STATEMENT_TYPE

# 采样不足阈值（RULES_SPEC §1.3）：有效同行样本 < 5 时不计算分位
MIN_PEER_SAMPLE = 5


def _quantile(sorted_values: list[float], q: float) -> float:
    """线性插值分位数（numpy.percentile 默认 Type-7 算法，确定性）。

    q ∈ [0,1]。调用前必须保证 len(sorted_values) >= 1。
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def percentile_rank(value: float, values: Iterable[float]) -> float:
    """非插值百分位排名：≤ value 的样本占比 × 100（RULES_SPEC §1.3）。

    percentile_rank 方法（非插值）。
    """
    vals = [v for v in values]
    if not vals:
        return 0.0
    le_count = sum(1 for v in vals if v <= value)
    return round(le_count / len(vals) * 100, 2)


def aggregate_stats(values: list[float]) -> dict:
    """聚合分布统计（确定性）。"""
    n = len(values)
    if n == 0:
        return {
            "sample_count": 0,
            "mean_value": None,
            "std_value": None,
            "min_value": None,
            "p05": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p95": None,
            "max_value": None,
        }
    srt = sorted(values)
    std = statistics.pstdev(srt) if n >= 2 else 0.0
    return {
        "sample_count": n,
        "mean_value": round(statistics.fmean(srt), 6),
        "std_value": round(std, 6),
        "min_value": srt[0],
        "p05": round(_quantile(srt, 0.05), 6),
        "p25": round(_quantile(srt, 0.25), 6),
        "p50": round(_quantile(srt, 0.50), 6),
        "p75": round(_quantile(srt, 0.75), 6),
        "p95": round(_quantile(srt, 0.95), 6),
        "max_value": srt[-1],
    }


def eligible_companies(engine: Engine, industry_l1: str) -> list[str]:
    """返回该行业 eligible 公司列表（comp_type_code=1，排除金融/NULL）。"""
    sql = text(
        "SELECT wind_code FROM companies "
        "WHERE industry_l1 = :ind AND comp_type_code = 1 "
        "ORDER BY wind_code ASC"  # 确定性顺序
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"ind": industry_l1}).fetchall()
    return [r[0] for r in rows]


def fetch_company_series(
    engine: Engine,
    wind_codes: list[str],
    metric: MetricSpec,
    as_of: str,
) -> dict[str, dict[str, list]]:
    """按公司批量取所需财务字段的最近 periods 期（升序，缺失为 None）。

    固定母公司报表口径。返回 {wind_code: {field: [升序 values]}}。
    """
    if not wind_codes:
        return {}
    # 字段 → 表聚合查询（每个表一条 SQL，避免 N+1）
    tables: dict[str, list[str]] = {}
    for f in metric.fields:
        tables.setdefault(field_table(f), []).append(f)

    result: dict[str, dict[str, list]] = {
        wc: {f: [] for f in metric.fields} for wc in wind_codes
    }
    placeholders = ",".join(f":wc{i}" for i in range(len(wind_codes)))
    params = {f"wc{i}": wc for i, wc in enumerate(wind_codes)}

    with engine.connect() as conn:
        for table, fields in tables.items():
            # 列存在性检查（RULES_SPEC §4.5: 字段列不存在 → 视为 NULL/0 处理）
            if _is_mysql(conn):
                col_rows = conn.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
                existing_cols = {c[0] for c in col_rows}
            else:
                col_rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing_cols = {c[1] for c in col_rows}
            available = [f for f in fields if f in existing_cols]
            missing = [f for f in fields if f not in existing_cols]
            for wc in wind_codes:
                for f in missing:
                    result[wc][f] = [None] * metric.periods
            if not available:
                continue

            cols = ", ".join(available)
            sql = text(
                f"SELECT wind_code, report_period, {cols} FROM {table} "
                f"WHERE wind_code IN ({placeholders}) "
                f"AND statement_type = :stmt AND report_period <= :as_of "
                f"ORDER BY report_period ASC"
            )
            rows = conn.execute(
                sql, {**params, "stmt": PARENT_STATEMENT_TYPE, "as_of": as_of}
            ).fetchall()
            # 每公司保留最近 periods 期（每个 report_period 一行，最后出现者覆盖）
            per_company: dict[str, dict[str, list]] = {
                wc: {f: [] for f in available} for wc in wind_codes
            }
            for row in rows:
                wc = row[0]
                if wc not in per_company:
                    continue
                bucket = per_company[wc]
                for idx, f in enumerate(available):
                    val = row[2 + idx]
                    bucket[f].append(float(val) if val is not None else None)
            for wc in wind_codes:
                for f in available:
                    seq = per_company[wc][f][-metric.periods :]
                    result[wc][f] = seq
    return result


def _is_mysql(conn) -> bool:
    """判断当前连接是否为 MySQL（用于 SHOW COLUMNS vs PRAGMA）。"""
    return conn.dialect.name == "mysql"


def compute_metric_values(
    engine: Engine,
    metric: MetricSpec,
    industry_l1: str,
    as_of: str,
) -> list[tuple[str, float]]:
    """计算该行业所有 eligible 公司在 as_of 的指标值。

    返回 [(wind_code, value)]，仅含有效值；样本不足由调用方判定。
    """
    companies = eligible_companies(engine, industry_l1)
    if not companies:
        return []
    series_map = fetch_company_series(engine, companies, metric, as_of)
    out: list[tuple[str, float]] = []
    for wc in companies:
        value = metric.compute_from_series(series_map.get(wc, {}))
        if value is not None and math.isfinite(value):
            out.append((wc, value))
    # 确定性顺序
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def compute_benchmark_row(
    engine: Engine,
    metric: MetricSpec,
    industry_l1: str,
    as_of: str,
    *,
    dataset_version: str,
    rule_set_version: str,
) -> dict:
    """计算单个 行业×指标 基准行（含 sample_count 与各分位）。

    样本 < MIN_PEER_SAMPLE 时，分位值置 None（不伪造 percentile），
    仅保留 sample_count 与基础统计。
    """
    pairs = compute_metric_values(engine, metric, industry_l1, as_of)
    values = [v for _, v in pairs]
    stats = aggregate_stats(values)
    if stats["sample_count"] < MIN_PEER_SAMPLE:
        for k in ("p05", "p25", "p50", "p75", "p95"):
            stats[k] = None
    row = {
        "metric_id": metric.metric_id,
        "rule_id": metric.rule_id,
        "industry_l1": industry_l1,
        "period": as_of,
        "statement_scope": "parent_company",
        "company_type": 1,
        "dataset_version": dataset_version,
        "rule_set_version": rule_set_version,
        **stats,
    }
    return row
