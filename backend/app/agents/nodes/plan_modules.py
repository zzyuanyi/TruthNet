"""PlanModules — V12 §7.2. 根据用户问题确定执行计划。

Phase B 确定性路由：关键词 → 模块选择 → graph 条件边
Phase C 可替换为 LLM 意图识别增强。
"""

from app.agents.state import AgentState, ExecutionPlan


# ── 关键词表 ──────────────────────────────────────────────

_FINANCE_KW = [
    "财务", "造假", "风险", "利润", "收入", "营收", "应收",
    "现金流", "负债", "存货", "毛利", "报表", "勾稽", "盈利",
    "舞弊", "异常",
]

_EQUITY_KW = [
    "股权", "股东", "控制", "穿透", "关联", "实控人", "持股",
]

_EVENTS_KW = [
    "事件", "舆情", "新闻", "公告", "处罚", "调查", "st", "立案",
]

# 综合诊断 — 命中任一词 → 展开三模块（"异常"不在此列，避免"应收异常吗"误扩）
_DIAGNOSIS_KW = [
    "造假", "风险", "舞弊", "是否有问题", "有没有问题",
]


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

    # 宽泛问题 → 默认全模块
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
    if need_finance and need_equity:
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
