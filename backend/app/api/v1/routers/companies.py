"""公司查询路由 — V12 baseline (集成版).

整合 PR #9 公司画像端点 + 统一 entity_id 格式。

GET /api/v1/companies?query=...      搜索
GET /api/v1/companies/{code}         企业画像摘要

变更（相对于 PR #9 原版）：
  - 搜索返回字段对齐 V12 CompanyRef（entity_id, wind_code, sec_name, exchange, industry_l1）
  - 公司不存在返回 HTTP 404 Problem Details（非 200 + data=null）
  - 硬编码风险因素仅限 mock（标注 TODO）
  - lite profile 使用 fixture adapter，full profile 查询 MySQL
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.core.config import settings

router = APIRouter(tags=["companies"])

# ── Mock 数据（lite profile / Phase B） ──
# TODO(Phase C): 替换为 MySQL CompanyRepository 查询

_MOCK_COMPANIES: list[dict] = [
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
    query: str = Query(default="", description="公司名称或代码"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """搜索公司 — V12 response envelope.

    返回字段对齐 V12 CompanyRef:
      entity_id, wind_code, sec_name, exchange, industry_l1
    """
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
    """企业画像摘要 — V12 baseline。

    未找到公司时返回 HTTP 404 + Problem Details。
    暂未接通真实数据的模块返回 warnings/partial。
    """
    trace_id = _trace()

    company = next((c for c in _MOCK_COMPANIES if c["wind_code"] == code), None)

    if not company:
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

    # TODO(Phase C): 从 MySQL/Neo4j/Chroma 组合真实数据
    profile = {
        **company,
        "risk_level": "red" if "康美" in company["sec_name"] else "green",
        # ⚠️ 以下风险因素来自 mock 数据，非真实数据库查询
        "risk_factors": (
            [
                {
                    "category": "财务勾稽",
                    "level": "high",
                    "detail": "应收-营收背离、现金流-利润背离",
                }
            ]
            if "康美" in company["sec_name"]
            else []
        ),
        "data_quality": {
            "source": "mock",
            "warnings": ["企业画像使用 mock 数据，非真实数据库查询"],
        },
    }

    return V12Response(
        data=profile,
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
        ),
        warnings=[
            {
                "code": "MOCK_DATA",
                "message": "企业画像使用 mock 数据（Phase C 将接入 MySQL/Neo4j）",
            }
        ],
    )
