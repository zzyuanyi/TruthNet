"""BuildClaimsAndEvidence — V12 §9.2. Mock: build claims from results."""

from app.agents.state import AgentState, Claim


def build_claims_node(state: AgentState) -> dict:
    results = state.get("results")
    claims = []

    if results and results.finance and results.finance.rule_statuses:
        for rule_id, status in results.finance.rule_statuses.items():
            if status == "triggered":
                claims.append(
                    Claim(
                        claim_id=f"claim_{rule_id}_01",
                        text=f"规则 {rule_id} 触发：康美药业存在财务异常信号",
                        claim_type="financial",
                        severity="red" if rule_id in ("R1", "R2") else "orange",
                        rule_id=rule_id,
                        rule_version="1.0.0",
                        evidence_ids=["ev_bs_01"],
                    )
                )

    if results and results.equity and results.equity.chains:
        claims.append(
            Claim(
                claim_id="claim_eq_01",
                text="康美药业控制链穿透: 马兴田→康美实业→康美药业, 最终控制30.1%",
                claim_type="equity",
                severity="red",
                evidence_ids=["ev_eq_01"],
            )
        )

    if results and results.events and results.events.timeline:
        claims.append(
            Claim(
                claim_id="claim_events_01",
                text="康美药业存在多项负面事件，含证监会立案调查及ST",
                claim_type="event",
                severity="red",
                evidence_ids=["ev_ev_01"],
            )
        )

    return {"claims": claims}
