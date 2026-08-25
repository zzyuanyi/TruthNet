"""Market Pulse 路由 — 全球金融舆情脉搏（旋转地球监控）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.application.services.market_pulse_service import fetch_market_pulse
from app.application.services.web_search_service import web_search_async
from app.schemas.market_pulse import (
    MarketPulseClusterDTO,
    MarketPulseData,
    MarketPulseDigData,
    MarketPulseDigItemDTO,
    MarketPulseItemDTO,
)

router = APIRouter(prefix="/market-pulse", tags=["market-pulse"])

# 联网深挖查询词：指数名/市场术语锚定财经域（实测短泛查询会命中生活泛闻）
_DIG_QUERY_MAP: dict[str, str] = {
    "中国": "A股 沪指 今日 财经新闻 东方财富",
    "中国香港": "港股 恒生指数 今日 新闻",
    "美国": "美股 纳斯达克 标普 今日 财经新闻",
    "日本": "日经225 日本股市 今日 行情",
    "韩国": "韩国KOSPI 股市 今日 行情",
    "印度": "印度Sensex 股市 今日 行情",
    "英国": "英国富时100 股市 今日 行情",
    "法国": "法国CAC40 股市 今日 行情",
    "德国": "德国DAX 股市 今日 行情",
    "俄罗斯": "俄罗斯MOEX指数 股市 今日",
    "新加坡": "新加坡海峡时报指数 股市 今日",
    "澳大利亚": "澳大利亚ASX200 股市 今日",
    "加拿大": "加拿大多伦多TSX指数 股市 今日",
}


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


@router.get(
    "/dig",
    response_model=V12Response[MarketPulseDigData],
    responses={500: {"model": dict}},
)
async def dig_market_pulse(
    country: str = Query(..., min_length=1, max_length=24, description="国家/地区名"),
) -> V12Response[MarketPulseDigData]:
    """联网深挖：对指定国家实时联网搜索今日财经舆情（平台托管搜索源）.

    与 RSS 监控互补——RSS 只覆盖 8 个固定源，本端点按需真实联网检索，
    结果带 AI 摘要与原文链接。搜索源未启用/限流/超时均诚实返回空列表。
    """
    query = _DIG_QUERY_MAP.get(country.strip(), f"{country.strip()} 股市 指数 今日 行情")
    hits = await web_search_async(query, max_results=8)
    data = MarketPulseDigData(
        country=country.strip(),
        query=query,
        items=[
            MarketPulseDigItemDTO(
                title=h.title,
                url=h.url,
                snippet=h.snippet[:200],
                domain=h.domain,
                published_at=h.published_at,
            )
            for h in hits
        ],
        fetched_at=datetime.now(timezone.utc),
    )
    return V12Response(
        data=data,
        meta=ApiMeta(request_id=str(uuid.uuid4()), trace_id=str(uuid.uuid4()), data_as_of=""),
    )
