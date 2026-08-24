"""Phase E 成员 A 评估脚本的纯函数回归测试。"""

import pytest

from scripts.phasee_member_a_evaluation import (
    OFFICIAL_CLEAN_XLSX,
    _official_dataset_snapshot,
    assess_raw_traceability,
    compute_route_metrics,
    detect_plausibility_flags,
    effective_route_modules,
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


@pytest.mark.skipif(
    not OFFICIAL_CLEAN_XLSX.is_file(),
    reason="官方 clean.xlsx 未随公共仓库分发",
)
def test_official_dataset_snapshot_matches_77_deep_questions():
    snapshot = _official_dataset_snapshot()
    assert snapshot["question_count"] == 77
    assert snapshot["deep_question_count"] == 77
    assert snapshot["source_validation"] == "passed"
    assert len(snapshot["clean_xlsx_sha256"]) == 64
    assert len(snapshot["sidecar_sha256"]) == 64


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
    assert result["arithmetic_verified"] is True


def test_raw_fields_do_not_pass_when_displayed_arithmetic_is_wrong():
    claim = {
        "rule_id": "R6",
        "text": "其他应收款增速较快（99.9%）",
        "evidence_ids": ["e1", "e2", "e3"],
    }
    evidence = [
        _ev("e1", "oth_rcv", "20251231", "104"),
        _ev("e2", "tot_assets", "20251231", "1000"),
        _ev("e3", "oth_rcv", "20241231", "94.2"),
    ]
    result = assess_raw_traceability(claim, evidence)
    assert result["raw_traceable"] is False
    assert result["arithmetic_verified"] is False
    assert "重算=" in result["reason"]


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
    assert result["micro_recall"] == 0.5
    assert result["by_module"]["finance"]["fn"] == 1


def test_indicator_fast_path_counts_as_finance_family_only_with_raw_evidence():
    statuses = {
        module: {"state": "missing"} for module in ("finance", "equity", "events")
    }
    actual, path = effective_route_modules(
        plan_intent="indicator",
        statuses=statuses,
        evidence_items=[
            {
                "source_type": "financial_statement",
                "field_path": "oper_rev",
                "value": "100",
            }
        ],
    )
    assert actual == ["finance"]
    assert path == "indicator_query"

    actual, path = effective_route_modules(
        plan_intent="indicator", statuses=statuses, evidence_items=[]
    )
    assert actual == []
    assert path == "full_module"


def test_detect_plausibility_flags_marks_zero_quarters_and_extreme_pp():
    flags = detect_plausibility_flags(
        "净利润为正但经营现金流近 0 个季度为负，费用率下降 -168509.0pp"
    )
    assert len(flags) == 2
    assert "0 个季度" in flags[0]
    assert "超过 100" in flags[1]


def test_detect_plausibility_flags_marks_negative_growth_wording():
    flags = detect_plausibility_flags("其他应收款增速较快（-2.3%），建议持续关注")
    assert len(flags) == 1
    assert "负增长 -2.3%" in flags[0]


def test_extreme_ratio_wording_does_not_mistake_data_period_for_ratio():
    flags = detect_plausibility_flags(
        "现金流/利润比呈极端值，具体以原始金额为准（数据期：2026-03-31）"
    )
    assert flags == []
