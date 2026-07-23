"""Finance — V12 §8.1. Mock: return sample rule results."""

from app.agents.state import (
    AgentState,
    ModuleStatus,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
)


def finance_node(state: AgentState) -> dict:
    return {
        "module_status": {"finance": ModuleStatus(state="success", duration_ms=120)},
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={
                    "R1": "triggered",
                    "R2": "triggered",
                    "R3": "triggered",
                    "R4": "not_triggered",
                    "R5": "insufficient_data",
                    "R6": "not_applicable",
                    "R7": "not_triggered",
                },
                warnings=["R1 应收-营收背离: 47.2% vs 12.1%", "R2 现金流-利润背离"],
                evidence=[
                    EvidenceRef(
                        evidence_id="ev_bs_01",
                        source_type="balance_sheet",
                        field_path="acct_rcv",
                        period="2025Q3",
                        value="47.2%",
                        source_title="资产负债表",
                    )
                ],
            )
        ),
    }
