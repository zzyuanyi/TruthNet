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

v3.5（审查要求）：
- 引擎用 URL.create() 构建；缓存键含 backend/host/port/database/user，
  不只按 backend（测试库/演示库 engine 不串）；
- cleanup_session() 返回 session_found/session_deleted + 真实删除行数
  （claims/links 用 SQL rowcount，不再按 turn 数累计）。

调用方：REST DELETE session、E2E 脚本（scripts/e2e_ws_three_turn.py）。
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def _get_engine() -> Engine:
    """按 (backend, host, port, database, user) 键缓存 engine（v3.5）。"""
    if settings.SQL_BACKEND == "mysql":
        key = (
            f"mysql|{settings.MYSQL_HOST}|{settings.MYSQL_PORT}|"
            f"{settings.MYSQL_DATABASE}|{settings.MYSQL_USER}"
        )
    else:
        key = f"sqlite|{settings.SQLITE_PATH}"
    if key in _engines:
        return _engines[key]
    if settings.SQL_BACKEND == "mysql":
        url = URL.create(
            "mysql+pymysql",
            username=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            database=settings.MYSQL_DATABASE,
            query={"charset": "utf8mb4"},
        )
        _engines[key] = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[4] / path
        _engines[key] = create_engine(
            URL.create("sqlite", database=path.as_posix()), echo=False
        )
    return _engines[key]


class SessionCleanupService:
    """会话级联清理（单事务）。"""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or _get_engine()

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
