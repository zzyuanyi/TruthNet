"""会话路由 — V12 §11.2. 会话列表、创建、详情/历史。

GET  /api/v1/sessions                  → 列表（按 updated_at 倒序）
POST /api/v1/sessions                  → 创建
GET  /api/v1/sessions/{session_id}     → 详情 + turns 历史

SQL_BACKEND != mysql 时返回空列表 / 仅生成 session_id（lite/mock 行为）。
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.api.v1.schemas.sessions import (
    SessionCreateDataV1,
    SessionDeleteDataV1,
    SessionDetailDataV1,
    SessionListDataV1,
)
from app.core.errors import ErrorCode, ProblemDetail
from app.core.config import settings
from app.domain.conversation.models import DEFAULT_SESSION_TITLE

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


def _json_value(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _build_turn_sources(
    src_map: dict[str, dict], evidence_ids: list[str], max_items: int = 10
) -> list[dict]:
    """按轮组装来源列表（P1-3，与 WS 实时 sources 同构）。

    格式：{id: evidence_id, title: source_title, source: source_type, url: source_uri}
    规则：有 URL 的来源优先 → 按 evidence_id 稳定排序 → 去重 → 截取 max_items。
    """
    items = []
    for eid in evidence_ids:
        info = src_map.get(eid)
        if not info:
            continue
        items.append(
            {
                "id": eid,
                "title": info.get("source_title", ""),
                "source": info.get("source_type", ""),
                "url": info.get("source_uri", ""),
            }
        )
    items.sort(key=lambda x: (0 if x["url"] else 1, x["id"]))
    return items[:max_items]


class SessionCreateRequest(BaseModel):
    """创建会话请求 — V12 §11.2."""

    user_id: str | None = Field(default=None, description="用户 ID")
    title: str | None = Field(default=None, description="会话标题")


@router.get(
    "/sessions",
    response_model=V12Response[SessionListDataV1],
    responses={503: {"model": ProblemDetail}},
)
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """会话列表 — V12 §11.2 (P0)。"""
    trace_id = _trace()

    sessions: list[dict] = []
    if settings.SQL_BACKEND == "mysql":
        try:
            with _get_engine().connect() as conn:
                total = int(
                    conn.execute(
                        text("SELECT COUNT(*) FROM conversation_sessions")
                    ).scalar_one()
                )
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
                            "ORDER BY s.updated_at DESC, s.session_id ASC "
                            "LIMIT :limit OFFSET :offset"
                        ),
                        {"limit": limit, "offset": offset},
                    )
                    .mappings()
                    .all()
                )
            sessions = [
                {
                    "session_id": str(r["session_id"]),
                    "user_id": r["user_id"],
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
                status_code=503,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 503,
                    "detail": "会话列表查询失败",
                    "error_code": ErrorCode.DATASTORE_UNAVAILABLE,
                    "trace_id": trace_id,
                    "recoverable": True,
                },
            )

    else:
        total = 0

    return V12Response(
        data={
            "sessions": sessions,
            "total": total,
            "limit": limit,
            "offset": offset,
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
                    "message": "当前为 lite/mock 模式，未启用会话持久化",
                    "recoverable": True,
                }
            ]
        ),
    )


@router.post(
    "/sessions",
    response_model=V12Response[SessionCreateDataV1],
    responses={503: {"model": ProblemDetail}},
)
def create_session(request: SessionCreateRequest):
    """创建会话 — V12 §11.2 (P0)。"""
    trace_id = _trace()
    session_id = _new_session_id()
    now = datetime.now(timezone.utc).isoformat()
    title = request.title or DEFAULT_SESSION_TITLE

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
                status_code=503,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 503,
                    "detail": "会话创建失败",
                    "error_code": ErrorCode.DATASTORE_UNAVAILABLE,
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


@router.get(
    "/sessions/{session_id}",
    response_model=V12Response[SessionDetailDataV1],
    responses={404: {"model": ProblemDetail}, 503: {"model": ProblemDetail}},
)
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
                        "user_id": row["user_id"],
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
                                "       company_code, trace_id, module_status, "
                                "       panel_data, response_meta, created_at "
                                "FROM conversation_turns "
                                "WHERE session_id = :sid "
                                "ORDER BY turn_index ASC"
                            ),
                            {"sid": session_id},
                        )
                        .mappings()
                        .all()
                    )
                    # 每轮证据 ID 列表（前端证据链按 evidence_ids 展示，
                    # 历史会话必须携带，否则一律显示"无直接证据支撑"）。
                    # 证据来源 = turn 直接关联 ∪ 该轮 claims 的证据链接
                    # （全局证据 turn_id 多为 NULL，经 claims→links 关联）
                    ev_map: dict[str, list[str]] = {}
                    if turn_rows:
                        tids = tuple(t["turn_id"] for t in turn_rows)
                        rows = conn.execute(
                            text(
                                "SELECT turn_id, evidence_id FROM evidence_refs "
                                "WHERE turn_id IN :tids"
                            ).bindparams(bindparam("tids", expanding=True)),
                            {"tids": tids},
                        ).all()
                        for tr in rows:
                            ev_map.setdefault(str(tr[0]), []).append(str(tr[1]))
                        rows = conn.execute(
                            text(
                                "SELECT c.turn_id, l.evidence_id FROM claims c "
                                "JOIN claim_evidence_links l "
                                "  ON l.claim_id = c.claim_id "
                                "WHERE c.turn_id IN :tids"
                            ).bindparams(bindparam("tids", expanding=True)),
                            {"tids": tids},
                        ).all()
                        for tr in rows:
                            lst = ev_map.setdefault(str(tr[0]), [])
                            if str(tr[1]) not in lst:
                                lst.append(str(tr[1]))
                    # P1-3：来源详情（sources，与 WS 实时同构 {id,title,source,url}）。
                    # 批量查全部证据 ID 的来源字段（含 turn_id=NULL 的全局证据，
                    # 已通过 claims→links 进入 ev_map）。
                    src_map: dict[str, dict] = {}
                    all_eids = [eid for eids in ev_map.values() for eid in eids]
                    if all_eids:
                        ev_rows = conn.execute(
                            text(
                                "SELECT evidence_id, source_type, source_title, source_uri "
                                "FROM evidence_refs WHERE evidence_id IN :eids"
                            ).bindparams(bindparam("eids", expanding=True)),
                            {"eids": all_eids},
                        ).all()
                        for er in ev_rows:
                            src_map[str(er[0])] = {
                                "source_type": str(er[1] or ""),
                                "source_title": str(er[2] or ""),
                                "source_uri": str(er[3] or ""),
                            }
                    turns = [
                        {
                            "turn_id": str(t["turn_id"]),
                            "turn_index": int(t["turn_index"] or 0),
                            "question": t["question"],
                            "answer": t["answer"],
                            "company_code": t["company_code"],
                            "trace_id": t["trace_id"],
                            # MySQL text() 对 JSON 列不做类型解析，需手动反序列化
                            "module_status": _json_value(t["module_status"], None),
                            # 面板摘要（历史会话分析面板恢复，v7；旧数据为 None）
                            "panel_data": _json_value(t["panel_data"], None),
                            "evidence_ids": ev_map.get(str(t["turn_id"]), []),
                            # P1-3：与 WS 同构 sources——URI 优先、按 ID 稳定排序、
                            # 去重并截取 10 条（旧数据无来源则空列表）
                            "sources": _build_turn_sources(
                                src_map, ev_map.get(str(t["turn_id"]), [])
                            ),
                            "intent": _json_value(t["response_meta"], {}).get(
                                "intent", ""
                            ),
                            "follow_ups": _json_value(t["response_meta"], {}).get(
                                "follow_ups", []
                            ),
                            "supporting_evidence_ids": _json_value(
                                t["response_meta"], {}
                            ).get("supporting_evidence_ids", []),
                            "requested_period_text": _json_value(
                                t["response_meta"], {}
                            ).get("requested_period_text", ""),
                            "created_at": _iso(t["created_at"]),
                        }
                        for t in turn_rows
                    ]
        except Exception:
            raise HTTPException(
                status_code=503,
                detail={
                    "type": "https://truthnet.dev/errors/db-unavailable",
                    "title": "Database Unavailable",
                    "status": 503,
                    "detail": "会话详情查询失败",
                    "error_code": ErrorCode.DATASTORE_UNAVAILABLE,
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


@router.delete(
    "/sessions/{session_id}",
    response_model=V12Response[SessionDeleteDataV1],
    responses={404: {"model": ProblemDetail}, 503: {"model": ProblemDetail}},
)
def delete_session(session_id: str):
    """删除会话（级联清理：links → claims → evidence → turns → session）.

    单独删除只清理该会话 turns 关联的证据（evidence_refs.turn_id）；
    与 claims 无关的全局 evidence 不在删除范围（批量清理见
    scripts/cleanup_sessions.py：白名单 + --dry-run）。
    """
    trace_id = _trace()

    if settings.SQL_BACKEND != "mysql":
        return V12Response(
            data={"deleted": False, "session_id": session_id},
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
            warnings=[],
        )

    try:
        with _get_engine().connect() as conn:
            # 先确认会话存在（不能以 turn_rows 判断：零轮次会话也应可删除）
            exists = conn.execute(
                text("SELECT 1 FROM conversation_sessions " "WHERE session_id = :sid"),
                {"sid": session_id},
            ).scalar()
            if not exists:
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
            turn_rows = (
                conn.execute(
                    text(
                        "SELECT turn_id FROM conversation_turns "
                        "WHERE session_id = :sid"
                    ),
                    {"sid": session_id},
                )
                .mappings()
                .all()
            )
            # 级联删除（依赖顺序：links → claims → evidence → turns → session）
            for t in turn_rows:
                conn.execute(
                    text(
                        "DELETE FROM claim_evidence_links WHERE claim_id IN "
                        "(SELECT claim_id FROM claims WHERE turn_id = :t)"
                    ),
                    {"t": t["turn_id"]},
                )
                conn.execute(
                    text("DELETE FROM claims WHERE turn_id = :t"),
                    {"t": t["turn_id"]},
                )
                # evidence_refs 是全局资产（曾无条件按 turn 删除导致共享证据
                # 丢失——P1 教训）：
                # 1) 仍被 Claim/评级/事件簇引用的证据：清空 turn_id，
                #    避免对已删 turn 产生无效引用（IN 子查询写法，
                #    MySQL/SQLite 通用，不用 MySQL 特有表别名）
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
                    {"t": t["turn_id"]},
                )
                # 2) 不再被任何地方引用的会话本地证据：删除
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
                    {"t": t["turn_id"]},
                )
            conn.execute(
                text("DELETE FROM conversation_turns WHERE session_id = :sid"),
                {"sid": session_id},
            )
            conn.execute(
                text("DELETE FROM conversation_sessions WHERE session_id = :sid"),
                {"sid": session_id},
            )
            conn.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://truthnet.dev/errors/db-unavailable",
                "title": "Database Unavailable",
                "status": 503,
                "detail": "会话删除失败",
                "error_code": ErrorCode.DATASTORE_UNAVAILABLE,
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    return V12Response(
        data={"deleted": True, "session_id": session_id},
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )
