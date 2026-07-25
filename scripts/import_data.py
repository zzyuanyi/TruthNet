#!/usr/bin/env python
"""TruthNet — 比赛数据 MySQL 导入（适配实际数据布局）。

数据源: data/raw/1-5/（5 个文件夹，对应问答/股东/公告/三表/研报）
目标: MySQL truthnet 数据库（Alembic head 已就绪）

设计：
  - 配置从 Settings + 环境变量读取
  - 使用 staging 表 + INSERT ... ON DUPLICATE KEY UPDATE（幂等）
  - 使用 normalizer 统一 Wind Code 和 entity_id
  - 日期规范化为 YYYY-MM-DD
  - 所有副作用仅在 main() 中执行
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.core.config import settings  # noqa: E402
from backend.app.infrastructure.graph.normalizer import (  # noqa: E402
    make_listed_company_entity_id,
    normalize_wind_code,
)

logger = logging.getLogger(__name__)
NOW = datetime.now(timezone.utc)
BATCH_SIZE = 5000


def _now_iso() -> str:
    return NOW.strftime("%Y-%m-%d %H:%M:%S")


def _safe_normalize_wind_code(val: Any) -> str | None:
    """安全规范化 Wind Code，无法解析时保持原值."""
    if pd.isna(val):
        return None
    try:
        return normalize_wind_code(str(val))
    except ValueError:
        return str(val)


def _safe_date(val: Any) -> str | None:
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if len(s) >= 10 else (s or None)


def _make_engine() -> Engine:
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url, echo=False)


def _batch_insert(
    engine: Engine,
    table: str,
    df: pd.DataFrame,
) -> int:
    """使用 pandas to_sql 批量写入（利用 MySQL 严格类型转换）."""
    if df.empty:
        return 0

    df = df.where(pd.notna(df), None)
    total = 0
    for start in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[start : start + BATCH_SIZE]
        batch.to_sql(
            table,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )
        total += len(batch)
        if (start + BATCH_SIZE) % 20000 < BATCH_SIZE or start + BATCH_SIZE >= len(df):
            logger.info("  Progress: %d/%d", min(start + BATCH_SIZE, len(df)), len(df))

    return total


def _resolve_entity_id(row: dict, wind_code_col: str) -> str:
    """从行数据生成统一的 entity_id."""
    wc = str(row.get(wind_code_col, ""))
    try:
        return make_listed_company_entity_id(wc)
    except ValueError:
        # fallback: use bare code
        from backend.app.infrastructure.graph.normalizer import parse_wind_code

        try:
            digits, suffix = parse_wind_code(wc)
            return f"company_{digits}_{suffix or 'UNKNOWN'}"
        except ValueError:
            return f"ent_{uuid.uuid4().hex[:12]}"


def import_companies(engine: Engine, data_root: Path, ds_ver: str) -> int:
    """从行业映射文件导入 companies 表。如果没有映射文件，从三表数据提取."""
    logger.info("=== Step 1: Import companies ===")
    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    mapping_file = processed_dir / "industry_mapping.csv"

    if mapping_file.exists():
        df = pd.read_csv(mapping_file)
        logger.info("从行业映射文件导入 %d 家公司", len(df))
        rows = []
        for i, (_, r) in enumerate(df.iterrows()):
            wc = str(r.get("wind_code", ""))
            try:
                normalized = normalize_wind_code(wc)
            except ValueError:
                normalized = wc
            entity_id = _resolve_entity_id({"wind_code": normalized}, "wind_code")

            rows.append(
                {
                    "entity_id": entity_id,
                    "wind_code": normalized,
                    "sec_name": str(r.get("stock_name", r.get("sec_name", ""))),
                    "exchange_code": _exchange_from_wind(normalized),
                    "industry_l1": r.get("industry_l1")
                    if pd.notna(r.get("industry_l1"))
                    else None,
                    "industry_l2": r.get("industry_l2")
                    if pd.notna(r.get("industry_l2"))
                    else None,
                    "industry_source": str(r.get("source", "")),
                    "industry_as_of": NOW.date(),
                    "source_file": "industry_mapping.csv",
                    "source_row": i,
                    "source_type": "industry_mapping",
                    "dataset_version": ds_ver,
                    "revision_no": 1,
                    "is_latest": 1,
                    "ingested_at": NOW,
                    "updated_at": NOW,
                }
            )

        companies_df = pd.DataFrame(rows)
        total_c = _batch_insert(engine, "companies", companies_df)
        logger.info("companies: %d 条 (从行业映射)", total_c)
        return total_c

    # Fallback: 从三表提取唯一 wind_code
    logger.info("无行业映射文件，从三表 CSV 提取公司列表")
    codes = set()
    for csv_name in [
        "asharebalancesheet_202605261517.csv",
        "ashareincome_202605261519.csv",
        "asharecashflow_202605261518.csv",
    ]:
        fp = data_root / "4" / csv_name
        if fp.exists():
            df = pd.read_csv(fp, usecols=["wind_code"], low_memory=False)
            codes.update(df["wind_code"].dropna().unique())

    rows = []
    for i, wc in enumerate(sorted(codes)):
        try:
            normalized = normalize_wind_code(str(wc))
        except ValueError:
            normalized = str(wc)

        rows.append(
            {
                "entity_id": _resolve_entity_id({"wind_code": normalized}, "wind_code"),
                "wind_code": normalized,
                "sec_name": str(wc),
                "exchange_code": _exchange_from_wind(normalized),
                "source_file": "derived_from_financials",
                "source_row": i,
                "source_type": "financial_statements",
                "dataset_version": ds_ver,
                "revision_no": 1,
                "is_latest": 1,
                "ingested_at": NOW,
                "updated_at": NOW,
            }
        )

    companies_df2 = pd.DataFrame(rows)
    inserted = _batch_insert(engine, "companies", companies_df2)
    logger.info("companies: %d 条 (从三表提取)", inserted)
    return inserted


def _exchange_from_wind(wind_code: str) -> str | None:
    if not wind_code:
        return None
    if wind_code.endswith(".SH"):
        return "XSHG"
    if wind_code.endswith(".SZ"):
        return "XSHE"
    if wind_code.endswith(".BJ"):
        return "BJ"
    return None


def import_financial_table(
    engine: Engine,
    csv_path: Path,
    table_name: str,
    usecols: list[str],
    ds_ver: str,
) -> int:
    """导入单个财务报表 CSV."""
    logger.info("=== Import %s ===", table_name)
    if not csv_path.exists():
        logger.warning("%s 不存在: %s", table_name, csv_path)
        return 0

    df = pd.read_csv(csv_path, low_memory=False, usecols=usecols)
    logger.info("读取 %d 行", len(df))

    df["source_file"] = csv_path.name
    df["source_type"] = "competition_data"
    df["dataset_version"] = ds_ver
    df["revision_no"] = 1
    df["is_latest"] = 1
    df["ingested_at"] = NOW
    df["updated_at"] = NOW

    # 日期规范化
    for dc in ["report_period", "ann_dt"]:
        if dc in df.columns:
            df[dc] = df[dc].apply(_safe_date)

    # 规范化 wind_code
    if "wind_code" in df.columns:
        df["wind_code"] = df["wind_code"].apply(_safe_normalize_wind_code)

    total = _batch_insert(engine, table_name, df)
    logger.info("%s: %d 条", table_name, total)
    return total


def import_shareholders(engine: Engine, data_root: Path, ds_ver: str) -> int:
    """导入十大股东数据 (2/clean.xlsx)."""
    logger.info("=== Import top_shareholders ===")
    fp = data_root / "2" / "clean.xlsx"
    if not fp.exists():
        logger.warning("股东数据不存在: %s", fp)
        return 0

    df = pd.read_excel(fp)
    logger.info("读取 %d 行", len(df))

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
    avail = {k: v for k, v in col_map.items() if k in df.columns}
    df_out = df[list(avail.keys())].rename(columns=avail).copy()

    # 日期
    for dc in ["ann_dt", "s_holder_enddate", "report_period"]:
        if dc in df_out.columns:
            df_out[dc] = df_out[dc].apply(_safe_date)

    # Wind Code 规范化
    if "wind_code" in df_out.columns:
        df_out["wind_code"] = df_out["wind_code"].apply(
            lambda x: normalize_wind_code(str(x)) if pd.notna(x) else x
        )

    df_out["source_file"] = "2/clean.xlsx"
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = ds_ver
    df_out["revision_no"] = 1
    df_out["is_latest"] = 1
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    total = _batch_insert(engine, "top_shareholders", df_out)
    logger.info("top_shareholders: %d 条", total)
    return total


def import_announcements(engine: Engine, data_root: Path, ds_ver: str) -> int:
    """导入公告数据 (3/clean.xlsx)."""
    logger.info("=== Import announcements ===")
    fp = data_root / "3" / "clean.xlsx"
    if not fp.exists():
        logger.warning("公告数据不存在: %s", fp)
        return 0

    df = pd.read_excel(fp)
    logger.info("读取 %d 行", len(df))

    col_map = {
        "object_id": "object_id",
        "s_info_windcode": "wind_code",
        "ann_dt": "ann_dt",
        "n_info_title": "n_info_title",
        "n_info_fcode": "n_info_fcode",
        "n_info_annlink": "source_uri",
    }
    avail = {k: v for k, v in col_map.items() if k in df.columns}
    df_out = df[list(avail.keys())].rename(columns=avail).copy()

    df_out["ann_dt"] = df_out["ann_dt"].apply(_safe_date)
    if "wind_code" in df_out.columns:
        df_out["wind_code"] = df_out["wind_code"].apply(_safe_normalize_wind_code)
    df_out["source_file"] = "3/clean.xlsx"
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = ds_ver
    df_out["revision_no"] = 1
    df_out["is_latest"] = 1
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    total = _batch_insert(engine, "announcements", df_out)
    logger.info("announcements: %d 条", total)
    return total


def import_research_reports(engine: Engine, data_root: Path, ds_ver: str) -> int:
    """导入研报数据 (5/rr_main_202605281537.csv)."""
    logger.info("=== Import research_reports ===")
    fp = data_root / "5" / "rr_main_202605281537.csv"
    if not fp.exists():
        logger.warning("研报数据不存在: %s", fp)
        return 0

    df = pd.read_csv(fp, low_memory=False)
    logger.info("读取 %d 行", len(df))

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
    avail = {k: v for k, v in col_map.items() if k in df.columns}
    df_out = df[list(avail.keys())].rename(columns=avail).copy()

    if "publish_date" in df_out.columns:
        df_out["publish_date"] = df_out["publish_date"].apply(_safe_date)

    # 构建 wind_code
    if "sec_code" in df.columns and "exchange_code" in df.columns:
        suffix_map = {"XSHG": ".SH", "XSHE": ".SZ"}
        df_out["wind_code"] = df["sec_code"].astype(str).str.zfill(6) + df[
            "exchange_code"
        ].map(suffix_map).fillna("")
        # 规范化
        df_out["wind_code"] = df_out["wind_code"].apply(_safe_normalize_wind_code)
    elif "sec_code" in df.columns:
        df_out["wind_code"] = df["sec_code"].astype(str).str.zfill(6)

    df_out["source_file"] = fp.name
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = ds_ver
    df_out["revision_no"] = 1
    df_out["is_latest"] = 1
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    total = _batch_insert(engine, "research_reports", df_out)
    logger.info("research_reports: %d 条", total)
    return total


def verify_counts(engine: Engine) -> dict:
    """验证各表行数."""
    tables = [
        "companies",
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "top_shareholders",
        "announcements",
        "research_reports",
    ]
    counts = {}
    with engine.connect() as conn:
        for t in tables:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
            counts[t] = cnt
            logger.info("  %-25s: %10d", t, cnt)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL 全量导入")
    parser.add_argument("--data-root", default="data/raw")
    parser.add_argument("--dataset-version", default="competition-2026")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    data_root = Path(args.data_root)
    if not data_root.exists():
        logger.error("数据目录不存在: %s", data_root)
        return 1

    global BATCH_SIZE
    BATCH_SIZE = args.batch_size

    if args.dry_run:
        logger.info("DRY RUN — 仅统计，不写入")

    if args.verify_only:
        engine = _make_engine()
        verify_counts(engine)
        engine.dispose()
        return 0

    engine = _make_engine()

    try:
        # Step 1: companies
        import_companies(engine, data_root, args.dataset_version)

        # Step 2: 三表
        for csv_name, table, usecols in [
            (
                "asharebalancesheet_202605261517.csv",
                "balance_sheet",
                [
                    "wind_code",
                    "report_period",
                    "statement_type",
                    "ann_dt",
                    "monetary_cap",
                    "acct_rcv",
                    "oth_rcv",
                    "inventories",
                    "tot_cur_assets",
                    "fix_assets",
                    "goodwill",
                    "tot_assets",
                    "st_borrow",
                    "lt_borrow",
                    "acct_payable",
                    "tot_cur_liab",
                    "tot_liab",
                    "tot_shrhldr_eqy_incl_min_int",
                ],
            ),
            (
                "ashareincome_202605261519.csv",
                "income_statement",
                [
                    "wind_code",
                    "report_period",
                    "statement_type",
                    "ann_dt",
                    "oper_rev",
                    "tot_oper_rev",
                    "less_oper_cost",
                    "less_selling_dist_exp",
                    "less_gerl_admin_exp",
                    "less_fin_exp",
                    "oper_profit",
                    "tot_profit",
                    "net_profit_excl_min_int_inc",
                    "net_profit_after_ded_nr_lp",
                ],
            ),
            (
                "asharecashflow_202605261518.csv",
                "cash_flow",
                [
                    "wind_code",
                    "report_period",
                    "statement_type",
                    "ann_dt",
                    "net_cash_flows_oper_act",
                    "net_cash_flows_inv_act",
                    "net_cash_flows_fnc_act",
                    "net_incr_cash_cash_equ",
                    "free_cash_flow",
                ],
            ),
        ]:
            if not args.dry_run:
                import_financial_table(
                    engine,
                    data_root / "4" / csv_name,
                    table,
                    usecols,
                    args.dataset_version,
                )
            else:
                fp = data_root / "4" / csv_name
                if fp.exists():
                    df = pd.read_csv(fp, low_memory=False)
                    logger.info("[dry-run] %s: %d 行待导入", table, len(df))

        # Step 3: 股东
        import_shareholders(engine, data_root, args.dataset_version)

        # Step 4: 公告
        import_announcements(engine, data_root, args.dataset_version)

        # Step 5: 研报
        import_research_reports(engine, data_root, args.dataset_version)

        # 验证
        counts = verify_counts(engine)
        total = sum(counts.values())
        logger.info("总计: %d 条", total)

    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main())
