"""Build deterministic derivation chains for company profile risk conclusions."""

from __future__ import annotations

from app.domain.risk.models import (
    RiskDataReference,
    RiskDerivationChain,
    RiskDerivationSignal,
    RiskOutput,
)
from app.domain.risk.severity import risk_level_label

_RULE_PERCENTILE_METRIC = {
    "R1": "r1_gap",
    "R2": "r2_cf_ratio",
    "R3": "r3_cash_to_assets",
    "R4": "r4_growth_gap",
    "R6": "r6_oth_rcv_to_assets",
}


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _rule_signals(finance_result) -> dict[str, RiskDerivationSignal]:
    if finance_result is None:
        return {}
    details = getattr(finance_result, "rule_details", {}) or {}
    statuses = getattr(finance_result, "rule_statuses", {}) or {}
    evidence_index = {
        item.evidence_id: item
        for item in (getattr(finance_result, "evidence", []) or [])
    }
    benchmark = getattr(finance_result, "industry_benchmark", {}) or {}
    percentiles = benchmark.get("percentiles") or {}
    signals: dict[str, RiskDerivationSignal] = {}
    for rule_id, detail in details.items():
        if statuses.get(rule_id) != "triggered":
            continue
        evidence_ids = _unique(list(detail.get("evidence_ids") or []))
        refs = []
        for evidence_id in evidence_ids:
            evidence = evidence_index.get(evidence_id)
            if evidence is None:
                continue
            refs.append(
                RiskDataReference(
                    evidence_id=evidence_id,
                    source_type=evidence.source_type,
                    field_path=evidence.field_path or "",
                    period=evidence.period or "",
                    value=evidence.value,
                    unit=evidence.unit,
                )
            )
        metric_id = _RULE_PERCENTILE_METRIC.get(rule_id, "")
        signals[rule_id] = RiskDerivationSignal(
            signal_id=rule_id,
            signal_type="rule",
            label=detail.get("rule_name") or rule_id,
            severity=detail.get("severity") or "unknown",
            explanation=detail.get("explanation") or "",
            current=dict(detail.get("current") or {}),
            industry_percentile=percentiles.get(metric_id) if metric_id else None,
            data_refs=refs,
            evidence_ids=evidence_ids,
        )
    return signals


def _dimension_signals(output: RiskOutput) -> list[RiskDerivationSignal]:
    return [
        RiskDerivationSignal(
            signal_id=f"dimension:{item.dimension}",
            signal_type="dimension",
            label=item.label,
            severity="unknown",
            explanation=(
                f"维度得分 {item.score:.3f}，权重 {item.weight:.1%}，"
                f"对综合分贡献 {item.contribution:.3f}，状态 {item.status}。"
            ),
        )
        for item in output.sub_scores
    ]


def build_risk_derivation_chains(
    output: RiskOutput, finance_result
) -> list[RiskDerivationChain]:
    """Assemble overall, triggered-rule and pattern derivation chains."""
    rule_signals = _rule_signals(finance_result)
    overall_signals = list(rule_signals.values()) or _dimension_signals(output)
    overall_evidence = _unique(
        [eid for signal in overall_signals for eid in signal.evidence_ids]
    )
    level_text = (
        "数据不足"
        if output.risk_level == "unknown"
        else risk_level_label(output.risk_level)
    )
    chains = [
        RiskDerivationChain(
            conclusion_id="overall_risk",
            conclusion_type="risk_level",
            conclusion=f"综合风险等级：{level_text}",
            risk_level=output.risk_level,
            signals=overall_signals,
            evidence_ids=overall_evidence,
        )
    ]

    for rule_id, signal in rule_signals.items():
        chains.append(
            RiskDerivationChain(
                conclusion_id=f"rule:{rule_id}",
                conclusion_type="rule_trigger",
                conclusion=f"{rule_id} {signal.label}已触发",
                risk_level=signal.severity,
                signals=[signal],
                evidence_ids=signal.evidence_ids,
            )
        )

    for pattern in output.pattern_matches:
        signals = [
            rule_signals[rule_id]
            for rule_id in pattern.triggered_rules
            if rule_id in rule_signals
        ]
        evidence_ids = _unique(
            [eid for signal in signals for eid in signal.evidence_ids]
        )
        chains.append(
            RiskDerivationChain(
                conclusion_id=f"pattern:{pattern.pattern_id}",
                conclusion_type="pattern_match",
                conclusion=f"匹配风险模式：{pattern.pattern_name}",
                risk_level=output.risk_level,
                signals=signals,
                evidence_ids=evidence_ids,
            )
        )
    return chains
