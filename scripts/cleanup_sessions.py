#!/usr/bin/env python
"""会话清理脚本 — 保留白名单，按依赖顺序删除（links → claims → evidence → turns → sessions）.

背景：直接 DELETE FROM conversation_sessions 会留下孤儿 claims/evidence_refs
（无外键级联）。2026-08-04 实测 897 个会话中仅 5 个是标准演示/验证用途。

用法:
    python scripts/cleanup_sessions.py --dry-run              # 预检（默认，不写库）
    python scripts/cleanup_sessions.py --confirm              # 正式执行
    python scripts/cleanup_sessions.py --keep <id> [<id>...]  # 追加保留 ID
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

# 默认保留白名单：仅仓库内固定演示会话（WS 联调每次生成新 UUID，
# 不作为默认值提交——需要保留时用 --keep 追加）
DEFAULT_KEEP: tuple[str, ...] = (
    "ses_demo_teacher",  # 金牌家居 REST 四轮标准演示
)


def _engine():
    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url)


def _counts(conn) -> dict[str, int]:
    """各表当前行数（清理前后对比用）。"""
    out = {}
    for table in (
        "conversation_sessions",
        "conversation_turns",
        "claims",
        "evidence_refs",
        "claim_evidence_links",
    ):
        out[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return out


_ORPHAN_CLAIM_SQL = """
    SELECT c.claim_id FROM claims c
    LEFT JOIN conversation_turns t ON c.turn_id = t.turn_id
    WHERE t.turn_id IS NULL
"""


def _integrity_stats(conn) -> dict[str, int]:
    """清理后完整性复查（与 restore_evidence.py 同口径）.

    曾出现清理后残留无效 turn_id 证据（turn 被删但 evidence 未被置空/
    删除）。清理后必须复查，残留时提示运行 restore_evidence.py --confirm。
    """
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


def _report_integrity(engine) -> int:
    """打印完整性复查，返回是否通过（0=通过）。"""
    with engine.connect() as conn:
        st = _integrity_stats(conn)
    print("\n完整性复查:")
    print(f"  评级证据缺失: {st['rating_missing']}")
    print(f"  事件簇证据缺失: {st['cluster_missing']}")
    print(f"  无效 turn_id: {st['invalid_turn']}")
    print(f"  断链 Claim: {st['broken_claims']}")
    ok = all(v == 0 for v in st.values())
    if ok:
        print("✅ 完整性通过")
    else:
        print(
            "⚠️ 仍有残留（无效 turn_id 等）——运行 "
            "scripts/restore_evidence.py --confirm 修复"
        )
    return 0 if ok else 1


def _cleanup_orphans(conn, execute: bool) -> tuple[int, int, int]:
    """清理无主 claims（turn 无效）+ 其 links + 无引用孤儿 evidence.

    实测（2026-08-04）：180 孤儿 claims / 601 links / 916 无引用 evidence，
    孤儿 claims 引用的 evidence 与有效 claims 零共享——可安全删除。
    """
    orphan_claim_ids = conn.execute(text(_ORPHAN_CLAIM_SQL)).scalars().all()
    orphan_links = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM claim_evidence_links l
            LEFT JOIN claims c ON l.claim_id = c.claim_id
            LEFT JOIN conversation_turns t ON c.turn_id = t.turn_id
            WHERE t.turn_id IS NULL
            """
        )
    ).scalar()
    # 统计口径必须与下方 DELETE 完全一致（含评级/事件簇保护），
    # 否则预检报告的数字与实际执行不符（P2 教训）
    orphan_ev = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM evidence_refs e
            LEFT JOIN conversation_turns t ON e.turn_id = t.turn_id
            LEFT JOIN rating_changes r ON r.evidence_id = e.evidence_id
            LEFT JOIN event_cluster_sources s ON s.evidence_id = e.evidence_id
            WHERE t.turn_id IS NULL
              AND NOT EXISTS (
                    SELECT 1 FROM claim_evidence_links l
                    JOIN claims c ON c.claim_id = l.claim_id
                    JOIN conversation_turns valid_t ON valid_t.turn_id = c.turn_id
                    WHERE l.evidence_id = e.evidence_id
              )
              AND r.evidence_id IS NULL AND s.evidence_id IS NULL
            """
        )
    ).scalar()

    if execute:
        for cid in orphan_claim_ids:
            conn.execute(
                text("DELETE FROM claim_evidence_links WHERE claim_id = :c"), {"c": cid}
            )
        # JOIN 形式删除：MySQL 禁止 DELETE 目标表并从自身子查询读取（1093）
        conn.execute(
            text(
                """
                DELETE c FROM claims c
                LEFT JOIN conversation_turns t ON c.turn_id = t.turn_id
                WHERE t.turn_id IS NULL
                """
            )
        )
        # LEFT JOIN 形式：NOT IN 子查询对 NULL turn_id 不生效（返回 NULL 被过滤），
        # 评估查询用 LEFT JOIN（含 NULL turn_id 的 evidence）——执行必须同口径
        # evidence_refs 是全局资产：仍被 Claim/评级/事件簇引用的不得删（P1 教训）
        conn.execute(
            text(
                """
                DELETE e FROM evidence_refs e
                LEFT JOIN conversation_turns t ON e.turn_id = t.turn_id
                LEFT JOIN claim_evidence_links l ON l.evidence_id = e.evidence_id
                LEFT JOIN rating_changes r ON r.evidence_id = e.evidence_id
                LEFT JOIN event_cluster_sources s ON s.evidence_id = e.evidence_id
                WHERE t.turn_id IS NULL AND l.evidence_id IS NULL
                  AND r.evidence_id IS NULL AND s.evidence_id IS NULL
                """
            )
        )
    return len(orphan_claim_ids), int(orphan_links or 0), int(orphan_ev or 0)


def _confirm_requires_keep(args) -> bool:
    """Session deletion needs an explicit keep list; orphan-only cleanup does not."""
    return bool(args.confirm and not args.orphans and not args.keep)


def main() -> int:
    parser = argparse.ArgumentParser(description="清理非白名单会话（级联顺序）")
    parser.add_argument("--dry-run", action="store_true", help="预检，不写库")
    parser.add_argument("--confirm", action="store_true", help="正式执行")
    parser.add_argument("--keep", nargs="*", default=[], help="追加保留的 session_id")
    parser.add_argument(
        "--orphans",
        action="store_true",
        help="只清理无主 claims/links/evidence（turn 无效），跳过会话清理",
    )
    args = parser.parse_args()

    # 安全闸（对齐审计 P2-7）：--confirm 必须显式 --keep，
    # 防止默认白名单（仅仓库固定演示会话）未覆盖真实演示会话时误删
    if _confirm_requires_keep(args):
        print(
            "⚠️ 拒绝执行：--confirm 必须显式指定 --keep <session_id>（至少一个），"
            "默认白名单不保护随机 UUID 演示会话。\n"
            "请先运行 --dry-run --keep <id> 确认保留对象，再带同一 --keep 执行。"
        )
        return 2

    keep = set(DEFAULT_KEEP) | set(args.keep)
    execute = args.confirm  # 无 --confirm 则默认 dry-run

    engine = _engine()
    with engine.connect() as conn:
        before = _counts(conn)

        if args.orphans:
            n_claims, n_links, n_ev = _cleanup_orphans(conn, execute)
            if execute:
                conn.commit()
            print(
                f"孤儿清理: {n_claims} claims / {n_links} links / {n_ev} evidence "
                f"({'已执行' if execute else '预检（--confirm 执行）'})"
            )
            with engine.connect() as conn2:
                after = _counts(conn2)
            print("\n清理前后对比:")
            for table in before:
                delta = before[table] - after[table]
                mark = "" if delta == 0 else f"  (-{delta})"
                print(f"  {table}: {before[table]} → {after[table]}{mark}")
            return _report_integrity(engine)
        all_rows = conn.execute(
            text(
                "SELECT session_id, "
                "(SELECT COUNT(*) FROM conversation_turns t "
                " WHERE t.session_id = s.session_id) AS turn_count "
                "FROM conversation_sessions s ORDER BY s.created_at"
            )
        ).all()

        to_delete = [r for r in all_rows if r[0] not in keep]
        print(
            f"总会话: {len(all_rows)} | 保留: {len(all_rows) - len(to_delete)} | 待清理: {len(to_delete)}"
        )
        if args.dry_run and not execute:
            print("预检模式（--dry-run），不写库；确认执行加 --confirm")

        deleted_turns = 0
        for sid, turn_count in to_delete:
            print(f"  {'[预检]' if not execute else '[删除]'} {sid} ({turn_count} 轮)")
            if not execute:
                deleted_turns += turn_count or 0
                continue
            # 级联删除（依赖顺序：links → claims → evidence → turns → session）
            turn_ids = (
                conn.execute(
                    text(
                        "SELECT turn_id FROM conversation_turns WHERE session_id = :s"
                    ),
                    {"s": sid},
                )
                .scalars()
                .all()
            )
            for tid in turn_ids:
                conn.execute(
                    text(
                        "DELETE FROM claim_evidence_links WHERE claim_id IN "
                        "(SELECT claim_id FROM claims WHERE turn_id = :t)"
                    ),
                    {"t": tid},
                )
                conn.execute(text("DELETE FROM claims WHERE turn_id = :t"), {"t": tid})
                # evidence_refs 是全局资产（P1 教训）：先清空仍被 Claim/评级/
                # 事件簇引用的证据的 turn_id（避免对已删 turn 的无效引用），
                # 再删除不再被任何地方引用的会话本地证据
                conn.execute(
                    text(
                        "UPDATE evidence_refs SET turn_id = NULL "
                        "WHERE turn_id = :t AND ("
                        "  evidence_id IN (SELECT l.evidence_id "
                        "                   FROM claim_evidence_links l) "
                        "  OR evidence_id IN (SELECT r.evidence_id "
                        "                      FROM rating_changes r) "
                        "  OR evidence_id IN (SELECT s.evidence_id "
                        "                      FROM event_cluster_sources s))"
                    ),
                    {"t": tid},
                )
                conn.execute(
                    text(
                        "DELETE FROM evidence_refs WHERE turn_id = :t "
                        "AND NOT EXISTS (SELECT 1 FROM claim_evidence_links l "
                        "  WHERE l.evidence_id = evidence_refs.evidence_id) "
                        "AND NOT EXISTS (SELECT 1 FROM rating_changes r "
                        "  WHERE r.evidence_id = evidence_refs.evidence_id) "
                        "AND NOT EXISTS (SELECT 1 FROM event_cluster_sources s "
                        "  WHERE s.evidence_id = evidence_refs.evidence_id)"
                    ),
                    {"t": tid},
                )
            conn.execute(
                text("DELETE FROM conversation_turns WHERE session_id = :s"), {"s": sid}
            )
            conn.execute(
                text("DELETE FROM conversation_sessions WHERE session_id = :s"),
                {"s": sid},
            )
            deleted_turns += len(turn_ids)
        if execute:
            conn.commit()

    with engine.connect() as conn:
        after = _counts(conn)
    print("\n清理前后对比:")
    for table in before:
        delta = before[table] - after[table]
        mark = "" if delta == 0 else f"  (-{delta})"
        print(f"  {table}: {before[table]} → {after[table]}{mark}")
    print(f"合计删除: {len(to_delete)} 会话 / {deleted_turns} 轮")
    return _report_integrity(engine)


if __name__ == "__main__":
    sys.exit(main())
