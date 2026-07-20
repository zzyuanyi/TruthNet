"""ResolveEntity — V12 §7.2. Mock: hardcoded Kangmei."""

from app.agents.state import AgentState, CompanyRef


def resolve_entity_node(state: AgentState) -> dict:
    return {
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
            industry_l1="中药",
        )
    }
