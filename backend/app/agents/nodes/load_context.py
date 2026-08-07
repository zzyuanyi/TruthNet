"""LoadContext — V12 §7.2. 从 session 恢复上下文。

按 session_id 回读最近 N 轮 (question, answer)，组装为 messages 历史
注入 state，供 memory 节点做指代消解（公司/指标从文本提取，
company_code 当前无消费者，不入库查询）。

Phase C 集成修正:
- 恢复窗口由 5 轮扩至 _HISTORY_LIMIT=10，满足"10 轮指代正确"验收。
- 支持 SQL_BACKEND 双后端（sqlite lite / mysql full），lite 模式同样可
  从 SQLite conversation_turns 恢复历史。
- 数据库不可用/异常时保持占位行为（返回空历史，不阻断图执行）。

Bug fix: 空 {} 会导致 LangGraph InvalidUpdateError，始终返回 state key。
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

# 回读最近轮次上限（10 轮：验收要求第 10 轮仍能恢复正确主体）
_HISTORY_LIMIT = 10

_engines: dict[str, Engine] = {}


def _repo_root() -> Path:
    # backend/app/agents/nodes/load_context.py -> 项目根
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


def load_context_node(state: AgentState) -> dict:
    """恢复最近 N 轮历史消息 + 远期记忆摘要（Phase D #15）。

    返回 messages 追加到已有列表（LangGraph add_messages reducer），
    下游 memory 节点可从中提取公司/指标做指代消解。

    记忆策略（settings.MEMORY_STRATEGY）：
      - none / recent_only：仅近期轮次；
      - summary_plus_recent：近期 N 轮全量 + 更早轮次的限长摘要
        （摘要注入为 system 消息，与近期轮次/当前问题清晰区分）。
    """
    runtime = state.get("runtime")

    session_id = _session_id(state)
    if not session_id:
        return {"messages": [], "runtime": runtime}

    strategy = settings.MEMORY_STRATEGY
    history: list[dict] = []

    # 远期记忆摘要（优先注入，标注来源轮次，不覆盖近期事实）
    summary = None
    if strategy == "summary_plus_recent":
        try:
            from app.application.services.memory_distillation import (
                load_or_build_summary,
            )

            summary = load_or_build_summary(session_id)
        except Exception:  # noqa: BLE001 — 摘要失败回退近期轮次
            logger.warning("LoadContext: 远期摘要加载失败，回退近期轮次", exc_info=True)
        if summary is not None and summary.text:
            history.append(
                {
                    "role": "system",
                    "content": (
                        f"【远期记忆摘要】（覆盖至第 {summary.covered_until_turn_index} 轮，"
                        f"来源 {len(summary.source_turn_ids)} 轮；仅供参考，不覆盖近期事实）："
                        f"{summary.text}"
                    ),
                }
            )

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
        return {"messages": history, "runtime": runtime}

    # 倒序结果反转 → 按时间升序注入
    for row in reversed(rows):
        q = str(row["question"] or "")
        a = str(row["answer"] or "")
        if q:
            history.append({"role": "user", "content": q})
        if a:
            history.append({"role": "assistant", "content": a})

    if history:
        logger.info(
            "LoadContext: session=%s 恢复 %d 条历史消息（strategy=%s）",
            session_id,
            len(history),
            strategy,
        )

    return {"messages": history, "runtime": runtime}
