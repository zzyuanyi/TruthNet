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
    EventsResult,
    EvidenceRef,
    ModuleResults,
    ModuleStatus,
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

    # 无公告 → 空结果（成功）
    if not rows:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "module_status": {
                "events": ModuleStatus(state="success", duration_ms=elapsed_ms)
            },
            "results": ModuleResults(
                events=EventsResult(timeline=[], clusters=[], evidence=[])
            ),
        }

    # 生成 timeline、分类统计、Evidence
    timeline = []
    categories: dict[str, int] = {}
    sentiment_counts: dict[str, int] = {}
    evidence_list = []

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
                "sources": [str(r.get("source_uri", ""))]
                if r.get("source_uri")
                else [],
            }
        )

        categories[category_label] = categories.get(category_label, 0) + 1
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

        evidence_list.append(
            EvidenceRef(
                evidence_id=f"ann_{r['object_id']}",
                source_type="announcement",
                source_record_id=str(r["object_id"]),
                source_title=str(r.get("n_info_title", ""))[:120],
            )
        )

    # 事件簇
    clusters = []
    if sentiment_counts.get("negative", 0) > 0:
        first_date = sorted_rows[0].get("ann_dt", "")
        last_date = sorted_rows[-1].get("ann_dt", "")
        clusters.append(
            {
                "topic": "负面公告",
                "event_count": sentiment_counts["negative"],
                "date_range": f"{first_date} 至 {last_date}"
                if len(sorted_rows) > 1
                else str(first_date),
            }
        )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "module_status": {
            "events": ModuleStatus(state="success", duration_ms=elapsed_ms)
        },
        "results": ModuleResults(
            events=EventsResult(
                timeline=timeline,
                clusters=clusters,
                evidence=evidence_list,
            )
        ),
    }
