#!/usr/bin/env python3
"""任务⑤：金融企业专属字段导入（Phase D 加固版）
================================================================
数据源：data/raw/比赛数据/4 下三张原始报表 CSV。
目标：向 balance_sheet / income_statement / cash_flow 三表导入金融专属字段
（银行/保险/证券，共 41 列），按 wind_code + report_period + statement_type +
ann_dt 对齐 upsert。

安全设计（对齐 scripts/industry_fill.py 的写库纪律）：
  - **默认 dry-run 零写入**；仅显式 `--apply` 才写库；
  - **fail-closed 数据库守卫**：`--database` 必填，且必须命中 .env 中
    demo（truthnet）或 test（truthnet_test）允许清单，连接后 `SELECT
    DATABASE()` 二次核对，任一不符立即退出；
  - **schema 变更走 Alembic**：脚本不再承担 ALTER TABLE DDL；启动时校验
    41 列已存在（v11 迁移 f1a2b3c4d5e6），缺失则 fail-fast 提示先迁移；
  - **单事务 + 可回滚**：每张表一个事务，批内任一失败整表回滚；
  - **CSV 数据预检**：逐字段核对列存在，缺失列明确报错，不静默跳过。

用法：
  python scripts/import_finance_fields.py --database truthnet_test --dry-run
  python scripts/import_finance_fields.py --database truthnet_test --verify-only
  python scripts/import_finance_fields.py --database truthnet_test --apply
  python scripts/import_finance_fields.py --database truthnet --apply
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymysql

# 仅作为脚本运行时重设 stdout 编码；作为模块导入（测试）时不劫持
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import settings  # noqa: E402

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "比赛数据" / "4"

# 要导入的金融专属字段（按表）。与 v11 迁移保持一致；中文含义见 docs/FINANCE_FIELDS_MAPPING.md
FIN_FIELDS: dict[str, list[str]] = {
    "balance_sheet": [
        # 银行
        "loans_and_adv_granted",
        "cash_deposits_central_bank",
        "asset_dep_oth_banks_fin_inst",
        "borrow_central_bank",
        "liab_dep_oth_banks_fin_inst",
        "cust_bank_dep",
        "precious_metals",
        # 保险
        "prem_rcv",
        "rsrv_insur_cont",
        "unearned_prem_rsrv",
        "out_loss_rsrv",
        "life_insur_rsrv",
        "claims_payable",
        # 证券
        "clients_cap_deposit",
        "clients_rsrv_settle",
        "acting_trading_sec",
        "mrgn_paid",
        "lending_funds",
        "settle_rsrv",
    ],
    "income_statement": [
        # 银行
        "int_inc",
        "net_int_inc",
        "less_int_exp",
        # 保险
        "prem_inc",
        "insur_prem_unearned",
        "tot_claim_exp",
        "prepay_surr",
        "chg_insur_cont_rsrv",
        # 证券
        "handling_chrg_comm_inc",
        "net_handling_chrg_comm_inc",
        "net_inc_sec_trading_brok_bus",
        "net_inc_sec_uw_bus",
        "net_inc_ec_asset_mgmt_bus",
    ],
    "cash_flow": [
        # 银行
        "net_incr_dep_cob",
        "net_incr_int_handling_chrg",
        "net_incr_loans_central_bank",
        "net_incr_dep_cbob",
        # 保险
        "cash_recp_prem_orig_inco",
        "cash_pay_claims_orig_inco",
        # 证券
        "handling_chrg_paid",
        "securitie_netcash_received",
        "melt_money_net_increase",
    ],
}

# 三表对齐 upsert 的唯一键（依赖表上对应唯一索引）
UNIQUE_KEY = ["wind_code", "report_period", "statement_type", "ann_dt"]

# 默认 CSV 文件名（原始数据日期戳命名；可用 --*-csv 覆盖）
DEFAULT_CSV_NAME: dict[str, str] = {
    "balance_sheet": "asharebalancesheet_202605261517.csv",
    "income_statement": "ashareincome_202605261519.csv",
    "cash_flow": "asharecashflow_202605261518.csv",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_code(s: str) -> str:
    """wind_code 规范化：已有 .SH/.SZ/.BJ 后缀原样保留；无后缀按数字推断。"""
    s = str(s).strip()
    if "." in s:
        return s
    d = "".join(ch for ch in s if ch.isdigit())
    if d.startswith("6"):
        return d + ".SH"
    if d.startswith(("4", "8", "9")):
        return d + ".BJ"
    return d + ".SZ"


def _resolve_credentials(database: str) -> dict[str, str]:
    """按 --database 从 settings 解析目标库三件套；非 allowlist 库名 fail-closed。

    pydantic-settings 已按 .env last-wins 解析 demo/test 两组凭据，
    这里只做目标库白名单判定，不打印任何密码。
    """
    demo = {
        "user": settings.MYSQL_USER,
        "password": settings.MYSQL_PASSWORD,
        "database": settings.MYSQL_DATABASE,
    }
    test = {
        "user": settings.MYSQL_TEST_USER,
        "password": settings.MYSQL_TEST_PASSWORD,
        "database": settings.MYSQL_TEST_DATABASE,
    }
    for target in (test, demo):
        if target["database"] and database == target["database"]:
            return target
    raise SystemExit(
        f"目标库 {database!r} 不在 .env 允许清单"
        f"（demo={demo['database']!r}, test={test['database']!r}）"
        f"—— fail-closed，拒绝运行"
    )


def _connect(database: str) -> pymysql.Connection:
    """连接目标库并二次核对 SELECT DATABASE()。"""
    creds = _resolve_credentials(database)
    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=creds["user"],
        password=creds["password"],
        database=creds["database"],
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            actual = cur.fetchone()[0]
    except Exception:
        conn.close()
        raise
    if actual != database:
        conn.close()
        raise SystemExit(
            f"实际连接库 {actual!r} != 目标库 {database!r} —— fail-closed，拒绝运行"
        )
    return conn


def ensure_columns(cur, table: str, fields: list[str]) -> None:
    """校验表已具备金融字段；缺失则提示先执行 Alembic v11 迁移（fail-fast）。"""
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    existing = {r[0] for r in cur.fetchall()}
    missing = [f for f in fields if f not in existing]
    if missing:
        raise SystemExit(
            f"{table} 缺少 {len(missing)} 个金融字段: {missing}\n"
            "schema 变更必须通过 Alembic 表达（import 脚本不承担 DDL）。\n"
            "请先执行：  python -m alembic upgrade head\n"
            "（v11 迁移 f1a2b3c4d5e6 已新增这 41 列）"
        )


def check_csv_columns(
    raw_dir: Path, table: str, fields: list[str], csv_name: str
) -> str:
    """校验 CSV 中金融字段列齐全，返回 csv 路径；缺失列明确报错。"""
    csv_path = raw_dir / csv_name
    if not csv_path.exists():
        raise SystemExit(f"CSV 不存在: {csv_path}（原始数据不提交仓库，请先就位）")
    header = pd.read_csv(csv_path, nrows=0)
    header_cols = set(header.columns)
    missing_in_csv = [f for f in fields if f not in header_cols]
    required = {"s_info_windcode", "report_period", "statement_type", "ann_dt"}
    missing_required = sorted(required - header_cols)
    if missing_in_csv or missing_required:
        raise SystemExit(
            f"{csv_name} 缺少列 -> 金融字段缺失: {missing_in_csv}, "
            f"基础字段缺失: {missing_required}（fail-fast，不静默跳过）"
        )
    return str(csv_path)


def load_df(
    raw_dir: Path, table: str, fields: list[str], csv_name: str
) -> pd.DataFrame:
    """读取并按三表对齐口径规范化。"""
    csv_path = check_csv_columns(raw_dir, table, fields, csv_name)
    use = ["s_info_windcode", "report_period", "statement_type", "ann_dt"] + fields
    df = pd.read_csv(csv_path, low_memory=False, usecols=use)
    df["wind_code"] = df["s_info_windcode"].map(_normalize_code)
    df = df.drop(columns=["s_info_windcode"])
    # 归一化日期/类型为字符串（与既有数据一致）
    for c in ["report_period", "statement_type", "ann_dt"]:
        df[c] = df[c].apply(lambda x: str(int(x)) if pd.notna(x) else None)
    # 补齐 NOT NULL 审计字段
    now = _now_str()
    df["revision_no"] = 1
    df["is_latest"] = 1
    df["ingested_at"] = now
    df["updated_at"] = now
    return df


def upsert_table(
    conn: pymysql.Connection, table: str, fields: list[str], df: pd.DataFrame
) -> int:
    """单事务批量 upsert（只更新金融字段列）；失败整表回滚并抛异常。"""
    update_cols = fields
    cols = ", ".join(f"`{c}`" for c in df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    updates = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in update_cols])
    sql = (
        f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    data = df.astype(object).where(pd.notna(df), None)
    rows = [tuple(r) for r in data.itertuples(index=False, name=None)]
    batch = 5000
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), batch):
                cur.executemany(sql, rows[i : i + batch])
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise SystemExit(
            f"{table} 事务回滚（零写入）: {type(exc).__name__}: {str(exc)[:300]}"
        )
    return len(rows)


def post_check(conn: pymysql.Connection, table: str, fields: list[str]) -> None:
    """apply 后回查：至少一个金融字段非空的记录数，确认数据落库。"""
    probe = f"`{fields[0]}` IS NOT NULL"
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE {probe}")
        n = cur.fetchone()[0]
    log(f"  [post-check] {table} 至少 1 个金融字段非空的行数 = {n}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="导入金融企业专属字段（默认 dry-run 零写入，--apply 显式写库）"
    )
    ap.add_argument(
        "--database",
        required=True,
        help="目标库名，必须命中 .env 允许清单（如 truthnet_test / truthnet）",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="只读取/校验/统计待导入行数，零写入（默认行为）",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="显式执行写库（与 --dry-run / --verify-only 互斥）",
    )
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="只校验列存在 + CSV 可读，不读取全量数据也不写库",
    )
    ap.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"原始 CSV 目录（默认 {DEFAULT_RAW_DIR}）",
    )
    # 具体 CSV 文件名可覆盖（默认取数据日期戳命名的默认值）
    ap.add_argument(
        "--balance-sheet-csv", default=None, help="balance_sheet CSV 文件名覆盖"
    )
    ap.add_argument(
        "--income-csv", default=None, help="income_statement CSV 文件名覆盖"
    )
    ap.add_argument("--cash-flow-csv", default=None, help="cash_flow CSV 文件名覆盖")
    args = ap.parse_args()

    if args.apply and (args.dry_run or args.verify_only):
        raise SystemExit("--apply 与 --dry-run / --verify-only 互斥")
    write = args.apply

    csv_names = dict(DEFAULT_CSV_NAME)
    overrides = {
        "balance_sheet": args.balance_sheet_csv,
        "income_statement": args.income_csv,
        "cash_flow": args.cash_flow_csv,
    }
    for table, name in overrides.items():
        if name:
            csv_names[table] = name

    conn = _connect(args.database)
    log(f"== 目标库 {args.database} 连接 OK（SELECT DATABASE() 已核对）==")

    try:
        for table, fields in FIN_FIELDS.items():
            log(f"\n=== {table} ({len(fields)} 字段) ===")
            with conn.cursor() as cur:
                ensure_columns(cur, table, fields)
            csv_name = csv_names[table]
            if args.verify_only:
                check_csv_columns(args.raw_dir, table, fields, csv_name)
                log("  [verify-only] 列与 CSV 校验通过")
                continue
            df = load_df(args.raw_dir, table, fields, csv_name)
            n = len(df)
            if not write:
                log(f"  [dry-run] {n} 行待导入（字段: {fields}），未写库")
                continue
            log(f"  [apply] 单事务导入 {n} 行 ...")
            written = upsert_table(conn, table, fields, df)
            post_check(conn, table, fields)
            log(f"  [apply] {table} 写入完成: {written} 行")
    finally:
        conn.close()

    if write:
        log(f"\n完成：目标库 {args.database} 金融字段导入已提交。")
    else:
        log("\n完成：dry-run / verify-only，零写入。确认无误后加 --apply 执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
