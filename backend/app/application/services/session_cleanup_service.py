"""会话定向清理共享服务 — v3.4/v3.5（2026-08-11）.

从 sessions.py 会话删除语义提取，REST（sessions.py）与 E2E/清理脚本
共用，避免各脚本复制一份 SQL。单事务内完成，删除顺序固定：

  1. 收集本 session 的 turn_ids；
  2. 删 claim_evidence_links + claims（按 turn）；
  3. Evidence 是全局资产（P1 教训：曾无条件按 turn 删除导致共享证据丢失）：
     a. 仍被 claim_evidence_links / rating_changes / event_cluster_sources
        引用的证据：保留，仅 turn_id 置 NULL（避免对已删 turn 的无效引用）；
     b. 不再被任何地方引用的会话本地证据：删除；
  4. 删 conversation_turns + conversation_sessions。

REST DELETE 先走 soft_delete_session()：标记 archived + metadata.deleted_at；
cleanup_session() 作为 TTL/脚本的物理清理入口保留。

v3.5（审查要求）：
- 引擎用 URL.create() 构建；缓存键含 backend/host/port/database/user，
  不只按 backend（测试库/演示库 engine 不串）；
- cleanup_session() 返回 session_found/session_deleted + 真实删除行数
  （claims/links 用 SQL rowcount，不再按 turn 数累计）。

调用方：REST DELETE session、E2E 脚本（scripts/e2e_ws_three_turn.py）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_engine() -> Engine:
    """8/19 全面审查：改用公共工厂（完整 profile key + 切 profile 即 dispose）。

    原实现自带 profile key 缓存但切库不 dispose 旧 Engine，连接池滞留旧库。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


class SessionCleanupService:
    """会话级联清理（单事务）。"""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or _get_engine()

    def soft_delete_session(self, session_id: str, user_id: str | None = None) -> dict:
        """软删除指定 session；不删除 turns/evidence，供审计与 TTL 清理。

        历史 user_id 为 NULL 的会话归属默认用户；显式 user_id 不可删除他人会话。
        """
        stats = {
            "session_found": False,
            "session_deleted": False,
            "session_id": session_id,
        }
        owner = (user_id or "").strip() or settings.SESSION_DEFAULT_USER_ID
        from app.core.write_guard import assert_db_writable

        assert_db_writable(
            database=getattr(getattr(self._engine, "url", None), "database", None)
        )
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT metadata FROM conversation_sessions "
                        "WHERE session_id = :sid "
                        "AND COALESCE(user_id, :default_user_id) = :user_id "
                        "AND COALESCE(status, 'active') != 'archived' "
                        "LIMIT 1"
                    ),
                    {
                        "sid": session_id,
                        "user_id": owner,
                        "default_user_id": settings.SESSION_DEFAULT_USER_ID,
                    },
                )
                .mappings()
                .first()
            )
            if row is None:
                return stats
            stats["session_found"] = True
            meta = _json_value(row["metadata"], {})
            meta["deleted_at"] = datetime.now(timezone.utc).isoformat()
            meta["delete_ttl_days"] = settings.SESSION_SOFT_DELETE_TTL_DAYS
            res = conn.execute(
                text(
                    "UPDATE conversation_sessions "
                    "SET status = 'archived', metadata = :meta, "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE session_id = :sid "
                    "AND COALESCE(user_id, :default_user_id) = :user_id "
                    "AND COALESCE(status, 'active') != 'archived'"
                ),
                {
                    "sid": session_id,
                    "user_id": owner,
                    "default_user_id": settings.SESSION_DEFAULT_USER_ID,
                    "meta": json.dumps(meta, ensure_ascii=False),
                },
            )
            stats["session_deleted"] = (res.rowcount or 0) > 0
        return stats

    def purge_expired_soft_deleted(
        self, now: datetime | None = None, ttl_days: int | None = None
    ) -> dict:
        """物理清理已超过 TTL 的软删除会话。

        返回 {scanned, purged, sessions}；单个 session 清理失败时继续处理其他
        session，并在 sessions 项记录 error。
        """
        now = now or datetime.now(timezone.utc)
        ttl = settings.SESSION_SOFT_DELETE_TTL_DAYS if ttl_days is None else ttl_days
        cutoff = now - timedelta(days=max(int(ttl), 0))
        scanned = 0
        sessions: list[dict] = []
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT session_id, metadata FROM conversation_sessions "
                        "WHERE status = 'archived'"
                    )
                )
                .mappings()
                .all()
            )
        for row in rows:
            scanned += 1
            meta = _json_value(row["metadata"], {})
            deleted_at = _parse_datetime(str(meta.get("deleted_at") or ""))
            if deleted_at is None or deleted_at > cutoff:
                continue
            sid = str(row["session_id"])
            try:
                stats = self.cleanup_session(sid)
                sessions.append({"session_id": sid, "stats": stats})
            except Exception as exc:  # noqa: BLE001 — 清理其他 session 不受影响
                logger.warning("session purge failed: %s", sid, exc_info=True)
                sessions.append({"session_id": sid, "error": str(exc)})
        return {"scanned": scanned, "purged": len(sessions), "sessions": sessions}

    def cleanup_session(self, session_id: str) -> dict:
        """删除指定 session 全部数据；返回统计。单事务，失败整体回滚。

        v3.5 返回结构：
          session_found    — session 是否存在（不存在返回全 0，不抛异常）；
          session_deleted  — 是否实际删除成功；
          turns/claims/links/evidence_kept/evidence_deleted — 真实删除行数
            （SQL rowcount 累计，claims 不再按 turn 数估算）。
        """
        stats = {
            "session_found": False,
            "session_deleted": False,
            "turns": 0,
            "claims": 0,
            "links": 0,
            "evidence_kept": 0,
            "evidence_deleted": 0,
        }
        from app.core.write_guard import assert_db_writable

        assert_db_writable(  # 8/19 P0：写路径运行时守卫（演示库零写入）
            database=getattr(getattr(self._engine, "url", None), "database", None)
        )
        with self._engine.begin() as conn:
            found = conn.execute(
                text(
                    "SELECT 1 FROM conversation_sessions "
                    "WHERE session_id = :sid LIMIT 1"
                ),
                {"sid": session_id},
            ).scalar()
            if not found:
                return stats
            stats["session_found"] = True
            turn_rows = conn.execute(
                text("SELECT turn_id FROM conversation_turns WHERE session_id = :sid"),
                {"sid": session_id},
            ).all()
            for row in turn_rows:
                t = row[0]
                # 1. links + claims（rowcount 累计）
                res = conn.execute(
                    text(
                        "DELETE FROM claim_evidence_links WHERE claim_id IN "
                        "(SELECT claim_id FROM claims WHERE turn_id = :t)"
                    ),
                    {"t": t},
                )
                stats["links"] += res.rowcount or 0
                res = conn.execute(
                    text("DELETE FROM claims WHERE turn_id = :t"), {"t": t}
                )
                stats["claims"] += res.rowcount or 0
                # 2a. 仍被全局引用的证据：保留，turn_id 置 NULL
                res = conn.execute(
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
                    {"t": t},
                )
                stats["evidence_kept"] += res.rowcount or 0
                # 2b. 无全局引用的会话本地证据：删除
                res = conn.execute(
                    text(
                        "DELETE FROM evidence_refs WHERE turn_id = :t "
                        "AND NOT EXISTS (SELECT 1 FROM claim_evidence_links l "
                        "  WHERE l.evidence_id = evidence_refs.evidence_id) "
                        "AND NOT EXISTS (SELECT 1 FROM rating_changes r "
                        "  WHERE r.evidence_id = evidence_refs.evidence_id) "
                        "AND NOT EXISTS (SELECT 1 FROM event_cluster_sources s "
                        "  WHERE s.evidence_id = evidence_refs.evidence_id)"
                    ),
                    {"t": t},
                )
                stats["evidence_deleted"] += res.rowcount or 0
            res = conn.execute(
                text("DELETE FROM conversation_turns WHERE session_id = :sid"),
                {"sid": session_id},
            )
            stats["turns"] = res.rowcount or 0
            res = conn.execute(
                text("DELETE FROM conversation_sessions WHERE session_id = :sid"),
                {"sid": session_id},
            )
            stats["session_deleted"] = (res.rowcount or 0) > 0
        return stats


def _json_value(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
