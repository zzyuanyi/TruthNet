"""公司查询路由 — V12 baseline.

GET /api/v1/companies?query=...
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.v1.schemas.common import ApiMeta, V12Response

router = APIRouter(tags=["companies"])

# Mock 公司数据
_MOCK_COMPANIES = [
    {
        "code": "600519",
        "name": "贵州茅台酒股份有限公司",
        "short_name": "贵州茅台",
        "industry": "白酒",
    },
    {
        "code": "000858",
        "name": "五粮液股份有限公司",
        "short_name": "五粮液",
        "industry": "白酒",
    },
    {
        "code": "600518",
        "name": "康美药业股份有限公司",
        "short_name": "康美药业",
        "industry": "中药",
    },
    {
        "code": "300750",
        "name": "宁德时代新能源科技股份有限公司",
        "short_name": "宁德时代",
        "industry": "电池",
    },
    {
        "code": "002415",
        "name": "杭州海康威视数字技术股份有限公司",
        "short_name": "海康威视",
        "industry": "安防",
    },
]


@router.get("/companies")
async def search_companies(
    query: str = Query(default="", description="公司名称或代码搜索"),
    limit: int = Query(default=10, ge=1, le=50, description="最大返回数"),
):
    """搜索公司 — V12 response envelope."""
    trace_id = str(uuid.uuid4())

    results = [
        c
        for c in _MOCK_COMPANIES
        if query.lower() in c["code"].lower()
        or query.lower() in c["name"].lower()
        or query.lower() in (c.get("short_name") or "").lower()
    ][:limit]

    if not results and not query:
        results = _MOCK_COMPANIES[:limit]

    return V12Response(
        data={
            "companies": results,
            "total": len(results),
        },
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )
