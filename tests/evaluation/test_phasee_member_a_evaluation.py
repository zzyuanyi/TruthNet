"""Phase E 成员 A 评估脚本的纯函数回归测试。"""

from scripts.phasee_member_a_evaluation import (
    assess_raw_traceability,
    compute_route_metrics,
    detect_plausibility_flags,
    extract_numeric_mentions,
)


def _ev(evidence_id: str, field: str, period: str, value: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "field_path": field,
        "period": period,
        "value": value,
        "source_excerpt": "其他应收款增速 10.4%",
    }


def test_extract_numeric_mentions_excludes_date_and_stock_code():
    text = "600518.SH：近 2 个季度比率 -6.2，增速 47.9%（2025-12-31）"
    assert extract_numeric_mentions(text) == ["2 个季度", "47.9%"]


def test_r6_growth_is_not_raw_traceable_with_single_period():
    claim = {
        "rule_id": "R6",
        "text": "其他应收款增速较快（10.4%）",
        "evidence_ids": ["e1", "e2"],
    }
    evidence = [
        _ev("e1", "oth_rcv", "20251231", "104"),
        _ev("e2", "tot_assets", "20251231", "1000"),
    ]
    result = assess_raw_traceability(claim, evidence)
    assert result["all_evidence_ids_resolved"] is True
    assert result["excerpt_replay"] is True
    assert result["raw_traceable"] is False
    assert "基期" in result["reason"]


def test_r6_growth_is_raw_traceable_with_current_and_base_periods():
    claim = {
        "rule_id": "R6",
        "text": "其他应收款增速较快（10.4%）",
        "evidence_ids": ["e1", "e2", "e3"],
    }
    evidence = [
        _ev("e1", "oth_rcv", "20251231", "104"),
        _ev("e2", "tot_assets", "20251231", "1000"),
        _ev("e3", "oth_rcv", "20241231", "94.2"),
    ]
    result = assess_raw_traceability(claim, evidence)
    assert result["raw_traceable"] is True


def test_compute_route_metrics_separates_precision_and_recall():
    records = [
        {
            "category": "财务",
            "expected_modules": ["finance"],
            "actual_modules": [],
        },
        {
            "category": "股权",
            "expected_modules": ["equity"],
            "actual_modules": ["equity"],
        },
    ]
    result = compute_route_metrics(records)
    assert result["required_hit_rate"] == 0.5
    assert result["exact_match_rate"] == 0.5
    assert result["micro_precision"] == 1.0
    assert result["by_module"]["finance"]["fn"] == 1


def test_detect_plausibility_flags_marks_zero_quarters_and_extreme_pp():
    flags = detect_plausibility_flags(
        "净利润为正但经营现金流近 0 个季度为负，费用率下降 -168509.0pp"
    )
    assert len(flags) == 2
    assert "0 个季度" in flags[0]
    assert "超过 100" in flags[1]
