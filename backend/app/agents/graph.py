"""Agent Graph — V12 §7.1.

LangGraph StateGraph: LoadContext → ResolveEntity → PlanModules
→ Finance → Equity → Events → CrossValidate → BuildClaims
→ GenerateAnswer → ValidateEvidence → PersistTurn
"""

from langgraph.graph import END, StateGraph

from app.agents.nodes.build_claims import build_claims_node
from app.agents.nodes.cross_validate import cross_validate_node
from app.agents.nodes.equity import equity_node
from app.agents.nodes.events import events_node
from app.agents.nodes.finance import finance_node
from app.agents.nodes.generate_answer import generate_answer_node
from app.agents.nodes.load_context import load_context_node
from app.agents.nodes.persist_turn import persist_turn_node
from app.agents.nodes.plan_modules import plan_modules_node
from app.agents.nodes.resolve_entity import resolve_entity_node
from app.agents.nodes.validate_evidence import validate_evidence_node
from app.agents.state import AgentState


def _after_resolve(state: AgentState) -> str:
    """ResolveEntity 条件路由。"""
    if state.get("company") is None:
        return "no_company"
    return "continue"


def _after_plan(state: AgentState) -> str:
    """PlanModules 条件路由。"""
    plan = state.get("plan")
    if plan is None:
        return "no_plan"
    if plan.intent == "simple_query":
        return "simple"
    return "diagnose"


def create_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # nodes
    graph.add_node("load_context", load_context_node)
    graph.add_node("resolve_entity", resolve_entity_node)
    graph.add_node("plan_modules", plan_modules_node)
    graph.add_node("finance", finance_node)
    graph.add_node("equity", equity_node)
    graph.add_node("events", events_node)
    graph.add_node("cross_validate", cross_validate_node)
    graph.add_node("build_claims", build_claims_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("validate_evidence", validate_evidence_node)
    graph.add_node("persist_turn", persist_turn_node)

    # edges: linear chain with conditional fallbacks
    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "resolve_entity")

    graph.add_conditional_edges(
        "resolve_entity",
        _after_resolve,
        {"continue": "plan_modules", "no_company": "generate_answer"},
    )

    graph.add_conditional_edges(
        "plan_modules",
        _after_plan,
        {"diagnose": "finance", "simple": "build_claims", "no_plan": "generate_answer"},
    )

    # serial for Phase B; Phase C fan-out with Send
    graph.add_edge("finance", "equity")
    graph.add_edge("equity", "events")
    graph.add_edge("events", "cross_validate")
    graph.add_edge("cross_validate", "build_claims")
    graph.add_edge("build_claims", "generate_answer")
    graph.add_edge("generate_answer", "validate_evidence")
    graph.add_edge("validate_evidence", "persist_turn")
    graph.add_edge("persist_turn", END)

    return graph


agent_graph = create_agent_graph()
