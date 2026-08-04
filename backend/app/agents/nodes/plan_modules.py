"""PlanModules — V12 §7.2. 根据用户问题确定执行计划。

混合路由（Phase D 增强）：
  1. 关键词强命中（财务/股权/事件/诊断词表）→ 确定性模块选择（保留）
  2. 关键词未命中（口语化/同义表达）→ LLM 意图识别兜底
     （structured_chat 输出 finance/equity/events 布尔）
  3. LLM 失败/超时/全 False → 全模块保守展开（不丢信息）
"""

import logging

from pydantic import BaseModel

from app.agents.state import AgentState, ExecutionPlan

logger = logging.getLogger(__name__)


class _IntentResult(BaseModel):
    """LLM 意图识别输出：三个业务模块是否需要执行。"""

    finance: bool = False
    equity: bool = False
    events: bool = False


# ── 关键词表 ──────────────────────────────────────────────

_FINANCE_KW = [
    "财务",
    "造假",
    "风险",
    "利润",
    "收入",
    "营收",
    "应收",
    "现金流",
    "负债",
    "存货",
    "毛利",
    "报表",
    "勾稽",
    "盈利",
    "舞弊",
    "异常",
]

_EQUITY_KW = [
    "股权",
    "股东",
    "控制",
    "穿透",
    "关联",
    "实控人",
    "持股",
]

_EVENTS_KW = [
    "事件",
    "舆情",
    "新闻",
    "公告",
    "处罚",
    "调查",
    "st",
    "立案",
]

# 综合诊断 — 命中任一词 → 展开三模块（"异常"不在此列，避免"应收异常吗"误扩）
_DIAGNOSIS_KW = [
    "造假",
    "风险",
    "舞弊",
    "是否有问题",
    "有没有问题",
]


def _llm_intent_fallback(user_query: str) -> _IntentResult | None:
    """关键词未命中时，用 LLM 识别意图；失败/超时 → None（调用方全模块兜底）。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是财报问答系统的意图识别器。判断用户问题需要哪些分析模块："
                "finance（财务指标/规则/报表）、equity（股权/股东/控制链）、"
                "events（舆情/公告/事件/评级）。"
                '输出 JSON：{"finance": bool, "equity": bool, "events": bool}。'
                "不确定或宽泛问题时全部设为 true（保守展开）。"
            ),
        },
        {"role": "user", "content": f"用户问题：{user_query}"},
    ]
    try:
        from app.agents.llm_sync import run_llm_structured

        return run_llm_structured(messages, _IntentResult)
    except Exception:  # noqa: BLE001 — 意图识别失败走全模块兜底
        logger.warning("plan_modules: LLM 意图识别失败，全模块兜底", exc_info=True)
        return None


def plan_modules_node(state: AgentState) -> dict:
    user_query = state.get("user_query", "")
    company = state.get("company")

    if company is None:
        return {
            "plan": ExecutionPlan(
                intent="simple_query",
                requested_modules=[],
                cross_checks=[],
            )
        }

    ql = user_query.lower()

    need_finance = any(kw in ql for kw in _FINANCE_KW)
    need_equity = any(kw in ql for kw in _EQUITY_KW)
    need_events = any(kw in ql for kw in _EVENTS_KW)

    # 综合诊断 → 展开全部模块
    if any(kw in ql for kw in _DIAGNOSIS_KW):
        need_finance = need_equity = need_events = True

    # 关键词未命中 → LLM 语义识别兜底（口语化/同义表达）
    if not need_finance and not need_equity and not need_events:
        intent = _llm_intent_fallback(user_query)
        if intent is not None:
            need_finance = intent.finance
            need_equity = intent.equity
            need_events = intent.events
        # intent 为 None（LLM 失败）或全 False → 走下方全模块兜底

    # 宽泛问题/LLM 未识别 → 默认全模块
    if not need_finance and not need_equity and not need_events:
        need_finance = need_equity = need_events = True

    modules = []
    if need_finance:
        modules.append("finance")
    if need_equity:
        modules.append("equity")
    if need_events:
        modules.append("events")

    cross_checks = []
    if need_equity and need_events:
        cross_checks.append("equity_vs_events")
    if need_finance and len(modules) >= 2:
        cross_checks.append("financial_vs_cashflow")

    return {
        "plan": ExecutionPlan(
            intent="diagnose" if len(modules) >= 2 else "simple_query",
            requested_modules=modules,
            cross_checks=cross_checks,
        )
    }
