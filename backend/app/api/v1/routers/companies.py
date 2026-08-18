"""公司查询路由 — Phase C 真实画像.

GET /api/v1/companies?query=...      搜索（MySQL/SQLite 真实数据）
GET /api/v1/companies/{code}         企业画像摘要（真实数据，无硬编码风险）

链路: Router → CompanyResolver → CompanyRepository Port
      → MySQLCompanyRepository（full） / SQLiteCompanyRepository（lite）

画像不硬编码风险等级/风险因素；无风险评估数据时返回 risk_summary=null + warning。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.companies import CompanyProfileV1, CompanySearchData
from app.core.errors import ErrorCode
from app.application.services.company_resolver import CompanyResolver
from app.core.config import settings
from app.domain.company.models import CompanyRecord
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)

router = APIRouter(tags=["companies"])


def _trace() -> str:
    return str(uuid.uuid4())


def _candidate(record: CompanyRecord) -> dict:
    """V12 CompanyRef 兼容的候选字段."""
    return {
        "entity_id": record.entity_id,
        "wind_code": record.wind_code,
        "sec_name": record.sec_name,
        "exchange": record.exchange,
        "industry_l1": record.industry_l1,
        "industry_l2": record.industry_l2,
        "comp_type_code": record.comp_type_code,
        "company_type": record.company_type,
        "listing_date": (
            record.listing_date.isoformat() if record.listing_date else None
        ),
    }


def _data_quality(record: CompanyRecord, source: str) -> dict:
    """构造画像数据质量信息."""
    return {
        "source": source,
        "dataset_version": record.dataset_version or settings.DATASET_VERSION,
        "source_record_id": record.source_record_id,
        "is_latest": record.is_latest,
        "quality_flags": record.quality_flags or {},
        "partial": False,
    }


def _profile_body(record: CompanyRecord, source: str) -> dict:
    """画像响应体（不硬编码风险）。"""
    return {
        "entity_id": record.entity_id,
        "wind_code": record.wind_code,
        "sec_name": record.sec_name,
        "aliases": record.aliases,
        "exchange": record.exchange,
        "industry_l1": record.industry_l1,
        "industry_l2": record.industry_l2,
        "sw_indu_code": record.sw_indu_code,
        "comp_type_code": record.comp_type_code,
        "company_type": record.company_type,
        "listing_date": (
            record.listing_date.isoformat() if record.listing_date else None
        ),
        "data_quality": _data_quality(record, source),
        "risk_summary": None,  # 风险评估数据组尚未交付；不得伪造
    }


@router.get(
    "/companies",
    response_model=V12Response[CompanySearchData],
)
async def search_companies(
    query: str = Query(default="", description="公司名称或代码"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """搜索公司 — V12 response envelope.

    返回字段对齐 V12 CompanyRef + Phase C 真实字段。
    """
    trace_id = _trace()
    resolver = CompanyResolver()
    result = await resolver.repo.search(query, limit=limit)
    candidates = [_candidate(c) for c in result.companies]

    return V12Response(
        data={"query": query, "total": result.total, "candidates": candidates},
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )


@router.get(
    "/companies/{code}",
    response_model=V12Response[CompanyProfileV1],
)
async def company_profile(code: str):
    """企业画像摘要 — 真实 MySQL/SQLite 数据.

    未找到公司时返回 HTTP 404 + Problem Details。
    风险摘要无数据时返回 risk_summary=null + warning。
    """
    trace_id = _trace()
    resolver = CompanyResolver()
    company = await resolver.resolve(code)

    if not company:
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

    source = (
        "mysql"
        if isinstance(resolver.repo, MySQLCompanyRepository)
        else "sqlite_fixture"
    )
    profile = _profile_body(company, source)

    warnings: list[WarningItem] = [
        WarningItem(
            code="RISK_SUMMARY_UNAVAILABLE",
            message="风险评估数据组尚未交付，画像 risk_summary 为空，未伪造。",
            module="companies",
            recoverable=True,
        )
    ]

    # Phase E 会5：画像环节触发点——listing_date 库内无值 → 联网检索 + 来源标注
    # （默认 off 时 web_search 返回 []，profile 保持现状）
    if profile.get("listing_date") is None:
        await _web_search_fill_profile_listing_date(company, profile, warnings)

    return V12Response(
        data=profile,
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
        ),
        warnings=warnings,
    )


async def _web_search_fill_profile_listing_date(
    company: CompanyRecord, profile: dict, warnings: list[WarningItem]
) -> bool:
    """会5：画像 listing_date 库内无值 → 联网检索并回填 + 来源 warning.

    Returns:
        True=已联网回填；False=未回填（保持现状）。
        默认 off 时 web_search 返回 []，恒 False，行为与现状完全一致。
    """
    from app.application.services.web_search_fact_fill import (
        extract_listing_date_from_hits,
    )
    from app.application.services.web_search_service import web_search_async

    hits = await web_search_async(f"{company.sec_name} 上市日期")
    if not hits:
        return False
    value = extract_listing_date_from_hits(hits)
    if not value:
        return False
    hit = next((h for h in hits if (h.snippet or h.title)), None)
    profile["listing_date"] = value
    warnings.append(
        WarningItem(
            code="WEB_SEARCH_SOURCE",
            message=(
                f"{company.sec_name} 上市日期为联网检索结果：{value}（来源："
                f"{hit.url if hit else ''}，建议以官方披露为准）"
            ),
            module="companies",
            recoverable=True,
        )
    )
    return True
