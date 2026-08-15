"""Events — V12 §8.5. 从 MySQL announcements 表查询真实公告数据。

Phase C: mock → 真实 MySQL 查询。
使用共享 fcode_taxonomy 模块做分类，避免映射漂移。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
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

# ── B2 第二阶段：舆情影响分析同步适配 ─────────────────────
# 事件节点是同步 def（graph 全同步 add_node），而 generate_impacts 是
# async。两条调用路径：REST（asyncio.to_thread → 线程池线程，无事件循环）
# 与 WS（astream_events 在事件循环线程驱动同步节点）。统一做法：始终在
# 专用 worker 线程内 asyncio.run 该 coroutine 并带统一超时——禁止在事件
# 循环线程内直接 asyncio.run（抛 RuntimeError），也不引入通用 event-loop
# 框架。超时/异常 → impacts=[] + warning，绝不阻塞公告/事件链路。
_IMPACT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="events-impact"
)


def _impact_timeout() -> float:
    """影响分析统一超时：LLM 请求超时 + 股权事实/组装缓冲。"""
    try:
        return float(settings.LLM_REQUEST_TIMEOUT) + 10.0
    except Exception:  # noqa: BLE001
        return 70.0


def _run_event_impacts(
    *, company, clusters: list, timeline: list, rating_changes: list
) -> tuple[list, list[str]]:
    """构造 facts + 输入证据集并调用 generate_impacts（专用 worker 线程）。"""
    from app.application.services.events_impact_service import (
        build_equity_impact_facts,
        build_impact_facts,
        generate_impacts,
    )

    async def _compute() -> tuple[list, list[str]]:
        facts, input_evidence = build_impact_facts(
            event_clusters=clusters,
            timeline=timeline,
            rating_changes=rating_changes,
        )
        # v3.4：股权事实只送已材料化（evidence_refs 可回查）的直接持股边；
        # Neo4j/MySQL 失败 → 空事实（内部已兜底，不阻塞影响分析）
        eq_facts, eq_evidence = await build_equity_impact_facts(
            company.wind_code, settings.GRAPH_VERSION
        )
        facts.extend(eq_facts)
        input_evidence |= eq_evidence
        return await generate_impacts(
            wind_code=company.wind_code,
            sec_name=company.sec_name,
            months=36,
            graph_version=settings.GRAPH_VERSION,
            facts=facts,
            input_evidence_ids=input_evidence,
        )

    timeout = _impact_timeout()
    future = _IMPACT_EXECUTOR.submit(asyncio.run, _compute())
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        logger.warning("events: 影响分析超时（>%ss），降级", timeout)
        return [], [f"IMPACT_TIMEOUT: 影响分析超过 {timeout}s，已放弃"]
    except Exception as exc:  # noqa: BLE001 — 影响分析失败不阻塞事件链路
        logger.warning("events: 影响分析失败，降级: %s", exc)
        return [], [f"IMPACT_ERROR: {exc}"]


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


def _fetch_announcements(wind_code: str, as_of: str = "") -> list[dict]:
    """从 MySQL 查询公告元数据，最多 50 条。

    #5 期次传播：as_of（YYYYMMDD）存在时只取公告日 <= as_of 的记录。
    """
    if settings.SQL_BACKEND != "mysql":
        return []

    sql = (
        "SELECT object_id, ann_dt, n_info_title, n_info_fcode, "
        "sentiment, sentiment_method, source_uri "
        "FROM announcements "
        "WHERE wind_code = :code AND is_latest = 1 "
    )
    params: dict = {"code": wind_code}
    if as_of:
        sql += "AND ann_dt <= :asof "
        params["asof"] = as_of
    sql += "ORDER BY ann_dt DESC LIMIT 50"

    with _get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


def _fetch_event_clusters(wind_code: str, as_of: str = "") -> list[dict]:
    """从 event_clusters 表读取交接事件簇（同步）。

    #5 期次传播：as_of（YYYYMMDD）存在时只保留 end_date <= as_of 的簇。
    """
    if settings.SQL_BACKEND != "mysql":
        return []
    try:
        from app.infrastructure.persistence.mysql.event_cluster_repository import (
            MySQLEventClusterRepository,
        )
        from datetime import date, datetime

        repo = MySQLEventClusterRepository()
        cutoff = (
            datetime.strptime(as_of, "%Y%m%d").date() if as_of else date(2100, 1, 1)
        )
        records = repo.list_by_company_sync(wind_code, date(1970, 1, 1), cutoff)
        # repo 为重叠窗口语义，这里精确过滤：end_date <= 截止期
        records = [rec for rec in records if rec.end_date <= cutoff]
    except Exception:  # noqa: BLE001
        # 表未迁移或数据未交付 → 无事件簇
        return []
    clusters = []
    for rec in records:
        source_evidence = (
            rec.evidence_ids if len(rec.evidence_ids) == len(rec.sources) else []
        )
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
                        "evidence_id": source_evidence[index]
                        if source_evidence
                        else None,
                    }
                    for index, s in enumerate(rec.sources)
                ],
                "evidence_ids": rec.evidence_ids,
                "cluster_method": rec.cluster_method,
                "cluster_version": rec.cluster_version,
                "dataset_version": rec.dataset_version,
            }
        )
    return clusters


def _fetch_rating_changes(wind_code: str, as_of: str = "") -> list[dict]:
    """从 rating_changes 表读取该公司真实评级变更（供 EventsResult.rating_changes）。

    #5 期次传播：as_of（YYYYMMDD）存在时只取 published_at <= as_of 的记录
    （published_at 为空的历史记录保留，避免误删无日期数据）。
    """
    if settings.SQL_BACKEND != "mysql":
        return []
    try:
        sql = (
            "SELECT r.rating_change_id, r.quarter, r.institution, "
            "r.previous_rating, r.current_rating, r.direction, r.report_id, "
            "r.published_at, r.evidence_id, r.dataset_version, "
            "rr.title AS source_title, rr.source_uri "
            "FROM rating_changes r "
            "LEFT JOIN research_reports rr ON rr.report_id = r.report_id "
            "WHERE r.wind_code = :code "
        )
        params: dict = {"code": wind_code}
        if as_of:
            # published_at 为 varchar 日期（YYYY-MM-DD），归一化后与 YYYYMMDD 比较
            sql += (
                "AND (r.published_at IS NULL "
                "OR REPLACE(r.published_at, '-', '') <= :asof) "
            )
            params["asof"] = as_of
        sql += "ORDER BY r.quarter DESC LIMIT 30"
        with _get_engine().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().fetchall()
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

    # #5 期次传播：公告/评级/事件簇均按截止期过滤
    as_of = ""
    if plan is not None and plan.as_of:
        as_of = plan.as_of.strftime("%Y%m%d")

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

    # 查询 MySQL（P1：异常不提前返回——评级/事件簇独立查询仍需执行；
    # 记录 announcement_error，最终 partial + DB_ERROR + recoverable=True）
    announcement_error = False
    try:
        rows = _fetch_announcements(company.wind_code, as_of=as_of)
    except Exception:
        logger.exception("公告查询失败: wind_code=%s", company.wind_code)
        rows = []
        announcement_error = True

    # 无公告 → NO_ANNOUNCEMENT_DATA（P1-4：不提前返回——评级/事件簇独立查询，
    # 公告为空时模块状态为 partial/NO_ANNOUNCEMENT_DATA，但保留评级与事件簇）
    no_announcement = not rows
    runtime = state.get("runtime")
    if no_announcement and runtime is not None and hasattr(runtime, "warnings"):
        no_ann_warn = (
            "NO_ANNOUNCEMENT_DATA: 该公司在公告数据集中无公告记录，"
            "事件时间线为空，公告维度 coverage=0"
        )
        if no_ann_warn not in runtime.warnings:
            runtime.warnings.append(no_ann_warn)

    # 生成 timeline、分类统计、Evidence（确定性 ID）
    timeline = []
    categories: dict[str, int] = {}
    sentiment_counts: dict[str, int] = {}
    evidence_list = []
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    from app.domain.provenance.id_factory import NS_ANNOUNCEMENT, make_evidence_id

    sorted_rows = sorted(rows, key=lambda r: r.get("ann_dt", ""))

    for r in sorted_rows:
        fcode_raw = str(r.get("n_info_fcode", "") or "")
        first_fcode = fcode_raw.split("|")[0].strip() if fcode_raw else "unknown"
        category_label = fcode_category_label(first_fcode)
        sentiment = str(r.get("sentiment", "neutral") or "neutral")

        object_id = str(r["object_id"])
        ann_dt = str(r.get("ann_dt", "") or "")
        evidence_id = make_evidence_id(
            source_namespace=NS_ANNOUNCEMENT,
            source_type="announcement",
            source_record_id=object_id,
            period=ann_dt,
            dataset_version=settings.DATASET_VERSION,
            company_code=company.wind_code,
        )

        timeline.append(
            {
                "date": str(r.get("ann_dt", "")),
                "title": str(r.get("n_info_title", "")),
                "category": category_label,
                "sentiment": sentiment,
                "object_id": object_id,
                "sources": [str(r.get("source_uri", ""))]
                if r.get("source_uri")
                else [],
                # B2：时间线携带统一 evidence_id（供 build_impact_facts 输入
                # 证据集合，REST TimelineEvent.evidence_ids 同构）
                "evidence_ids": [evidence_id] if object_id else [],
            }
        )

        categories[category_label] = categories.get(category_label, 0) + 1
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

        evidence_list.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="announcement",
                source_record_id=object_id,
                source_table="announcements",
                # P1-4：公告 Evidence 补 period（期次一致性校验依赖它）
                period=ann_dt,
                source_title=str(r.get("n_info_title", ""))[:120],
                source_uri=r.get("source_uri"),
                module="events",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                dataset_version=settings.DATASET_VERSION,
            )
        )

    # 评级拐点（真实 rating_changes 表，独立于公告查询）
    rating_changes = _fetch_rating_changes(company.wind_code, as_of=as_of)
    for rating in rating_changes:
        evidence_id = str(rating.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        report_id = str(rating.get("report_id") or "").strip()
        published_at = str(rating.get("published_at") or "").strip()
        source_record_id = report_id or "|".join(
            [
                company.wind_code,
                str(rating.get("quarter") or ""),
                str(rating.get("institution") or ""),
                published_at,
            ]
        )
        previous = str(rating.get("previous_rating") or "")
        current = str(rating.get("current_rating") or "")
        evidence_list.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="research_report",
                source_record_id=source_record_id,
                source_table="research_reports",
                field_path="rating_change",
                period=published_at or None,
                value=f"{previous}→{current}",
                source_title=str(rating.get("source_title") or "")[:120],
                source_uri=rating.get("source_uri"),
                module="events",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                dataset_version=str(
                    rating.get("dataset_version") or settings.DATASET_VERSION
                ),
            )
        )

    # 事件簇（优先消费 event_clusters 交接数据，不重新生成/不伪造）
    clusters = _fetch_event_clusters(company.wind_code, as_of=as_of)
    known_evidence_ids = {item.evidence_id for item in evidence_list}
    for cluster in clusters:
        for source in cluster.get("sources") or []:
            evidence_id = str(source.get("evidence_id") or "").strip()
            if not evidence_id or evidence_id in known_evidence_ids:
                continue
            if source.get("source_type") != "announcement":
                continue
            evidence_list.append(
                EvidenceRef(
                    evidence_id=evidence_id,
                    source_type="announcement",
                    source_record_id=str(source.get("source_record_id") or ""),
                    source_table="announcements",
                    period=str(source.get("published_at") or "") or None,
                    source_title=str(source.get("title") or "")[:120],
                    source_uri=source.get("source_uri"),
                    module="events",
                    turn_id=turn_id,
                    trace_id=trace_id,
                    company_code=company.wind_code,
                    dataset_version=str(
                        cluster.get("dataset_version") or settings.DATASET_VERSION
                    ),
                )
            )
            known_evidence_ids.add(evidence_id)
    if not clusters and runtime is not None and hasattr(runtime, "warnings"):
        not_ready = (
            "EVENT_CLUSTER_DATA_NOT_READY: 事件簇交接数据未交付或未覆盖"
            "该公司，不生成/不伪造事件簇"
        )
        if not_ready not in runtime.warnings:
            runtime.warnings.append(not_ready)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    # 公告查询异常 → partial/DB_ERROR/recoverable=True（评级/事件簇已独立查询保留）
    if announcement_error:
        status, error_code = "partial", "DB_ERROR"
    # 无公告 → partial/NO_ANNOUNCEMENT_DATA + recoverable=True（P2 回归原行为）
    elif no_announcement:
        status, error_code = "partial", "NO_ANNOUNCEMENT_DATA"
    else:
        status, error_code = "success", None

    # ── B2 第二阶段：舆情影响分析（共享服务 generate_impacts；失败降级）──
    # 无公告且无事件簇 → 无事实可分析，跳过（不伪造影响结论），公告/事件链路原样。
    impacts: list = []
    impact_warnings: list[str] = []
    if not no_announcement or clusters:
        impacts, impact_warnings = _run_event_impacts(
            company=company,
            clusters=clusters,
            timeline=timeline,
            rating_changes=rating_changes,
        )
    else:
        impact_warnings.append(
            "IMPACT_SKIPPED_NO_FACTS: 无公告且无事件簇，跳过影响分析"
        )

    return {
        "module_status": {
            "events": ModuleStatus(
                state=status,
                error_code=error_code,
                recoverable=True if no_announcement or announcement_error else False,
                duration_ms=elapsed_ms,
            )
        },
        "results": ModuleResults(
            events=EventsResult(
                timeline=timeline,
                clusters=clusters,
                rating_changes=rating_changes,
                evidence=evidence_list,
                impacts=impacts,
                impact_warnings=impact_warnings,
            )
        ),
    }
