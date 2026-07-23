#!/usr/bin/env python
"""TruthNet — 竞赛财务数据 MySQL 导入流水线 (Phase B Task 1).

零硬编码 · 幂等导入 · 可恢复 · 批次安全 · staging 表 + ON DUPLICATE KEY UPDATE
所有配置来自 app.core.config.Settings + CLI 覆盖。无模块级 DB 连接。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from sqlalchemy import create_engine, text, inspect as sa_inspect  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from backend.app.core.config import settings as app_settings  # noqa: E402
from backend.app.infrastructure.graph.normalizer import (  # noqa: E402
    make_listed_company_entity_id,
    normalize_wind_code,
)

# ── Constants ──────────────────────────────────────────────────────────────

STATEMENT_TYPE_MAP = {"408001000": "consolidated", "408006000": "parent_company"}

# 需要日期标准化的列名
_DATE_COLS = frozenset(
    {
        "listing_date",
        "industry_as_of",
        "report_period",
        "ann_dt",
        "s_holder_enddate",
        "publish_date",
    }
)

# 各表的唯一键列表（用于 ON DUPLICATE KEY UPDATE）
_PK_COLS: dict[str, tuple[str, ...]] = {
    "companies": ("entity_id",),
    "announcements": ("object_id",),
    "research_reports": ("report_id",),
}

# 导入顺序
_TABLE_ORDER = (
    "companies",
    "balance_sheet",
    "income_statement",
    "cash_flow",
    "top_shareholders",
    "announcements",
    "research_reports",
)

logger = logging.getLogger("task1_import")


# ── CLI ────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TruthNet 竞赛数据 MySQL 导入")
    p.add_argument("--data-root", default=os.environ.get("DATA_ROOT") or "data/raw")
    p.add_argument(
        "--processed-dir",
        default=os.environ.get("PROCESSED_DATA_DIR") or "data/processed",
    )
    p.add_argument("--dataset-version", default=app_settings.DATASET_VERSION)
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--verify-only", action="store_true")
    p.add_argument(
        "--replace-dataset-version",
        action="store_true",
        help="标记旧版本 is_latest=0 后导入 (explicit opt-in)",
    )
    p.add_argument(
        "--tables", nargs="*", default=list(_TABLE_ORDER), choices=list(_TABLE_ORDER)
    )
    return p.parse_args()


# ── Engine ─────────────────────────────────────────────────────────────────


def _make_engine() -> Engine:
    url = (
        f"mysql+pymysql://{app_settings.MYSQL_USER}:{app_settings.MYSQL_PASSWORD}"
        f"@{app_settings.MYSQL_HOST}:{app_settings.MYSQL_PORT}"
        f"/{app_settings.MYSQL_DATABASE}?charset=utf8mb4"
    )
    return create_engine(url, echo=False, pool_pre_ping=True, pool_recycle=3600)


# ── Helpers ────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _norm_date(val: Any) -> str | None:
    if val is None or val == "":
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%d-%b-%Y",
        "%b %d, %Y",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _norm_statement_type(val: Any) -> str | None:
    if val is None:
        return None
    return STATEMENT_TYPE_MAP.get(str(val).strip(), str(val).strip())


def _src_record_id(table: str, row: dict[str, Any], idx: int) -> str:
    wc = row.get("wind_code", "")
    rp = row.get("report_period", "")
    st = row.get("statement_type", "")
    if table == "companies":
        return f"{table}:{wc}" if wc else f"{table}:row:{idx}"
    if table in ("balance_sheet", "income_statement", "cash_flow"):
        return f"{table}:{wc}:{rp}:{st}"
    if table == "announcements":
        return row.get("object_id") or f"{table}:row:{idx}"
    if table == "research_reports":
        return row.get("report_id") or f"{table}:row:{idx}"
    if table == "top_shareholders":
        sn = row.get("s_holder_name", "")
        sq = row.get("s_holder_sequence", idx)
        return f"{table}:{wc}:{sn}:{sq}"
    return f"{table}:row:{idx}"


def _normalize_row(
    row: dict[str, Any],
    table: str,
    source_file: str,
    row_idx: int,
    dataset_version: str,
) -> dict[str, Any]:
    """规范化单行：日期、Wind Code、entity_id、statement_type、系统字段。"""
    out: dict[str, Any] = {}
    for k, v in row.items():
        out[k] = _norm_date(v) if k in _DATE_COLS else v

    # Wind Code
    if out.get("wind_code"):
        try:
            out["wind_code"] = normalize_wind_code(str(out["wind_code"]))
        except ValueError:
            pass

    # companies 特殊处理
    if table == "companies":
        wc = out.get("wind_code", "")
        try:
            out["entity_id"] = make_listed_company_entity_id(wc)
        except ValueError:
            out["entity_id"] = f"company_{wc.replace('.', '_')}"
        if "." in wc and not out.get("exchange_code"):
            em = {"SH": "XSHG", "SZ": "XSHE", "BJ": "BJ"}
            out["exchange_code"] = em.get(wc.split(".")[1], wc.split(".")[1])

    # statement_type
    if "statement_type" in out:
        out["statement_type"] = _norm_statement_type(out["statement_type"])

    # 系统字段
    now = _utcnow()
    out["source_record_id"] = _src_record_id(table, out, row_idx)
    out["source_file"] = source_file
    out["source_row"] = row_idx + 1
    out["source_type"] = "competition-csv"
    out["dataset_version"] = dataset_version
    out["revision_no"] = 1
    out["is_latest"] = True
    out["ingested_at"] = now
    out["updated_at"] = now
    out["checksum"] = _sha256(out)
    out["quality_flags"] = {}
    return out


# ── File I/O ───────────────────────────────────────────────────────────────


def _discover_files(data_root: Path, version: str) -> dict[str, list[Path]]:
    base = data_root / version
    files: dict[str, list[Path]] = {t: [] for t in _TABLE_ORDER}
    if not base.exists():
        return files
    for t in _TABLE_ORDER:
        for ext in (".json", ".jsonl", ".csv"):
            p = base / f"{t}{ext}"
            if p.exists():
                files[t].append(p)
                break
    return files


def _read_rows(fp: Path) -> list[dict[str, Any]]:
    suf = fp.suffix.lower()
    if suf == ".json":
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    if suf == ".jsonl":
        rows = []
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return rows
    if suf == ".csv":
        try:
            import pandas as pd
        except ImportError:
            logger.error("读取 CSV 需要 pandas: pip install pandas")
            return []
        df = pd.read_csv(fp, encoding="utf-8")
        return df.where(pd.notna(df), None).to_dict(orient="records")
    return []


# ── Staging + Upsert ───────────────────────────────────────────────────────


def _stg_name(table: str) -> str:
    return f"_stg_{table}"


def _col_list(cols: list[str]) -> str:
    return ", ".join(f"`{c}`" for c in cols)


def _ph_list(cols: list[str]) -> str:
    return ", ".join(f":{c}" for c in cols)


def _on_dup(cols: list[str], pk: tuple[str, ...]) -> str:
    updates = [f"`{c}` = VALUES(`{c}`)" for c in cols if c not in pk]
    return "ON DUPLICATE KEY UPDATE " + ", ".join(updates) if updates else ""


def _batch_upsert(
    engine: Engine,
    table: str,
    rows: list[dict[str, Any]],
    batch_size: int,
    pk: tuple[str, ...],
) -> tuple[int, int]:
    """staging 表批量 upsert。返回 (成功, 错误)。"""
    if not rows:
        return 0, 0

    # 只保留目标表中存在的列（丢弃未知列）
    insp = sa_inspect(engine)
    existing = {c["name"]: c for c in insp.get_columns(table)}
    cols = [c for c in rows[0].keys() if c in existing]
    rows = [{k: v for k, v in r.items() if k in cols} for r in rows]

    stg = _stg_name(table)
    col_n = _col_list(cols)
    ph_n = _ph_list(cols)
    ins = f"INSERT INTO `{stg}` ({col_n}) VALUES ({ph_n})"
    mrg = f"INSERT INTO `{table}` ({col_n}) SELECT {col_n} FROM `{stg}` {_on_dup(cols, pk)}"

    # 创建 staging 表（从目标表复制 schema）
    col_defs = []
    for c in cols:
        t = str(existing[c]["type"])
        n = "NULL" if existing[c].get("nullable", True) else "NOT NULL"
        col_defs.append(f"`{c}` {t} {n}")
    ddl = f"CREATE TABLE IF NOT EXISTS `{stg}` ({', '.join(col_defs)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{stg}`"))
        conn.execute(text(ddl))

    # 批量写入 staging
    ok, err = 0, 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            with engine.begin() as conn:
                conn.execute(text(ins), batch)
        except Exception as e:
            logger.error(f"staging batch {i // batch_size} 失败: {e}")
            err += len(batch)

    # 合并
    try:
        with engine.begin() as conn:
            result = conn.execute(text(mrg))
            ok = result.rowcount
    except Exception as e:
        logger.error(f"合并失败: {e}")
        # 逐行回退
        up_sql = f"INSERT INTO `{table}` ({col_n}) VALUES ({ph_n}) {_on_dup(cols, pk)}"
        for row in rows:
            try:
                with engine.begin() as conn:
                    conn.execute(text(up_sql), row)
                ok += 1
            except Exception:
                pass
        err += max(0, len(rows) - ok)

    # 清理
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{stg}`"))
    return ok, err


# ── Manifest ───────────────────────────────────────────────────────────────


def _manifest_path(processed_dir: Path) -> Path:
    return processed_dir / "task1_resume_manifest.json"


def _load_manifest(processed_dir: Path) -> dict[str, Any]:
    p = _manifest_path(processed_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_manifest(m: dict[str, Any], processed_dir: Path) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(processed_dir).write_text(
        json.dumps(m, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
        newline="\n",
    )


# ── Mark old ───────────────────────────────────────────────────────────────


def _mark_old(engine: Engine, dataset_version: str, tables: list[str]) -> None:
    for t in tables:
        with engine.begin() as conn:
            r = conn.execute(
                text(
                    f"UPDATE `{t}` SET is_latest=0, updated_at=:now "
                    f"WHERE dataset_version=:ver AND is_latest=1"
                ),
                {"now": _utcnow(), "ver": dataset_version},
            )
            if r.rowcount:
                logger.info(f"标记 {t}: {r.rowcount} 行 is_latest=0")


# ── Verify only ────────────────────────────────────────────────────────────


def _verify(
    engine: Engine, args: argparse.Namespace, files: dict[str, list[Path]]
) -> int:
    insp = sa_inspect(engine)
    print("=" * 60 + "\n  VERIFY-ONLY — 不执行导入\n" + "=" * 60)
    total = 0
    for t in args.tables:
        fl = files.get(t, [])
        if not fl:
            print(f"\n  [{t}] 未发现文件")
            continue
        try:
            db_cols = {c["name"] for c in insp.get_columns(t)}
        except Exception:
            print(f"\n  [{t}] 表不存在于数据库中，跳过 schema 检查")
            continue
        for fp in fl:
            rows = _read_rows(fp)
            total += len(rows)
            src_cols = set()
            for r in rows:
                src_cols.update(r.keys())
            print(f"\n  [{t}] {fp.name}: {len(rows)} 行, {len(src_cols)} 源列")
            overlap = src_cols & db_cols
            missing = (
                db_cols
                - src_cols
                - {
                    "id",
                    "source_record_id",
                    "source_file",
                    "source_row",
                    "source_type",
                    "dataset_version",
                    "revision_no",
                    "is_latest",
                    "ingested_at",
                    "updated_at",
                    "checksum",
                    "quality_flags",
                    "entity_id",
                    "holder_entity_id",
                    "entity_match_confidence",
                }
            )
            extra = src_cols - db_cols
            print(f"    匹配 {len(overlap)}/{len(db_cols)} 列")
            if missing:
                print(f"    缺失: {', '.join(sorted(missing))}")
            if extra:
                print(f"    多余: {', '.join(sorted(extra))}")
    print(f"\n  总计 {total} 行\n" + "=" * 60)
    return 0


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    data_root = Path(args.data_root).resolve()
    processed_dir = Path(args.processed_dir).resolve()
    tables = args.tables

    logger.info(
        f"dataset={args.dataset_version} root={data_root} batch={args.batch_size}"
    )

    files = _discover_files(data_root, args.dataset_version)
    if not any(v for v in files.values()):
        logger.warning("未发现数据文件")
        return 1

    engine = _make_engine()
    logger.info(
        f"DB: {app_settings.MYSQL_HOST}:{app_settings.MYSQL_PORT}/{app_settings.MYSQL_DATABASE}"
    )

    if args.verify_only:
        return _verify(engine, args, files)

    manifest = _load_manifest(processed_dir) if args.resume else {}

    if args.replace_dataset_version:
        if args.dry_run:
            logger.info("[dry-run] 将标记旧版本 is_latest=0")
        else:
            _mark_old(engine, args.dataset_version, tables)

    stats: dict[str, dict[str, int]] = {}
    for table_name in tables:
        if manifest.get(table_name, {}).get("complete"):
            logger.info(f"跳过: {table_name} (已完成)")
            continue

        fl = files.get(table_name, [])
        if not fl:
            logger.info(f"跳过: {table_name} (无文件)")
            continue

        pk = _PK_COLS.get(table_name, ("source_record_id",))
        total_ok, total_err = 0, 0

        for fp in fl:
            logger.info(f"{table_name} ← {fp.name}")
            raw = _read_rows(fp)
            normalized = []
            for i, row in enumerate(raw):
                try:
                    normalized.append(
                        _normalize_row(
                            row, table_name, fp.name, i, args.dataset_version
                        )
                    )
                except Exception as e:
                    logger.warning(f"行 {i} 规范化失败: {e}")
                    total_err += 1

            if args.dry_run:
                logger.info(f"[dry-run] {table_name}: {len(normalized)} 行")
                total_ok += len(normalized)
                continue

            ok, err = _batch_upsert(engine, table_name, normalized, args.batch_size, pk)
            total_ok += ok
            total_err += err
            logger.info(f"  → 成功 {ok}, 错误 {err}")

        stats[table_name] = {"inserted": total_ok, "errors": total_err}
        manifest[table_name] = {
            "complete": (total_err == 0) or args.dry_run,
            "inserted": total_ok,
            "errors": total_err,
            "dataset_version": args.dataset_version,
            "updated_at": _utcnow().isoformat(),
        }
        if not args.dry_run:
            _save_manifest(manifest, processed_dir)

    # 汇总
    print("\n" + "=" * 60 + "\n  导入汇总\n" + "=" * 60)
    gi, ge = 0, 0
    for t, s in stats.items():
        print(f"  [{t}] 插入: {s['inserted']}, 错误: {s['errors']}")
        gi += s["inserted"]
        ge += s["errors"]
    print(f"  {'─' * 20}\n  总计: {gi} 插入, {ge} 错误\n" + "=" * 60)
    if args.dry_run:
        logger.info("dry-run 完成")
    return 0 if ge == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
