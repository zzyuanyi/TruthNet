#!/usr/bin/env python
"""研报评级拐点构建 CLI — Phase C 数据任务 5.

从 research_reports 真实字段（rating_org / rating_change / org_name / publish_date）
规范化评级并写入 rating_changes 表。

用法:
    python scripts/build_rating_changes.py --dry-run
    python scripts/build_rating_changes.py
    python scripts/build_rating_changes.py --verify-only

约束:
    - 只写高置信度解析结果（confidence >= MIN_CONFIDENCE）；低置信度跳过并统计
    - 保留原始值，同时映射有序等级
    - 确定性 ID、幂等（同键 upsert）
    - 康美等无真实研报的公司 → 无记录，不伪造
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.domain.events.rating_inflection import detect_inflections  # noqa: E402
from backend.app.domain.events.rating_normalizer import (  # noqa: E402
    MIN_CONFIDENCE,
    normalize_rating,
)
from backend.app.domain.provenance.id_factory import (  # noqa: E402
    NS_REPORT,
    make_evidence_id,
)

_DATE_RE = re.compile(r"(\d{4})[-/]?(\d{2})[-/]?\d{2}")
# 标准 A 股 Wind 代码（600518.SH / 000001.SZ / 920571.BJ）
_WIND_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def _quarter_of(publish_date: str | None) -> str | None:
    """'2026-03-15' / '20260315' → '2026Q1'."""
    if not publish_date:
        return None
    m = _DATE_RE.search(str(publish_date))
    if not m:
        return None
    year, month = m.group(1), int(m.group(2))
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def _rc_id(
    wind_code: str, quarter: str, institution: str, report_id: str | None
) -> str:
    raw = f"rc|{wind_code}|{quarter}|{institution}|{report_id or ''}"
    return f"rc_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _engine():
    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
    else:
        url = f"sqlite:///{settings.SQLITE_PATH}"
    return create_engine(url, pool_pre_ping=True)


def _table_exists(engine, table: str) -> bool:
    with engine.connect() as conn:
        if settings.SQL_BACKEND == "mysql":
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :t"
                ),
                {"t": table},
            ).scalar()
        else:
            row = conn.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE name = :t"),
                {"t": table},
            ).scalar()
    return bool(row)


def build_records(engine) -> tuple[list[dict], dict[str, int]]:
    """从 research_reports 构建规范化评级变更记录。"""
    stats = {
        "total": 0,
        "low_confidence_skipped": 0,
        "no_direction": 0,
        "orphan_company_skipped": 0,
        "written": 0,
    }

    with engine.connect() as conn:
        # companies 存在性 Gate：研报代码不在 companies 时跳过（防孤儿污染 Lookup）
        valid_codes = {
            r[0]
            for r in conn.execute(text("SELECT wind_code FROM companies")).fetchall()
        }
        rows = (
            conn.execute(
                text(
                    "SELECT wind_code, org_name, title, publish_date, rating_org, "
                    "rating_change, report_id, source_uri FROM research_reports "
                    "WHERE rating_org IS NOT NULL AND rating_org != '' "
                    "ORDER BY wind_code ASC, publish_date ASC"
                )
            )
            .mappings()
            .fetchall()
        )

    stats["total"] = len(rows)

    # 按 (wind_code, institution) 分机构，publish_date 升序，用于提取 previous_rating
    by_inst: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        wc = str(r["wind_code"] or "").strip()
        if not _WIND_CODE_RE.match(wc):
            continue  # 过滤脏代码（如 0000OR）
        inst = (r["org_name"] or "未知机构").strip()
        by_inst.setdefault((wc, inst), []).append(dict(r))

    records_out: list[dict] = []
    for (wind_code, inst), seq in by_inst.items():
        if wind_code not in valid_codes:
            stats["orphan_company_skipped"] += 1
            continue  # companies 不存在 → 跳过，不写孤儿评级
        prev_rating: str | None = None
        prev_level: int | None = None
        for rec in seq:
            norm = normalize_rating(rec.get("rating_org"), rec.get("rating_change"))
            # direction 推断：rating_change 字段优先；否则与上一份评级比较
            direction = norm.direction
            if direction is None and prev_level is not None and norm.level is not None:
                if norm.level < prev_level:
                    direction = "down"
                elif norm.level > prev_level:
                    direction = "up"
                else:
                    direction = "keep"

            quarter = _quarter_of(rec.get("publish_date"))
            if direction not in ("down", "up") or quarter is None:
                stats["no_direction"] += 1
                prev_rating, prev_level = rec.get("rating_org"), norm.level
                continue
            if norm.confidence < MIN_CONFIDENCE:
                stats["low_confidence_skipped"] += 1
                prev_rating, prev_level = rec.get("rating_org"), norm.level
                continue

            # 报告粒度 Evidence ID（确定性；report_id 缺失时回退组合键防御）
            # 实际使用的 source_record_id 随记录保存，ID 生成与 EvidenceRef 写入复用同一值
            src_record_id = str(rec.get("report_id") or "") or (
                f"{wind_code}|{quarter}|{inst}|{rec.get('publish_date') or ''}"
            )
            evidence_id = make_evidence_id(
                source_namespace=NS_REPORT,
                source_type="research_report",
                source_record_id=src_record_id,
                field_path="rating_change",
                period=str(rec.get("publish_date") or quarter),
                dataset_version=settings.DATASET_VERSION or "competition-2026",
                company_code=wind_code,
            )
            records_out.append(
                {
                    "rating_change_id": _rc_id(
                        wind_code, quarter, inst, rec.get("report_id")
                    ),
                    "wind_code": wind_code,
                    "quarter": quarter,
                    "institution": inst,
                    "previous_rating": prev_rating,
                    "current_rating": rec.get("rating_org"),
                    "direction": direction,
                    "report_id": rec.get("report_id"),
                    "published_at": str(rec.get("publish_date"))
                    if rec.get("publish_date")
                    else None,
                    "confidence": round(norm.confidence, 3),
                    "evidence_id": evidence_id,
                    "dataset_version": settings.DATASET_VERSION or "competition-2026",
                    "title": str(rec.get("title") or "")[:200],
                    "source_uri": str(rec.get("source_uri") or ""),
                    "_src_record_id": src_record_id,
                    "_change_value": f"{prev_rating or ''}→{rec.get('rating_org') or ''}",
                }
            )
            stats["written"] += 1
            prev_rating, prev_level = rec.get("rating_org"), norm.level

    return records_out, stats


def _verify(engine, dataset_version: str) -> int:
    if not _table_exists(engine, "rating_changes"):
        print("ERROR: rating_changes 表不存在", file=sys.stderr)
        return 2
    problems: list[str] = []
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM rating_changes WHERE dataset_version = :d"),
            {"d": dataset_version},
        ).scalar()
        rows = conn.execute(
            text(
                "SELECT direction, COUNT(*) AS cnt FROM rating_changes "
                "WHERE dataset_version = :d GROUP BY direction"
            ),
            {"d": dataset_version},
        ).fetchall()
        # 新契约验证：evidence_id 非空 / 无重复 / 无孤儿 / evidence_refs 无缺失 / 字段正确
        nonnull_ev = conn.execute(
            text(
                "SELECT COUNT(*) FROM rating_changes WHERE dataset_version = :d "
                "AND (evidence_id IS NULL OR evidence_id = '')"
            ),
            {"d": dataset_version},
        ).scalar()
        dup_ev = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT evidence_id FROM rating_changes WHERE dataset_version = :d "
                "  GROUP BY evidence_id HAVING COUNT(*) > 1"
                ") t"
            ),
            {"d": dataset_version},
        ).scalar()
        orphan = conn.execute(
            text(
                "SELECT COUNT(*) FROM rating_changes rc "
                "LEFT JOIN companies co ON co.wind_code = rc.wind_code "
                "WHERE rc.dataset_version = :d AND co.wind_code IS NULL"
            ),
            {"d": dataset_version},
        ).scalar()
        missing_refs = conn.execute(
            text(
                "SELECT COUNT(*) FROM rating_changes rc "
                "LEFT JOIN evidence_refs er ON er.evidence_id = rc.evidence_id "
                "WHERE rc.dataset_version = :d AND er.evidence_id IS NULL"
            ),
            {"d": dataset_version},
        ).scalar()
        # NULL 不参与 <> 比较（NULL <> x 恒不成立），须 COALESCE 后才能计入异常
        bad_fields = conn.execute(
            text(
                "SELECT COUNT(*) FROM rating_changes rc "
                "JOIN evidence_refs er ON er.evidence_id = rc.evidence_id "
                "WHERE rc.dataset_version = :d AND ("
                "  COALESCE(er.source_type, '') <> 'research_report' OR "
                "  COALESCE(er.source_table, '') <> 'research_reports' OR "
                "  COALESCE(er.field_path, '') <> 'rating_change')"
            ),
            {"d": dataset_version},
        ).scalar()
    print(f"verify-only: 共 {total} 条 (dataset={dataset_version})")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")
    checks = [
        ("evidence_id 全非空", nonnull_ev == 0, f"空值 {nonnull_ev}"),
        ("Evidence ID 无重复", dup_ev == 0, f"重复组 {dup_ev}"),
        ("公司孤儿为 0", orphan == 0, f"孤儿 {orphan}"),
        ("evidence_refs 无缺失", missing_refs == 0, f"缺失 {missing_refs}"),
        (
            "source_type/table/field_path 正确",
            bad_fields == 0,
            f"异常 {bad_fields}",
        ),
    ]
    failed = 0
    for name, ok, detail in checks:
        # ASCII 输出：Windows 默认 GBK 终端下 emoji 会 UnicodeEncodeError
        print(f"  [{'OK' if ok else 'FAIL'}] {name} - {detail}")
        if not ok:
            failed += 1
            problems.append(name)
    if problems:
        print(f"VERIFY: FAIL ({failed} 项) -> {', '.join(problems)}")
        return 1
    print("VERIFY: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="研报评级拐点构建")
    parser.add_argument("--dry-run", action="store_true", help="只计算打印，不写库")
    parser.add_argument("--verify-only", action="store_true", help="只校验已写库数据")
    args = parser.parse_args()

    engine = _engine()
    dataset_version = settings.DATASET_VERSION or "competition-2026"

    if args.verify_only:
        return _verify(engine, dataset_version)

    records, stats = build_records(engine)
    print(
        f"统计: 总研报 {stats['total']}, 低置信度跳过 {stats['low_confidence_skipped']}, "
        f"无方向/无季度 {stats['no_direction']}, "
        f"孤儿跳过 {stats['orphan_company_skipped']}, 可写 {stats['written']}"
    )

    if args.dry_run:
        print("\n=== DRY-RUN 抽样（前 15 条方向变更）===")
        for r in records[:15]:
            print(
                f"  {r['wind_code']} {r['quarter']} {r['institution']}: "
                f"{r['previous_rating']}→{r['current_rating']} ({r['direction']}, conf={r['confidence']})"
            )
        # 拐点预览
        from backend.app.domain.events.rating_inflection import RatingChangeRecord

        recs = [
            RatingChangeRecord(
                wind_code=r["wind_code"],
                quarter=r["quarter"],
                institution=r["institution"],
                direction=r["direction"],
            )
            for r in records
        ]
        infs = detect_inflections(recs)
        print(
            f"\n拐点预览: {len(infs)} 个（orange {sum(1 for i in infs if i.severity=='orange')} 个）"
        )
        print("dry-run 完成，未写库。")
        return 0

    if not _table_exists(engine, "rating_changes"):
        print(
            "ERROR: rating_changes 表不存在，请先运行 alembic migration",
            file=sys.stderr,
        )
        return 2

    cols = [
        "rating_change_id",
        "wind_code",
        "quarter",
        "institution",
        "previous_rating",
        "current_rating",
        "direction",
        "report_id",
        "published_at",
        "confidence",
        "evidence_id",
        "dataset_version",
    ]
    with engine.begin() as conn:
        # 幂等：先删同 dataset_version 旧记录
        del_result = conn.execute(
            text("DELETE FROM rating_changes WHERE dataset_version = :d"),
            {"d": dataset_version},
        )
        print(f"已清除旧记录: {del_result.rowcount} 行")
        if records:
            insert_sql = text(
                "INSERT INTO rating_changes ("
                + ", ".join(cols)
                + ") VALUES ("
                + ", ".join(f":{c}" for c in cols)
                + ")"
            )
            conn.execute(insert_sql, records)
            # 同步写 evidence_refs（同一事务；批处理证据无会话 → turn_id/trace_id 保持 NULL）
            evidence_rows = [
                {
                    "eid": r["evidence_id"],
                    "srid": r["_src_record_id"],
                    "cc": r["wind_code"],
                    "per": str(r["published_at"] or ""),
                    "val": r["_change_value"],
                    "title": r["title"],
                    "uri": r["source_uri"],
                    "dv": dataset_version,
                }
                for r in records
            ]
            inserted_ev = 0
            for ev in evidence_rows:
                existing = conn.execute(
                    text(
                        "SELECT 1 FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
                    ),
                    {"eid": ev["eid"]},
                ).first()
                if existing is not None:
                    continue  # 幂等复用（内容一致性由 digest 保证）
                conn.execute(
                    text(
                        "INSERT INTO evidence_refs "
                        "(evidence_id, source_type, source_record_id, company_code, "
                        " field_path, period, value, unit, statement_scope, "
                        " source_title, source_uri, dataset_version, retrieved_at, "
                        " turn_id, trace_id, module, source_table) "
                        "VALUES (:eid, 'research_report', :srid, :cc, 'rating_change', "
                        " :per, :val, NULL, NULL, :title, :uri, :dv, CURRENT_TIMESTAMP, "
                        " NULL, NULL, 'events', 'research_reports')"
                    ),
                    ev,
                )
                inserted_ev += 1
            if inserted_ev:
                print(f"evidence_refs 同步写入: {inserted_ev} 条（已存在跳过）")
    print(f"写入完成: {len(records)} 条 (dataset={dataset_version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
