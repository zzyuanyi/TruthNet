"""行业分位共享服务 — benchmarks 路由与 finance 规则明细共用.

历史问题: /benchmarks 端点计算行业分位，但 /finance 端点的每条规则 industry
字段从未填充（r.industry 恒空），前端 RuleCard 依赖 p50/p75/p95 显示 '--'。
本服务把 9 个指标的计算提取为单一来源，两端点共用，避免口径漂移。
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.domain.benchmarks.calculator import (
    MIN_PEER_SAMPLE,
    aggregate_stats,
    compute_metric_values,
    percentile_rank,
)
from app.domain.benchmarks.metric_registry import all_metrics
from app.domain.finance._fetch import _get_engine

logger = logging.getLogger(__name__)


def compute_industry_percentiles(
    wind_code: str, industry_l1: str, period_ymd: str
) -> dict:
    """计算全指标行业分位（固定母公司口径）.

    返回:
      percentiles: list[IndustryPercentile]（样本不足时 p* 与 company_percentile 置 None，不伪造）
      peer_count / is_sufficient / warnings
    """
    from app.api.v1.schemas.benchmarks import IndustryPercentile

    engine = _get_engine()
    percentiles: list[IndustryPercentile] = []
    peer_count = 0
    is_sufficient = False
    warnings: list[str] = []

    for metric in all_metrics():
        try:
            pairs = compute_metric_values(engine, metric, industry_l1, period_ymd)
        except Exception as exc:  # noqa: BLE001 — 单指标失败不阻塞整体
            warnings.append(f"指标 {metric.metric_id} 计算失败: {exc}")
            continue
        values = [v for _, v in pairs]
        stats = aggregate_stats(values)
        company_value = next((v for c, v in pairs if c == wind_code), None)
        peer_count = max(peer_count, stats["sample_count"])

        if stats["sample_count"] < MIN_PEER_SAMPLE:
            percentiles.append(
                IndustryPercentile(
                    indicator=metric.metric_id,
                    label=metric.name,
                    rule_id=metric.rule_id,
                    metric_id=metric.metric_id,
                    company_value=company_value,
                    company_percentile=None,
                    unit=metric.unit,
                    sample_count=stats["sample_count"],
                    p05=None,
                    p25=None,
                    p50=None,
                    p75=None,
                    p95=None,
                    peer_count=stats["sample_count"],
                    statement_scope="parent_company",
                )
            )
            continue

        is_sufficient = True
        company_percentile = (
            percentile_rank(company_value, values)
            if company_value is not None
            else None
        )
        percentiles.append(
            IndustryPercentile(
                indicator=metric.metric_id,
                label=metric.name,
                rule_id=metric.rule_id,
                metric_id=metric.metric_id,
                company_value=company_value,
                company_percentile=company_percentile,
                unit=metric.unit,
                sample_count=stats["sample_count"],
                p05=stats.get("p05"),
                p25=stats.get("p25"),
                p50=stats.get("p50"),
                p75=stats.get("p75"),
                p95=stats.get("p95"),
                peer_count=stats["sample_count"],
                statement_scope="parent_company",
            )
        )

    return {
        "percentiles": percentiles,
        "peer_count": peer_count,
        "is_sufficient": is_sufficient,
        "warnings": warnings,
    }
