"""LoadContext — V12 §7.2. 从 session 恢复上下文。

按 session_id 回读最近 N 轮 (question, answer)，组装为 messages 历史
注入 state，供 memory 节点做指代消解（公司/指标从文本提取，
company_code 当前无消费者，不入库查询）。

Phase C 集成修正:
- 恢复窗口由配置项 MEMORY_RECENT_TURNS 控制，默认 20 轮，满足长对话验收。
- 支持 SQL_BACKEND 双后端（sqlite lite / mysql full），lite 模式同样可
  从 SQLite conversation_turns 恢复历史。
- 数据库不可用/异常时保持占位行为（返回空历史，不阻断图执行）。

Bug fix: 空 {} 会导致 LangGraph InvalidUpdateError，始终返回 state key。
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)


def _history_limit() -> int:
    """回读最近轮次上限（默认 20 轮，由 MEMORY_RECENT_TURNS 配置）。"""
    return max(int(settings.MEMORY_RECENT_TURNS), 0)


def _parse_json_meta(value) -> dict:
    """response_meta 双形态解析（共享实现，最终续审 §7 D1）。

    ORM JSON 列可能已反序列化为 dict，原生 SQL 查询返回 JSON 字符串；
    坏 JSON/None 回退空 dict（调用方 fallback company_code）。
    """
    from app.application.services.response_meta_utils import parse_response_meta

    return parse_response_meta(value)


def _get_engine() -> Engine:
    """惰性缓存引擎，尊重 SQL_BACKEND（sqlite/mysql）。

    8/19 全面审查：改用完整 profile key + 切 profile 即 dispose 旧 Engine
    （与 _fetch._ENGINES 同契约）——load_context 回读历史消息驱动指代消解，
    backend-only key 缓存在切库后会命中旧库，产出错误轮次数据。
    """
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def _session_id(state: AgentState) -> str | None:
    """从 runtime 获取会话 ID。"""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    sid = getattr(runtime, "session_id", "") or ""
    return sid or None


def _user_id(state: AgentState) -> str:
    """从 runtime 获取用户 ID；未传时归属默认本地用户。"""
    runtime = state.get("runtime")
    user_id = getattr(runtime, "user_id", "") if runtime is not None else ""
    return (user_id or "").strip() or settings.SESSION_DEFAULT_USER_ID


def _session_owned_and_active(session_id: str, user_id: str) -> bool:
    """会话归属校验：历史 NULL user_id 只归默认用户。"""
    with _get_engine().connect() as conn:
        found = conn.execute(
            text(
                "SELECT 1 FROM conversation_sessions "
                "WHERE session_id = :sid "
                "AND COALESCE(user_id, :default_user_id) = :user_id "
                "AND COALESCE(status, 'active') != 'archived' "
                "LIMIT 1"
            ),
            {
                "sid": session_id,
                "user_id": user_id,
                "default_user_id": settings.SESSION_DEFAULT_USER_ID,
            },
        ).scalar()
    return bool(found)


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
        return {
            "messages": [],
            "memory_summary": None,
            "recent_company_codes": [],
            "recent_executed_metrics": [],
            "runtime": runtime,
        }

    strategy = settings.MEMORY_STRATEGY
    history: list[dict] = []
    user_id = _user_id(state)

    try:
        if not _session_owned_and_active(session_id, user_id):
            return {
                "messages": [],
                "memory_summary": None,
                "recent_company_codes": [],
                "recent_executed_metrics": [],
                "runtime": runtime,
            }
    except Exception:
        logger.exception("LoadContext 会话归属校验失败: session=%s", session_id)
        return {
            "messages": [],
            "memory_summary": None,
            "recent_company_codes": [],
            "recent_executed_metrics": [],
            "runtime": runtime,
        }

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

    # 近期轮次的公司代码（DESC 顺序 = 最近优先，去重保序）
    recent_company_codes: list[str] = []
    try:
        with _get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT question, answer, company_code, response_meta "
                        "FROM conversation_turns "
                        "WHERE session_id = :sid "
                        "ORDER BY turn_index DESC LIMIT :limit"
                    ),
                    {"sid": session_id, "limit": _history_limit()},
                )
                .mappings()
                .all()
            )
    except Exception:
        logger.exception("LoadContext 读取失败: session=%s", session_id)
        return {
            "messages": history,
            "memory_summary": summary.to_dict() if summary else None,
            "recent_company_codes": [],
            "recent_executed_metrics": [],
            "runtime": runtime,
        }

    # 倒序结果反转 → 按时间升序注入（消息注入）
    for row in reversed(rows):
        q = str(row["question"] or "")
        a = str(row["answer"] or "")
        if q:
            history.append({"role": "user", "content": q})
        if a:
            history.append({"role": "assistant", "content": a})

    # recent_company_codes 单独遍历原始 rows（DESC = 最近优先，P1-1）：
    # 不能随 reversed() 收集——那会把顺序反成最旧在前。
    # v3.3.2-R1 §8.1：优先该轮活跃主体（response_meta.active_company_code，
    # comparison/reference 的 primary 也持久化于此），fallback company_code
    # v3.3.3 批次 B：同样从 response_meta 收集最近成功 executed_metrics
    # （仅 status=ok；收口批次 B 按 (company_code, metric_id) 去重保序，
    # 最近优先——切换公司后同指标记录不互相覆盖）
    recent_executed_metrics: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in rows:
        code = str(row["company_code"] or "").strip()
        # 老数据/测试 fake rows 可能无 response_meta 列
        meta = _parse_json_meta(
            row["response_meta"] if "response_meta" in row else None
        )
        active = str(meta.get("active_company_code") or "").strip()
        if active:
            code = active
        if code and code not in recent_company_codes:
            recent_company_codes.append(code)
        for item in meta.get("executed_metrics") or []:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "ok":
                continue
            metric_id = str(item.get("metric_id") or "").strip()
            # 收口批次 B（方案 §3.4）：记录公司归属；旧记录无 company_code
            # 时以该轮活跃主体回填，仍无则保留空归属（不得用于跨指标比较）
            item_code = str(item.get("company_code") or "").strip() or code
            key = (item_code, metric_id)
            if not metric_id or key in seen_keys:
                continue
            seen_keys.add(key)
            recent_executed_metrics.append(
                {
                    "metric_id": metric_id,
                    "period": str(item.get("period") or ""),
                    "unit": str(item.get("unit") or ""),
                    "status": "ok",
                    "company_code": item_code,
                }
            )

    if history:
        logger.info(
            "LoadContext: session=%s 恢复 %d 条历史消息（strategy=%s）",
            session_id,
            len(history),
            strategy,
        )

    return {
        "messages": history,
        "memory_summary": summary.to_dict() if summary else None,
        "recent_company_codes": recent_company_codes,
        "recent_executed_metrics": recent_executed_metrics,
        "runtime": runtime,
    }
