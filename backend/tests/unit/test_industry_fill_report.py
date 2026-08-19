"""report.py 单元测试（档案 v1.1 §9 输出契约 + Task C C7 诊断键透出）。"""

from __future__ import annotations

from backend.app.application.services.industry_fill.report import (
    REPORT_METRIC_KEYS,
    build_report,
    render_text,
    save_report,
)


class TestBuildReport:
    def test_whitelist_includes_task_c_throttle_keys(self):
        """Task C C7 批量限流/熔断诊断键必须进入报告白名单（C12 可诊断）。"""
        for key in (
            "provider_batch_throttled",
            "provider_batch_circuit_opens",
            "provider_batch_circuit_failfast",
        ):
            assert key in REPORT_METRIC_KEYS

    def test_build_report_passes_through_known_keys(self):
        metrics = {
            "akshare_success": 5,
            "provider_batch_throttled": 3,
            "provider_batch_circuit_opens": 1,
            "provider_batch_circuit_failfast": 2,
        }
        out = build_report(metrics, ["gate1"], [])
        assert out["akshare_success"] == 5
        assert out["provider_batch_throttled"] == 3
        assert out["provider_batch_circuit_opens"] == 1
        assert out["provider_batch_circuit_failfast"] == 2
        assert out["quality_gates"] == ["gate1"]

    def test_build_report_fills_missing_with_none(self):
        out = build_report({}, [], [])
        assert out["akshare_success"] is None
        assert out["provider_batch_throttled"] is None

    def test_render_text_includes_throttle_keys(self):
        text = render_text(
            build_report(
                {
                    "akshare_success": 5,
                    "provider_batch_throttled": 3,
                    "provider_batch_circuit_opens": 1,
                    "provider_batch_circuit_failfast": 2,
                },
                ["gate1"],
                [],
            ),
            title="测试",
        )
        assert "provider_batch_throttled: 3" in text
        assert "provider_batch_circuit_opens: 1" in text
        assert "provider_batch_circuit_failfast: 2" in text

    def test_save_report_roundtrip(self, tmp_path):
        report = build_report({"provider_batch_throttled": 1}, [], [])
        out = save_report(report, tmp_path / "r" / "report.json")
        import json

        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["provider_batch_throttled"] == 1
        assert loaded["quality_gates"] == []
