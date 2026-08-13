#!/usr/bin/env python
"""任务⑤ 金融企业字段前置 — 字段盘点 + 覆盖率统计。

从 data/raw/4/ 的三表数据字典中，识别金融企业专属字段（银行/保险/证券），
并统计每个字段在「全量 + 银行 + 保险 + 证券」四类样本中的非空覆盖率。

输出：字段清单（含中文含义、所属表、覆盖率、建议），供 docs/FINANCE_FIELDS_MAPPING.md 引用。
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW = Path("data/raw/比赛数据/4")
TABLES = {
    "balance_sheet": "asharebalancesheet_202605261517.csv",
    "income_statement": "ashareincome_202605261519.csv",
    "cash_flow": "asharecashflow_202605261518.csv",
}
DICTS = {
    "balance_sheet": "balancesheet_dict.txt",
    "income_statement": "income_dict.txt",
    "cash_flow": "cashflow_dict.txt",
}

# 金融企业专属字段的描述特征词（用于从字典里识别）
FIN_MARKERS = [
    "银行", "保险", "证券", "金融", "保费", "准备金", "赔款", "赔付", "同业",
    "央行", "分保", "再保", "退保", "保户", "承销", "经纪", "贵金属", "拆借",
    "备付金", "融出", "保单", "红利", "存出保证金", "独立账户", "受托", "贴现",
    "客户资金", "客户备付", "手续费", "佣金", "利息净收入", "利息收入", "利息支出",
    "已赚保费", "分出保费", "存放中央银行", "存放同业", "发放贷款", "吸收存款",
]


def parse_dict(table: str) -> dict[str, str]:
    """解析数据字典 → {字段名: 中文含义}。"""
    out: dict[str, str] = {}
    for line in (RAW / DICTS[table]).read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^([A-Z0-9_]+)\s*\(([^)]*)\)", line)
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def main() -> None:
    comp = pd.read_csv(RAW / TABLES["income_statement"], low_memory=False,
                       usecols=["s_info_windcode", "comp_type_code"])
    comp_map = comp.groupby("s_info_windcode")["comp_type_code"].agg(
        lambda s: s.mode()[0] if not s.mode().empty else s.iloc[0]
    )

    rows: list[dict] = []
    for table, csv_name in TABLES.items():
        meanings = parse_dict(table)
        # 读表头，拿到实际列名
        all_cols = pd.read_csv(RAW / csv_name, nrows=0).columns.tolist()
        fin_cols = [c for c in all_cols if meanings.get(c, "") and any(
            k in meanings[c] for k in FIN_MARKERS)]
        if not fin_cols:
            continue
        # 读金融列 + wind_code
        use = ["s_info_windcode"] + fin_cols
        df = pd.read_csv(RAW / csv_name, low_memory=False, usecols=use)
        df["ctype"] = df["s_info_windcode"].map(comp_map)
        total = len(df)
        bank = df[df["ctype"] == 2]
        ins = df[df["ctype"] == 3]
        sec = df[df["ctype"] == 4]
        for c in fin_cols:
            rows.append({
                "table": table,
                "field": c,
                "meaning": meanings[c],
                "all_pct": round(df[c].notna().sum() / total * 100, 1),
                "bank_pct": round(bank[c].notna().sum() / max(len(bank), 1) * 100, 1),
                "ins_pct": round(ins[c].notna().sum() / max(len(ins), 1) * 100, 1),
                "sec_pct": round(sec[c].notna().sum() / max(len(sec), 1) * 100, 1),
                "bank_n": int(bank[c].notna().sum()),
                "ins_n": int(ins[c].notna().sum()),
                "sec_n": int(sec[c].notna().sum()),
            })

    # 输出
    print(f"{'表':18} {'字段':32} {'含义':22} {'全量%':>6} {'银行%':>6} {'保险%':>6} {'证券%':>6} 银行n 保险n 证券n")
    print("-" * 130)
    for r in rows:
        print(f"{r['table']:18} {r['field']:32} {r['meaning']:22} "
              f"{r['all_pct']:>6} {r['bank_pct']:>6} {r['ins_pct']:>6} {r['sec_pct']:>6} "
              f"{r['bank_n']:>5} {r['ins_n']:>5} {r['sec_n']:>5}")
    print(f"\n共识别 {len(rows)} 个金融字段")


if __name__ == "__main__":
    main()
