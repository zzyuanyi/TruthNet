"""PlanModules — V12 §7.2. 根据用户问题确定执行计划。

Bug fix: 不再无条件返回 diagnose 三个模块。
根据问题关键词判断是否需要执行特定模块。
"""

from app.agents.state import AgentState, ExecutionPlan


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

    # 关键词检测
    need_finance = any(
        kw in ql
        for kw in [
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
        ]
    )
    need_equity = any(
        kw in ql
        for kw in [
            "股权",
            "股东",
            "控制",
            "穿透",
            "关联",
            "实控人",
            "持股",
        ]
    )
    need_events = any(
        kw in ql
        for kw in [
            "事件",
            "舆情",
            "新闻",
            "公告",
            "处罚",
            "调查",
            "st",
            "立案",
        ]
    )

    # 如果问题很宽泛（如"有造假风险吗"），默认执行全部模块
    if not need_finance and not need_equity and not need_events:
        need_finance = True
        need_equity = True
        need_events = True

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
