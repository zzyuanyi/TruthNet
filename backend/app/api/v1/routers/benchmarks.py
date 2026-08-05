"""行业对标路由 — V12 §11.13 + Phase C 任务 12.

GET /api/v1/companies/{code}/benchmarks?period=2026Q2

真实 percentile:
  - 从 industry_benchmarks 表读预计算分位（p05-p95/mean/std/sample_count）
  - 实时计算目标公司值（metric_registry，与 Finance 同一指标定义）
  - company_percentile = percentile_rank（非插值）
  - 样本 < 5：不计算 percentile，明确 sample_count，不伪造分位
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.benchmarks import BenchmarksResponseData
from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.errors import ErrorCode
from app.core.config import settings

router = APIRouter(tags=["benchmarks"])


def _trace() -> str:
    return str(uuid.uuid4())


async def _resolve_company(code: str) -> tuple[str, str, str] | None:
    """解析公司代码 → (wind_code, sec_name, industry_l1)。"""
    from app.application.services.company_resolver import resolve_company

    rec = await resolve_company(code)
    if rec is None:
        return None
    return (rec.wind_code, rec.sec_name, rec.industry_l1 or "")


@router.get("/companies/{code}/benchmarks")
async def get_company_benchmarks(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    period: str = Query(default="2026Q2", description="对标期间"),
):
    """行业对标 — 真实分位值 + 公司值百分位。"""
    from app.domain.benchmarks.calculator import (
        MIN_PEER_SAMPLE,
    )

    trace_id = _trace()
    warnings: list[WarningItem] = []

    resolved = await _resolve_company(code)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/company-not-found",
                "title": "Company Not Found",
                "status": 404,
                "detail": f"未找到公司: {code}",
                "error_code": ErrorCode.COMPANY_NOT_COVERED,
                "trace_id": trace_id,
                "recoverable": True,
            },
        )
    wind_code, sec_name, industry_l1 = resolved

    # period 规范化（2026Q2 → 20260630）
    from app.domain.finance.period import normalize_period

    period_ymd = normalize_period(period)
    if period_ymd is None:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://truthnet.dev/errors/invalid-period",
                "title": "Invalid Period",
                "status": 422,
                "detail": f"无法解析期间: {period}",
                "error_code": "INVALID_PERIOD",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    if not industry_l1:
        return V12Response(
            data=BenchmarksResponseData(
                wind_code=wind_code,
                sec_name=sec_name,
                industry_l1="",
                period=period,
                percentiles=[],
                peer_count=0,
                is_sample_sufficient=False,
                generic_thresholds_only=True,
                dataset_version=settings.DATASET_VERSION,
                statement_scope="parent_company",
                warnings=["INDUSTRY_UNKNOWN: 公司行业未知，无法计算行业分位"],
            ),
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
                dataset_version=settings.DATASET_VERSION,
            ),
            warnings=warnings,
        )

    # 共享服务计算（与 /finance 规则明细同口径，避免双口径漂移）
    from app.application.services.industry_benchmark_service import (
        compute_industry_percentiles,
    )

    result = compute_industry_percentiles(wind_code, industry_l1, period_ymd)
    percentiles = result["percentiles"]
    peer_count = result["peer_count"]
    is_sufficient = result["is_sufficient"]
    for w in result["warnings"]:
        warnings.append(
            WarningItem(
                code="BENCHMARK_METRIC_ERROR",
                message=w,
                module="benchmarks",
                recoverable=True,
            )
        )
    if not is_sufficient:
        warnings.append(
            WarningItem(
                code="INSUFFICIENT_PEER_SAMPLE",
                message=(
                    f"行业「{industry_l1}」各指标有效样本 < {MIN_PEER_SAMPLE}，"
                    f"不展示伪造分位值"
                ),
                module="benchmarks",
                recoverable=True,
            )
        )

    return V12Response(
        data=BenchmarksResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            industry_l1=industry_l1,
            period=period,
            percentiles=percentiles,
            peer_count=peer_count,
            is_sample_sufficient=is_sufficient,
            generic_thresholds_only=not is_sufficient,
            dataset_version=settings.DATASET_VERSION,
            statement_scope="parent_company",
            warnings=[w.message for w in warnings],
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
        ),
        warnings=warnings,
    )
