#!/usr/bin/env python
"""真实事件聚类构建 CLI — Phase C 数据任务 4.

从 MySQL announcements 真实公告生成事件簇（JSONL，供 import_event_clusters.py 导入）。
聚类方法：semantic_rule_fcode_timewindow_v1（无网络、无 LLM）：
  1. 公告清洗去重（object_id）
  2. fcode 一级分类（fcode_taxonomy 29 类）
  3. 同类内按 30 天时间窗聚类
  4. topic = 类别标签；sentiment 来源 = 公告情绪（fcode 映射/已存 sentiment）
  5. evidence_ids = make_evidence_id（与后端统一 ID Factory，可 Lookup 查询）
  6. 事件簇 ID 确定性（make_event_cluster_id，同输入重跑不变）

用法:
    python scripts/build_event_clusters.py --company 603377.SH
    python scripts/build_event_clusters.py --top-n 10 --min-announcements 10
    python scripts/build_event_clusters.py --company 603377.SH --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.domain.events.clustering import (  # noqa: E402
    cluster_announcements,
    dedup_announcements,
    first_fcode,
    majority_sentiment,
)
from backend.app.domain.events.contracts import (  # noqa: E402
    EventClusterRecord,
    EventSourceRef,
    make_event_cluster_id,
)
from backend.app.domain.events.fcode_taxonomy import (  # noqa: E402
    fcode_category_label,
)
from backend.app.domain.provenance.id_factory import (  # noqa: E402
    NS_ANNOUNCEMENT,
    make_evidence_id,
)

CLUSTER_VERSION = "semantic_fcode_tw_v1"
MIN_ANNOUNCEMENTS = 10


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


def _company_entity_id(engine, wind_code: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT entity_id FROM companies WHERE wind_code = :c"),
            {"c": wind_code},
        ).fetchone()
    return row[0] if row else None


def _fetch_announcements(engine, wind_code: str) -> list[dict]:
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT object_id, ann_dt, n_info_title, n_info_fcode, sentiment "
                    "FROM announcements WHERE wind_code = :c AND is_latest = 1 "
                    "ORDER BY ann_dt ASC"
                ),
                {"c": wind_code},
            )
            .mappings()
            .fetchall()
        )
    return dedup_announcements([dict(r) for r in rows])


def build_clusters_for_company(
    engine, wind_code: str, dataset_version: str
) -> list[dict]:
    """为单家公司构建事件簇（JSONL 行 dict 列表）。"""
    entity_id = _company_entity_id(engine, wind_code)
    if entity_id is None:
        print(f"  [SKIP] {wind_code}: companies 表无此公司", file=sys.stderr)
        return []
    anns = _fetch_announcements(engine, wind_code)
    if len(anns) < MIN_ANNOUNCEMENTS:
        print(
            f"  [SKIP] {wind_code}: 公告 {len(anns)} 条 < {MIN_ANNOUNCEMENTS}",
            file=sys.stderr,
        )
        return []

    raw_clusters = cluster_announcements(anns)
    rows: list[dict] = []
    for anns_in_cluster in raw_clusters:
        if len(anns_in_cluster) < 1:
            continue
        primary_fcode = first_fcode(anns_in_cluster[0])
        category = fcode_category_label(primary_fcode)
        start = min(str(a.get("ann_dt")) for a in anns_in_cluster)
        end = max(str(a.get("ann_dt")) for a in anns_in_cluster)
        try:
            start_d = date.fromisoformat(start)
            end_d = date.fromisoformat(end)
        except ValueError:
            continue

        sources = []
        evidence_ids = []
        for idx, a in enumerate(anns_in_cluster):
            oid = str(a["object_id"])
            try:
                pub = date.fromisoformat(str(a.get("ann_dt")))
            except (ValueError, TypeError):
                pub = start_d
            ev_id = make_evidence_id(
                source_namespace=NS_ANNOUNCEMENT,
                source_type="announcement",
                source_record_id=oid,
                period=str(a.get("ann_dt") or ""),
                dataset_version=dataset_version,
                company_code=wind_code,
            )
            sources.append(
                EventSourceRef(
                    source_id=f"src_{idx}",
                    source_type="announcement",
                    source_record_id=oid,
                    title=str(a.get("n_info_title") or "")[:120],
                    published_at=pub,
                    source_uri=None,
                    fcode=str(a.get("n_info_fcode") or ""),
                )
            )
            evidence_ids.append(ev_id)

        sentiment, score = majority_sentiment(anns_in_cluster)
        topic = (
            f"{category}"
            if len(raw_clusters) == 1
            else f"{category}（{start_d.month:02d}-{end_d.month:02d}）"
        )
        record = EventClusterRecord(
            event_cluster_id=make_event_cluster_id(
                wind_code,
                topic,
                start_d,
                end_d,
                [s.source_record_id for s in sources],
                CLUSTER_VERSION,
            ),
            entity_id=entity_id,
            wind_code=wind_code,
            topic=topic,
            summary=f"{category} 相关公告 {len(sources)} 条，"
            f"时间跨度 {start_d.isoformat()} ~ {end_d.isoformat()}",
            start_date=start_d,
            end_date=end_d,
            event_count=len(sources),
            sentiment=sentiment,
            sentiment_score=score,
            sources=sources,
            evidence_ids=evidence_ids,
            cluster_method="semantic_rule_fcode_timewindow_v1",
            cluster_version=CLUSTER_VERSION,
            dataset_version=dataset_version,
            quality_flags=[],
            created_at=datetime.now(timezone.utc),
        )
        rows.append(record.model_dump(mode="json"))
    return rows


def _announcement_counts(engine) -> list[tuple[str, int]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wind_code, COUNT(*) AS cnt FROM announcements "
                "WHERE is_latest = 1 GROUP BY wind_code "
                "HAVING cnt >= :m ORDER BY cnt DESC"
            ),
            {"m": MIN_ANNOUNCEMENTS},
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="真实事件聚类构建")
    parser.add_argument("--company", default=None, help="指定公司 wind_code")
    parser.add_argument("--top-n", type=int, default=0, help="公告最多的 N 家公司")
    parser.add_argument("--min-announcements", type=int, default=MIN_ANNOUNCEMENTS)
    parser.add_argument("--dry-run", action="store_true", help="只打印不落盘")
    parser.add_argument(
        "--outdir", default="data/processed/event_clusters", help="JSONL 输出目录"
    )
    args = parser.parse_args()

    engine = _engine()
    dataset_version = settings.DATASET_VERSION or "competition-2026"

    if args.company:
        targets = [(args.company, None)]
    else:
        counts = _announcement_counts(engine)
        if args.top_n > 0:
            counts = counts[: args.top_n]
        targets = counts
        print(f"覆盖公司（公告>={args.min_announcements}）: {len(counts)} 家")

    out_dir = Path(args.outdir)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    total_clusters = 0
    for wind_code, cnt in targets:
        print(f"处理 {wind_code}（公告 {cnt if cnt else '?'} 条）...")
        rows = build_clusters_for_company(engine, wind_code, dataset_version)
        if not rows:
            continue
        total_clusters += len(rows)
        print(f"  -> 事件簇 {len(rows)} 个")
        if not args.dry_run:
            out_file = out_dir / f"{wind_code}_event_clusters.jsonl"
            with out_file.open("w", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  已写入 {out_file}")

    print(f"\n总计: {total_clusters} 个事件簇")
    if total_clusters == 0:
        print("无符合条件公司（公告数不足），请确认公告数据已导入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
