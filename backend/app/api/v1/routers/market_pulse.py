"""Market Pulse 路由 — 全球金融舆情脉搏（旋转地球监控）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.application.services.market_pulse_service import fetch_market_pulse
from app.schemas.market_pulse import (
    MarketPulseClusterDTO,
    MarketPulseData,
    MarketPulseItemDTO,
)

router = APIRouter(prefix="/market-pulse", tags=["market-pulse"])


@router.get(
    "",
    response_model=V12Response[MarketPulseData],
    responses={500: {"model": dict}},
)
async def get_market_pulse() -> V12Response[MarketPulseData]:
    """聚合公开 RSS 的全球金融资讯，每条映射到区域坐标。

    单源失败自动降级（failed_sources 记录），不阻塞整体。
    """
    payload = await fetch_market_pulse()
    data = MarketPulseData(
        fetched_at=payload["fetched_at"],
        ttl_seconds=payload["ttl_seconds"],
        poll_seconds=payload["poll_seconds"],
        regions=payload["regions"],
        items=[MarketPulseItemDTO(**item) for item in payload["items"]],
        clusters=[MarketPulseClusterDTO(**c) for c in payload["clusters"]],
        ok_sources=payload["ok_sources"],
        failed_sources=payload["failed_sources"],
    )

    warnings = []
    if payload["failed_sources"]:
        failed = "、".join(payload["failed_sources"])
        warnings.append(
            {
                "code": "PARTIAL_SOURCES",
                "message": f"部分资讯源暂不可达（{failed}），已跳过。",
                "module": "market-pulse",
                "recoverable": True,
            }
        )

    return V12Response(
        data=data,
        meta=ApiMeta(
            request_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            data_as_of="",
        ),
        warnings=warnings,
    )
