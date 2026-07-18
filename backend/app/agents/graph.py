"""Agent Graph — V12 baseline.

LangGraph StateGraph 编排骨架。
当前只定义图结构，不实现真实 Agent 逻辑。
"""

from app.agents.state import AgentState


def create_agent_graph():
    """创建 LangGraph StateGraph 实例 (骨架).

    TODO: 实现完整的 Agent 编排流程。
    节点：memory → intent → route → execute → answer
    """
    try:
        from langgraph.graph import StateGraph

        graph = StateGraph(AgentState)

        # TODO: 添加节点
        # graph.add_node("memory", memory_node)
        # graph.add_node("intent", intent_node)
        # graph.add_node("finance", finance_node)
        # graph.add_node("equity", equity_node)
        # graph.add_node("qa", qa_node)

        # TODO: 添加边和条件路由
        # graph.set_entry_point("memory")
        # graph.add_edge("memory", "intent")
        # graph.add_conditional_edges("intent", router, {...})
        # graph.add_edge("qa", END)

        return graph

    except ImportError:
        return None


# 模块级实例（骨架）
agent_graph = create_agent_graph()
