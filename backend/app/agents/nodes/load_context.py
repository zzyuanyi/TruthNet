"""LoadContext — V12 §7.2. 从 session 恢复上下文。

按 session_id 回读最近 N 轮 (question, answer)，组装为 messages 历史
注入 state，供 memory 节点做指代消解（公司/指标从文本提取，
company_code 当前无消费者，不入库查询）。
SQL_BACKEND != mysql 或不可恢复时保持占位行为。

Bug fix: 空 {} 会导致 LangGraph InvalidUpdateError，始终返回 state key。
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

# 回读最近轮次上限（V12 长对话记忆：超过 10 轮后主体丢失 → 滑动窗口回读）
_HISTORY_LIMIT = 5

_engine: Engine | None = None


def _get_engine() -> Engine:
    """惰性缓存 MySQL engine（与 resolve_entity 节点一致）。"""
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        _engine = create_engine(url, echo=False)
    return _engine


def _session_id(state: AgentState) -> str | None:
    """从 runtime 获取会话 ID。"""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    sid = getattr(runtime, "session_id", "") or ""
    return sid or None


def load_context_node(state: AgentState) -> dict:
    """恢复最近 N 轮历史消息。

    返回 messages 追加到已有列表（LangGraph add_messages reducer），
    下游 memory 节点可从中提取公司/指标做指代消解。
    """
    runtime = state.get("runtime")

    if settings.SQL_BACKEND != "mysql":
        return {"messages": [], "runtime": runtime}

    session_id = _session_id(state)
    if not session_id:
        return {"messages": [], "runtime": runtime}

    try:
        with _get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT question, answer FROM conversation_turns "
                        "WHERE session_id = :sid "
                        "ORDER BY turn_index DESC LIMIT :limit"
                    ),
                    {"sid": session_id, "limit": _HISTORY_LIMIT},
                )
                .mappings()
                .all()
            )
    except Exception:
        logger.exception("LoadContext 读取失败: session=%s", session_id)
        return {"messages": [], "runtime": runtime}

    # 倒序结果反转 → 按时间升序注入
    history: list[dict] = []
    for row in reversed(rows):
        q = str(row["question"] or "")
        a = str(row["answer"] or "")
        if q:
            history.append({"role": "user", "content": q})
        if a:
            history.append({"role": "assistant", "content": a})

    if history:
        logger.info(
            "LoadContext: session=%s 恢复 %d 条历史消息", session_id, len(history)
        )

    return {"messages": history, "runtime": runtime}
