"""PlanModules — V12 §7.2. Mock: always diagnose with 3 modules."""

from app.agents.state import AgentState, ExecutionPlan


def plan_modules_node(state: AgentState) -> dict:
    return {
        "plan": ExecutionPlan(
            intent="diagnose",
            requested_modules=["finance", "equity", "events"],
            cross_checks=["financial_vs_cashflow", "equity_vs_events"],
        )
    }
