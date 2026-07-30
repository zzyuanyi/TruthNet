"""LoadContext — V12 §7.2. 从 session/state 恢复上下文。

Bug fix: 空 {} 导致 LangGraph InvalidUpdateError。
返回至少一个 state key。
"""

from app.agents.state import AgentState


def load_context_node(state: AgentState) -> dict:
    runtime = state.get("runtime")

    return {
        "messages": [],
        "runtime": runtime,
    }
