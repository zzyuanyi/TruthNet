#!/usr/bin/env python
"""任务⑤ — 扩展 MySQL 三表，导入金融企业专属字段。

1. ALTER TABLE 为三表新增金融专属字段（float，可空）
2. 从原始 CSV 导入这些字段（按 wind_code + report_period + statement_type + ann_dt 对齐 upsert）

用法：
  python scripts/import_finance_fields.py --dry-run
  python scripts/import_finance_fields.py
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
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

# 要导入的金融专属字段（按表）。中文含义见 docs/FINANCE_FIELDS_MAPPING.md
FIN_FIELDS: dict[str, list[str]] = {
    "balance_sheet": [
        # 银行
        "loans_and_adv_granted", "cash_deposits_central_bank",
        "asset_dep_oth_banks_fin_inst", "borrow_central_bank",
        "liab_dep_oth_banks_fin_inst", "cust_bank_dep", "precious_metals",
        # 保险
        "prem_rcv", "rsrv_insur_cont", "unearned_prem_rsrv", "out_loss_rsrv",
        "life_insur_rsrv", "claims_payable",
        # 证券
        "clients_cap_deposit", "clients_rsrv_settle", "acting_trading_sec",
        "mrgn_paid", "lending_funds", "settle_rsrv",
    ],
    "income_statement": [
        # 银行
        "int_inc", "net_int_inc", "less_int_exp",
        # 保险
        "prem_inc", "insur_prem_unearned", "tot_claim_exp", "prepay_surr",
        "chg_insur_cont_rsrv",
        # 证券
        "handling_chrg_comm_inc", "net_handling_chrg_comm_inc",
        "net_inc_sec_trading_brok_bus", "net_inc_sec_uw_bus",
        "net_inc_ec_asset_mgmt_bus",
    ],
    "cash_flow": [
        # 银行
        "net_incr_dep_cob", "net_incr_int_handling_chrg",
        "net_incr_loans_central_bank", "net_incr_dep_cbob",
        # 保险
        "cash_recp_prem_orig_inco", "cash_pay_claims_orig_inco",
        # 证券
        "handling_chrg_paid", "securitie_netcash_received",
        "melt_money_net_increase",
    ],
}

CSV_NAME = {
    "balance_sheet": "asharebalancesheet_202605261517.csv",
    "income_statement": "ashareincome_202605261519.csv",
    "cash_flow": "asharecashflow_202605261518.csv",
}

# 三表对齐 upsert 的唯一键
_UNIQUE_KEY = {
    "balance_sheet": ["wind_code", "report_period", "statement_type", "ann_dt"],
    "income_statement": ["wind_code", "report_period", "statement_type", "ann_dt"],
    "cash_flow": ["wind_code", "report_period", "statement_type", "ann_dt"],
}


def _db():
    return pymysql.connect(
        host=ENV.get("MYSQL_HOST", "localhost"),
        port=int(ENV.get("MYSQL_PORT", 3306)),
        user=ENV.get("MYSQL_USER"),
        password=ENV.get("MYSQL_PASSWORD"),
        database=ENV.get("MYSQL_DATABASE"),
        charset="utf8mb4",
    )


def _normalize_code(s: str) -> str:
    s = str(s).strip()
    if "." in s:
        return s
    # 无后缀 → 按数字推断
    d = "".join(ch for ch in s if ch.isdigit())
    if d.startswith("6"):
        return d + ".SH"
    if d.startswith(("4", "8", "9")):
        return d + ".BJ"
    return d + ".SZ"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = _db()
    cur = conn.cursor()

    for table, fields in FIN_FIELDS.items():
        print(f"\n=== {table} ({len(fields)} 字段) ===")
        # 1. 检查/新增列
        cur.execute(f"SHOW COLUMNS FROM {table}")
        existing = {r[0] for r in cur.fetchall()}
        missing = [f for f in fields if f not in existing]
        if missing and not args.dry_run:
            for f in missing:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {f} FLOAT NULL "
                    f"COMMENT '金融企业专属字段'"
                )
            conn.commit()
            print(f"  ALTER TABLE 新增 {len(missing)} 列: {missing}")
        elif missing:
            print(f"  [dry-run] 需新增 {len(missing)} 列")
        else:
            print(f"  字段均已存在")

        # 2. 读 CSV
        csv_name = CSV_NAME[table]
        use = ["s_info_windcode", "report_period", "statement_type", "ann_dt"] + fields
        df = pd.read_csv(RAW / csv_name, low_memory=False, usecols=use)
        df["wind_code"] = df["s_info_windcode"].map(_normalize_code)
        df = df.drop(columns=["s_info_windcode"])
        # 归一化日期/类型为字符串（与既有数据一致）
        for c in ["report_period", "statement_type", "ann_dt"]:
            df[c] = df[c].apply(
                lambda x: str(int(x)) if pd.notna(x) else None)
        # 补齐 NOT NULL 审计字段
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df["revision_no"] = 1
        df["is_latest"] = 1
        df["ingested_at"] = now
        df["updated_at"] = now

        # 3. upsert（只更新金融字段列）
        n = len(df)
        if args.dry_run:
            print(f"  [dry-run] {n} 行待导入（字段: {fields}）")
            continue

        update_cols = fields
        placeholders = ", ".join(["%s"] * len(df.columns))
        updates = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in update_cols])
        cols = ", ".join(f"`{c}`" for c in df.columns)
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
        df = df.astype(object).where(pd.notna(df), None)
        rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        batch = 5000
        ok = fail = 0
        for i in range(0, len(rows), batch):
            try:
                cur.executemany(sql, rows[i:i + batch])
                conn.commit()
                ok += len(rows[i:i + batch])
            except Exception as e:
                conn.rollback()
                fail += len(rows[i:i + batch])
                if i == 0:
                    print(f"  [error] {type(e).__name__}: {str(e)[:200]}",
                          file=sys.stderr)
        print(f"  导入完成: ok={ok} fail={fail}")

    conn.close()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
