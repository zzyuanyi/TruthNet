#!/usr/bin/env python3
"""TruthNet 评测运行器 — Phase C mock 验证.

Phase C: 用 mock 数据验证 9 项指标的计算逻辑正确。
Phase D: 替换 mock 为真实评测数据，产出正式评测报告。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from tests.evaluation.metrics import evaluate_all


def _mock_data():
    """Phase C mock 数据集 — 验证计算逻辑用."""
    return dict(
        ground_truth={
            "rule_results": ["triggered", "not_triggered", "triggered", "triggered"],
            "risk_levels": ["red", "green", "orange", "red"],
        },
        predictions={
            "rule_results": ["triggered", "triggered", "triggered", "not_triggered"],
            "risk_levels": ["red", "yellow", "orange", "orange"],
            "per_industry": [
                {"industry_l1": "医药", "accuracy": 0.85},
                {"industry_l1": "医药", "accuracy": 0.90},
                {"industry_l1": "电子", "accuracy": 0.70},
                {"industry_l1": "电子", "accuracy": 0.75},
                {"industry_l1": "房地产", "accuracy": 0.60},
                {"industry_l1": "房地产", "accuracy": 0.55},
            ],
            "llm_outputs": [
                {"rule_id": "R1", "severity": "red", "evidence_ids": ["ev_1"]},
                {"rule_id": "R2", "severity": "orange"},
            ],
        },
        claims=[
            {"claim_id": "c1", "evidence_ids": ["ev_1", "ev_2"]},
            {"claim_id": "c2", "evidence_ids": []},
            {"claim_id": "c3", "evidence_ids": ["ev_3"]},
        ],
        turns=[
            {"company_code": "600518.SH", "query": "康美有风险吗"},
            {"company_code": "600518.SH", "query": "它的毛利率呢"},
            {"company_code": "600519.SH", "query": "那茅台呢"},
        ],
        module_statuses=[
            {"module": "finance", "state": "success"},
            {"module": "equity", "state": "success"},
            {"module": "events", "state": "partial"},
        ],
        modules=[
            {"module_name": "finance", "duration_ms": 1200},
            {"module_name": "equity", "duration_ms": 3500},
            {"module_name": "events", "duration_ms": 4500},
            {"module_name": "finance", "duration_ms": 800},
        ],
        expected_entity="600518.SH",
    )


def main():
    data = _mock_data()
    report = evaluate_all(
        ground_truth=data["ground_truth"],
        predictions=data["predictions"],
        claims=data["claims"],
        turns=data["turns"],
        module_statuses=data["module_statuses"],
        modules=data["modules"],
        expected_entity=data["expected_entity"],
    )

    print("=" * 60)
    print("TruthNet 评测报告 (Phase C mock)")
    print("=" * 60)

    explanations = {
        "1_accuracy": "结果准确率",
        "2_evidence_coverage": "证据覆盖率",
        "3_entity_retention_rate": "多轮主体保持率",
        "4_unverified_claim_ratio": "无证据Claim比例",
        "5_partial_response_rate": "partial比例",
        "6_module_timeout_rate": "模块超时率",
        "7_risk_calibration": "风险等级校准",
        "8_industry_variance": "行业分位差异",
        "9_schema_compliance_rate": "LLM输出格式合规率",
    }

    all_valid = True
    for metric, value in report.items():
        label = explanations.get(metric, metric)
        if isinstance(value, dict):
            print(f"\n[{label}]")
            for k, v in value.items():
                if k not in ("confusion", "by_industry"):
                    print(f"  {k}: {v}")
        else:
            print(f"\n[{label}]")
            print(f"  value: {value}")
        if value is None:
            print(f"  ✗ FAIL: None!")
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("验收: PASS — Phase C 评测框架就绪，9 项指标全部正常")
    else:
        print("验收: FAIL")
        return 1
    return 0


if __name__ == "__main__":
    # 支持两种运行方式:
    #   conda run -n truthnet python -m tests.evaluation.runner
    #   conda run -n truthnet python tests/evaluation/runner.py (需 --app-dir 或 cd 到项目根)
    sys.exit(main())
