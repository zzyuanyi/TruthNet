"""PersistTurn — V12 §7.2. 保存 turn 状态（conversation 表）。

完整 State → conversation_sessions + conversation_turns (§10.8)。
Phase C 集成修正: 尊重 SQL_BACKEND（sqlite lite / mysql full），lite 模式
同样写入 SQLite，保证与 load_context 读写一致（多轮记忆闭环）。
数据库异常吞掉并记日志，不阻断 Agent 主流程。
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def _repo_root() -> Path:
    # backend/app/agents/nodes/persist_turn.py -> 项目根
    return Path(__file__).resolve().parents[4]


def _get_engine() -> Engine:
    """惰性缓存引擎，尊重 SQL_BACKEND（sqlite/mysql）。"""
    backend = settings.SQL_BACKEND
    if backend in _engines:
        return _engines[backend]

    if backend == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _engines[backend] = create_engine(url, echo=False)
    else:  # sqlite
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _engines[backend] = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return _engines[backend]


def _session_id(state: AgentState) -> str | None:
    """从 runtime 获取会话 ID。"""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    sid = getattr(runtime, "session_id", "") or ""
    return sid or None


def _to_json(value) -> str | None:
    """JSON 序列化，Pydantic model 走 model_dump。"""
    if value is None:
        return None
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
        )
    except (TypeError, ValueError):
        logger.warning("module_status 序列化失败，跳过持久化该字段", exc_info=True)
        return None


def persist_turn_node(state: AgentState) -> dict:
    """持久化当前轮次。

    写入 conversation_sessions（upsert）+ conversation_turns（turn_index 递增）。
    任何异常都吞掉并记日志，不阻断 Agent 主流程。
    """
    session_id = _session_id(state)
    question = state.get("user_query", "")
    if not session_id or not question:
        return {"messages": []}

    final_response = state.get("final_response")
    answer = ""
    if final_response is not None:
        answer = getattr(final_response, "answer", "") or ""

    company = state.get("company")
    company_code = company.wind_code if company else None

    runtime = state.get("runtime")
    trace_id = ""
    turn_id = ""
    if runtime is not None:
        trace_id = getattr(runtime, "trace_id", "") or ""
        turn_id = getattr(runtime, "turn_id", "") or ""
    # 优先复用 runtime.turn_id（WS 契约可追溯），REST 未设置时自生成
    db_turn_id = turn_id or f"turn_{uuid.uuid4().hex[:12]}"

    module_status_json = _to_json(state.get("module_status", {}))
    title = question[:30]

    try:
        with _get_engine().begin() as conn:
            # 会话 upsert：已存在 → 仅刷新状态/时间；不存在 → 插入（title 取自首轮）
            existing = conn.execute(
                text(
                    "SELECT session_id FROM conversation_sessions "
                    "WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).first()
            if existing:
                conn.execute(
                    text(
                        "UPDATE conversation_sessions "
                        "SET status = 'active', updated_at = CURRENT_TIMESTAMP "
                        "WHERE session_id = :sid"
                    ),
                    {"sid": session_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO conversation_sessions "
                        "(session_id, title, status, created_at, updated_at) "
                        "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, "
                        "CURRENT_TIMESTAMP)"
                    ),
                    {"sid": session_id, "title": title},
                )

            # turn_index = 该会话已有轮数 + 1
            turn_index = conn.execute(
                text(
                    "SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_index "
                    "FROM conversation_turns WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).scalar_one()

            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, answer, "
                    " company_code, trace_id, module_status, created_at) "
                    "VALUES (:turn_id, :sid, :index, :q, :a, :cc, :trace, :ms, "
                    "CURRENT_TIMESTAMP)"
                ),
                {
                    "turn_id": db_turn_id,
                    "sid": session_id,
                    "index": turn_index,
                    "q": question,
                    "a": answer,
                    "cc": company_code,
                    "trace": trace_id,
                    "ms": module_status_json,
                },
            )
        logger.info(
            "PersistTurn: session=%s turn_index=%d company=%s",
            session_id,
            turn_index,
            company_code,
        )
    except Exception:
        logger.exception("PersistTurn 写入失败: session=%s", session_id)

    return {"messages": []}
