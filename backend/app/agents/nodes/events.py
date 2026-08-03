"""Events — V12 §8.5. 从 MySQL announcements 表查询真实公告数据。

Phase C: mock → 真实 MySQL 查询。
使用共享 fcode_taxonomy 模块做分类，避免映射漂移。
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import (
    AgentState,
    ModuleStatus,
    EvidenceRef,
    EventsResult,
    ModuleResults,
)
from app.core.config import settings
from app.domain.events.fcode_taxonomy import fcode_category_label

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def _get_engine() -> Engine:
    """惰性缓存 MySQL engine。"""
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        _engine = create_engine(url, echo=False)
    return _engine


def _fetch_announcements(wind_code: str) -> list[dict]:
    """从 MySQL 查询公告元数据，最多 50 条。"""
    if settings.SQL_BACKEND != "mysql":
        return []

    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT object_id, ann_dt, n_info_title, n_info_fcode, "
                    "sentiment, sentiment_method, source_uri "
                    "FROM announcements "
                    "WHERE wind_code = :code AND is_latest = 1 "
                    "ORDER BY ann_dt DESC "
                    "LIMIT 50"
                ),
                {"code": wind_code},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]


def _fetch_event_clusters(wind_code: str) -> list[dict]:
    """从 event_clusters 表读取交接事件簇（同步）。"""
    if settings.SQL_BACKEND != "mysql":
        return []
    try:
        from app.infrastructure.persistence.mysql.event_cluster_repository import (
            MySQLEventClusterRepository,
        )
        from datetime import date

        repo = MySQLEventClusterRepository()
        records = repo.list_by_company_sync(
            wind_code, date(1970, 1, 1), date(2100, 1, 1)
        )
    except Exception:  # noqa: BLE001
        # 表未迁移或数据未交付 → 无事件簇
        return []
    clusters = []
    for rec in records:
        clusters.append(
            {
                "event_cluster_id": rec.event_cluster_id,
                "topic": rec.topic,
                "summary": rec.summary,
                "start_date": rec.start_date.isoformat(),
                "end_date": rec.end_date.isoformat(),
                "event_count": rec.event_count,
                "sentiment": rec.sentiment,
                "sentiment_score": rec.sentiment_score,
                "sources": [
                    {
                        "source_id": s.source_id,
                        "source_type": s.source_type,
                        "source_record_id": s.source_record_id,
                        "title": s.title,
                        "published_at": (
                            s.published_at.isoformat() if s.published_at else None
                        ),
                        "source_uri": s.source_uri,
                        "content_hash": s.content_hash,
                        "fcode": s.fcode,
                    }
                    for s in rec.sources
                ],
                "evidence_ids": rec.evidence_ids,
                "cluster_method": rec.cluster_method,
                "cluster_version": rec.cluster_version,
                "dataset_version": rec.dataset_version,
            }
        )
    return clusters


def _fetch_rating_changes(wind_code: str) -> list[dict]:
    """从 rating_changes 表读取该公司真实评级变更（供 EventsResult.rating_changes）。"""
    if settings.SQL_BACKEND != "mysql":
        return []
    try:
        with _get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT quarter, institution, previous_rating, current_rating, "
                        "direction, published_at "
                        "FROM rating_changes WHERE wind_code = :code "
                        "ORDER BY quarter DESC LIMIT 30"
                    ),
                    {"code": wind_code},
                )
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001 — 评级表缺失时无拐点
        return []


def events_node(state: AgentState) -> dict:
    t0 = time.perf_counter()

    plan = state.get("plan")
    company = state.get("company")

    # 未选中 → no-op
    if plan is not None and "events" not in plan.requested_modules:
        return {
            "module_status": {"events": ModuleStatus(state="skipped")},
            "results": ModuleResults(events=None),
        }

    if company is None:
        return {
            "module_status": {
                "events": ModuleStatus(state="failed", error_code="NO_COMPANY")
            },
            "results": ModuleResults(events=None),
        }

    # 数据源不可用 → partial
    if settings.SQL_BACKEND != "mysql":
        return {
            "module_status": {
                "events": ModuleStatus(
                    state="partial",
                    error_code="DATA_SOURCE_UNAVAILABLE",
                    recoverable=True,
                )
            },
            "results": ModuleResults(
                events=EventsResult(timeline=[], clusters=[], evidence=[])
            ),
        }

    # 查询 MySQL
    try:
        rows = _fetch_announcements(company.wind_code)
    except Exception:
        logger.exception("公告查询失败: wind_code=%s", company.wind_code)
        return {
            "module_status": {
                "events": ModuleStatus(
                    state="partial", error_code="DB_ERROR", recoverable=True
                )
            },
            "results": ModuleResults(
                events=EventsResult(timeline=[], clusters=[], evidence=[])
            ),
        }

    # 无公告 → NO_ANNOUNCEMENT_DATA（空 timeline + 明确 warning + coverage 说明）
    if not rows:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        runtime = state.get("runtime")
        if runtime is not None and hasattr(runtime, "warnings"):
            no_ann_warn = (
                "NO_ANNOUNCEMENT_DATA: 该公司在公告数据集中无公告记录，"
                "事件时间线为空，公告维度 coverage=0"
            )
            if no_ann_warn not in runtime.warnings:
                runtime.warnings.append(no_ann_warn)
        return {
            "module_status": {
                "events": ModuleStatus(
                    state="partial",
                    error_code="NO_ANNOUNCEMENT_DATA",
                    recoverable=True,
                    duration_ms=elapsed_ms,
                )
            },
            "results": ModuleResults(
                events=EventsResult(timeline=[], clusters=[], evidence=[])
            ),
            "runtime": runtime,
        }

    # 生成 timeline、分类统计、Evidence（确定性 ID）
    timeline = []
    categories: dict[str, int] = {}
    sentiment_counts: dict[str, int] = {}
    evidence_list = []
    runtime = state.get("runtime")
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    from app.domain.provenance.id_factory import NS_ANNOUNCEMENT, make_evidence_id

    sorted_rows = sorted(rows, key=lambda r: r.get("ann_dt", ""))

    for r in sorted_rows:
        fcode_raw = str(r.get("n_info_fcode", "") or "")
        first_fcode = fcode_raw.split("|")[0].strip() if fcode_raw else "unknown"
        category_label = fcode_category_label(first_fcode)
        sentiment = str(r.get("sentiment", "neutral") or "neutral")

        timeline.append(
            {
                "date": str(r.get("ann_dt", "")),
                "title": str(r.get("n_info_title", "")),
                "category": category_label,
                "sentiment": sentiment,
                "object_id": str(r.get("object_id", "")),
                "sources": [str(r.get("source_uri", ""))]
                if r.get("source_uri")
                else [],
            }
        )

        categories[category_label] = categories.get(category_label, 0) + 1
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

        object_id = str(r["object_id"])
        evidence_id = make_evidence_id(
            source_namespace=NS_ANNOUNCEMENT,
            source_type="announcement",
            source_record_id=object_id,
            period=str(r.get("ann_dt", "") or ""),
            dataset_version=settings.DATASET_VERSION,
            company_code=company.wind_code,
        )
        evidence_list.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="announcement",
                source_record_id=object_id,
                source_table="announcements",
                source_title=str(r.get("n_info_title", ""))[:120],
                source_uri=r.get("source_uri"),
                module="events",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                dataset_version=settings.DATASET_VERSION,
            )
        )

    # 评级拐点（真实 rating_changes 表）
    rating_changes = _fetch_rating_changes(company.wind_code)

    # 事件簇（优先消费 event_clusters 交接数据，不重新生成/不伪造）
    clusters = _fetch_event_clusters(company.wind_code)
    if not clusters:
        runtime = state.get("runtime")
        if runtime is not None and hasattr(runtime, "warnings"):
            not_ready = (
                "EVENT_CLUSTER_DATA_NOT_READY: 事件簇交接数据未交付或未覆盖"
                "该公司，不生成/不伪造事件簇"
            )
            if not_ready not in runtime.warnings:
                runtime.warnings.append(not_ready)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "module_status": {
            "events": ModuleStatus(state="success", duration_ms=elapsed_ms)
        },
        "results": ModuleResults(
            events=EventsResult(
                timeline=timeline,
                clusters=clusters,
                rating_changes=rating_changes,
                evidence=evidence_list,
            )
        ),
    }
