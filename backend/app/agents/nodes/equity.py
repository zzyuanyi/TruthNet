"""Equity — V12 §8.6. Mock: return sample ownership chain."""

from app.agents.state import (
    AgentState,
    ModuleStatus,
    EvidenceRef,
    EquityResult,
    ModuleResults,
)


def equity_node(state: AgentState) -> dict:
    return {
        "module_status": {"equity": ModuleStatus(state="success", duration_ms=200)},
        "results": ModuleResults(
            equity=EquityResult(
                graph={
                    "nodes": [
                        {"id": "person_01", "label": "马兴田", "type": "person"},
                        {"id": "company_02", "label": "康美实业", "type": "company"},
                        {
                            "id": "company_600518_SH",
                            "label": "康美药业",
                            "type": "listed_company",
                        },
                    ],
                    "edges": [
                        {
                            "source": "person_01",
                            "target": "company_02",
                            "relation": "99.7%",
                        },
                        {
                            "source": "company_02",
                            "target": "company_600518_SH",
                            "relation": "30.1%",
                        },
                    ],
                },
                chains=[
                    {
                        "path": ["马兴田", "康美实业", "康美药业"],
                        "total_stake": 0.301,
                        "depth": 2,
                    }
                ],
                evidence=[
                    EvidenceRef(
                        evidence_id="ev_eq_01",
                        source_type="ownership_record",
                        field_path="s_holder_pct",
                        period="2024-12-31",
                        value="30.1%",
                        source_title="十大股东",
                    )
                ],
            )
        ),
    }
