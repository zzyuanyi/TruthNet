from app.agents.state import EvidenceRef, FinanceResult
from app.application.services.risk_derivation_service import (
    build_risk_derivation_chains,
)
from app.domain.risk.models import RiskOutput, RiskPatternMatch, RiskSubScore


def _finance() -> FinanceResult:
    evidence = EvidenceRef(
        evidence_id="ev_fin_r1",
        source_type="financial_statement",
        source_record_id="600518.SH|20251231|408006000",
        field_path="acct_rcv",
        period="20251231",
        value="123.4",
        unit="CNY",
    )
    return FinanceResult(
        rule_statuses={"R1": "triggered"},
        rule_details={
            "R1": {
                "rule_name": "应收与收入增速背离",
                "severity": "orange",
                "explanation": "应收账款增速显著高于营业收入。",
                "current": {"acct_rcv_growth": {"value": 45.0, "unit": "percent"}},
                "history": [{"period": "20251231", "acct_rcv_growth": 45.0}],
                "evidence_ids": ["ev_fin_r1"],
            }
        },
        industry_benchmark={"percentiles": {"r1_gap": 92.0}},
        evidence=[evidence],
    )


def test_derivation_contains_rule_metric_percentile_and_evidence():
    output = RiskOutput(
        wind_code="600518.SH",
        risk_level="orange",
        pattern_matches=[
            RiskPatternMatch(
                pattern_id="P1",
                pattern_name="收入提前确认",
                triggered_rules=["R1"],
            )
        ],
    )
    chains = build_risk_derivation_chains(output, _finance())
    by_id = {chain.conclusion_id: chain for chain in chains}

    assert {"overall_risk", "rule:R1", "pattern:P1"} <= set(by_id)
    signal = by_id["rule:R1"].signals[0]
    assert signal.explanation == "应收账款增速显著高于营业收入。"
    assert signal.current["acct_rcv_growth"]["value"] == 45.0
    assert signal.history[0]["period"] == "20251231"
    assert signal.industry_percentile == 92.0
    assert signal.data_refs[0].period == "20251231"
    assert signal.data_refs[0].evidence_id == "ev_fin_r1"
    assert by_id["pattern:P1"].evidence_ids == ["ev_fin_r1"]


def test_overall_chain_uses_dimensions_when_no_rule_triggered():
    output = RiskOutput(
        wind_code="600518.SH",
        risk_level="green",
        sub_scores=[
            RiskSubScore(
                dimension="finance",
                label="财务勾稽",
                score=0.1,
                weight=0.4,
                contribution=0.04,
                status="success",
            )
        ],
    )
    chains = build_risk_derivation_chains(output, FinanceResult())
    assert chains[0].conclusion == "综合风险等级：绿色"
    assert chains[0].signals[0].signal_type == "dimension"
