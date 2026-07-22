"""公司查询路由 — V12 baseline.

GET /api/v1/companies?query=...  搜索
GET /api/v1/companies/{code}     企业画像摘要
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.v1.schemas.common import ApiMeta, WarningItem, V12Response

router = APIRouter(tags=["companies"])

_MOCK_COMPANIES = [
    {
        "entity_id": "company_600519_SH",
        "wind_code": "600519.SH",
        "sec_name": "贵州茅台",
        "exchange": "XSHG",
        "industry_l1": "白酒",
    },
    {
        "entity_id": "company_000858_SZ",
        "wind_code": "000858.SZ",
        "sec_name": "五粮液",
        "exchange": "XSHE",
        "industry_l1": "白酒",
    },
    {
        "entity_id": "company_600518_SH",
        "wind_code": "600518.SH",
        "sec_name": "康美药业",
        "exchange": "XSHG",
        "industry_l1": "中药",
    },
    {
        "entity_id": "company_300750_SZ",
        "wind_code": "300750.SZ",
        "sec_name": "宁德时代",
        "exchange": "XSHE",
        "industry_l1": "电池",
    },
    {
        "entity_id": "company_002415_SZ",
        "wind_code": "002415.SZ",
        "sec_name": "海康威视",
        "exchange": "XSHE",
        "industry_l1": "安防",
    },
]


def _trace() -> str:
    return str(uuid.uuid4())


def _match(c: dict, q: str) -> bool:
    ql = q.lower()
    return (
        ql in c["wind_code"].lower()
        or ql in c["sec_name"]
        or ql in c["exchange"].lower()
    )


@router.get("/companies")
async def search_companies(
    # TODO(Phase C): 替换 mock 数据为 MySQL 查询
    query: str = Query(default="", description="公司名称或代码"),
    limit: int = Query(default=10, ge=1, le=50),
):
    trace_id = _trace()
    results = [c for c in _MOCK_COMPANIES if _match(c, query)][:limit]
    if not results and not query:
        results = _MOCK_COMPANIES[:limit]

    return V12Response(
        data={"query": query, "total": len(results), "candidates": results},
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )


@router.get("/companies/{code}")
async def company_profile(code: str):
    trace_id = _trace()
    company = next((c for c in _MOCK_COMPANIES if c["wind_code"] == code), None)
    if not company:
        return V12Response(
            data=None,
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
            warnings=[
                WarningItem(code="COMPANY_NOT_FOUND", message=f"未找到公司: {code}")
            ],
        )

    return V12Response(
        data={
            **company,
            "risk_level": "red" if "康美" in company["sec_name"] else "green",
            "risk_factors": [
                {
                    "category": "财务勾稽",
                    "level": "high",
                    "detail": "应收-营收背离、现金流-利润背离",
                }
            ]
            if "康美" in company["sec_name"]
            else [],
        },
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )
