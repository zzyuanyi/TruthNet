"""舆情事件路由 — V12 §11.11.

GET /api/v1/companies/{code}/events?months=36

返回 sentiment_summary、event_clusters、timeline、rating_changes、
keyword_summary、evidence_ids。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.events import (
    EventCluster,
    EventsResponseData,
    KeywordSummary,
    RatingChange,
    SentimentSummary,
    TimelineEvent,
)
from app.core.config import settings

router = APIRouter(tags=["events"])


def _trace() -> str:
    return str(uuid.uuid4())


def _resolve_company(code: str) -> tuple[str, str] | None:
    """解析公司代码 → (wind_code, sec_name)。"""
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    for c in _MOCK_COMPANIES:
        wc = c["wind_code"]
        if code in (wc, wc.replace(".", "_"), wc.split(".")[0]):
            return (wc, c["sec_name"])
    return None


@router.get("/companies/{code}/events")
async def get_company_events(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    months: int = Query(default=36, ge=1, le=120, description="回溯月数"),
):
    """舆情事件 — 返回公告时间线、事件簇、情绪统计、评级变化。

    公告不可用时返回 NO_ANNOUNCEMENT_DATA warning + 空时间线。
    """
    trace_id = _trace()
    warnings: list[WarningItem] = []

    # 1. 解析公司
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

    wind_code, sec_name = resolved

    # 2. 查询公告数据
    timeline: list[TimelineEvent] = []
    sentiment_summary = SentimentSummary()
    clusters: list[EventCluster] = []
    rating_changes: list[RatingChange] = []
    announcements_available = False
    evidence_ids: list[str] = []

    try:
        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            rows = conn.execute(
                text(
                    "SELECT object_id, ann_date, fcode, title "
                    "FROM announcements "
                    "WHERE wind_code = :code "
                    "ORDER BY ann_date DESC "
                    "LIMIT :limit"
                ),
                {"code": wind_code, "limit": 200},
            ).fetchall()

        if rows:
            announcements_available = True
            from collections import Counter

            from app.domain.events.fcode_taxonomy import (
                classify_sentiment,
                fcode_category_label,
            )

            sentiment_counter = Counter()
            for row in rows:
                _, ann_date, fcode_raw, title = row
                ann_date_str = (
                    str(ann_date) if ann_date else ""
                )
                sentiment, _, _ = classify_sentiment(
                    str(fcode_raw) if fcode_raw else ""
                )
                sentiment_counter[sentiment] += 1
                label = fcode_category_label(str(fcode_raw) if fcode_raw else "")

                timeline.append(
                    TimelineEvent(
                        date=ann_date_str,
                        title=title or "",
                        category="公告",
                        fcode_label=label,
                        sentiment=sentiment,
                        summary=title or "",
                    )
                )

            sentiment_summary = SentimentSummary(
                positive_count=sentiment_counter.get("positive", 0),
                negative_count=sentiment_counter.get("negative", 0),
                neutral_count=sentiment_counter.get("neutral", 0),
                total_count=len(rows),
                negative_ratio=(
                    sentiment_counter.get("negative", 0) / len(rows)
                    if rows
                    else 0.0
                ),
            )

            # 基础事件簇（按 fcode 分组，Phase C 后续改 LLM 聚类）
            cluster_map: dict[str, list[TimelineEvent]] = {}
            for evt in timeline:
                key = evt.fcode_label or "其他"
                cluster_map.setdefault(key, []).append(evt)
            for label, evts in cluster_map.items():
                if len(evts) >= 2:
                    dates = [e.date for e in evts if e.date]
                    clusters.append(
                        EventCluster(
                            cluster_id=f"cluster_{label}",
                            topic=label,
                            event_count=len(evts),
                            date_range=(
                                f"{min(dates)} 至 {max(dates)}"
                                if dates
                                else ""
                            ),
                            sentiment=(
                                "negative"
                                if any(e.sentiment == "negative" for e in evts)
                                else "neutral"
                            ),
                            summary=f"{label}相关公告 {len(evts)} 条",
                        )
                    )
        else:
            warnings.append(
                WarningItem(
                    code="NO_ANNOUNCEMENT_DATA",
                    message=(
                        f"{sec_name}({wind_code}) 无公告数据覆盖，"
                        f"返回空时间线。系统已自动降级，不影响其他模块分析。"
                    ),
                    module="events",
                    recoverable=True,
                )
            )
    except Exception as exc:
        warnings.append(
            WarningItem(
                code="EVENTS_DATA_ERROR",
                message=f"公告数据查询失败: {exc}",
                module="events",
                recoverable=True,
            )
        )

    return V12Response(
        data=EventsResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            sentiment_summary=sentiment_summary,
            event_clusters=clusters,
            timeline=timeline,
            rating_changes=rating_changes,
            keyword_summary=KeywordSummary(),
            evidence_ids=evidence_ids,
            announcements_available=announcements_available,
            months_covered=months,
            warnings=(
                [w.message for w in warnings]
                if not announcements_available
                else []
            ),
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
        ),
        warnings=warnings,
    )
