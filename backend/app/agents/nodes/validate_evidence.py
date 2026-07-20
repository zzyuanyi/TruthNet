"""ValidateEvidenceAndSchema — V12 §7.2. Verify every claim has evidence."""

from app.agents.state import AgentState


def validate_evidence_node(state: AgentState) -> dict:
    claims = state.get("claims", [])
    issues = []
    for claim in claims:
        if not claim.evidence_ids:
            issues.append(f"{claim.claim_id}: no evidence_ids")

    runtime = state.get("runtime")
    if runtime and issues:
        runtime.warnings.extend(issues)
    return {}
