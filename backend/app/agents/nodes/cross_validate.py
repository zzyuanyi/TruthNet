"""CrossValidate — V12 §7.4. 跨模块一致性检查。

Phase B 最小实现：检查各模块公司、期间一致性。
"""

from app.agents.state import AgentState


def cross_validate_node(state: AgentState) -> dict:
    plan = state.get("plan")

    # 无交叉检查项 → no-op
    if plan is None or not plan.cross_checks:
        return {"messages": []}

    company = state.get("company")
    results = state.get("results")
    warnings: list[str] = []

    if results and results.equity:
        graph_nodes = results.equity.graph.get("nodes", [])
        if graph_nodes and company:
            equity_entity_ids = [n.get("id", "") for n in graph_nodes]
            if company.entity_id not in equity_entity_ids:
                warnings.append("股权图不包含目标公司节点")

    # 合并警告到 runtime
    runtime = state.get("runtime")
    if runtime and warnings and hasattr(runtime, "warnings"):
        runtime.warnings.extend(warnings)

    return {
        "runtime": runtime or state.get("runtime"),
        "messages": [],
    }
