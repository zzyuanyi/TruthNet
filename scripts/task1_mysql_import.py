"""任务①：MySQL 全量入库
========================
将比赛数据全部导入 MySQL truthnet 数据库。
执行顺序：companies → 三表 → 股东 → 公告 → 研报
"""

import sys
import io
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pymysql
from sqlalchemy import create_engine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── 配置 ──
DB_URL = "mysql+pymysql://truthnet:truthnet123@localhost:3306/truthnet"
engine = create_engine(DB_URL, echo=False)
BASE = Path(r"d:\projects\TruthNet\data\raw\比赛数据")
PROCESSED = Path(r"d:\projects\TruthNet\data\processed")
NOW = datetime.now(timezone.utc)

BATCH_SIZE = 5000  # 每批写入行数
DATASET_VERSION = "competition-2026"

def now_iso():
    return NOW.strftime("%Y-%m-%d %H:%M:%S")

def safe_date_str(val):
    """将各种日期格式统一转成 YYYY-MM-DD 字符串"""
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if len(s) >= 10:
        return s[:10]  # 截取日期部分
    return s if s else None

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest() if s else ""

def system_cols(source_file, source_row, source_type="competition_data"):
    """生成系统字段 dict"""
    return {
        "source_record_id": None,
        "source_file": source_file,
        "source_row": source_row,
        "source_type": source_type,
        "dataset_version": DATASET_VERSION,
        "revision_no": 1,
        "is_latest": True,
        "ingested_at": NOW,
        "updated_at": NOW,
        "quality_flags": None,
        "checksum": None,
    }


# ====================================================================
# Step 1: 导入 companies 表
# ====================================================================
def import_companies():
    print("=" * 60)
    print("Step 1: Import companies")
    print("=" * 60)

    df = pd.read_csv(PROCESSED / "industry_mapping.csv")
    print(f"Total companies in mapping: {len(df)}")

    rows = []
    for i, (_, r) in enumerate(df.iterrows()):
        wind_code = r["wind_code"]
        # entity_id: 用 wind_code 去掉后缀作为实体 ID
        entity_id = wind_code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        exchange_map = {".SZ": "XSHE", ".SH": "XSHG", ".BJ": "XBJ"}
        exchange_code = None
        for suffix, code in exchange_map.items():
            if suffix in wind_code:
                exchange_code = code
                break

        row = {
            "entity_id": entity_id,
            "wind_code": wind_code,
            "sec_name": r["stock_name"] if pd.notna(r["stock_name"]) else "",
            "aliases": None,
            "exchange_code": exchange_code,
            "industry_l1": r["industry_l1"] if pd.notna(r["industry_l1"]) and r["industry_l1"] != "" else None,
            "industry_l2": r["industry_l2"] if pd.notna(r["industry_l2"]) and r["industry_l2"] != "" else None,
            "sw_indu_code": None,
            "comp_type_code": None,
            "listing_date": None,
            "industry_source": r["source"],
            "industry_as_of": NOW.date(),
            **system_cols("industry_mapping.csv", i, "industry_mapping"),
        }
        rows.append(row)

    # 用 to_sql 批量写入
    df_out = pd.DataFrame(rows)
    df_out.to_sql("companies", engine, if_exists="append", index=False,
                  method="multi", chunksize=BATCH_SIZE)
    print(f"Inserted {len(df_out)} companies")
    return df_out


# ====================================================================
# Step 2: 导入三表（资产负债表）
# ====================================================================
def import_balance_sheet():
    print("\n" + "=" * 60)
    print("Step 2a: Import balance_sheet")
    print("=" * 60)

    fname = "asharebalancesheet_202605261517"
    fp = BASE / "4" / f"{fname}.csv"
    source_file = f"4/{fname}.csv"

    # 只读需要的列
    usecols = [
        "wind_code", "report_period", "statement_type", "ann_dt",
        "monetary_cap", "acct_rcv", "oth_rcv", "inventories",
        "tot_cur_assets", "fix_assets", "goodwill", "tot_assets",
        "st_borrow", "lt_borrow", "acct_payable", "tot_cur_liab",
        "tot_liab", "tot_shrhldr_eqy_incl_min_int",
    ]
    df = pd.read_csv(fp, low_memory=False, usecols=usecols)
    print(f"Rows: {len(df)}")

    total = len(df)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end].copy()
        # 添加系统字段
        batch["source_file"] = source_file
        batch["source_type"] = "competition_data"
        batch["dataset_version"] = DATASET_VERSION
        batch["revision_no"] = 1
        batch["is_latest"] = True
        batch["ingested_at"] = NOW
        batch["updated_at"] = NOW

        batch.to_sql("balance_sheet", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into balance_sheet")


# ====================================================================
# Step 2b: 导入利润表
# ====================================================================
def import_income_statement():
    print("\n" + "=" * 60)
    print("Step 2b: Import income_statement")
    print("=" * 60)

    fname = "ashareincome_202605261519"
    fp = BASE / "4" / f"{fname}.csv"
    source_file = f"4/{fname}.csv"

    usecols = [
        "wind_code", "report_period", "statement_type", "ann_dt",
        "oper_rev", "tot_oper_rev", "less_oper_cost",
        "less_selling_dist_exp", "less_gerl_admin_exp", "less_fin_exp",
        "oper_profit", "tot_profit",
        "net_profit_excl_min_int_inc", "net_profit_after_ded_nr_lp",
    ]
    df = pd.read_csv(fp, low_memory=False, usecols=usecols)
    print(f"Rows: {len(df)}")

    total = len(df)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end].copy()
        batch["source_file"] = source_file
        batch["source_type"] = "competition_data"
        batch["dataset_version"] = DATASET_VERSION
        batch["revision_no"] = 1
        batch["is_latest"] = True
        batch["ingested_at"] = NOW
        batch["updated_at"] = NOW

        batch.to_sql("income_statement", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into income_statement")


# ====================================================================
# Step 2c: 导入现金流量表
# ====================================================================
def import_cash_flow():
    print("\n" + "=" * 60)
    print("Step 2c: Import cash_flow")
    print("=" * 60)

    fname = "asharecashflow_202605261518"
    fp = BASE / "4" / f"{fname}.csv"
    source_file = f"4/{fname}.csv"

    usecols = [
        "wind_code", "report_period", "statement_type", "ann_dt",
        "net_cash_flows_oper_act", "net_cash_flows_inv_act",
        "net_cash_flows_fnc_act", "net_incr_cash_cash_equ",
        "free_cash_flow",
    ]
    df = pd.read_csv(fp, low_memory=False, usecols=usecols)
    print(f"Rows: {len(df)}")

    total = len(df)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end].copy()
        batch["source_file"] = source_file
        batch["source_type"] = "competition_data"
        batch["dataset_version"] = DATASET_VERSION
        batch["revision_no"] = 1
        batch["is_latest"] = True
        batch["ingested_at"] = NOW
        batch["updated_at"] = NOW

        batch.to_sql("cash_flow", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into cash_flow")


# ====================================================================
# Step 3: 导入十大股东
# ====================================================================
def import_shareholders():
    print("\n" + "=" * 60)
    print("Step 3: Import top_shareholders")
    print("=" * 60)

    fp = BASE / "2" / "clean.xlsx"
    source_file = "2/clean.xlsx"

    df = pd.read_excel(fp)
    print(f"Rows: {len(df)}")

    # 列映射: Excel → DB
    col_map = {
        "s_info_windcode": "wind_code",
        "ann_dt": "ann_dt",
        "s_holder_enddate": "s_holder_enddate",
        "s_holder_name": "s_holder_name",
        "s_holder_aname": "s_holder_aname",
        "s_holder_pct": "s_holder_pct",
        "s_holder_quantity": "s_holder_quantity",
        "s_holder_holdercategory": "s_holder_holdercategory",
        "s_holder_sequence": "s_holder_sequence",
        "report_period": "report_period",
    }
    df_out = df[list(col_map.keys())].rename(columns=col_map).copy()
    # 日期转换
    for date_col in ["ann_dt", "s_holder_enddate", "report_period"]:
        if date_col in df_out.columns:
            df_out[date_col] = df_out[date_col].apply(safe_date_str)
    df_out["source_file"] = source_file
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = DATASET_VERSION
    df_out["revision_no"] = 1
    df_out["is_latest"] = True
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    total = len(df_out)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df_out.iloc[start:end]
        batch.to_sql("top_shareholders", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 50000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into top_shareholders")


# ====================================================================
# Step 4: 导入公司公告
# ====================================================================
def import_announcements():
    print("\n" + "=" * 60)
    print("Step 4: Import announcements")
    print("=" * 60)

    fp = BASE / "3" / "clean.xlsx"
    source_file = "3/clean.xlsx"

    df = pd.read_excel(fp)
    print(f"Rows: {len(df)}")

    # 列映射
    col_map = {
        "object_id": "object_id",
        "s_info_windcode": "wind_code",
        "ann_dt": "ann_dt",
        "n_info_title": "n_info_title",
        "n_info_fcode": "n_info_fcode",
        "n_info_annlink": "source_uri",
    }
    df_out = df[list(col_map.keys())].rename(columns=col_map).copy()
    # 日期转换
    df_out["ann_dt"] = df_out["ann_dt"].apply(safe_date_str)
    df_out["source_file"] = source_file
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = DATASET_VERSION
    df_out["revision_no"] = 1
    df_out["is_latest"] = True
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW
    df_out["sentiment"] = None
    df_out["sentiment_method"] = None

    total = len(df_out)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df_out.iloc[start:end]
        batch.to_sql("announcements", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into announcements")


# ====================================================================
# Step 5: 导入研报
# ====================================================================
def import_research_reports():
    print("\n" + "=" * 60)
    print("Step 5: Import research_reports")
    print("=" * 60)

    fname = "rr_main_202605281537"
    fp = BASE / "5" / f"{fname}.csv"
    source_file = f"5/{fname}.csv"

    df = pd.read_csv(fp, low_memory=False)
    print(f"Rows: {len(df)}")

    # 列映射: CSV → DB
    col_map = {
        "report_id": "report_id",
        "sec_code": "sec_code",
        "exchange_code": "exchange_code",
        "sec_name": "sec_name",
        "org_name": "org_name",
        "title": "title",
        "publish_date": "publish_date",
        "abstract": "abstract",
        "rating_org": "rating_org",
        "rating_change": "rating_change",
        "industry_l1": "industry_l1",
        "sw_indu_code": "sw_indu_code",
        "source_uri": "source_uri",
    }
    # 安全提取存在的列
    available_cols = [c for c in col_map if c in df.columns]
    col_map_available = {c: col_map[c] for c in available_cols}
    df_out = df[available_cols].rename(columns=col_map_available).copy()

    # 日期转换
    if "publish_date" in df_out.columns:
        df_out["publish_date"] = df_out["publish_date"].apply(safe_date_str)

    # 构建 wind_code（从 sec_code 推断）
    if "exchange_code" in df.columns:
        # exchange_code: XSHG=上海, XSHE=深圳
        suffix_map = {"XSHG": ".SH", "XSHE": ".SZ"}
        df_out["wind_code"] = df["sec_code"].astype(str).str.zfill(6) + \
                              df["exchange_code"].map(suffix_map).fillna("")
    else:
        df_out["wind_code"] = df["sec_code"].astype(str).str.zfill(6)

    df_out["source_file"] = source_file
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = DATASET_VERSION
    df_out["revision_no"] = 1
    df_out["is_latest"] = True
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    total = len(df_out)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df_out.iloc[start:end]
        batch.to_sql("research_reports", engine, if_exists="append", index=False,
                     method="multi", chunksize=1000)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or end == total:
            print(f"  Progress: {end}/{total}")

    print(f"Inserted {total} rows into research_reports")


# ====================================================================
# Step 6: 验证
# ====================================================================
def verify():
    print("\n" + "=" * 60)
    print("Verification: SELECT COUNT(*) from all tables")
    print("=" * 60)

    tables = ["companies", "balance_sheet", "income_statement", "cash_flow",
              "top_shareholders", "announcements", "research_reports"]

    with pymysql.connect(host="localhost", port=3306, user="truthnet",
                          password="truthnet123", database="truthnet") as conn:
        with conn.cursor() as cur:
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                cnt = cur.fetchone()[0]
                print(f"  {t:25s}: {cnt:>10,}")

    # 行业覆盖率
    with pymysql.connect(host="localhost", port=3306, user="truthnet",
                          password="truthnet123", database="truthnet") as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  COUNT(CASE WHEN industry_l1 IS NOT NULL AND industry_l1 != '' THEN 1 END) * 1.0 / COUNT(*) AS coverage
                FROM companies
            """)
            coverage = cur.fetchone()[0]
            print(f"\n  Industry coverage: {coverage*100:.1f}%")


# ====================================================================
# Main
# ====================================================================
if __name__ == "__main__":
    t0 = time.time()
    print(f"Task 1: MySQL Full Import — {now_iso()}")
    print(f"Batch size: {BATCH_SIZE}")

    import_companies()
    import_balance_sheet()
    import_income_statement()
    import_cash_flow()
    import_shareholders()
    import_announcements()
    import_research_reports()

    verify()

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    print("Task 1 complete!")
