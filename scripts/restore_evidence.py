#!/usr/bin/env python
"""证据恢复脚本 — 幂等重建全局证据 + 完整性检查.

背景（2026-08-04）：会话清理按 turn 删除 evidence_refs 时误删了
rating_changes / event_cluster_sources 引用的全局证据。evidence 是全局资产
（评级/事件簇证据不依附会话）；主数据表及其 evidence_id 完整保留，可从此类
现有表幂等重建 evidence_refs。

同时处理：有效证据的无效 turn_id → 置 NULL（指向已删除轮次的引用）。

用法:
    python scripts/restore_evidence.py --dry-run   # 预检（默认，不写库）
    python scripts/restore_evidence.py --confirm   # 单事务执行
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 修复 Windows GBK 控制台 Unicode 输出问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import create_engine, text  # noqa: E402

_RATING_INSERT = """
    INSERT INTO evidence_refs
      (evidence_id, source_type, source_record_id, company_code, field_path,
       period, value, unit, statement_scope, source_title, source_uri,
       dataset_version, retrieved_at, turn_id, trace_id, module, source_table)
    SELECT r.evidence_id, 'research_report',
           COALESCE(r.report_id,
                    CONCAT(r.wind_code, '|', r.quarter, '|', r.institution,
                           '|', COALESCE(r.published_at, ''))),
           r.wind_code, 'rating_change',
           r.published_at,
           CONCAT(COALESCE(r.previous_rating, ''), '→', COALESCE(r.current_rating, '')),
           NULL, NULL, rr.title, rr.source_uri,
           r.dataset_version, CURRENT_TIMESTAMP, NULL, NULL, 'events',
           'research_reports'
    FROM rating_changes r
    LEFT JOIN research_reports rr ON rr.report_id = r.report_id
    WHERE r.evidence_id IS NOT NULL AND r.evidence_id != ''
      AND NOT EXISTS (SELECT 1 FROM evidence_refs e
                      WHERE e.evidence_id = r.evidence_id)
"""

_ANNOUNCEMENT_INSERT = """
    INSERT INTO evidence_refs
      (evidence_id, source_type, source_record_id, company_code, field_path,
       period, value, unit, statement_scope, source_title, source_uri,
       dataset_version, retrieved_at, turn_id, trace_id, module, source_table)
    SELECT s.evidence_id, 'announcement', s.source_record_id, a.wind_code, NULL,
           s.published_at, NULL, NULL, NULL, s.source_title, s.source_uri,
           a.dataset_version, CURRENT_TIMESTAMP, NULL, NULL, 'events',
           'announcements'
    FROM event_cluster_sources s
    LEFT JOIN announcements a ON a.object_id = s.source_record_id
    WHERE s.evidence_id IS NOT NULL AND s.evidence_id != ''
      AND NOT EXISTS (SELECT 1 FROM evidence_refs e
                      WHERE e.evidence_id = s.evidence_id)
"""

_INVALID_TURN_UPDATE = """
    UPDATE evidence_refs e
    LEFT JOIN conversation_turns t ON e.turn_id = t.turn_id
    SET e.turn_id = NULL
    WHERE e.turn_id IS NOT NULL AND e.turn_id != '' AND t.turn_id IS NULL
"""


def _engine():
    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url)


def _stats(conn) -> dict:
    """恢复目标统计（缺失数/断链数/无效 turn 数）。"""
    return {
        "rating_missing": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM rating_changes r
                WHERE r.evidence_id IS NOT NULL AND r.evidence_id != ''
                  AND NOT EXISTS (SELECT 1 FROM evidence_refs e
                                  WHERE e.evidence_id = r.evidence_id)
                """
            )
        ).scalar(),
        "cluster_missing": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM event_cluster_sources s
                WHERE s.evidence_id IS NOT NULL AND s.evidence_id != ''
                  AND NOT EXISTS (SELECT 1 FROM evidence_refs e
                                  WHERE e.evidence_id = s.evidence_id)
                """
            )
        ).scalar(),
        "invalid_turn": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM evidence_refs e
                LEFT JOIN conversation_turns t ON e.turn_id = t.turn_id
                WHERE e.turn_id IS NOT NULL AND e.turn_id != ''
                  AND t.turn_id IS NULL
                """
            )
        ).scalar(),
        "broken_claims": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM claims c
                LEFT JOIN claim_evidence_links l ON l.claim_id = c.claim_id
                WHERE l.claim_id IS NULL
                """
            )
        ).scalar(),
    }


def _counts(conn) -> dict[str, int]:
    out = {}
    for table in (
        "conversation_sessions",
        "conversation_turns",
        "claims",
        "evidence_refs",
        "claim_evidence_links",
        "rating_changes",
        "event_cluster_sources",
    ):
        out[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="重建被误删的全局证据")
    parser.add_argument("--dry-run", action="store_true", help="预检，不写库")
    parser.add_argument("--confirm", action="store_true", help="单事务执行")
    args = parser.parse_args()
    execute = args.confirm  # 无 --confirm 则默认 dry-run

    engine = _engine()
    with engine.connect() as conn:
        before = _counts(conn)
        st = _stats(conn)
        print(
            f"待修复: 评级证据缺失 {st['rating_missing']} | "
            f"事件簇证据缺失 {st['cluster_missing']} | "
            f"无效 turn_id {st['invalid_turn']} | "
            f"断链 Claim {st['broken_claims']}"
        )
        if not execute:
            print("预检模式（--dry-run），不写库；确认执行加 --confirm")
        if execute:
            # 1) 重建评级证据（幂等）
            n_rating = conn.execute(text(_RATING_INSERT)).rowcount
            # 2) 重建事件簇证据（幂等）
            n_cluster = conn.execute(text(_ANNOUNCEMENT_INSERT)).rowcount
            # 3) 无效 turn_id 置 NULL
            n_turn = conn.execute(text(_INVALID_TURN_UPDATE)).rowcount
            conn.commit()
            print(
                f"已执行: 重建评级证据 {n_rating} | 事件簇证据 {n_cluster} | "
                f"turn_id 置空 {n_turn}"
            )

    # 完整性复查
    with engine.connect() as conn:
        after = _counts(conn)
        st2 = _stats(conn)
    print("\n清理前后对比:")
    for table in before:
        delta = before[table] - after[table]
        mark = "" if delta == 0 else f"  ({'-' if delta < 0 else '+'}{abs(delta)})"
        print(f"  {table}: {before[table]} → {after[table]}{mark}")
    print("\n完整性复查:")
    print(f"  评级证据缺失: {st2['rating_missing']}")
    print(f"  事件簇证据缺失: {st2['cluster_missing']}")
    print(f"  无效 turn_id: {st2['invalid_turn']}")
    print(f"  断链 Claim: {st2['broken_claims']}")
    ok = (
        st2["rating_missing"] == 0
        and st2["cluster_missing"] == 0
        and st2["invalid_turn"] == 0
        and st2["broken_claims"] == 0
    )
    print(f"\n{'✅ 完整性通过' if ok else '❌ 仍有残留，请检查'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
