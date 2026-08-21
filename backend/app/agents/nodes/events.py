"""Events — V12 §8.5. 从 MySQL announcements 表查询真实公告数据。

Phase C: mock → 真实 MySQL 查询。
使用共享 fcode_taxonomy 模块做分类，避免映射漂移。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import text
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

# ── B2 第二阶段：舆情影响分析同步适配 ─────────────────────
# 事件节点是同步 def（graph 全同步 add_node），而 generate_impacts 是
# async。两条调用路径：REST（asyncio.to_thread → 线程池线程，无事件循环）
# 与 WS（astream_events 在事件循环线程驱动同步节点）。统一做法：始终在
# 专用 worker 线程内 asyncio.run 该 coroutine 并带统一超时——禁止在事件
# 循环线程内直接 asyncio.run（抛 RuntimeError），也不引入通用 event-loop
# 框架。超时/异常 → impacts=[] + warning，绝不阻塞公告/事件链路。
#
# B2 批次 C（方案 §四）：不再使用全局单线程 ThreadPoolExecutor(max_workers=1)；
# 改为按配置的有界执行器（EVENT_IMPACT_MAX_WORKERS）+ 有界信号量
# （EVENT_IMPACT_MAX_INFLIGHT）限制同时执行数；队列已满快速返回
# impacts=[] + IMPACT_BUSY。执行器/信号量惰性创建，便于测试注入重置。
_IMPACT_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None
_IMPACT_SEMAPHORE: threading.Semaphore | None = None


def _impact_executor() -> concurrent.futures.ThreadPoolExecutor:
    """惰性创建有界影响分析执行器（线程数 = EVENT_IMPACT_MAX_WORKERS）。"""
    global _IMPACT_EXECUTOR
    if _IMPACT_EXECUTOR is None:
        try:
            workers = max(1, int(settings.EVENT_IMPACT_MAX_WORKERS))
        except Exception:  # noqa: BLE001
            workers = 3
        _IMPACT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="events-impact"
        )
    return _IMPACT_EXECUTOR


def _impact_semaphore() -> threading.Semaphore:
    """惰性创建有界信号量（同时执行/在途影响分析上限 = EVENT_IMPACT_MAX_INFLIGHT）。"""
    global _IMPACT_SEMAPHORE
    if _IMPACT_SEMAPHORE is None:
        try:
            inflight = max(1, int(settings.EVENT_IMPACT_MAX_INFLIGHT))
        except Exception:  # noqa: BLE001
            inflight = 8
        _IMPACT_SEMAPHORE = threading.Semaphore(inflight)
    return _IMPACT_SEMAPHORE


def _impact_timeout() -> float:
    """影响分析统一超时：LLM 请求超时 + 股权事实/组装缓冲。"""
    try:
        return float(settings.LLM_REQUEST_TIMEOUT) + 10.0
    except Exception:  # noqa: BLE001
        return 70.0


def _run_event_impacts(
    *, company, clusters: list, timeline: list, rating_changes: list
) -> tuple[list, list[str]]:
    """构造 facts + 输入证据集并调用 generate_impacts（专用 worker 线程）。

    B2 批次 C：有界信号量限制在途影响分析数；满时快速返回 IMPACT_BUSY。
    外层超时后取消未开始 future，已运行任务只标降级 warning（不宣称已取消）。
    B2 批次 D：股权事实失败经 build_equity_impact_facts 返回 warnings，并入
    影响分析 warnings（保留公告/事件簇/评级事实，不阻断 B2）。
    """
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
        # Neo4j/MySQL 失败 → 空事实 + IMPACT_EQUITY_FACTS_FAILED warning
        # （内部已兜底，不阻断影响分析）
        eq_facts, eq_evidence, eq_warnings = await build_equity_impact_facts(
            company.wind_code, settings.GRAPH_VERSION
        )
        facts.extend(eq_facts)
        input_evidence |= eq_evidence
        conclusions, impact_warnings = await generate_impacts(
            wind_code=company.wind_code,
            sec_name=company.sec_name,
            months=36,
            graph_version=settings.GRAPH_VERSION,
            facts=facts,
            input_evidence_ids=input_evidence,
        )
        return conclusions, list(eq_warnings) + list(impact_warnings)

    sem = _impact_semaphore()
    # 队列/在途已满 → 快速降级（不排队、不阻塞公告/事件链路）
    if not sem.acquire(blocking=False):
        logger.warning("events: 影响分析在途数已达上限，快速降级 IMPACT_BUSY")
        return [], ["IMPACT_BUSY: 影响分析并发已满，本次跳过影响分析"]

    timeout = _impact_timeout()
    future = _impact_executor().submit(asyncio.run, _compute())
    # 任务真正完成（成功/失败/超时后仍在运行）才释放信号量，防止超时后
    # 提前释放导致在途数被低估、突破有界并发
    future.add_done_callback(lambda _f: sem.release())
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        # 尚未开始的 future → cancel()（返回 True）；已运行任务 cancel() 返回
        # False，不宣称"已取消"，只标降级 warning（LLM 自身 timeout 兜底退出）
        if future.cancel():
            logger.warning("events: 影响分析超时（>%ss），已取消未开始任务", timeout)
        else:
            logger.warning("events: 影响分析超时（>%ss），任务仍在运行，降级", timeout)
        return [], [f"IMPACT_TIMEOUT: 影响分析超过 {timeout}s，已降级"]
    except Exception as exc:  # noqa: BLE001 — 影响分析失败不阻塞事件链路
        logger.warning("events: 影响分析失败，降级: %s", exc)
        return [], [f"IMPACT_ERROR: {exc}"]


def _get_engine() -> Engine:
    """惰性缓存 MySQL engine（8/19 全面审查：改用完整 profile key，
    避免切库后复用旧库 Engine 命中错误数据）。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


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


def _fetch_event_clusters(
    wind_code: str, as_of: str = ""
) -> tuple[list[dict], str | None]:
    """从 event_clusters 表读取交接事件簇（同步）。

    返回 (clusters, issue)。issue 取值：
    - None：正常（含转换后确有簇）；
    - "EVENT_CLUSTER_DATA_ERROR"：查询/结构校验失败，或数据存在但全部不可解析；
    - "EVENT_CLUSTER_DATA_NOT_READY"：该库该表确无此公司数据（未交付/未覆盖）。

    #5 期次传播：as_of（YYYYMMDD）存在时只保留 end_date <= as_of 的簇。
    批次 E 整改：不再静默 return []——异常全 traceback，转换循环纳入统一
    错误处理，空结果区分 DATA_ERROR 与 NOT_READY（防止把数据损坏误报为未交付）。
    """
    if settings.SQL_BACKEND != "mysql":
        return [], None
    from datetime import date, datetime

    cutoff = datetime.strptime(as_of, "%Y%m%d").date() if as_of else date(2100, 1, 1)
    start = date(1970, 1, 1)
    try:
        from app.infrastructure.persistence.mysql.event_cluster_repository import (
            MySQLEventClusterRepository,
        )

        records = MySQLEventClusterRepository().list_by_company_sync(
            wind_code, start, cutoff
        )
        # repo 为重叠窗口语义，这里精确过滤：end_date <= 截止期
        records = [rec for rec in records if rec.end_date <= cutoff]
    except Exception:  # noqa: BLE001
        logger.exception(
            "event_clusters 查询失败（EVENT_CLUSTER_DATA_ERROR） wind_code=%s",
            wind_code,
        )
        return [], "EVENT_CLUSTER_DATA_ERROR"
    try:
        clusters = [_cluster_to_dict(rec) for rec in records]
    except Exception:  # noqa: BLE001
        logger.exception(
            "event_clusters 行转换失败（EVENT_CLUSTER_DATA_ERROR） wind_code=%s",
            wind_code,
        )
        return [], "EVENT_CLUSTER_DATA_ERROR"
    if clusters:
        return clusters, None
    # 空结果区分：数据存在但全部不可解析（DATA_ERROR）vs 真无数据（NOT_READY）
    try:
        with _get_engine().connect() as conn:
            has_rows = (
                conn.execute(
                    text(
                        "SELECT 1 FROM event_clusters "
                        "WHERE wind_code = :code "
                        "  AND start_date <= :end AND end_date >= :start "
                        "LIMIT 1"
                    ),
                    {"code": wind_code, "start": start, "end": cutoff},
                ).first()
                is not None
            )
    except Exception:  # noqa: BLE001
        logger.exception(
            "event_clusters 存在性检查失败（EVENT_CLUSTER_DATA_ERROR） wind_code=%s",
            wind_code,
        )
        return [], "EVENT_CLUSTER_DATA_ERROR"
    issue = "EVENT_CLUSTER_DATA_ERROR" if has_rows else "EVENT_CLUSTER_DATA_NOT_READY"
    return [], issue


def _cluster_to_dict(rec) -> dict:
    """EventClusterRecord → Agent 事件簇 dict（B2 输入口径）。"""
    source_evidence = (
        rec.evidence_ids if len(rec.evidence_ids) == len(rec.sources) else []
    )
    return {
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
                "evidence_id": source_evidence[index] if source_evidence else None,
            }
            for index, s in enumerate(rec.sources)
        ],
        "evidence_ids": rec.evidence_ids,
        "cluster_method": rec.cluster_method,
        "cluster_version": rec.cluster_version,
        "dataset_version": rec.dataset_version,
    }


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


def _web_search_company_news(
    *, company, turn_id: str, trace_id: str
) -> list[EvidenceRef]:
    """会5：舆情环节库内无公告 → 联网检索新闻/公告并构建来源标注证据.

    Returns:
        list[EvidenceRef]（source_type="web_search"），无命中 → []。
        默认 off 时 web_search 返回 []，恒 []，行为与现状完全一致。
    """
    from app.application.services.web_search_service import web_search
    from app.domain.provenance.id_factory import NS_WEB_SEARCH, make_evidence_id

    hits = web_search(f"{company.sec_name} {company.wind_code} 公告 舆情 最新")
    if not hits:
        return []
    evidence: list[EvidenceRef] = []
    for i, hit in enumerate(hits[:3]):
        evidence.append(
            EvidenceRef(
                evidence_id=make_evidence_id(
                    source_namespace=NS_WEB_SEARCH,
                    source_type="web_search",
                    source_record_id=company.wind_code,
                    field_path=f"news_{i}",
                    company_code=company.wind_code,
                ),
                source_type="web_search",
                source_record_id=company.wind_code,
                field_path=f"news_{i}",
                source_title=(hit.title or "")[:120],
                source_uri=hit.url or None,
                source_excerpt=(hit.snippet or "")[:200],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                module="events",
                retrieved_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    return evidence


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
    clusters, cluster_issue = _fetch_event_clusters(company.wind_code, as_of=as_of)
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
        # 批次 E：区分数据错误与未交付（数据损坏不得误报为"未覆盖"）
        if cluster_issue == "EVENT_CLUSTER_DATA_ERROR":
            warn = (
                "EVENT_CLUSTER_DATA_ERROR: 事件簇数据存在但读取/结构校验失败"
                "（详见服务日志），不生成/不伪造事件簇"
            )
        else:
            warn = (
                "EVENT_CLUSTER_DATA_NOT_READY: 事件簇交接数据未交付或未覆盖"
                "该公司，不生成/不伪造事件簇"
            )
        if warn not in runtime.warnings:
            runtime.warnings.append(warn)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    # 公告查询异常 → partial/DB_ERROR/recoverable=True（评级/事件簇已独立查询保留）
    if announcement_error:
        status, error_code = "partial", "DB_ERROR"
    # 批次 E：事件簇数据错误 → partial/EVENT_CLUSTER_DATA_ERROR（不得静默成功）
    elif cluster_issue == "EVENT_CLUSTER_DATA_ERROR":
        status, error_code = "partial", "EVENT_CLUSTER_DATA_ERROR"
    # 无公告 → partial/NO_ANNOUNCEMENT_DATA + recoverable=True（P2 回归原行为）
    elif no_announcement:
        status, error_code = "partial", "NO_ANNOUNCEMENT_DATA"
    else:
        status, error_code = "success", None

    # ── B2 第二阶段：舆情影响分析（共享服务 generate_impacts；失败降级）──
    # B2 批次 A（方案 §二.4）：只有 plan.impact_requested 才触发 B2。
    # B2 批次 B（方案 §三）：有任一事实（公告时间线/事件簇/评级变化）才可
    # 分析——评级-only 路径不再被遗漏。无事实 → 跳过（不伪造影响结论），
    # 公告/事件链路原样。
    impacts: list = []
    impact_warnings: list[str] = []
    # B2 批次 B（方案 §三）：评级-only 路径不再被遗漏。评级无 evidence_id
    # （数据不足）不可被引用 → 不计入 B2 事实（仍保留在
    # EventsResult.rating_changes 供展示/评分），不伪造影响结论。
    citable_rating_changes = [
        r for r in rating_changes if str(r.get("evidence_id") or "").strip()
    ]
    has_facts = bool(timeline or clusters or citable_rating_changes)
    if plan is not None and plan.impact_requested and has_facts:
        impacts, impact_warnings = _run_event_impacts(
            company=company,
            clusters=clusters,
            timeline=timeline,
            rating_changes=citable_rating_changes,
        )
    elif plan is not None and plan.impact_requested and not has_facts:
        impact_warnings.append(
            "IMPACT_SKIPPED_NO_FACTS: 无公告/事件簇/评级变化，跳过影响分析"
        )

    # Phase E 会5：舆情环节触发点——库内无公告且非查询异常 → 联网检索 + 来源标注
    # （默认 off 时 web_search 返回 []，无任何副作用，行为与现状完全一致）
    if no_announcement and not announcement_error:
        evidence_list.extend(
            _web_search_company_news(
                company=company, turn_id=turn_id, trace_id=trace_id
            )
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
