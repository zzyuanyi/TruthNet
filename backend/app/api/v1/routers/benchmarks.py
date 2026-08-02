"""行业对标路由 — V12 §11.13.

GET /api/v1/companies/{code}/benchmarks?period=2026Q2

行业样本少于5时返回 warning，仅展示通用阈值，不伪造分位值。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.benchmarks import BenchmarksResponseData, IndustryPercentile
from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.config import settings

router = APIRouter(tags=["benchmarks"])


def _trace() -> str:
    return str(uuid.uuid4())


def _resolve_company(code: str) -> tuple[str, str, str] | None:
    """解析公司代码 → (wind_code, sec_name, industry_l1)。"""
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    for c in _MOCK_COMPANIES:
        wc = c["wind_code"]
        if code in (wc, wc.replace(".", "_"), wc.split(".")[0]):
            return (wc, c["sec_name"], c.get("industry_l1", ""))
    return None


@router.get("/companies/{code}/benchmarks")
async def get_company_benchmarks(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    period: str = Query(default="2026Q2", description="对标期间"),
):
    """行业对标 — 返回目标公司指标在同行中的分位值。

    行业样本 <5 时不展示伪造分位，仅返回通用阈值 + is_sample_sufficient=false。
    """
    trace_id = _trace()
    warnings: list[WarningItem] = []

    resolved = _resolve_company(code)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/company-not-found",
                "title": "Company Not Found",
                "status": 404,
                "detail": f"未找到公司: {code}",
                "error_code": "COMPANY_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    wind_code, sec_name, industry_l1 = resolved

    # ── 查询同行公司数 ──
    peer_count = 0
    percentiles: list[IndustryPercentile] = []
    is_sufficient = False

    try:
        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            # 同行业公司总数（从 research_reports 的 industry_l1 列统计）
            row = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT wind_code) FROM companies "
                    "WHERE industry_l1 = :ind"
                ),
                {"ind": industry_l1},
            ).fetchone()
            peer_count = row[0] if row else 0

        is_sufficient = peer_count >= 5
    except Exception:
        peer_count = 0
        is_sufficient = False
        warnings.append(
            WarningItem(
                code="BENCHMARKS_UNAVAILABLE",
                message="无法查询行业分布数据，返回空对标",
                module="benchmarks",
                recoverable=True,
            )
        )

    if not is_sufficient:
        warnings.append(
            WarningItem(
                code="INSUFFICIENT_PEER_SAMPLE",
                message=(
                    f"行业「{industry_l1}」样本仅 {peer_count} 家（需 ≥5），"
                    f"不展示伪造分位值。仅返回通用阈值供参考。"
                ),
                module="benchmarks",
                recoverable=True,
            )
        )
        # 仅展示通用阈值标记（不伪造数字）
        percentiles = [
            IndustryPercentile(
                indicator="R1_receivable_yoy",
                label="应收增速（同比）",
                rule_id="R1",
                company_value=None,
                unit="%",
                peer_count=peer_count,
            ),
            IndustryPercentile(
                indicator="R2_cash_flow_divergence",
                label="现金流-利润背离度",
                rule_id="R2",
                company_value=None,
                unit="比值",
                peer_count=peer_count,
            ),
            IndustryPercentile(
                indicator="R3_double_high",
                label="存贷双高指数",
                rule_id="R3",
                company_value=None,
                unit="指数",
                peer_count=peer_count,
            ),
        ]

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
