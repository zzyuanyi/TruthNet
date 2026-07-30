"""PersistTurn — V12 §7.2. 保存 turn 状态。

Phase B 最小实现：返回 state 原样通过，不做持久化。
"""

from app.agents.state import AgentState


def persist_turn_node(state: AgentState) -> dict:
    return {
        "messages": [],
    }
