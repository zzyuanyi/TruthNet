"""LoadContext — V12 §7.2. Mock: return empty context."""

from app.agents.state import AgentState


def load_context_node(state: AgentState) -> dict:
    return {}
