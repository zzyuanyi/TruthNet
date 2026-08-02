#!/usr/bin/env python3
"""任务① 100 只股票规则验收 — 合并报表优先、显式口径与覆盖度.

Phase C 集成验收修正:
- DB 连接来自 app.core.config.settings（尊重 SQL_BACKEND，禁止硬编码凭据）。
- 规则内部已实现"合并报表(408001000)优先、母公司(408006000)降级并显式标记"，
  本脚本逐条报告每规则实际使用的 statement_scope 分布。
- 触发率分母 = eligible（triggered + not_triggered）; insufficient_data / not_applicable
  单独统计，绝不混入"未触发"。
- 随机抽样可复现（--seed）。

用法:
  python scripts/test_rules_on_100_stocks.py [--seed 42] [--sample-size 100] [--as-of 20260331]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domain.finance.rule_engine import evaluate_all_rules  # noqa: E402


def _get_engine():
    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
    else:
        url = f"sqlite:///{settings.SQLITE_PATH}"
    return create_engine(url)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42, help="随机种子（可复现）")
    ap.add_argument("--sample-size", type=int, default=100)
    ap.add_argument("--as-of", default="20260331")
    ap.add_argument(
        "--no-random", action="store_true", help="确定性：取前 N 家公司（不随机抽样）"
    )
    args = ap.parse_args()

    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT wind_code FROM companies")).fetchall()
    all_codes = sorted(r[0] for r in rows if r[0])

    rng = random.Random(args.seed)
    if args.no_random:
        sample = all_codes[: args.sample_size]
    else:
        sample = rng.sample(all_codes, min(args.sample_size, len(all_codes)))

    print(
        f"DB backend: {settings.SQL_BACKEND} | 样本: {len(sample)} 只 "
        f"(从 {len(all_codes)} 只中{'取前' if args.no_random else '随机'}抽取, seed={args.seed})"
    )
    print(f"as_of: {args.as_of}")
    print("=" * 78)

    # 每规则统计
    per_rule: dict[str, dict] = {}
    for rid in [f"R{i}" for i in range(1, 8)]:
        per_rule[rid] = {
            "status": {},
            "scope": {},
            "stmt": {},
            "industry": {},
            "periods": set(),
        }

    for idx, code in enumerate(sample):
        results = evaluate_all_rules(code, args.as_of)
        for rid, r in results.items():
            st = per_rule[rid]
            st["status"][r.status] = st["status"].get(r.status, 0) + 1
            q = r.quality or {}
            scope = q.get("statement_scope", "unknown")
            st["scope"][scope] = st["scope"].get(scope, 0) + 1
            stmt = q.get("statement_type", "unknown")
            st["stmt"][stmt] = st["stmt"].get(stmt, 0) + 1
            for p in r.history if isinstance(r.history, list) else []:
                pass
        if (idx + 1) % 20 == 0:
            print(f"  已处理 {idx + 1}/{len(sample)}...")

    print()
    hdr = f"{'规则':5s} {'总样本':>5s} {'eligible':>8s} {'触发':>4s} {'未触发':>5s} {'insuf':>6s} {'NA':>4s} {'error':>5s} {'触发率(eligible)':>15s}"
    print(hdr)
    print("-" * 78)

    for rid in [f"R{i}" for i in range(1, 8)]:
        st = per_rule[rid]
        n = len(sample)
        trig = st["status"].get("triggered", 0)
        not_t = st["status"].get("not_triggered", 0)
        insuf = st["status"].get("insufficient_data", 0)
        na = st["status"].get("not_applicable", 0)
        err = st["status"].get("error", 0)
        eligible = trig + not_t
        rate = trig / eligible if eligible else 0.0
        scopes = ", ".join(f"{k}={v}" for k, v in sorted(st["scope"].items()))
        stmts = ", ".join(f"{k}={v}" for k, v in sorted(st["stmt"].items()))
        print(
            f"{rid:5s} {n:>5d} {eligible:>8d} {trig:>4d} {not_t:>5d} "
            f"{insuf:>6d} {na:>4d} {err:>5d} {rate * 100:>14.1f}%"
        )
        print(f"      scope分布: {scopes}")
        print(f"      stmt_type分布: {stmts}")

    print("-" * 78)
    print(
        "触发率分母定义: eligible = triggered + not_triggered（排除 insufficient_data 与 not_applicable）。"
    )
    print(
        "本脚本不评估触发率是否'合理'——只输出事实分布。口径/覆盖度是否异常需结合字段覆盖率分析。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
