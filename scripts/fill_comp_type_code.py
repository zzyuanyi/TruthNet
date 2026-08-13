#!/usr/bin/env python
"""任务⑤ 前置 — 填充 companies.comp_type_code。

原始三表 CSV 已含 comp_type_code（1=非金融 2=银行 3=保险 4=证券），
无需 akshare 推导。三表交叉校验后按 wind_code 聚合写回 companies。

用法：
  python scripts/fill_comp_type_code.py --dry-run   # 只统计
  python scripts/fill_comp_type_code.py             # 实际写入
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pandas as pd
import pymysql

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = Path("data/raw/比赛数据/4")
ENV = {}
for _l in (Path(".").resolve() / ".env").read_text(encoding="utf-8").splitlines():
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        ENV[_k.strip()] = _v.strip()

CSVS = {
    "balance_sheet": "asharebalancesheet_202605261517.csv",
    "income_statement": "ashareincome_202605261519.csv",
    "cash_flow": "asharecashflow_202605261518.csv",
}


def build_mapping() -> dict[str, int]:
    """wind_code -> comp_type_code（三表众数，缺失时跨表互补）."""
    per_table = {}
    for csv_name in CSVS.values():
        df = pd.read_csv(RAW / csv_name, low_memory=False,
                         usecols=["s_info_windcode", "comp_type_code"])
        df = df.dropna(subset=["comp_type_code"])
        g = df.groupby("s_info_windcode")["comp_type_code"].agg(
            lambda s: s.mode()[0] if not s.mode().empty else s.iloc[0])
        per_table[csv_name] = g.astype(int)

    all_codes = set().union(*(set(g.index) for g in per_table.values()))
    mapping: dict[str, int] = {}
    conflict = 0
    for code in all_codes:
        vals = {per_table[t].get(code) for t in per_table
                if code in per_table[t].index}
        vals = {int(v) for v in vals}
        if len(vals) == 1:
            mapping[code] = vals.pop()
        else:
            # 冲突：取众数（多为 1 表值，多数票）
            from collections import Counter
            all_votes = [int(per_table[t][code]) for t in per_table
                         if code in per_table[t].index]
            mapping[code] = Counter(all_votes).most_common(1)[0][0]
            conflict += 1
    print(f"  三表交叉：{len(all_codes)} 只，冲突 {conflict} 只（已取众数）")
    return mapping


def _db():
    return pymysql.connect(
        host=ENV.get("MYSQL_HOST", "localhost"),
        port=int(ENV.get("MYSQL_PORT", 3306)),
        user=ENV.get("MYSQL_USER"),
        password=ENV.get("MYSQL_PASSWORD"),
        database=ENV.get("MYSQL_DATABASE"),
        charset="utf8mb4",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("== 1. 从三表 CSV 读 comp_type_code ==")
    mapping = build_mapping()
    from collections import Counter
    dist = Counter(mapping.values())
    print(f"  公司级分布: 非金融(1)={dist[1]} 银行(2)={dist[2]} "
          f"保险(3)={dist[3]} 证券(4)={dist[4]}")

    print("== 2. 读取 companies 表 ==")
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT wind_code, comp_type_code FROM companies")
    companies = {r[0]: r[1] for r in cur.fetchall()}
    print(f"  companies 共 {len(companies)} 家")

    to_update = 0
    missing = 0
    for wc, cur_val in companies.items():
        new_val = mapping.get(wc)
        if new_val is not None and new_val != cur_val:
            to_update += 1
        elif new_val is None:
            missing += 1

    print(f"  待更新: {to_update} 家, CSV 中无此代码（境外股/NEEQ）: {missing} 家")

    if args.dry_run:
        print("[dry-run] 未写库")
        conn.close()
        return 0

    print("== 3. 写入 MySQL ==")
    updated = 0
    for wc, cur_val in companies.items():
        new_val = mapping.get(wc)
        if new_val is not None and new_val != cur_val:
            cur.execute(
                "UPDATE companies SET comp_type_code=%s WHERE wind_code=%s",
                (new_val, wc),
            )
            updated += 1
    conn.commit()
    print(f"  更新 {updated} 家")

    # 验证
    cur.execute(
        "SELECT comp_type_code, COUNT(*) FROM companies GROUP BY comp_type_code "
        "ORDER BY comp_type_code"
    )
    print("  最终 companies.comp_type_code 分布:")
    for r in cur.fetchall():
        print(f"    {r[0]}: {r[1]}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
