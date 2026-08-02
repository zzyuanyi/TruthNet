"""舆情事件路由 — V12 §11.11 + Phase C 任务 15.

GET /api/v1/companies/{code}/events?months=36

优先消费 event_clusters 交接数据（返回 event_cluster_id + 结构化 sources + evidence_ids）；
无事件簇数据 → EVENT_CLUSTER_DATA_NOT_READY；无公告 → NO_ANNOUNCEMENT_DATA。
不使用 Mock 补齐，不重新生成事件簇 ID。
"""

import uuid
from collections import Counter
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.events import (
    EventCluster,
    EventSourceDTO,
    EventsResponseData,
    KeywordSummary,
    SentimentSummary,
    TimelineEvent,
)
from app.application.services.company_resolver import CompanyResolver
from app.core.config import settings

router = APIRouter(tags=["events"])


def _trace() -> str:
    return str(uuid.uuid4())


def _fetch_event_clusters(wind_code: str) -> list[EventCluster]:
    """从 event_clusters 表读取交接数据."""
    from app.infrastructure.persistence.mysql.event_cluster_repository import (
        MySQLEventClusterRepository,
    )

    repo = MySQLEventClusterRepository()
    try:
        records = repo.list_by_company_sync(
            wind_code, date(1970, 1, 1), date(2100, 1, 1)
        )
    except Exception:  # noqa: BLE001
        # 表未迁移或数据未交付 → 视为无数据，不报错
        return []
    clusters = []
    for rec in records:
        clusters.append(
            EventCluster(
                event_cluster_id=rec.event_cluster_id,
                topic=rec.topic,
                event_count=rec.event_count,
                start_date=rec.start_date.isoformat(),
                end_date=rec.end_date.isoformat(),
                sentiment=rec.sentiment,
                summary=rec.summary,
                cluster_method=rec.cluster_method,
                cluster_version=rec.cluster_version,
                sources=[
                    EventSourceDTO(
                        source_id=s.source_id,
                        source_type=s.source_type,
                        source_record_id=s.source_record_id,
                        title=s.title,
                        published_at=s.published_at,
                        source_uri=s.source_uri,
                        content_hash=s.content_hash,
                        fcode=s.fcode,
                    )
                    for s in rec.sources
                ],
                evidence_ids=rec.evidence_ids,
            )
        )
    return clusters


def _fetch_announcements(wind_code: str, limit: int = 200) -> list[dict]:
    """查询公告元数据."""
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT object_id, ann_dt, n_info_title, n_info_fcode, "
                    "sentiment, source_uri "
                    "FROM announcements "
                    "WHERE wind_code = :code AND is_latest = 1 "
                    "ORDER BY ann_dt DESC "
                    "LIMIT :limit"
                ),
                {"code": wind_code, "limit": limit},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


@router.get("/companies/{code}/events")
async def get_company_events(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    months: int = Query(default=36, ge=1, le=120, description="回溯月数"),
):
    """舆情事件 — 事件簇（优先 event_clusters）+ 公告时间线。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []

    # 1. MySQL 解析公司
    resolver = CompanyResolver()
    company = await resolver.resolve(code)
    if company is None:
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
    wind_code = company.wind_code
    sec_name = company.sec_name

    if settings.SQL_BACKEND != "mysql":
        return V12Response(
            data=EventsResponseData(
                wind_code=wind_code,
                sec_name=sec_name,
                announcements_available=False,
                months_covered=months,
                warnings=["DATA_SOURCE_UNAVAILABLE: 非 full profile 不提供事件数据"],
            ),
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
                dataset_version=settings.DATASET_VERSION,
            ),
            warnings=[
                WarningItem(
                    code="DATA_SOURCE_UNAVAILABLE",
                    message="非 full profile 不提供事件数据。",
                    module="events",
                    recoverable=True,
                )
            ],
        )

    # 2. 读取事件簇交接数据
    event_clusters: list[EventCluster] = []
    try:
        event_clusters = _fetch_event_clusters(wind_code)
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            WarningItem(
                code="EVENT_CLUSTER_DATA_ERROR",
                message=f"事件簇读取失败: {exc}",
                module="events",
                recoverable=True,
            )
        )

    if not event_clusters:
        warnings.append(
            WarningItem(
                code="EVENT_CLUSTER_DATA_NOT_READY",
                message=(
                    "事件簇交接数据尚未交付或未覆盖该公司，" "本次不生成/不伪造事件簇。"
                ),
                module="events",
                recoverable=True,
            )
        )

    # 3. 公告时间线（降级视图 + 情绪统计）
    timeline: list[TimelineEvent] = []
    sentiment_summary = SentimentSummary()
    announcements_available = False
    cluster_evidence_ids: list[str] = [
        eid for c in event_clusters for eid in c.evidence_ids
    ]

    try:
        rows = _fetch_announcements(wind_code)
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            WarningItem(
                code="EVENTS_DATA_ERROR",
                message=f"公告数据查询失败: {exc}",
                module="events",
                recoverable=True,
            )
        )
        rows = []

    if rows:
        announcements_available = True
        from app.domain.events.fcode_taxonomy import fcode_category_label

        sentiment_counter: Counter = Counter()
        for r in rows:
            fcode_raw = str(r.get("n_info_fcode", "") or "")
            first_fcode = fcode_raw.split("|")[0].strip() if fcode_raw else ""
            label = fcode_category_label(first_fcode)
            sentiment = str(r.get("sentiment", "neutral") or "neutral")
            sentiment_counter[sentiment] += 1
            timeline.append(
                TimelineEvent(
                    date=str(r.get("ann_dt", "") or ""),
                    title=str(r.get("n_info_title", "") or ""),
                    category="公告",
                    fcode_label=label,
                    sentiment=sentiment,
                    summary=str(r.get("n_info_title", "") or ""),
                    sources=[str(r["source_uri"])] if r.get("source_uri") else [],
                    evidence_ids=[f"ann_{r.get('object_id', '')}"]
                    if r.get("object_id")
                    else [],
                )
            )
        sentiment_summary = SentimentSummary(
            positive_count=sentiment_counter.get("positive", 0),
            negative_count=sentiment_counter.get("negative", 0),
            neutral_count=sentiment_counter.get("neutral", 0),
            total_count=len(rows),
            negative_ratio=(
                sentiment_counter.get("negative", 0) / len(rows) if rows else 0.0
            ),
        )
    else:
        warnings.append(
            WarningItem(
                code="NO_ANNOUNCEMENT_DATA",
                message=f"{sec_name}({wind_code}) 无公告数据覆盖，返回空时间线。",
                module="events",
                recoverable=True,
            )
        )

    return V12Response(
        data=EventsResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            sentiment_summary=sentiment_summary,
            event_clusters=event_clusters,
            timeline=timeline,
            rating_changes=[],
            keyword_summary=KeywordSummary(),
            evidence_ids=cluster_evidence_ids,
            announcements_available=announcements_available,
            months_covered=months,
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
