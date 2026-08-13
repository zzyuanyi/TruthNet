#!/usr/bin/env python3
"""任务① 100 只股票规则验收 — 固定母公司报表口径 + 公司类型 Gate.

Phase C 口径修正:
- DB 连接来自 app.core.config.settings（尊重 SQL_BACKEND，禁止硬编码凭据）。
- 项目财务规则固定采用母公司报表口径（statement_type=408006000，scope=parent_company）。
- 公司类型 Gate: comp_type_code=1 → eligible；2/3/4 → financial_excluded；
  NULL/非法 → company_type_unknown（insufficient_data，禁止当作非金融）。
- 触发率分母只使用 eligible 公司（triggered + not_triggered）;
  insufficient_data / not_applicable / 金融排除 / 类型未知 单独统计，绝不混入"未触发"。
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
            "ctype": {},
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
            ctype = q.get("company_type_status", "unknown")
            st["ctype"][ctype] = st["ctype"].get(ctype, 0) + 1
        if (idx + 1) % 20 == 0:
            print(f"  已处理 {idx + 1}/{len(sample)}...")

    print()
    hdr = (
        f"{'规则':5s} {'样本':>5s} {'eligible':>8s} {'触发':>4s} {'未触发':>5s} "
        f"{'insuf':>6s} {'NA':>4s} {'金融排除':>7s} {'类型未知':>7s} {'触发率':>8s}"
    )
    print(hdr)
    print("-" * 82)

    for rid in [f"R{i}" for i in range(1, 8)]:
        st = per_rule[rid]
        n = len(sample)
        trig = st["status"].get("triggered", 0)
        not_t = st["status"].get("not_triggered", 0)
        insuf = st["status"].get("insufficient_data", 0)
        na = st["status"].get("not_applicable", 0)
        fin_excl = st["ctype"].get("excluded_financial", 0)
        type_unknown = st["ctype"].get("unknown", 0)
        eligible = trig + not_t
        rate = trig / eligible if eligible else 0.0
        scopes = ", ".join(f"{k}={v}" for k, v in sorted(st["scope"].items()))
        stmts = ", ".join(f"{k}={v}" for k, v in sorted(st["stmt"].items()))
        ctypes = ", ".join(f"{k}={v}" for k, v in sorted(st["ctype"].items()))
        print(
            f"{rid:5s} {n:>5d} {eligible:>8d} {trig:>4d} {not_t:>5d} "
            f"{insuf:>6d} {na:>4d} {fin_excl:>7d} {type_unknown:>7d} {rate * 100:>7.1f}%"
        )
        print(f"      scope分布: {scopes}")
        print(f"      stmt_type分布: {stmts}")
        print(f"      公司类型分布: {ctypes}")

    print("-" * 82)
    print(
        "触发率分母定义: eligible = triggered + not_triggered（仅非金融且类型已知公司）。"
    )
    print(
        "金融排除(2/3/4)与类型未知(NULL/非法)不计入触发率分母；"
        "类型未知公司输出 insufficient_data，绝不当作非金融。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
