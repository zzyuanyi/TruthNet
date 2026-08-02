"""评测 runner 语义测试 — calculator/target 状态分离与退出码.

对应集成验收 §9.2 / §9.4:
- "函数能算" 与 "生产达标" 必须分开（mock 值低于目标 → calculator passed, target failed）。
- 目标未达成不伪装为执行错误（退出码 0）。
- 显式传入损坏 manifest → 非法输入退出码 2。
"""

import json

import pytest

from tests.evaluation import runner


def test_evaluate_target_separates_status():
    # 低于目标 → failed
    status, desc = runner.evaluate_target("1_accuracy", 0.5)
    assert status == "failed"
    assert "0.500 < 0.7" in desc
    # 达到目标 → passed
    status, _ = runner.evaluate_target("1_accuracy", 0.85)
    assert status == "passed"
    # 方向：无证据比例越高越差（max 方向）
    status, _ = runner.evaluate_target("4_unverified_claim_ratio", 0.05)
    assert status == "passed"
    status, _ = runner.evaluate_target("4_unverified_claim_ratio", 0.5)
    assert status == "failed"
    # 模块超时率 dict
    status, _ = runner.evaluate_target(
        "6_module_timeout_rate", {"finance": 0.0, "events": 1.0}
    )
    assert status == "failed"
    status, _ = runner.evaluate_target("6_module_timeout_rate", {"finance": 0.0})
    assert status == "passed"
    # 未知指标 → not_applicable
    status, _ = runner.evaluate_target("unknown_metric", 1.0)
    assert status == "not_applicable"


def test_mock_run_calculator_passed_target_failed(capsys):
    monkey = pytest.MonkeyPatch()
    monkey.setattr("sys.argv", ["runner"])
    try:
        code = runner.main()
    finally:
        monkey.undo()
    out = capsys.readouterr().out
    assert code == 0  # 目标未达成不是执行错误
    assert "calculator_status: passed" in out
    assert "target_status: failed" in out
    assert "dataset_materialized=False" in out


def test_invalid_manifest_exit_2(tmp_path, capsys):
    bad = tmp_path / "missing.json"
    sys_argv = ["runner", "--manifest", str(bad)]
    monkey = pytest.MonkeyPatch()
    monkey.setattr("sys.argv", sys_argv)
    try:
        code = runner.main()
    finally:
        monkey.undo()
    assert code == 2
    assert "manifest" in capsys.readouterr().err.lower()


def test_json_output_parseable(capsys):
    monkey = pytest.MonkeyPatch()
    monkey.setattr("sys.argv", ["runner", "--json"])
    try:
        code = runner.main()
    finally:
        monkey.undo()
    out = capsys.readouterr().out
    assert code == 0
    # 找到最终 JSON 块（indent=2 的 json.dumps 输出）并解析
    start = out.rfind('{\n  "framework"')
    assert start != -1, "未找到 JSON 输出"
    payload = json.loads(out[start:])
    assert payload["result"]["calculator_status"] == "passed"
    assert payload["result"]["target_status"] == "failed"
    assert "1_accuracy" in payload["result"]["metrics"]
