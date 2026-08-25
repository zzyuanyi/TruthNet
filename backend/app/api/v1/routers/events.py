"""舆情事件路由 — V12 §11.11 + Phase C 任务 10/15.

GET /api/v1/companies/{code}/events?months=36

要求（任务 10）:
  - months 参数真正过滤日期（公告与事件簇）
  - 返回真实事件簇（event_clusters 表）
  - 返回真实评级拐点（research_reports → 规范化 direction）
  - keyword_summary 基于真实公告标题
  - timeline evidence_ids 使用统一 ID Factory（可 Lookup 查询）
  - 无事件簇 → EVENT_CLUSTER_DATA_NOT_READY；无公告 → NO_ANNOUNCEMENT_DATA
"""

import asyncio
import logging
import os
import re
import tempfile
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.errors import ErrorCode
from app.api.v1.schemas.events import (
    AnnouncementSummaryData,
    EventCluster,
    EventSourceDTO,
    EventsResponseData,
    ImpactConclusion,
    KeywordSummary,
    RatingChange,
    SentimentSummary,
    TimelineEvent,
)
from app.application.services.company_resolver import CompanyResolver
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

# 关键词提取：跳过常见停用词
_STOPWORDS = {
    "公司",
    "公告",
    "关于",
    "的",
    "与",
    "及",
    "暨",
    "提示",
    "进展",
    "情况",
    "事项",
    "报告",
    "通知",
    "结果",
    "公告日",
    "披露",
    "召开",
    "会议",
    "一次",
    "相关",
}


def _trace() -> str:
    return str(uuid.uuid4())


_MAX_PDF_BYTES = 15 * 1024 * 1024
_MAX_PDF_TEXT_CHARS = 12000
_MAX_PDF_PAGES = 8


def _is_http_uri(uri: str | None) -> bool:
    """只允许 http/https，避免 SSRF 类本地协议下载。"""
    return bool(uri) and str(uri).startswith(("http://", "https://"))


def _extract_pdf_text(path: str) -> str:
    """PDF → 纯文本（前 N 页 + 长度上限）。pypdf 未安装时明确报错。"""
    try:
        from pypdf import PdfReader
    except Exception as exc:  # noqa: BLE001 — 缺失依赖返回明确错误
        raise RuntimeError("PDF_PARSER_UNAVAILABLE: pypdf 未安装") from exc

    parts: list[str] = []
    reader = PdfReader(path)
    for page in reader.pages[:_MAX_PDF_PAGES]:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — 单页解析失败跳过
            text = ""
        parts.append(text.strip())
        if sum(len(p) for p in parts) >= _MAX_PDF_TEXT_CHARS:
            break
    return "\n".join(parts)[:_MAX_PDF_TEXT_CHARS].strip()


def _summarize_announcement_text(*, title: str, text: str, sec_name: str) -> str:
    """LLM 摘要；失败返回空串（由调用方降级为原文摘录）。"""
    if not text:
        return ""
    try:
        from app.agents.llm_sync import run_llm_chat

        messages = [
            {
                "role": "system",
                "content": (
                    "你是上市公司公告摘要助手。只依据给定公告原文概括，不得补充原文"
                    "没有的事实。输出 2-4 句中文摘要，先说明公告事项，再说影响与风险。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"公司：{sec_name}\n公告标题：{title}\n公告正文（节选）：\n{text}"
                ),
            },
        ]
        return str(run_llm_chat(messages) or "").strip()
    except Exception:  # noqa: BLE001 — LLM 失败降级为原文摘录
        return ""


def _fetch_event_clusters(wind_code: str, start_date: date) -> list[EventCluster]:
    """从 event_clusters 表读取交接数据（按日期过滤）。"""
    from app.infrastructure.persistence.mysql.event_cluster_repository import (
        MySQLEventClusterRepository,
    )

    repo = MySQLEventClusterRepository()
    try:
        records = repo.list_by_company_sync(wind_code, start_date, date(2100, 1, 1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取 event_clusters 失败 wind_code=%s: %s", wind_code, exc)
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


def _fetch_announcements(
    wind_code: str, start_date: str, limit: int = 200
) -> list[dict]:
    """查询公告元数据（months 过滤：ann_dt >= start_date）。lite 模式走 SQLite。"""
    from sqlalchemy import text

    from app.domain.finance._engine_utils import get_engine

    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT object_id, ann_dt, n_info_title, n_info_fcode, "
                        "sentiment, source_uri "
                        "FROM announcements "
                        "WHERE wind_code = :code AND is_latest = 1 "
                        "AND ann_dt >= :start "
                        "ORDER BY ann_dt DESC "
                        "LIMIT :limit"
                    ),
                    {"code": wind_code, "start": start_date, "limit": limit},
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]
    except Exception:
        return []


def _fetch_rating_changes(wind_code: str, start_date: str) -> list[RatingChange]:
    """从 rating_changes 衍生表读取真实评级变更（含统一 Evidence ID 可 Lookup）。

    与 Agent 消费同一衍生表，避免 research_reports 与衍生表两条链路口径漂移；
    title 从 evidence_refs.source_title 关联取回。
    """
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
                    "SELECT rc.quarter, rc.institution, rc.previous_rating, "
                    "rc.current_rating, rc.direction, rc.published_at, "
                    "rc.evidence_id, er.source_title "
                    "FROM rating_changes rc "
                    "LEFT JOIN evidence_refs er ON er.evidence_id = rc.evidence_id "
                    "WHERE rc.wind_code = :code AND rc.published_at >= :start "
                    "ORDER BY rc.published_at DESC LIMIT 100"
                ),
                {"code": wind_code, "start": start_date},
            )
            .mappings()
            .all()
        )
    out: list[RatingChange] = []
    for r in rows:
        out.append(
            RatingChange(
                date=str(r["published_at"] or ""),
                org_name=str(r["institution"] or "未知机构"),
                prev_rating=str(r["previous_rating"] or ""),
                new_rating=str(r["current_rating"] or ""),
                change=str(r["direction"] or "maintain"),
                title=str(r["source_title"] or "")[:120],
                evidence_id=str(r["evidence_id"] or ""),
            )
        )
    return out


def _build_keyword_summary(titles: list[str]) -> KeywordSummary:
    """从公告标题提取高频关键词。"""
    freq: Counter = Counter()
    for t in titles:
        text = str(t or "")
        # 提取 2-6 字词块
        tokens = re.findall(r"[一-龥A-Za-z0-9]{2,6}", text)
        for tok in tokens:
            if tok in _STOPWORDS or len(tok) < 2:
                continue
            freq[tok] += 1
    top = [{"keyword": k, "count": v} for k, v in freq.most_common(10)]
    return KeywordSummary(top_keywords=top, negative_keywords=[])


@router.get(
    "/companies/{code}/events",
    response_model=V12Response[EventsResponseData],
)
async def get_company_events(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    months: int = Query(default=36, ge=1, le=120, description="回溯月数"),
    include_impacts: bool = Query(
        default=False,
        description="是否生成舆情影响结论（⑧ B2：默认 false 不调用 LLM）",
    ),
    as_of: str = Query(
        default="",
        description="数据时点锚（YYYY-MM-DD）：以该日期为'今天'回溯 months 个月，演示历史案例用",
    ),
):
    """舆情事件 — 事件簇 + 公告时间线 + 评级拐点。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []

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
                "error_code": ErrorCode.COMPANY_NOT_COVERED,
                "trace_id": trace_id,
                "recoverable": True,
            },
        )
    wind_code = company.wind_code
    sec_name = company.sec_name
    data_warnings: list[str] = []  # ⑧ B2 影响结论降级提示（字符串级，不进 WarningItem）

    # lite/演示模式：数据在 SQLite 中，查询为空自然降级，不再硬拦截

    # months → 起始日期（真实过滤）；as_of 提供时以该时点为"今天"回溯（历史案例演示）
    anchor = date.today()
    if as_of:
        try:
            anchor = datetime.strptime(as_of, "%Y-%m-%d").date()
        except ValueError:
            pass  # 非法 as_of 回退今天
    cutoff = anchor - timedelta(days=months * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # 事件簇（按日期过滤）
    event_clusters: list[EventCluster] = []
    try:
        event_clusters = await asyncio.to_thread(
            _fetch_event_clusters, wind_code, cutoff
        )
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
                message="事件簇交接数据尚未交付或未覆盖该公司，本次不生成/不伪造事件簇。",
                module="events",
                recoverable=True,
            )
        )

    # 公告时间线（真实月份过滤 + 统一 evidence ID）
    timeline: list[TimelineEvent] = []
    sentiment_summary = SentimentSummary()
    announcements_available = False
    cluster_evidence_ids: list[str] = [
        eid for c in event_clusters for eid in c.evidence_ids
    ]
    timeline_evidence_ids: list[str] = []

    try:
        rows = await asyncio.to_thread(_fetch_announcements, wind_code, cutoff_str)
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

    # 无论是否有公告都必须初始化（持久化分支无条件引用）
    _timeline_object_ids: list[str] = []
    _timeline_ann_dates: list[str] = []

    if rows:
        announcements_available = True
        from app.domain.events.fcode_taxonomy import fcode_category_label
        from app.domain.provenance.id_factory import NS_ANNOUNCEMENT, make_evidence_id

        sentiment_counter: Counter = Counter()
        titles: list[str] = []
        for r in rows:
            fcode_raw = str(r.get("n_info_fcode", "") or "")
            first_fcode = fcode_raw.split("|")[0].strip() if fcode_raw else ""
            label = fcode_category_label(first_fcode)
            sentiment = str(r.get("sentiment", "neutral") or "neutral")
            sentiment_counter[sentiment] += 1
            object_id = str(r.get("object_id", "") or "")
            ann_date = str(r.get("ann_dt") or "")
            _timeline_object_ids.append(object_id)
            _timeline_ann_dates.append(ann_date)
            evidence_id = make_evidence_id(
                source_namespace=NS_ANNOUNCEMENT,
                source_type="announcement",
                source_record_id=object_id,
                period=str(r.get("ann_dt") or ""),
                dataset_version=settings.DATASET_VERSION,
                company_code=wind_code,
            )
            timeline_evidence_ids.append(evidence_id)
            titles.append(str(r.get("n_info_title") or ""))
            timeline.append(
                TimelineEvent(
                    date=str(r.get("ann_dt", "") or ""),
                    title=str(r.get("n_info_title") or "")[:120],
                    category="公告",
                    fcode_label=label,
                    sentiment=sentiment,
                    summary=str(r.get("n_info_title") or "")[:120],
                    sources=[str(r["source_uri"])] if r.get("source_uri") else [],
                    evidence_ids=[evidence_id] if object_id else [],
                    object_id=object_id,
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
        keyword_summary = _build_keyword_summary(titles)
    else:
        warnings.append(
            WarningItem(
                code="NO_ANNOUNCEMENT_DATA",
                message=f"{sec_name}({wind_code}) 近 {months} 个月无公告数据覆盖，返回空时间线。",
                module="events",
                recoverable=True,
            )
        )
        keyword_summary = KeywordSummary()

    # 评级拐点（真实）
    rating_changes: list[RatingChange] = []
    try:
        rating_changes = await asyncio.to_thread(
            _fetch_rating_changes, wind_code, cutoff_str
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            WarningItem(
                code="RATING_DATA_ERROR",
                message=f"评级数据查询失败: {exc}",
                module="events",
                recoverable=True,
            )
        )

    all_evidence_ids = list(dict.fromkeys(cluster_evidence_ids + timeline_evidence_ids))

    # 持久化 timeline 证据（统一 ID → Lookup 可查询）+ 独立 trace provenance
    try:
        from app.application.services.provenance_service import ProvenanceService

        svc = ProvenanceService()
        svc.create_analysis_run(
            trace_id=trace_id,
            endpoint="companies/{code}/events",
            company_codes=[wind_code],
            period=cutoff_str,
        )
        evidence_for_persist = [
            {
                "evidence_id": eid,
                "source_type": "announcement",
                "source_record_id": object_id,
                "company_code": wind_code,
                "period": ann_date,
                "module": "events",
                "source_table": "announcements",
            }
            for object_id, ann_date, eid in zip(
                _timeline_object_ids,
                _timeline_ann_dates,
                timeline_evidence_ids,
            )
        ]
        svc.persist_evidence(evidence_for_persist, trace_id=trace_id, turn_id=trace_id)
    except Exception as exc:  # noqa: BLE001 — 持久化失败不阻塞主流程
        warnings.append(
            WarningItem(
                code="PROVENANCE_PERSIST_FAILED",
                message=f"事件证据持久化失败: {exc}",
                module="events",
                recoverable=True,
            )
        )

    # ── ⑧ B2：舆情影响结论（include_impacts=true 按需调用；失败降级）──
    impact_conclusions: list[ImpactConclusion] = []
    if include_impacts:
        try:
            from app.application.services.events_impact_service import (
                build_equity_impact_facts,
                build_impact_facts,
                generate_impacts,
            )

            facts, input_evidence = build_impact_facts(
                event_clusters=event_clusters,
                timeline=timeline,
                rating_changes=rating_changes,
            )
            # v3.4：股权事实只送已材料化（evidence_refs 可回查）的
            # Neo4j 直接持股边证据（不可回查的边保守丢弃）。
            # B2 批次 D：build_equity_impact_facts 返回 (facts, evidence_ids,
            # warnings)，失败时带 IMPACT_EQUITY_FACTS_FAILED 且不阻断 B2。
            try:
                eq_facts, eq_evidence, eq_warnings = await build_equity_impact_facts(
                    wind_code, settings.GRAPH_VERSION
                )
                facts.extend(eq_facts)
                input_evidence |= eq_evidence
                for w in eq_warnings:
                    data_warnings.append(w)
            except Exception as exc:  # noqa: BLE001 — 股权事实失败不阻塞影响分析
                data_warnings.append(f"IMPACT_EQUITY_FACTS_FAILED: {exc}")
            impact_conclusions, impact_warnings = await generate_impacts(
                wind_code=wind_code,
                sec_name=sec_name,
                months=months,
                graph_version=settings.GRAPH_VERSION,
                facts=facts,
                input_evidence_ids=input_evidence,
            )
            for iw in impact_warnings:
                data_warnings.append(iw)
        except Exception as exc:  # noqa: BLE001 — 影响结论失败不阻塞基础事件
            data_warnings.append(f"IMPACT_ANALYSIS_FAILED: {exc}")

    return V12Response(
        data=EventsResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            sentiment_summary=sentiment_summary,
            event_clusters=event_clusters,
            timeline=timeline,
            rating_changes=rating_changes,
            keyword_summary=keyword_summary,
            impact_conclusions=impact_conclusions,
            impact_warnings=data_warnings,
            evidence_ids=all_evidence_ids,
            announcements_available=announcements_available,
            months_covered=months,
            warnings=[w.message for w in warnings] + data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
        ),
        warnings=warnings,
    )


@router.get(
    "/companies/{code}/announcements/{object_id}/summary",
    response_model=V12Response[AnnouncementSummaryData],
)
async def get_announcement_summary(
    code: str = Path(..., description="公司代码"),
    object_id: str = Path(..., description="公告 object_id"),
):
    """按需下载公告 PDF → 提取正文 → LLM 摘要 → 删除临时 PDF。

    设计约束：
    - 摘要按需生成，不落库、不缓存 PDF，原文链接仍可独立查看；
    - 只允许 http/https；超过 15MB 或无法提取文本时明确失败；
    - LLM 失败降级为 PDF 原文前 500 字摘录（method 标记 text_excerpt）。
    """
    trace_id = _trace()
    if settings.SQL_BACKEND != "mysql":
        raise HTTPException(
            status_code=503,
            detail="ANNOUNCEMENT_SUMMARY_UNAVAILABLE: 非 full profile 不提供公告摘要",
        )

    resolver = CompanyResolver()
    company = await resolver.resolve(code)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {code}")

    from sqlalchemy import create_engine, text

    engine = create_engine(
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4",
        echo=False,
    )
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT object_id, n_info_title, source_uri, sentiment, ann_dt "
                        "FROM announcements "
                        "WHERE wind_code = :code AND object_id = :object_id "
                        "AND is_latest = 1 LIMIT 1"
                    ),
                    {"code": company.wind_code, "object_id": object_id},
                )
                .mappings()
                .first()
            )
    finally:
        engine.dispose()

    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Announcement not found: {object_id}"
        )

    source_uri = row.get("source_uri") or ""
    title = str(row.get("n_info_title") or "")[:120]
    if not _is_http_uri(source_uri):
        raise HTTPException(
            status_code=422,
            detail="ANNOUNCEMENT_SOURCE_UNAVAILABLE: 该公告无可用原文下载链接",
        )

    try:
        import httpx

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": "Mozilla/5.0 (TruthNet announcement summarizer)"},
        ) as client:
            async with client.stream("GET", source_uri) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > _MAX_PDF_BYTES:
                    raise HTTPException(status_code=413, detail="PDF 文件过大（>15MB）")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_PDF_BYTES:
                        raise HTTPException(
                            status_code=413, detail="PDF 文件过大（>15MB）"
                        )
                    chunks.append(chunk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — 下载失败明确返回，不伪造摘要
        raise HTTPException(
            status_code=502,
            detail=f"ANNOUNCEMENT_DOWNLOAD_FAILED: {exc}",
        ) from exc

    pdf_bytes = b"".join(chunks)
    if not pdf_bytes:
        raise HTTPException(
            status_code=502, detail="ANNOUNCEMENT_DOWNLOAD_FAILED: 空文件"
        )

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            text = await asyncio.to_thread(_extract_pdf_text, tmp_path)
        except Exception as exc:  # noqa: BLE001 — 依赖缺失/PDF损坏返回明确错误
            raise HTTPException(
                status_code=503,
                detail=f"ANNOUNCEMENT_PDF_PARSE_FAILED: {exc}",
            ) from exc
        if not text:
            raise HTTPException(
                status_code=422,
                detail="ANNOUNCEMENT_PDF_NO_TEXT: PDF 无可提取文本（可能为扫描件）",
            )

        summary = await asyncio.to_thread(
            _summarize_announcement_text,
            title=title,
            text=text,
            sec_name=company.sec_name,
        )
        method = "pdf_llm" if summary else "text_excerpt"
        if not summary:
            summary = text[:500].replace("\n", " ").strip()
            if not summary:
                summary = title

        from app.domain.provenance.id_factory import NS_ANNOUNCEMENT, make_evidence_id

        evidence_id = make_evidence_id(
            source_namespace=NS_ANNOUNCEMENT,
            source_type="announcement",
            source_record_id=object_id,
            period=str(row.get("ann_dt", "")) if "ann_dt" in row else "",
            dataset_version=settings.DATASET_VERSION,
            company_code=company.wind_code,
        )
        return V12Response(
            data=AnnouncementSummaryData(
                object_id=object_id,
                title=title,
                evidence_id=evidence_id,
                source_uri=source_uri,
                summary=summary,
                method=method,
            ),
            meta=ApiMeta(
                request_id=trace_id,
                trace_id=trace_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
                dataset_version=settings.DATASET_VERSION,
            ),
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("announcement_summary: 临时 PDF 删除失败: %s", tmp_path)
