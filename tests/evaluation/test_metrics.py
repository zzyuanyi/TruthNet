"""9 项指标计算函数单元测试 — Phase C 评测框架.

验证每个指标: 正常输入 / 空输入 / 缺失数据 / 方向性（好与坏结果能被区分）。
"""

from tests.evaluation.metrics import (
    accuracy,
    entity_retention_rate,
    evidence_coverage,
    evaluate_all,
    industry_variance,
    module_timeout_rate,
    partial_response_rate,
    risk_calibration,
    schema_compliance_rate,
    unverified_claim_ratio,
)


# ── 1. 结果准确率 ────────────────────────────────────────────


def test_accuracy_basic():
    assert (
        accuracy(["triggered", "not_triggered"], ["triggered", "not_triggered"]) == 1.0
    )
    assert accuracy(["triggered"], ["not_triggered"]) == 0.0
    assert accuracy(["a", "b", "c"], ["a", "b", "x"]) == 2 / 3


def test_accuracy_empty():
    assert accuracy([], []) == 0.0


# ── 2. 证据覆盖率 ────────────────────────────────────────────


def test_evidence_coverage_basic():
    claims = [
        {"claim_id": "c1", "evidence_ids": ["ev_1"]},
        {"claim_id": "c2", "evidence_ids": []},
        {"claim_id": "c3", "evidence_ids": ["ev_2", "ev_3"]},
    ]
    assert evidence_coverage(claims) == 2 / 3


def test_evidence_coverage_empty():
    assert evidence_coverage([]) == 0.0


# ── 3. 多轮主体保持率 ────────────────────────────────────────


def test_entity_retention_basic():
    turns = [
        {"company_code": "600518.SH"},
        {"company_code": "600518.SH"},
        {"company_code": "600519.SH"},  # 切换主体，算保持失败
    ]
    assert entity_retention_rate(turns, "600518.SH") == 2 / 3


def test_entity_retention_empty():
    assert entity_retention_rate([], "600518.SH") == 0.0


# ── 4. 无证据 Claim 比例 ─────────────────────────────────────


def test_unverified_ratio_relationship():
    claims = [
        {"claim_id": "c1", "evidence_ids": ["ev_1"]},
        {"claim_id": "c2", "evidence_ids": []},
    ]
    assert unverified_claim_ratio(claims) == 0.5
    assert 1.0 - evidence_coverage(claims) == unverified_claim_ratio(claims)


# ── 5. partial 比例 ──────────────────────────────────────────


def test_partial_rate_basic():
    statuses = [
        {"module": "finance", "state": "success"},
        {"module": "equity", "state": "partial"},
        {"module": "events", "state": "failed"},
    ]
    assert partial_response_rate(statuses) == 2 / 3


def test_partial_rate_empty():
    assert partial_response_rate([]) == 0.0


# ── 6. 模块超时率 ────────────────────────────────────────────


def test_module_timeout_basic():
    modules = [
        {"module_name": "finance", "duration_ms": 1200},
        {"module_name": "finance", "duration_ms": 3500},  # deadline 3000 → timeout
        {"module_name": "events", "duration_ms": 4500},  # deadline 3000 → timeout
    ]
    result = module_timeout_rate(modules)
    assert result["finance"] == 0.5
    assert result["events"] == 1.0


def test_module_timeout_empty():
    assert module_timeout_rate([]) == {}


# ── 7. 风险等级校准 ──────────────────────────────────────────


def test_risk_calibration_perfect():
    r = risk_calibration(["red", "green"], ["red", "green"])
    assert r["accuracy"] == 1.0
    assert r["kappa"] == 1.0


def test_risk_calibration_empty():
    r = risk_calibration([], [])
    assert r["accuracy"] == 0.0


def test_risk_calibration_mismatch_detected():
    r = risk_calibration(["red", "green"], ["red", "red"])
    assert r["accuracy"] == 0.5


# ── 8. 行业分位差异 ──────────────────────────────────────────


def test_industry_variance_basic():
    results = [
        {"industry_l1": "医药", "accuracy": 0.9},
        {"industry_l1": "医药", "accuracy": 0.8},
        {"industry_l1": "电子", "accuracy": 0.5},
    ]
    r = industry_variance(results)
    assert r["max_gap"] > 0
    assert r["min_industry"] == "电子"


def test_industry_variance_empty():
    r = industry_variance([])
    assert r["std_dev"] == 0.0


# ── 9. LLM 输出格式合规率 ────────────────────────────────────


def test_schema_compliance_basic():
    responses = [
        {"rule_id": "R1", "severity": "red", "evidence_ids": ["ev_1"]},
        {"rule_id": "R2", "severity": "orange"},  # 缺 evidence_ids
    ]
    assert schema_compliance_rate(responses) == 0.5


def test_schema_compliance_empty():
    assert schema_compliance_rate([]) == 0.0


# ── 汇总入口 ─────────────────────────────────────────────────


def test_evaluate_all_returns_nine_metrics():
    data = dict(
        ground_truth={
            "rule_results": ["triggered"],
            "risk_levels": ["red"],
        },
        predictions={
            "rule_results": ["triggered"],
            "risk_levels": ["orange"],
            "per_industry": [{"industry_l1": "医药", "accuracy": 0.8}],
            "llm_outputs": [
                {"rule_id": "R1", "severity": "red", "evidence_ids": ["ev_1"]}
            ],
        },
        claims=[{"claim_id": "c1", "evidence_ids": ["ev_1"]}],
        turns=[{"company_code": "600518.SH"}],
        module_statuses=[{"module": "finance", "state": "success"}],
        modules=[{"module_name": "finance", "duration_ms": 1000}],
        expected_entity="600518.SH",
    )
    report = evaluate_all(**data)
    assert set(report.keys()) == {
        "1_accuracy",
        "2_evidence_coverage",
        "3_entity_retention_rate",
        "4_unverified_claim_ratio",
        "5_partial_response_rate",
        "6_module_timeout_rate",
        "7_risk_calibration",
        "8_industry_variance",
        "9_schema_compliance_rate",
    }
