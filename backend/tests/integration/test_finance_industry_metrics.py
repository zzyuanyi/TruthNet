"""行业分位契约回归测试（真实 MySQL）.

覆盖 V12 §11.10 行业对标契约（Phase D 外部审核补测）:
- /finance 返回的每条规则都带 industry_metrics 数组；
- 指标数量契约：R1/R2/R6 各 1、R3/R4/R5 各 2、R7 为 0（当前设计，R7 无行业指标）；
- 同期间 /finance 与 /benchmarks 按 metric_id 的 p50/p75/p95/company_percentile 完全一致；
- 行业分位计算整体异常 → /finance 降级不 500。
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]

_CODE = "600518.SH"  # 康美：industry_l1=中药，peer 样本充足
_PERIOD = "2026Q2"

# 指标数量契约（9 个注册指标 = 1+1+2+2+2+1，R7 无行业指标）
_EXPECTED_METRIC_COUNTS = {
    "R1": 1,
    "R2": 1,
    "R3": 2,
    "R4": 2,
    "R5": 2,
    "R6": 1,
    "R7": 0,
}


@pytest.mark.asyncio
async def test_finance_rules_industry_metrics_contract():
    """每条规则带 industry_metrics 数组，指标数量对齐注册表。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/companies/{_CODE}/finance?as_of={_PERIOD}")
        assert r.status_code == 200
        rules = r.json()["data"]["rules"]
        assert rules, "应返回规则结果"
        by_rule = {rule["rule_id"]: rule for rule in rules}

        for rule in rules:
            assert isinstance(
                rule["industry_metrics"], list
            ), f"{rule['rule_id']} 缺少 industry_metrics 数组"
            for m in rule["industry_metrics"]:
                assert (
                    m["metric_id"] and m["rule_id"]
                ), "industry_metrics 条目必须带 metric_id/rule_id"

        for rid, expect in _EXPECTED_METRIC_COUNTS.items():
            rule = by_rule.get(rid)
            if rule is None:
                continue  # 规则引擎未返回该规则（数据缺口），不强求
            assert (
                len(rule["industry_metrics"]) == expect
            ), f"{rid} 指标数应为 {expect}，实际 {len(rule['industry_metrics'])}"


@pytest.mark.asyncio
async def test_finance_and_benchmarks_share_percentiles():
    """同期间 /finance 与 /benchmarks 按 metric_id 分位完全一致（单一来源无漂移）。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        fin = await client.get(f"/api/v1/companies/{_CODE}/finance?as_of={_PERIOD}")
        bench = await client.get(
            f"/api/v1/companies/{_CODE}/benchmarks?period={_PERIOD}"
        )
        assert fin.status_code == 200
        assert bench.status_code == 200

        fin_metrics = {
            m["metric_id"]: m
            for rule in fin.json()["data"]["rules"]
            for m in rule["industry_metrics"]
        }
        bench_metrics = {m["metric_id"]: m for m in bench.json()["data"]["percentiles"]}
        assert bench_metrics, "benchmarks 应返回指标分位"

        for metric_id, bm in bench_metrics.items():
            fm = fin_metrics.get(metric_id)
            if fm is None:
                continue  # 该规则未返回（数据缺口），跳过
            for field in ("p50", "p75", "p95", "company_percentile"):
                assert (
                    fm[field] == bm[field]
                ), f"{metric_id}.{field} 两端点不一致: {fm[field]} vs {bm[field]}"


@pytest.mark.asyncio
async def test_finance_survives_benchmark_failure(monkeypatch):
    """行业分位整体异常 → /finance 降级不 500，规则明细的 industry_metrics 为空数组。"""
    from app.application.services import industry_benchmark_service as svc

    def boom(*args, **kwargs):
        raise RuntimeError("benchmark service down")

    monkeypatch.setattr(svc, "compute_industry_percentiles", boom)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/companies/{_CODE}/finance?as_of={_PERIOD}")
        assert r.status_code == 200
        rules = r.json()["data"]["rules"]
        assert all(rule["industry_metrics"] == [] for rule in rules)
