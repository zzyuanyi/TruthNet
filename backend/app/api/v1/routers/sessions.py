"""会话路由 — V12 §11.2. 会话列表、创建、详情/历史。

GET  /api/v1/sessions                  → 列表（按 updated_at 倒序）
POST /api/v1/sessions                  → 创建
GET  /api/v1/sessions/{session_id}     → 详情 + turns 历史

SQL_BACKEND != mysql 时返回空列表 / 仅生成 session_id（lite/mock 行为）。
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.core.config import settings

router = APIRouter(tags=["sessions"])

_engine: Engine | None = None


def _get_engine() -> Engine:
    """惰性缓存 MySQL engine。"""
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        _engine = create_engine(url, echo=False)
    return _engine


def _trace() -> str:
    return str(uuid.uuid4())


def _new_session_id() -> str:
    return f"ses_{uuid.uuid4().hex[:12]}"


def _iso(v) -> str | None:
    """时间列转 ISO 字符串。

    MySQL text() 返回 datetime，SQLite 返回 str，统一双后端行为。
    """
    if v is None:
        return None
    return v.isoformat() if isinstance(v, datetime) else str(v)


class SessionCreateRequest(BaseModel):
    """创建会话请求 — V12 §11.2."""

    user_id: str | None = Field(default=None, description="用户 ID")
    title: str | None = Field(default=None, description="会话标题")


@router.get("/sessions")
def list_sessions():
    """会话列表 — V12 §11.2 (P0)。"""
    trace_id = _trace()

    sessions: list[dict] = []
    if settings.SQL_BACKEND == "mysql":
        try:
            with _get_engine().connect() as conn:
                rows = (
                    conn.execute(
                        text(
                            "SELECT s.session_id, s.user_id, s.title, s.status, "
                            "       s.created_at, s.updated_at, "
                            "       COUNT(t.turn_id) AS turn_count "
                            "FROM conversation_sessions s "
                            "LEFT JOIN conversation_turns t "
                            "  ON s.session_id = t.session_id "
                            "GROUP BY s.session_id, s.user_id, s.title, s.status, "
                            "         s.created_at, s.updated_at "
                            "ORDER BY s.updated_at DESC"
                        )
                    )
                    .mappings()
                    .all()
                )
            sessions = [
                {
                    "session_id": str(r["session_id"]),
                    "title": r["title"],
                    "status": r["status"],
                    "created_at": _iso(r["created_at"]),
                    "updated_at": _iso(r["updated_at"]),
                    "turn_count": int(r["turn_count"] or 0),
                }
                for r in rows
            ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 500,
                    "detail": "会话列表查询失败",
                    "error_code": "DB_UNAVAILABLE",
                    "trace_id": trace_id,
                    "recoverable": True,
                },
            )

    return V12Response(
        data={"sessions": sessions, "total": len(sessions)},
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=(
            []
            if settings.SQL_BACKEND == "mysql"
            else [
                {
                    "code": "LITE_MODE",
                    "message": "当前为 lite/mock 模式，未启用会话持久化",
                    "recoverable": True,
                }
            ]
        ),
    )


@router.post("/sessions")
def create_session(request: SessionCreateRequest):
    """创建会话 — V12 §11.2 (P0)。"""
    trace_id = _trace()
    session_id = _new_session_id()
    now = datetime.now(timezone.utc).isoformat()
    title = request.title or "新会话"

    if settings.SQL_BACKEND == "mysql":
        try:
            with _get_engine().begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO conversation_sessions "
                        "(session_id, user_id, title, status, created_at, updated_at) "
                        "VALUES (:sid, :uid, :title, 'active', CURRENT_TIMESTAMP, "
                        "CURRENT_TIMESTAMP)"
                    ),
                    {
                        "sid": session_id,
                        "uid": request.user_id,
                        "title": title,
                    },
                )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 500,
                    "detail": "会话创建失败",
                    "error_code": "DB_UNAVAILABLE",
                    "trace_id": trace_id,
                    "recoverable": True,
                },
            )

    return V12Response(
        data={
            "session_id": session_id,
            "title": title,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=(
            []
            if settings.SQL_BACKEND == "mysql"
            else [
                {
                    "code": "LITE_MODE",
                    "message": "当前为 lite/mock 模式，会话不会持久化",
                    "recoverable": True,
                }
            ]
        ),
    )


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """会话详情 + turns 历史 — V12 §11.2 (P0)。"""
    trace_id = _trace()

    session: dict | None = None
    turns: list[dict] = []

    if settings.SQL_BACKEND == "mysql":
        try:
            with _get_engine().connect() as conn:
                row = (
                    conn.execute(
                        text(
                            "SELECT session_id, user_id, title, status, "
                            "       created_at, updated_at "
                            "FROM conversation_sessions WHERE session_id = :sid"
                        ),
                        {"sid": session_id},
                    )
                    .mappings()
                    .first()
                )
                if row:
                    session = {
                        "session_id": str(row["session_id"]),
                        "title": row["title"],
                        "status": row["status"],
                        "created_at": _iso(row["created_at"]),
                        "updated_at": _iso(row["updated_at"]),
                    }

                if session is not None:
                    turn_rows = (
                        conn.execute(
                            text(
                                "SELECT turn_id, turn_index, question, answer, "
                                "       company_code, trace_id, module_status, created_at "
                                "FROM conversation_turns "
                                "WHERE session_id = :sid "
                                "ORDER BY turn_index ASC"
                            ),
                            {"sid": session_id},
                        )
                        .mappings()
                        .all()
                    )
                    turns = [
                        {
                            "turn_id": str(t["turn_id"]),
                            "turn_index": int(t["turn_index"] or 0),
                            "question": t["question"],
                            "answer": t["answer"],
                            "company_code": t["company_code"],
                            "trace_id": t["trace_id"],
                            # MySQL text() 对 JSON 列不做类型解析，需手动反序列化
                            "module_status": json.loads(t["module_status"])
                            if t["module_status"]
                            else None,
                            "created_at": _iso(t["created_at"]),
                        }
                        for t in turn_rows
                    ]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 500,
                    "detail": "会话详情查询失败",
                    "error_code": "DB_UNAVAILABLE",
                    "trace_id": trace_id,
                    "recoverable": True,
                },
            )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/session-not-found",
                "title": "Session Not Found",
                "status": 404,
                "detail": f"未找到会话: {session_id}",
                "error_code": "SESSION_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    return V12Response(
        data={"session": session, "turns": turns},
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )
