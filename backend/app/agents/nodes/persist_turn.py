"""PersistTurn — V12 §7.2. Mock: no-op."""

from app.agents.state import AgentState


def persist_turn_node(state: AgentState) -> dict:
    return {}
