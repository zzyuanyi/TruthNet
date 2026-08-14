#!/usr/bin/env python
"""TruthNet — 比赛数据 MySQL 导入（适配实际数据布局）。

数据源: data/raw/1-5/（5 个文件夹，对应问答/股东/公告/三表/研报）
目标: MySQL truthnet 数据库（Alembic head 已就绪）

设计：
  - 表级 INSERT ... ON DUPLICATE KEY UPDATE（幂等）
  - 使用 normalizer 统一 Wind Code 和 entity_id
  - 日期规范化为 YYYY-MM-DD
  - --dry-run 跑完整读取/映射/规范化/校验链路，仅禁止写库
  - 所有副作用仅在 dry_run=False 时执行
"""

from __future__ import annotations

import argparse
import json
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

# 各表用于 ON DUPLICATE KEY UPDATE 的唯一键（对应数据库实际唯一约束）
_UNIQUE_KEYS: dict[str, list[str]] = {
    "companies": ["entity_id"],
    "balance_sheet": [
        "wind_code",
        "report_period",
        "statement_type",
        "ann_dt",
        "revision_no",
    ],
    "income_statement": [
        "wind_code",
        "report_period",
        "statement_type",
        "ann_dt",
        "revision_no",
    ],
    "cash_flow": [
        "wind_code",
        "report_period",
        "statement_type",
        "ann_dt",
        "revision_no",
    ],
    "top_shareholders": ["source_record_id"],
    "announcements": ["object_id"],
    "research_reports": ["report_id"],
}


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


def _batch_upsert(
    engine: Engine,
    table: str,
    df: pd.DataFrame,
    unique_keys: list[str],
    update_columns: list[str] | None = None,
) -> dict:
    """INSERT ... ON DUPLICATE KEY UPDATE。

    依赖数据库实际存在的唯一约束；键由 _UNIQUE_KEYS 提供。
    update_columns=None 时更新全部非键列；传列表时仅更新指定列。
    返回 {"processed": int, "failed": int}。
    """
    if df.empty:
        return {"processed": 0, "failed": 0}

    df = df.astype(object).where(pd.notna(df), None)
    columns = list(df.columns)
    placeholders = ", ".join([f":{c}" for c in columns])
    if update_columns is not None:
        update_cols = [
            c for c in update_columns if c in columns and c not in unique_keys
        ]
    else:
        update_cols = [c for c in columns if c not in unique_keys]
    if not update_cols:
        updates = f"`{columns[0]}` = VALUES(`{columns[0]}`)"
    else:
        updates = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in update_cols])

    sql = (
        f"INSERT INTO `{table}` ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    processed = 0
    failed = 0
    with engine.connect() as conn:
        for start in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[start : start + BATCH_SIZE]
            rows = batch.to_dict(orient="records")
            try:
                conn.execute(text(sql), rows)
                conn.commit()
                processed += len(rows)
            except Exception:
                conn.rollback()
                failed += len(rows)
                logger.exception(
                    "batch upsert failed: %s rows %d-%d",
                    table,
                    start,
                    start + len(rows),
                )

    logger.info("  %s: processed=%d failed=%d", table, processed, failed)
    return {"processed": processed, "failed": failed}


def _resolve_entity_id(row: dict, wind_code_col: str) -> str:
    """从行数据生成统一的 entity_id."""
    wc = str(row.get(wind_code_col, ""))
    try:
        return make_listed_company_entity_id(wc)
    except ValueError:
        from backend.app.infrastructure.graph.normalizer import parse_wind_code

        try:
            digits, suffix = parse_wind_code(wc)
            return f"company_{digits}_{suffix or 'UNKNOWN'}"
        except ValueError:
            return f"ent_{uuid.uuid4().hex[:12]}"


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


def _normalize_optional_text(value: object) -> str | None:
    """行业补全档案 v1.1 §8：None/nan/none/null/空白 → None，杜绝 "nan" 字符串落库。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


# ═══════════════════════════════════════════════════════════
# 导入函数（所有读取/映射/规范化逻辑，仅在 dry_run=False 时写库）
# ═══════════════════════════════════════════════════════════


def import_companies(
    engine: Engine, data_root: Path, ds_ver: str, *, dry_run: bool = False
) -> dict:
    """从行业映射文件导入 companies 表。"""
    logger.info("=== Step 1: Import companies ===")
    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    mapping_file = processed_dir / "industry_mapping.csv"

    # 证券主表（security_master.csv）负责 sec_name；industry_mapping.csv
    # 只提供行业字段，永远不能成为名称权威源。
    # P1-4：主表缺失/损坏/字段不完整 → 失败关闭（禁止回退行业映射的 sec_name）。
    master_names: dict[str, str] = {}
    master_quality: dict[str, str] = {}
    master_csv = processed_dir / "security_master.csv"
    if not master_csv.exists():
        raise ValueError(
            f"证券主表缺失: {master_csv}，请先运行 python scripts/security_master.py"
        )
    try:
        mdf = pd.read_csv(master_csv)
        if "wind_code" not in mdf.columns or "sec_name" not in mdf.columns:
            raise ValueError("security_master.csv 缺少 wind_code/sec_name 列")
        for _, mr in mdf.iterrows():
            wc = str(mr.get("wind_code") or "").strip()
            sn = str(mr.get("sec_name") or "").strip()
            if not wc or sn == "nan":
                continue
            master_names[wc] = sn
            # 空 quality_flag 在 CSV 读回为 NaN → 归一化为空串（否则误写 {"nan": true}）
            qflag = str(mr.get("quality_flag") or "").strip()
            master_quality[wc] = "" if qflag in ("nan", "None") else qflag
        logger.info(
            "证券主表 %s 载入 %d 条名称（含质量标记）",
            master_csv.name,
            len(master_names),
        )
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — 主表损坏 → 失败关闭
        raise ValueError(f"证券主表读取失败: {exc}") from exc

    if mapping_file.exists():
        df = pd.read_csv(mapping_file)
        logger.info("从行业映射文件导入 %d 家公司 (dry_run=%s)", len(df), dry_run)
        # P1-4（核验修订）：主表缺少 mapping 中的代码 → 失败关闭（禁止回退
        # 空字符串 sec_name——名称权威源必须完整，否则产生不可追溯的空白名称）。
        mapping_codes = []
        for _, r in df.iterrows():
            wc = str(r.get("wind_code", ""))
            try:
                mapping_codes.append(normalize_wind_code(wc))
            except ValueError:
                mapping_codes.append(wc)
        missing_master = sorted(set(c for c in mapping_codes if c not in master_names))
        if missing_master:
            raise ValueError(
                f"证券主表缺少 {len(missing_master)} 个代码，禁止导入: "
                + ", ".join(missing_master[:10])
            )
        rows = []
        for i, (_, r) in enumerate(df.iterrows()):
            wc = str(r.get("wind_code", ""))
            try:
                normalized = normalize_wind_code(wc)
            except ValueError:
                normalized = wc
            entity_id = _resolve_entity_id({"wind_code": normalized}, "wind_code")
            qflag = master_quality.get(normalized, "")
            rows.append(
                {
                    "entity_id": entity_id,
                    "wind_code": normalized,
                    # 名称以证券主表为准（P1-4：禁止回退 industry_mapping，主表缺失已失败关闭）
                    "sec_name": master_names[normalized],
                    "quality_flags": (
                        json.dumps({q: True for q in qflag.split(",") if q})
                        if qflag
                        else None
                    ),
                    "exchange_code": _exchange_from_wind(normalized),
                    "industry_l1": r.get("industry_l1")
                    if pd.notna(r.get("industry_l1"))
                    else None,
                    "industry_l2": r.get("industry_l2")
                    if pd.notna(r.get("industry_l2"))
                    else None,
                    # 行业补全档案 v1.1 §8：禁止把 NaN 字符串写进 source
                    "industry_source": _normalize_optional_text(r.get("source")),
                    # 行业补全档案 v1.1 §2.1：仅有行业值的行才写 as_of
                    "industry_as_of": (
                        NOW.date() if pd.notna(r.get("industry_l1")) else None
                    ),
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
        if dry_run:
            logger.info("[dry-run] companies: %d 行待导入", len(companies_df))
            v = _validate_table("companies", companies_df)
            return {
                "source_rows": len(df),
                "valid_rows": len(companies_df) - v["invalid_rows"],
                "invalid_rows": v["invalid_rows"],
                "processed": 0,
                "failed": 0,
            }
        # 行业导入禁止覆盖已有 sec_name/aliases（台积电类污染防护）；
        # 行业补全档案 v1.1 §7.4：行业字段写权统一移交 scripts/industry_fill.py，
        # 重导不再更新行业列（防止旧 CSV 抹掉 apply 后的补全结果）。
        result = _batch_upsert(
            engine,
            "companies",
            companies_df,
            _UNIQUE_KEYS["companies"],
            update_columns=[
                "exchange_code",
                "source_file",
                "source_row",
                "source_type",
                "dataset_version",
                "revision_no",
                "is_latest",
                "quality_flags",
                "ingested_at",
                "updated_at",
            ],
        )
        return {"source_rows": len(df), "valid_rows": len(companies_df), **result}

    # Fallback: 从三表提取唯一 wind_code
    logger.info("无行业映射文件，从三表 CSV 提取公司列表 (dry_run=%s)", dry_run)
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

    # P1-3（第二轮审查修订）：备用导入路径与主路径一致——主表缺失财务代码
    # → 失败关闭，禁止回退代码占位符（占位名会污染 sec_name 权威源）。
    normalized_codes = []
    for wc in sorted(codes):
        try:
            normalized_codes.append(normalize_wind_code(str(wc)))
        except ValueError:
            normalized_codes.append(str(wc))
    missing_master = sorted(set(c for c in normalized_codes if c not in master_names))
    if missing_master:
        raise ValueError(
            f"证券主表缺少 {len(missing_master)} 个财务代码，禁止回退导入: "
            + ", ".join(missing_master[:10])
        )

    rows = []
    for i, normalized in enumerate(normalized_codes):
        qflag = master_quality.get(normalized, "")
        rows.append(
            {
                "entity_id": _resolve_entity_id({"wind_code": normalized}, "wind_code"),
                "wind_code": normalized,
                "sec_name": master_names[normalized],
                "quality_flags": (
                    json.dumps({q: True for q in qflag.split(",") if q})
                    if qflag
                    else None
                ),
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
    if dry_run:
        logger.info("[dry-run] companies: %d 行待导入 (从三表)", len(companies_df2))
        v = _validate_table("companies", companies_df2)
        return {
            "source_rows": len(codes),
            "valid_rows": len(companies_df2) - v["invalid_rows"],
            "invalid_rows": v["invalid_rows"],
            "processed": 0,
            "failed": 0,
        }

    # 回退导入：仅更新 exchange_code、source_file 等审计字段，
    # 不覆盖已有的 sec_name、aliases（P0 修复）；
    # 行业补全档案 v1.1 §7.4：行业列写权移交 scripts/industry_fill.py。
    result = _batch_upsert(
        engine,
        "companies",
        companies_df2,
        _UNIQUE_KEYS["companies"],
        update_columns=[
            "exchange_code",
            "source_file",
            "source_row",
            "source_type",
            "dataset_version",
            "revision_no",
            "is_latest",
            "quality_flags",
            "ingested_at",
            "updated_at",
        ],
    )
    return {"source_rows": len(codes), "valid_rows": len(companies_df2), **result}


def import_financial_table(
    engine: Engine,
    csv_path: Path,
    table_name: str,
    usecols: list[str],
    ds_ver: str,
    *,
    dry_run: bool = False,
) -> dict:
    """导入单个财务报表 CSV."""
    logger.info("=== Import %s (dry_run=%s) ===", table_name, dry_run)
    if not csv_path.exists():
        logger.warning("%s 不存在: %s", table_name, csv_path)
        return {
            "source_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 1,
            "processed": 0,
            "failed": 0,
        }

    df = pd.read_csv(csv_path, low_memory=False, usecols=usecols)
    source_rows = len(df)
    logger.info("读取 %d 行", source_rows)

    df["source_file"] = csv_path.name
    df["source_type"] = "competition_data"
    df["dataset_version"] = ds_ver
    df["revision_no"] = 1
    df["is_latest"] = 1
    df["ingested_at"] = NOW
    df["updated_at"] = NOW

    for dc in ["report_period", "ann_dt"]:
        if dc in df.columns:
            df[dc] = df[dc].apply(_safe_date)
    if "wind_code" in df.columns:
        df["wind_code"] = df["wind_code"].apply(_safe_normalize_wind_code)

    if dry_run:
        v = _validate_table(table_name, df)
        logger.info(
            "[dry-run] %s: %d 行待导入, invalid=%d",
            table_name,
            source_rows,
            v["invalid_rows"],
        )
        return {
            "source_rows": source_rows,
            "valid_rows": source_rows - v["invalid_rows"],
            "invalid_rows": v["invalid_rows"],
            "processed": 0,
            "failed": 0,
        }

    result = _batch_upsert(engine, table_name, df, _UNIQUE_KEYS[table_name])
    return {"source_rows": source_rows, "valid_rows": source_rows, **result}


def import_shareholders(
    engine: Engine, data_root: Path, ds_ver: str, *, dry_run: bool = False
) -> dict:
    """导入十大股东数据 (2/clean.xlsx)。source_record_id 用作 upsert 键。"""
    logger.info("=== Import top_shareholders (dry_run=%s) ===", dry_run)
    fp = data_root / "2" / "clean.xlsx"
    if not fp.exists():
        logger.warning("股东数据不存在: %s", fp)
        return {
            "source_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 1,
            "processed": 0,
            "failed": 0,
        }

    df = pd.read_excel(fp)
    source_rows = len(df)
    logger.info("读取 %d 行", source_rows)

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

    for dc in ["ann_dt", "s_holder_enddate", "report_period"]:
        if dc in df_out.columns:
            df_out[dc] = df_out[dc].apply(_safe_date)
    if "wind_code" in df_out.columns:
        df_out["wind_code"] = df_out["wind_code"].apply(
            lambda x: normalize_wind_code(str(x)) if pd.notna(x) else x
        )

    df_out["source_file"] = "2/clean.xlsx"
    df_out["source_row"] = df_out.index  # 0-based，与 source_record_id 行号对齐
    df_out["source_type"] = "competition_data"
    df_out["dataset_version"] = ds_ver
    df_out["revision_no"] = 1
    df_out["is_latest"] = 1
    df_out["ingested_at"] = NOW
    df_out["updated_at"] = NOW

    # 生成稳定的 source_record_id: 版本|文件名|源行号
    df_out["source_record_id"] = [
        f"{ds_ver}|2/clean.xlsx|{i}" for i in range(len(df_out))
    ]

    if dry_run:
        v = _validate_table("top_shareholders", df_out)
        logger.info(
            "[dry-run] top_shareholders: %d 行待导入, invalid=%d",
            source_rows,
            v["invalid_rows"],
        )
        return {
            "source_rows": source_rows,
            "valid_rows": source_rows - v["invalid_rows"],
            "invalid_rows": v["invalid_rows"],
            "processed": 0,
            "failed": 0,
        }

    result = _batch_upsert(
        engine, "top_shareholders", df_out, _UNIQUE_KEYS["top_shareholders"]
    )
    return {"source_rows": source_rows, "valid_rows": source_rows, **result}


def import_announcements(
    engine: Engine, data_root: Path, ds_ver: str, *, dry_run: bool = False
) -> dict:
    """导入公告元数据 (3/clean.xlsx)。仅导入标题/日期/fcode/链接，不下载 PDF。"""
    logger.info("=== Import announcements (dry_run=%s) ===", dry_run)
    fp = data_root / "3" / "clean.xlsx"
    if not fp.exists():
        logger.warning("公告数据不存在: %s", fp)
        return {
            "source_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 1,
            "processed": 0,
            "failed": 0,
        }

    df = pd.read_excel(fp)
    source_rows = len(df)
    logger.info("读取 %d 行", source_rows)

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

    if dry_run:
        v = _validate_table("announcements", df_out)
        logger.info(
            "[dry-run] announcements: %d 行待导入, invalid=%d",
            source_rows,
            v["invalid_rows"],
        )
        return {
            "source_rows": source_rows,
            "valid_rows": source_rows - v["invalid_rows"],
            "invalid_rows": v["invalid_rows"],
            "processed": 0,
            "failed": 0,
        }

    result = _batch_upsert(
        engine, "announcements", df_out, _UNIQUE_KEYS["announcements"]
    )
    return {"source_rows": source_rows, "valid_rows": source_rows, **result}


def import_research_reports(
    engine: Engine, data_root: Path, ds_ver: str, *, dry_run: bool = False
) -> dict:
    """导入研报数据 (5/rr_main_202605281537.csv)."""
    logger.info("=== Import research_reports (dry_run=%s) ===", dry_run)
    fp = data_root / "5" / "rr_main_202605281537.csv"
    if not fp.exists():
        logger.warning("研报数据不存在: %s", fp)
        return {
            "source_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 1,
            "processed": 0,
            "failed": 0,
        }

    df = pd.read_csv(fp, low_memory=False)
    source_rows = len(df)
    logger.info("读取 %d 行", source_rows)

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

    if dry_run:
        v = _validate_table("research_reports", df_out)
        logger.info(
            "[dry-run] research_reports: %d 行待导入, invalid=%d",
            source_rows,
            v["invalid_rows"],
        )
        return {
            "source_rows": source_rows,
            "valid_rows": source_rows - v["invalid_rows"],
            "invalid_rows": v["invalid_rows"],
            "processed": 0,
            "failed": 0,
        }

    result = _batch_upsert(
        engine, "research_reports", df_out, _UNIQUE_KEYS["research_reports"]
    )
    return {"source_rows": source_rows, "valid_rows": source_rows, **result}


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


# ── dry-run 校验规则 ──
_TABLE_VALIDATION: dict[str, dict] = {
    "companies": {"required": ["entity_id", "wind_code"], "max_len": {"sec_name": 255}},
    "balance_sheet": {"required": ["wind_code", "report_period", "statement_type"]},
    "income_statement": {"required": ["wind_code", "report_period", "statement_type"]},
    "cash_flow": {"required": ["wind_code", "report_period", "statement_type"]},
    "top_shareholders": {
        "required": ["wind_code", "s_holder_name"],
        "file": "2/clean.xlsx",
    },
    "announcements": {
        "required": ["object_id", "wind_code", "n_info_title"],
        "max_len": {"n_info_title": 512},
        "unique_key": "object_id",
        "file": "3/clean.xlsx",
    },
    "research_reports": {
        "required": ["report_id", "title"],
        "unique_key": "report_id",
        "file": "5/rr_main_202605281537.csv",
    },
}


def _validate_table(table: str, df: pd.DataFrame) -> dict:
    """校验单表，返回 {invalid_rows, issues}。"""
    rules = _TABLE_VALIDATION.get(table, {})
    if not rules:
        return {"invalid_rows": 0, "issues": []}

    invalid_mask = pd.Series(False, index=df.index)
    issues: list[str] = []

    for col in rules.get("required", []):
        if col not in df.columns:
            issues.append(f"缺少必填列: {col}")
            invalid_mask[:] = True
        else:
            nulls = df[col].isna()
            if nulls.any():
                issues.append(f"{col} 空值: {nulls.sum()} 行")
                invalid_mask |= nulls

    for col, max_len in rules.get("max_len", {}).items():
        if col in df.columns:
            too_long = df[col].apply(
                lambda x: len(str(x)) > max_len if pd.notna(x) else False
            )
            if too_long.any():
                issues.append(f"{col} 超长 (> {max_len}): {too_long.sum()} 行")
                invalid_mask |= too_long

    key_col = rules.get("unique_key")
    if key_col and key_col in df.columns:
        dup = df[key_col].duplicated()
        if dup.any():
            issues.append(f"{key_col} 重复: {dup.sum()} 行")
            invalid_mask |= dup

    return {
        "invalid_rows": int(invalid_mask.sum()),
        "issues": issues,
    }


def _dry_run_all(data_root: Path, ds_ver: str) -> int:
    """--dry-run：跑完整读取/映射/规范化/校验链路，只禁止写库。"""
    logger.info("=" * 60)
    logger.info("DRY RUN — 完整校验链路（不写入数据库）")
    logger.info("=" * 60)

    engine = _make_engine()
    total_source = 0
    total_invalid = 0
    all_stats: dict[str, dict] = {}

    try:
        # Step 1
        s = import_companies(engine, data_root, ds_ver, dry_run=True)
        all_stats["companies"] = s
        total_source += s["source_rows"]

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
            fp = data_root / "4" / csv_name
            if fp.exists():
                s = import_financial_table(
                    engine, fp, table, usecols, ds_ver, dry_run=True
                )
            else:
                s = {
                    "source_rows": 0,
                    "valid_rows": 0,
                    "invalid_rows": 1,
                    "processed": 0,
                    "failed": 0,
                }
                logger.warning("[dry-run] %s: 文件不存在", csv_name)
            all_stats[table] = s
            total_source += s["source_rows"]

        # Step 3-5
        for name, fn in [
            ("top_shareholders", import_shareholders),
            ("announcements", import_announcements),
            ("research_reports", import_research_reports),
        ]:
            s = fn(engine, data_root, ds_ver, dry_run=True)
            all_stats[name] = s
            total_source += s["source_rows"]

    finally:
        engine.dispose()

    # 汇总
    logger.info("=" * 60)
    logger.info("DRY RUN 汇总:")
    for table, s in all_stats.items():
        invalid = s.get("invalid_rows", 0)
        total_invalid += invalid
        logger.info(
            "  %-25s source=%d valid=%d invalid=%d",
            table,
            s["source_rows"],
            s["valid_rows"],
            invalid,
        )
    logger.info("  总计 source_rows: %d  invalid_rows: %d", total_source, total_invalid)
    logger.info("  验证: 数据库未被修改")
    return 0 if total_invalid == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MySQL 全量导入")
    parser.add_argument("--data-root", default="data/raw")
    parser.add_argument("--dataset-version", default="competition-2026")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true", help="完整校验链路，不写库")
    parser.add_argument("--verify-only", action="store_true", help="仅统计各表行数")
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

    # --dry-run：完整校验，不写库
    if args.dry_run:
        return _dry_run_all(data_root, args.dataset_version)

    # --verify-only
    if args.verify_only:
        engine = _make_engine()
        try:
            verify_counts(engine)
        finally:
            engine.dispose()
        return 0

    # ── 正式导入 ──
    engine = _make_engine()
    all_stats: dict[str, dict] = {}
    total_failed = 0

    try:
        # Step 1（P1-4：证券主表缺失/损坏 → ValueError → 退出码非零，失败关闭）
        all_stats["companies"] = import_companies(
            engine, data_root, args.dataset_version
        )
        total_failed += all_stats["companies"]["failed"] + all_stats["companies"].get(
            "invalid_rows", 0
        )
        if all_stats["companies"]["failed"] > 0:
            logger.error("companies 导入失败 %d 条", all_stats["companies"]["failed"])

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
            fp = data_root / "4" / csv_name
            s = import_financial_table(engine, fp, table, usecols, args.dataset_version)
            all_stats[table] = s
            total_failed += s["failed"] + s.get("invalid_rows", 0)

        # Step 3-5
        for name, fn in [
            ("top_shareholders", import_shareholders),
            ("announcements", import_announcements),
            ("research_reports", import_research_reports),
        ]:
            s = fn(engine, data_root, args.dataset_version)
            all_stats[name] = s
            total_failed += s["failed"] + s.get("invalid_rows", 0)

        # 验证
        counts = verify_counts(engine)
        total = sum(counts.values())

    finally:
        engine.dispose()

    # 汇总报告
    logger.info("=" * 60)
    logger.info("导入汇总:")
    for table, s in all_stats.items():
        logger.info(
            "  %-25s source=%d processed=%d failed=%d",
            table,
            s["source_rows"],
            s.get("processed", 0),
            s.get("failed", 0),
        )
    logger.info("  数据库总计: %d 条", total)

    if total_failed > 0:
        logger.error("存在 %d 条失败记录，退出码非 0", total_failed)
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        # P1-4：数据校验异常（如证券主表缺失/损坏）→ 明确错误信息 + 非零退出码
        logger.error("导入前置校验失败: %s", exc)
        sys.exit(1)
