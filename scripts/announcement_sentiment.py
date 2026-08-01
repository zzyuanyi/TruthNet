#!/usr/bin/env python
"""TruthNet — 公告情绪映射 (Phase B Task 4, 最终修正版).

使用共享的 fcode_taxonomy 模块，避免两份映射漂移。
--update-mysql 写入前校验 object_id 匹配数量。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.core.config import settings  # noqa: E402
from backend.app.domain.events.fcode_taxonomy import (  # noqa: E402
    SENTIMENT_MAP_VERSION,
    classify_sentiment,
)

logger = logging.getLogger(__name__)
NOW = datetime.now(timezone.utc)


def _make_engine() -> Engine:
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url, echo=False)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="公告情绪映射")
    p.add_argument("--data-file", help="公告 Excel/CSV 路径")
    p.add_argument("--dict-file", help="fcode 字典 CSV 路径")
    p.add_argument("--output", default="announcements_sentiment.csv")
    p.add_argument("--map-output", default="fcode_sentiment_map.json")
    p.add_argument(
        "--update-mysql",
        action="store_true",
        help="幂等更新 MySQL 中公告 sentiment/sentiment_method/updated_at",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--analyze-dict", action="store_true", help="仅分析字典覆盖情况")
    return p.parse_args()


def analyze_dict_coverage(dict_path: Path) -> dict:
    if not dict_path or not dict_path.exists():
        logger.warning("fcode 字典文件不可用: %s", dict_path)
        return {}

    suffix = dict_path.suffix.lower()
    if suffix == ".csv":
        df_dict = pd.read_csv(dict_path)
    elif suffix in (".xlsx", ".xls"):
        df_dict = pd.read_excel(dict_path)
    elif suffix == ".txt":
        # TSV 格式：fcode\tname，过滤仅保留 10 位数字 fcode 行
        df_dict = pd.read_csv(dict_path, sep="\t", header=None, names=["fcode", "name"])
        df_dict = df_dict[df_dict["fcode"].astype(str).str.match(r"^\d{10}$")].copy()
    else:
        logger.warning("不支持的字典文件格式: %s", suffix)
        return {}

    if "fcode" not in df_dict.columns:
        if list(df_dict.columns)[:2] != ["fcode", "name"]:
            df_dict.columns = ["fcode", "name"] + list(df_dict.columns[2:])

    fcode_col = "fcode"
    all_codes = set(str(c).strip() for c in df_dict[fcode_col].dropna().unique())
    from backend.app.domain.events.fcode_taxonomy import FCODE_SENTIMENT_MAP

    mapped = set(FCODE_SENTIMENT_MAP.keys())
    unknown_in_dict = all_codes - mapped
    return {
        "dict_total_categories": len(all_codes),
        "mapped_categories": len(mapped),
        "unknown_categories": sorted(unknown_in_dict),
        "unknown_count": len(unknown_in_dict),
    }


def update_mysql_sentiment(data_file: Path) -> dict:
    """从源文件读取公告，分类后批量回写 MySQL。"""
    logger.info("=== --update-mysql: 批量回写公告 sentiment ===")
    if not data_file.exists():
        logger.error("数据文件不存在: %s", data_file)
        return {"updated": 0, "failed": 0, "unmatched": 0, "error": "FILE_NOT_FOUND"}

    if data_file.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_file)
    else:
        df = pd.read_csv(data_file, low_memory=False)

    logger.info("读取 %d 条公告", len(df))

    fcode_col = None
    for col in ["n_info_fcode", "fcode"]:
        if col in df.columns:
            fcode_col = col
            break
    if fcode_col is None:
        logger.error("无法找到 fcode 列，可用列: %s", list(df.columns))
        return {"updated": 0, "failed": 0, "unmatched": len(df)}

    # 分类
    stats: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}
    updates: list[dict] = []
    source_ids = set()

    for _, row in df.iterrows():
        fcodes = str(row.get(fcode_col, ""))
        label, method, _confidence = classify_sentiment(fcodes)
        stats[label] = stats.get(label, 0) + 1

        object_id = str(row.get("object_id", ""))
        if (
            pd.isna(row.get("object_id"))
            or not object_id.strip()
            or object_id.strip().lower() == "nan"
        ):
            continue
        object_id = object_id.strip()
        updates.append(
            {
                "object_id": object_id,
                "sentiment": label,
                "sentiment_method": method,
            }
        )
        source_ids.add(object_id)

    if not source_ids:
        logger.error("所有公告 object_id 均为空，无法回写")
        return {
            "updated": 0,
            "failed": 0,
            "unmatched": len(df),
            "error": "NO_OBJECT_IDS",
        }

    # ── 写库前校验：object_id 匹配 ──
    engine = _make_engine()
    try:
        with engine.connect() as conn:
            # 检查数据库中有多少条公告
            db_count = conn.execute(
                text("SELECT COUNT(*) FROM announcements WHERE is_latest = 1")
            ).scalar()
            logger.info("数据库公告数: %d", db_count)

            if db_count == 0:
                logger.error("announcements 表为空，无法回写")
                return {
                    "updated": 0,
                    "failed": 0,
                    "unmatched": len(source_ids),
                    "stats": stats,
                }

            # 分批校验 object_id 匹配数
            id_list = list(source_ids)
            matched_count = 0
            for start in range(0, len(id_list), 1000):
                batch = id_list[start : start + 1000]
                cnt = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM announcements "
                        "WHERE object_id IN :ids AND is_latest = 1"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"ids": batch},
                ).scalar()
                matched_count += cnt

            if matched_count != len(source_ids):
                unmatched = len(source_ids) - matched_count
                logger.error(
                    "object_id 不匹配: source=%d matched=%d unmatched=%d",
                    len(source_ids),
                    matched_count,
                    unmatched,
                )
                return {
                    "updated": 0,
                    "failed": 0,
                    "unmatched": unmatched,
                    "stats": stats,
                }

            logger.info("object_id 全部匹配: %d / %d", matched_count, len(source_ids))

            # ── 批量 UPDATE ──
            update_sql = text(
                "UPDATE announcements SET sentiment = :sentiment, "
                "sentiment_method = :sentiment_method, updated_at = :now "
                "WHERE object_id = :object_id"
            )
            batch_size = 1000
            updated = 0
            failed = 0

            for start in range(0, len(updates), batch_size):
                batch = updates[start : start + batch_size]
                for u in batch:
                    u["now"] = NOW
                try:
                    conn.execute(update_sql, batch)
                    conn.commit()
                    updated += len(batch)
                except Exception:
                    conn.rollback()
                    failed += len(batch)
                    logger.exception(
                        "batch update failed: rows %d-%d", start, start + len(batch)
                    )

            # 验证：sentiment IS NULL 数量
            null_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM announcements WHERE sentiment IS NULL AND is_latest = 1"
                )
            ).scalar()
            logger.info("sentiment IS NULL 剩余: %d", null_count)

            # 分布
            for label in ["positive", "negative", "neutral", "unknown"]:
                cnt = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM announcements "
                        "WHERE sentiment = :label AND is_latest = 1"
                    ),
                    {"label": label},
                ).scalar()
                logger.info("  DB %s: %d", label, cnt)

    finally:
        engine.dispose()

    logger.info("回写完成: updated=%d failed=%d", updated, failed)
    return {"updated": updated, "failed": failed, "unmatched": 0, "stats": stats}


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    if args.dict_file:
        coverage = analyze_dict_coverage(Path(args.dict_file))
        print(json.dumps(coverage, indent=2, ensure_ascii=False, default=str))
        if args.analyze_dict:
            return 0

    if args.update_mysql:
        if not args.data_file:
            logger.error("--update-mysql 需要 --data-file")
            return 1
        result = update_mysql_sentiment(Path(args.data_file))
        if result.get("error"):
            logger.error("回写失败: %s", result["error"])
            return 1
        if result.get("unmatched", 0) > 0:
            logger.error("存在未匹配 object_id，退出码非 0")
            return 1
        return 0 if result["failed"] == 0 else 1

    # 本地 CSV 输出模式
    if not args.data_file:
        logger.error("需要 --data-file 或 --analyze-dict")
        return 1

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error("数据文件不存在: %s", data_path)
        return 1

    if data_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, low_memory=False)

    logger.info("读取 %d 条公告", len(df))

    fcode_col = None
    for col in ["n_info_fcode", "fcode", "announcement_fcode"]:
        if col in df.columns:
            fcode_col = col
            break
    if fcode_col is None:
        logger.error("无法找到 fcode 列，可用列: %s", list(df.columns))
        return 1

    results = []
    stats = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}

    for _, row in df.iterrows():
        fcodes = str(row.get(fcode_col, ""))
        label, method, confidence = classify_sentiment(fcodes)
        stats[label] = stats.get(label, 0) + 1
        results.append(
            {
                "object_id": row.get("object_id", ""),
                "wind_code": row.get("s_info_windcode", row.get("wind_code", "")),
                "ann_dt": row.get("ann_dt", ""),
                "fcode": fcodes,
                "title": row.get("n_info_title", row.get("title", "")),
                "sentiment": label,
                "sentiment_method": method,
                "sentiment_confidence": confidence,
                "sentiment_map_version": SENTIMENT_MAP_VERSION,
            }
        )

    df_out = pd.DataFrame(results)
    if not args.dry_run:
        df_out.to_csv(args.output, index=False, encoding="utf-8")
        logger.info("输出: %s (%d 条)", args.output, len(df_out))

    total = sum(stats.values())
    print(f"\n情绪分类统计 ({total} 条公告):")
    for label in ["positive", "negative", "neutral", "unknown"]:
        cnt = stats.get(label, 0)
        pct = cnt / total * 100 if total > 0 else 0
        print(f"  {label:10s}: {cnt:>6,d}  ({pct:5.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
