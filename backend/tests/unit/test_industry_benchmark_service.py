"""行业分位共享服务单元测试 — 样本不足 / 单指标异常的降级语义.

不依赖真实 MySQL：monkeypatch compute_metric_values，验证：
- 样本不足（< MIN_PEER_SAMPLE）→ p* 与 company_percentile 全为 None（不伪造分位）；
- 单指标计算抛异常 → 该指标跳过并记录 warning，其余指标正常返回。
"""

import pytest

from app.application.services import industry_benchmark_service as svc
from app.domain.benchmarks.calculator import MIN_PEER_SAMPLE


@pytest.fixture(autouse=True)
def _stub_compute(monkeypatch):
    """默认替身：所有指标返回 1 个样本（不触发真实引擎查询）。"""
    monkeypatch.setattr(
        svc,
        "compute_metric_values",
        lambda engine, metric, industry_l1, period_ymd: [("600518.SH", 10.0)],
    )


def test_insufficient_sample_returns_null_not_faked():
    """样本不足 → p*/company_percentile 全 None，is_sufficient=False。"""
    result = svc.compute_industry_percentiles("600518.SH", "中药", "20260630")
    assert result["is_sufficient"] is False
    assert result["percentiles"], "应返回指标条目（即使样本不足）"
    for p in result["percentiles"]:
        assert p.p50 is None and p.p75 is None and p.p95 is None
        assert p.p05 is None and p.p25 is None
        assert p.company_percentile is None
        assert p.sample_count < MIN_PEER_SAMPLE


def test_metric_failure_is_skipped_with_warning(monkeypatch):
    """单指标抛异常 → 跳过该指标 + warning，其余指标正常计算（不炸整体）。"""

    def flaky(engine, metric, industry_l1, period_ymd):
        if metric.metric_id == "r1_gap":
            raise RuntimeError("boom")
        # 其余指标返回 200 个样本（充足）
        return [("600518.SH", 10.0)] * 200

    monkeypatch.setattr(svc, "compute_metric_values", flaky)
    result = svc.compute_industry_percentiles("600518.SH", "中药", "20260630")

    metric_ids = [p.metric_id for p in result["percentiles"]]
    assert "r1_gap" not in metric_ids, "异常指标应被跳过"
    assert any("r1_gap" in w for w in result["warnings"]), "应记录 warning"

    sufficient = [p for p in result["percentiles"] if p.sample_count >= MIN_PEER_SAMPLE]
    assert sufficient, "其余指标仍应正常计算"
    assert all(p.p50 is not None for p in sufficient)
