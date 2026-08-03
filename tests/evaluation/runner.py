#!/usr/bin/env python3
"""TruthNet 评测运行器 — 9 项指标 calculator/target 状态分离.

Phase C 语义（对应集成验收 §9.2）:
- calculator_status: 指标计算函数是否正常运行（passed / failed）。
- target_status: 指标值是否达到生产目标（passed / failed / not_applicable）。
  两者必须分开报告 —— "函数能算" 不等于 "生产达标"。
- 默认使用内置 mock 数据验证计算逻辑；可通过 --manifest 加载 1410/77 评测集。
- 输出 UTF-8 文本报告；--json 输出机器可读 JSON。
- 退出码:
    0  框架运行正常（无论目标是否达成）
    2  非法输入 / 参数错误
    3  指标计算异常（区别于业务不达标）
- 不访问网络、不读取生产密钥、不修改评测标签、不覆盖原始结果。
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
# root 必须在 backend 之前：否则 backend/tests 遮蔽根目录 tests 包，
# `python tests/evaluation/runner.py` 直接执行时 ModuleNotFoundError。
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from tests.evaluation.metrics import evaluate_all  # noqa: E402

# ── 9 项指标生产目标（方向 + 阈值）─────────────────────────────
# 来自 tests/evaluation/README.md §2（与文档口径严格一致）。
# 方向: min=不低于, max=不高于。
TARGETS: dict[str, dict] = {
    "1_accuracy": {"direction": "min", "threshold": 0.70},
    "2_evidence_coverage": {"direction": "min", "threshold": 0.90},
    "3_entity_retention_rate": {
        "direction": "min",
        "threshold": 0.85,
    },  # README §2 指标3
    "4_unverified_claim_ratio": {"direction": "max", "threshold": 0.10},
    "5_partial_response_rate": {
        "direction": "max",
        "threshold": 0.20,
    },  # README §2 指标5
    # 6 为按模块的 dict，单独处理
    # 7 为 dict {accuracy, kappa}，目标 Kappa ≥ 0.6
    # 8 为 dict {std_dev, max_gap}，目标 std_dev ≤ 0.15
    "9_schema_compliance_rate": {"direction": "min", "threshold": 0.95},
}

# 指标 7/8 的复合目标（README §2）
KAPPA_THRESHOLD = 0.60
STD_DEV_THRESHOLD = 0.15

LABELS = {
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


def _scalar_status(value, spec):
    """标量指标的 target_status."""
    if value is None:
        return "failed", "计算无结果"
    direction = spec["direction"]
    threshold = spec["threshold"]
    if direction == "min":
        ok = value >= threshold
        desc = f"{value:.3f} {'≥' if ok else '<'} {threshold}"
    else:
        ok = value <= threshold
        desc = f"{value:.3f} {'≤' if ok else '>'} {threshold}"
    return ("passed" if ok else "failed"), desc


def evaluate_target(metric: str, value) -> tuple[str, str]:
    """返回 (target_status, 判定描述). 绝不抛异常."""
    if metric == "6_module_timeout_rate":
        if not isinstance(value, dict) or not value:
            return "failed", "无模块耗时数据"
        # 任一模块超时率超 10% 即 failed
        worst = max(value.values()) if value else 0.0
        ok = worst <= 0.10
        desc = f"worst_module={worst:.3f} {'≤' if ok else '>'} 0.10"
        return ("passed" if ok else "failed"), desc
    if metric == "7_risk_calibration":
        if not isinstance(value, dict):
            return "failed", "无校准数据"
        acc = value.get("accuracy", 0.0)
        kappa = value.get("kappa", 0.0)
        # README §2 指标7: 目标 Kappa ≥ 0.6（substantial agreement）
        ok = kappa >= KAPPA_THRESHOLD
        desc = (
            f"kappa={kappa:.3f} {'≥' if ok else '<'} {KAPPA_THRESHOLD} (acc={acc:.3f})"
        )
        return ("passed" if ok else "failed"), desc
    if metric == "8_industry_variance":
        if not isinstance(value, dict):
            return "failed", "无行业分位数据"
        std = value.get("std_dev", 0.0)
        # README §2 指标8: 目标 std_dev ≤ 0.15
        ok = std <= STD_DEV_THRESHOLD
        desc = f"std_dev={std:.3f} {'≤' if ok else '>'} {STD_DEV_THRESHOLD}"
        return ("passed" if ok else "failed"), desc
    spec = TARGETS.get(metric)
    if spec is None:
        return "not_applicable", "无目标定义"
    return _scalar_status(value, spec)


def _mock_data():
    """Phase C mock 数据集 — 验证计算逻辑用（含好与坏的结果，验证方向性）."""
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


def _check_manifest(args) -> dict:
    """检查 1410/77 评测集 manifest 是否存在（数据真实化状态）.

    显式传入 --manifest 但文件缺失/无法解析 → 抛 ValueError（main 转退出码 2）。
    未传入 --manifest → framework_ready=True, dataset_materialized=False（不报错）。
    """
    status = {
        "framework_ready": True,
        "dataset_materialized": False,
        "manifest_1410": None,
        "manifest_77": None,
    }
    if not args.manifest:
        return status
    p = Path(args.manifest)
    if not p.exists():
        raise ValueError(f"manifest 路径不存在: {args.manifest}")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"manifest 无法解析: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("manifest 顶层必须是 JSON 对象")
    status["dataset_materialized"] = True
    status["manifest_1410"] = len(data.get("questions_1410", []))
    status["manifest_77"] = len(data.get("questions_77", []))
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--manifest", default=None, help="1410/77 评测集 manifest JSON 路径"
    )
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    try:
        manifest_status = _check_manifest(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    data = _mock_data()
    try:
        report = evaluate_all(
            ground_truth=data["ground_truth"],
            predictions=data["predictions"],
            claims=data["claims"],
            turns=data["turns"],
            module_statuses=data["module_statuses"],
            modules=data["modules"],
            expected_entity=data["expected_entity"],
        )
    except Exception as e:  # noqa: BLE001
        # 指标计算异常 ≠ 业务不达标
        print(f"ERROR: 指标计算异常: {e}", file=sys.stderr)
        return 3

    result = {
        "calculator_status": "passed",
        "target_status": "passed",
        "metrics": {},
        "dataset": manifest_status,
    }
    all_calculators_ok = True
    all_targets_ok = True

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TruthNet 评测报告 (Phase C mock)")
    lines.append("=" * 60)
    for metric, value in report.items():
        label = LABELS.get(metric, metric)
        # calculator 状态：有值即 passed
        calc_ok = value is not None
        all_calculators_ok &= calc_ok
        target_status, target_desc = evaluate_target(metric, value)
        if target_status == "failed":
            all_targets_ok = False

        if isinstance(value, dict):
            lines.append(f"\n[{label}] value={json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f"\n[{label}] value={value}")
        lines.append(f"  calculator_status: {'passed' if calc_ok else 'failed'}")
        lines.append(f"  target_status: {target_status}  ({target_desc})")

        result["metrics"][metric] = {
            "label": label,
            "value": value,
            "calculator_status": "passed" if calc_ok else "failed",
            "target_status": target_status,
            "target_desc": target_desc,
        }

    result["calculator_status"] = "passed" if all_calculators_ok else "failed"
    result["target_status"] = "passed" if all_targets_ok else "failed"

    lines.append("\n" + "=" * 60)
    lines.append(f"calculator_status: {result['calculator_status']}")
    lines.append(f"target_status: {result['target_status']}")
    lines.append("注意: mock 数据仅供验证计算方向；target 未达成不代表框架故障，")
    lines.append("      也不代表生产指标已达标。真实达标需 1410/77 评测集。")
    lines.append(
        f"dataset: framework_ready={result['dataset']['framework_ready']}, "
        f"dataset_materialized={result['dataset']['dataset_materialized']}"
    )
    print("\n".join(lines))

    if args.json:
        out = {"framework": "evaluation_runner", "result": result}
        print("\n" + json.dumps(out, ensure_ascii=False, indent=2))

    # 退出码：仅真实错误返回非 0；目标未达成不伪装为执行错误
    return 0


if __name__ == "__main__":
    sys.exit(main())
