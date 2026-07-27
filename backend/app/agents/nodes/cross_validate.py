"""CrossValidate — V12 §7.4. 跨模块一致性检查。

Phase B 最小实现：检查各模块公司、期间一致性。
"""

from app.agents.state import AgentState


def cross_validate_node(state: AgentState) -> dict:
    company = state.get("company")
    results = state.get("results")
    warnings: list[str] = []

    if results:
        if results.equity:
            graph_nodes = results.equity.graph.get("nodes", [])
            if graph_nodes and company:
                equity_entity_ids = [n.get("id", "") for n in graph_nodes]
                if company.entity_id not in equity_entity_ids:
                    warnings.append("股权图不包含目标公司节点")

    # 合并警告到 runtime
    runtime = state.get("runtime")
    if runtime and warnings:
        if hasattr(runtime, "warnings"):
            runtime.warnings.extend(warnings)

    return {
        "runtime": runtime or state.get("runtime"),
        "messages": [],
    }
