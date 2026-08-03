#!/usr/bin/env python
"""行业分位批量计算 CLI — Phase C 数据任务 3.

计算每个 行业×指标×报告期 的分位统计并写入 industry_benchmarks 表。

用法:
    python scripts/build_industry_benchmarks.py --dry-run
    python scripts/build_industry_benchmarks.py --period 20260331
    python scripts/build_industry_benchmarks.py --verify-only
    python scripts/build_industry_benchmarks.py --rebuild

约束:
    - 固定母公司报表口径 (408006000, parent_company)
    - 只用 comp_type_code=1；排除 NULL/非法/金融企业
    - 样本 < 5 时写 sample_count 但不伪造分位（p* 为 NULL）
    - 确定性、幂等：同 (industry_l1, metric_id, period, dataset_version) 重建覆盖
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.domain.benchmarks.calculator import (  # noqa: E402
    MIN_PEER_SAMPLE,
    compute_benchmark_row,
    eligible_companies,
)
from backend.app.domain.benchmarks.metric_registry import all_metrics  # noqa: E402


def _engine():
    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
    else:
        url = f"sqlite:///{settings.SQLITE_PATH}"
    return create_engine(url, pool_pre_ping=True)


def _latest_period(engine) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT MAX(report_period) FROM income_statement "
                "WHERE statement_type = '408006000'"
            )
        ).scalar()
    return row or "20260331"


def _industries(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT industry_l1 FROM companies "
                "WHERE industry_l1 IS NOT NULL AND industry_l1 != '' "
                "ORDER BY industry_l1 ASC"
            )
        ).fetchall()
    return [r[0] for r in rows]


def _table_exists(engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = :t"
            )
            if settings.SQL_BACKEND == "mysql"
            else text("SELECT COUNT(*) FROM sqlite_master WHERE name = :t"),
            {"t": table},
        ).scalar()
    return bool(row)


def _verify_rows(rows: list[dict]) -> list[str]:
    """数据质量检查：单调性、无 NaN/Infinity、样本不足不伪造分位。"""
    problems: list[str] = []
    import math

    for r in rows:
        if r["sample_count"] >= MIN_PEER_SAMPLE:
            p = [r["p05"], r["p25"], r["p50"], r["p75"], r["p95"]]
            if any(v is None for v in p):
                problems.append(
                    f"{r['industry_l1']}/{r['metric_id']} 样本充足但分位缺失"
                )
            elif not (p[0] <= p[1] <= p[2] <= p[3] <= p[4]):
                problems.append(f"{r['industry_l1']}/{r['metric_id']} 分位不单调: {p}")
        else:
            if any(r[k] is not None for k in ("p05", "p25", "p50", "p75", "p95")):
                problems.append(
                    f"{r['industry_l1']}/{r['metric_id']} 样本不足但伪造了分位"
                )
        for k in (
            "mean_value",
            "std_value",
            "min_value",
            "p05",
            "p25",
            "p50",
            "p75",
            "p95",
            "max_value",
        ):
            v = r[k]
            if v is not None and (math.isnan(v) or math.isinf(v)):
                problems.append(f"{r['industry_l1']}/{r['metric_id']} {k} 非有限值")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="行业分位批量计算")
    parser.add_argument("--dry-run", action="store_true", help="只计算并打印，不写库")
    parser.add_argument("--period", default=None, help="报告期 YYYYMMDD（默认最新）")
    parser.add_argument("--verify-only", action="store_true", help="只校验已写库数据")
    parser.add_argument(
        "--rebuild", action="store_true", help="重建（幂等覆盖同键记录）"
    )
    parser.add_argument("--industry", default=None, help="只计算指定行业（调试）")
    args = parser.parse_args()

    engine = _engine()
    period = args.period or _latest_period(engine)
    dataset_version = settings.DATASET_VERSION or "competition-2026"
    rule_set_version = settings.RULE_SET_VERSION or "finance-rules-1.0.0"
    metrics = all_metrics()

    if args.verify_only:
        if not _table_exists(engine, "industry_benchmarks"):
            print(
                "ERROR: industry_benchmarks 表不存在，请先运行 migration",
                file=sys.stderr,
            )
            return 2
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT * FROM industry_benchmarks "
                        "WHERE period = :p AND dataset_version = :d"
                    ),
                    {"p": period, "d": dataset_version},
                )
                .mappings()
                .fetchall()
            )
        print(
            f"verify-only: 已有 {len(rows)} 行 (period={period}, dataset={dataset_version})"
        )
        problems = _verify_rows([dict(r) for r in rows])
        if problems:
            for p in problems:
                print("  [FAIL]", p)
            print(f"VERIFY: {len(problems)} 问题")
            return 1
        print("VERIFY: OK")
        return 0

    industries = _industries(engine)
    if args.industry:
        industries = [i for i in industries if i == args.industry]
    print(f"报告期: {period} | 行业数: {len(industries)} | 指标数: {len(metrics)}")

    rows: list[dict] = []
    for ind in industries:
        peers = eligible_companies(engine, ind)
        print(f"  行业[{ind}]: eligible {len(peers)} 家")
        for m in metrics:
            row = compute_benchmark_row(
                engine,
                m,
                ind,
                period,
                dataset_version=dataset_version,
                rule_set_version=rule_set_version,
            )
            row["benchmark_id"] = f"bm_{ind}_{m.metric_id}_{period}".replace(" ", "_")
            rows.append(row)

    # 汇总
    with_peers = sum(1 for r in rows if r["sample_count"] >= MIN_PEER_SAMPLE)
    insuff = sum(1 for r in rows if r["sample_count"] < MIN_PEER_SAMPLE)
    print(
        f"计算完成: 总 {len(rows)} 行, 样本充足 {with_peers} 行, 样本不足 {insuff} 行"
    )

    problems = _verify_rows(rows)
    if problems:
        print("数据质量检查发现问题:")
        for p in problems[:20]:
            print("  [FAIL]", p)
        print(f"VERIFY: {len(problems)} 问题，中止写入", file=sys.stderr)
        return 1
    print("VERIFY: 数据质量检查通过")

    if args.dry_run:
        # 打印样本充足行业的抽样
        print("\n=== DRY-RUN 抽样（样本充足行业）===")
        shown = 0
        for r in rows:
            if r["sample_count"] >= MIN_PEER_SAMPLE and shown < 15:
                print(
                    f"  {r['industry_l1']}/{r['metric_id']}: n={r['sample_count']} "
                    f"p50={r['p50']} p05={r['p05']} p95={r['p95']} "
                    f"mean={r['mean_value']}"
                )
                shown += 1
        print("\ndry-run 完成，未写库。")
        return 0

    if not _table_exists(engine, "industry_benchmarks"):
        print(
            "ERROR: industry_benchmarks 表不存在，请先运行 alembic migration",
            file=sys.stderr,
        )
        return 2

    # 写库（幂等：同键先删后插，单事务）
    cols = [
        "benchmark_id",
        "industry_l1",
        "industry_l2",
        "metric_id",
        "rule_id",
        "period",
        "statement_scope",
        "company_type",
        "sample_count",
        "mean_value",
        "std_value",
        "min_value",
        "p05",
        "p25",
        "p50",
        "p75",
        "p95",
        "max_value",
        "dataset_version",
        "rule_set_version",
        "calculated_at",
    ]
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for r in rows:
        r["industry_l2"] = None
        r["calculated_at"] = now

    with engine.begin() as conn:
        # 删除同键旧记录（period + dataset_version 范围，幂等重建）
        del_result = conn.execute(
            text(
                "DELETE FROM industry_benchmarks "
                "WHERE period = :p AND dataset_version = :d"
            ),
            {"p": period, "d": dataset_version},
        )
        print(f"已清除旧记录: {del_result.rowcount} 行")
        if rows:
            # 批量插入
            insert_sql = text(
                "INSERT INTO industry_benchmarks ("
                + ", ".join(cols)
                + ") VALUES ("
                + ", ".join(f":{c}" for c in cols)
                + ")"
            )
            conn.execute(insert_sql, rows)

    print(f"写入完成: {len(rows)} 行 (period={period}, dataset={dataset_version})")

    # 校验写入
    with engine.connect() as conn:
        cnt = conn.execute(
            text(
                "SELECT COUNT(*) FROM industry_benchmarks "
                "WHERE period = :p AND dataset_version = :d"
            ),
            {"p": period, "d": dataset_version},
        ).scalar()
    print(f"校验: 库中 {cnt} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
