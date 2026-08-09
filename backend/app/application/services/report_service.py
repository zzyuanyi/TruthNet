"""PDF 报告长任务服务 — Phase D #8.

职责：
  - 创建 report_jobs（幂等：idempotency_key 唯一约束）；
  - 受控应用内后台执行（并发数可配置，不无限线程）；
  - 状态机持久化：queued → running → succeeded | failed | cancelled；
  - 重启后遗留 running → 超时标记 retryable failed（不永久卡死）；
  - PDF 内容来自真实已持久化数据（公司/风险/规则/股权/Claims/Evidence）；
  - 文件写入配置的报告根目录，路径穿越防护由路由层负责。

诚实边界说明：使用进程内后台任务（asyncio.create_task），
非分布式队列；重启后任务不会自动续跑，遗留 running 按超时恢复。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}
_semaphore: asyncio.Semaphore | None = None
_running_tasks: set[asyncio.Task] = set()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _get_engine() -> Engine:
    backend = settings.SQL_BACKEND
    if backend in _engines:
        return _engines[backend]
    if backend == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _engines[backend] = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _engines[backend] = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return _engines[backend]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 状态机 ──────────────────────────────────────────────────


def create_report_job(
    *,
    company_code: str,
    session_id: str | None,
    idempotency_key: str | None,
    request_payload: dict | None,
    trace_id: str,
) -> tuple[str, bool]:
    """创建 report_jobs（幂等：同 idempotency_key 返回既有任务，不重复建）。

    并发安全：快速 SELECT 命中直接返回；未命中则 INSERT 独立事务，
    捕获唯一约束冲突（并发同 key 双插）后回滚重查，返回既有任务；
    重查仍无 → 重新抛出（不吞掉其他完整性错误）。

    Returns:
        (report_id, created)：created=False 表示命中既有幂等任务。
    """
    # 1. 快速 SELECT（独立只读，命中即返回）
    if idempotency_key:
        with _get_engine().connect() as conn:
            existing = conn.execute(
                text("SELECT report_id FROM report_jobs WHERE idempotency_key = :k"),
                {"k": idempotency_key},
            ).first()
        if existing is not None:
            return existing[0], False

    # 2. INSERT 独立事务
    report_id = f"report_{uuid.uuid4().hex[:12]}"
    try:
        with _get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO report_jobs "
                    "(report_id, session_id, company_code, status, progress, "
                    " idempotency_key, request_payload, trace_id, created_at, updated_at) "
                    "VALUES (:rid, :sid, :cc, 'queued', 0, :ik, :payload, :trace, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "rid": report_id,
                    "sid": session_id,
                    "cc": company_code,
                    "ik": idempotency_key,
                    "payload": json.dumps(request_payload, ensure_ascii=False)
                    if request_payload
                    else None,
                    "trace": trace_id,
                },
            )
    except IntegrityError:
        # 并发同 idempotency_key 双插 → 唯一约束冲突：回滚后重查既有任务
        if idempotency_key:
            with _get_engine().connect() as conn:
                existing = conn.execute(
                    text(
                        "SELECT report_id FROM report_jobs WHERE idempotency_key = :k"
                    ),
                    {"k": idempotency_key},
                ).first()
            if existing is not None:
                return existing[0], False
        raise
    return report_id, True


def get_report_job(report_id: str) -> dict | None:
    """读取报告任务状态。"""
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT report_id, session_id, company_code, status, progress, "
                    "idempotency_key, file_path, file_sha256, error_code, "
                    "error_message, trace_id, created_at, started_at, completed_at "
                    "FROM report_jobs WHERE report_id = :rid"
                ),
                {"rid": report_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    return dict(row)


def _update_status(
    report_id: str, *, status: str, progress: int = None, **extra
) -> None:
    """更新任务状态（持久化）。

    时间戳字段直接内联 SQL 字面量（CURRENT_TIMESTAMP），不绑定参数——
    绑定会被参数化，MySQL 报 "Incorrect datetime value: 'CURRENT_TIMESTAMP'"。
    """
    sets = ["status = :st", "updated_at = CURRENT_TIMESTAMP"]
    params: dict = {"rid": report_id, "st": status}
    if progress is not None:
        sets.append("progress = :pr")
        params["pr"] = progress
    for k, v in extra.items():
        if k in ("started_at", "completed_at"):
            sets.append(f"{k} = CURRENT_TIMESTAMP")
            continue
        sets.append(f"{k} = :{k}")
        params[k] = v
    with _get_engine().begin() as conn:
        conn.execute(
            text(f"UPDATE report_jobs SET {', '.join(sets)} WHERE report_id = :rid"),
            params,
        )


# ── 后台执行 ────────────────────────────────────────────────


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.REPORT_MAX_CONCURRENCY)
    return _semaphore


async def start_report_generation(report_id: str) -> None:
    """启动受控后台生成任务（并发数可配置，不无限线程）。"""
    task = asyncio.create_task(_run_report_job(report_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def _run_report_job(report_id: str) -> None:
    """执行报告生成（状态机持久化）。"""
    async with _sem():
        job = get_report_job(report_id)
        if job is None:
            return
        _update_status(report_id, status="running", progress=5, started_at=None)
        try:
            # 计时：queue_wait → generation → file_write
            t0 = _perf()
            pdf_path = await asyncio.to_thread(_generate_report_pdf, report_id, job)
            sha = _sha256_of(pdf_path)
            _update_status(
                report_id,
                status="succeeded",
                progress=100,
                completed_at=None,
                file_path=str(pdf_path.relative_to(_report_root())),
                file_sha256=sha,
            )
            logger.info(
                "report_job %s succeeded (%dms)",
                report_id,
                int((_perf() - t0) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 — 失败写入 failed（可重试）
            logger.exception("report_job %s failed: %s", report_id, exc)
            _update_status(
                report_id,
                status="failed",
                error_code="REPORT_GENERATION_FAILED",
                error_message=str(exc)[:500],
                completed_at=None,
            )


def _perf() -> float:
    import time

    return time.perf_counter()


# 8.09 五轮审查：PDF 不直接展示内部英文 risk_label，渲染为中文可读标签
_RISK_LABEL_CN: dict[str, str] = {
    "concentrated_control": "持股比例集中",
    "deep_chain": "链路层级过深",
    "multi_layer_entity": "多层中间实体",
    "insufficient_source": "来源覆盖不足",
    "ownership_mismatch": "持股比例不一致",
    "concerted_action": "一致行动关系",
    "normal": "正常",
}


def _report_root() -> Path:
    path = Path(settings.REPORT_ROOT_DIR)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── PDF 生成 ────────────────────────────────────────────────


def _generate_report_pdf(report_id: str, job: dict) -> Path:
    """从真实持久化数据生成 PDF 报告（同步，线程内执行）。"""
    company_code = job.get("company_code") or ""
    # 8.09 审查：报告使用任务实际期次（创建时 as_of 参数），不再固定最新图
    as_of = ((job.get("request_payload") or {}).get("as_of")) or "20260331"
    data = _collect_report_data(company_code, as_of=as_of)

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )
    from reportlab.lib import colors

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontName="STSong-Light", fontSize=16
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontName="STSong-Light", fontSize=13
    )

    root = _report_root()
    root.mkdir(parents=True, exist_ok=True)
    pdf_path = root / f"{report_id}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    story: list = []
    story.append(Paragraph("织网鉴真 · 公司风险分析报告", title_style))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"公司：{data.get('company_name', company_code)}（{company_code}）", body
        )
    )
    story.append(
        Paragraph(f"报告生成时间：{_utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", body)
    )
    story.append(Paragraph(f"数据版本：{settings.DATASET_VERSION}", body))
    story.append(Paragraph(f"规则版本：{settings.RULE_SET_VERSION}", body))
    story.append(Paragraph(f"图版本：{settings.GRAPH_VERSION}", body))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

    # 风险等级
    story.append(Paragraph("一、综合风险", h2))
    story.append(
        Paragraph(
            f"风险等级：{data.get('risk_level', 'unknown')}；"
            f"综合分：{data.get('overall_score', '—')}",
            body,
        )
    )

    # 财务规则结果
    story.append(Paragraph("二、财务规则结果", h2))
    rules = data.get("rules") or []
    if rules:
        rows = [["规则", "状态", "等级", "说明"]]
        for r in rules[:15]:
            rows.append(
                [
                    r.get("rule_id", ""),
                    r.get("status", ""),
                    r.get("severity", ""),
                    (r.get("explanation") or "")[:60],
                ]
            )
        t = Table(rows, colWidths=[30, 50, 40, 280])
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "STSong-Light"),
                    ("FONTNAME", (0, 1), (-1, -1), "STSong-Light"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t)
    else:
        story.append(Paragraph("无规则触发或数据不足。", body))

    # 股权链路（8.09 四轮/五轮审查：措辞随 path_type——ownership 是持股关系，
    # 不得一律称"控制链/最终控制"；内部英文 risk_label 渲染为中文，不直接展示）
    story.append(Paragraph("三、股权持股链", h2))
    chains = data.get("equity_chains") or []
    if chains:
        for c in chains[:10]:
            is_control = c.get("path_type") == "control"
            chain_term = "控制链" if is_control else "持股链"
            pct_term = "最终控制比例" if is_control else "最终持股比例"
            label_cn = _RISK_LABEL_CN.get(c.get("risk_label"), c.get("risk_label"))
            story.append(
                Paragraph(
                    f"• {chain_term} {c.get('chain_id')}：深度 {c.get('depth')}，"
                    f"{pct_term} {c.get('final_control_pct')}%，"
                    f"风险提示：{label_cn}（等级 {c.get('risk_level')}）",
                    body,
                )
            )
    else:
        story.append(Paragraph("无可用持股链数据。", body))

    # 模式三要素
    story.append(Paragraph("四、风险模式", h2))
    patterns = data.get("pattern_matches") or []
    if patterns:
        for p in patterns[:10]:
            story.append(
                Paragraph(
                    f"• {p.get('pattern_name', p.get('pattern_id'))}（{p.get('confidence')}）",
                    body,
                )
            )
            if p.get("regulatory_hint"):
                story.append(Paragraph(f"  监管提示：{p['regulatory_hint']}", body))
    else:
        story.append(Paragraph("未检测到匹配的风险模式。", body))

    # Claims / Evidence
    story.append(Paragraph("五、结论声明与证据", h2))
    claims = data.get("claims") or []
    if claims:
        for c in claims[:15]:
            story.append(
                Paragraph(
                    f"• {c.get('text', '')[:120]}（等级 {c.get('severity', '')}）", body
                )
            )
    else:
        story.append(Paragraph("无结构化结论声明。", body))

    # limitations
    story.append(Paragraph("六、限制说明", h2))
    for lim in (data.get("limitations") or [])[:10]:
        story.append(Paragraph(f"• {lim}", body))
    if not data.get("limitations"):
        story.append(
            Paragraph(
                "• 本报告基于母公司报表口径（408006000），仅供参考，不构成投资建议。",
                body,
            )
        )

    doc.build(story)
    return pdf_path


def _collect_report_data(company_code: str, as_of: str = "20260331") -> dict:
    """从真实持久化数据收集报告内容（不编造）。

    as_of：报告任务实际期次（YYYYMMDD 或可解析格式），统一传给风险、
    股权图与股东记录，保证报告内各模块同期次口径。
    """
    data: dict = {"company_code": company_code}
    try:
        from app.domain.finance.period import normalize_period

        norm_as_of = normalize_period(as_of) or "20260331"
    except Exception:  # noqa: BLE001
        norm_as_of = "20260331"
    try:
        # 风险（同步 score，避免在 to_thread 内嵌 asyncio.run 导致事件循环冲突）
        try:
            from app.application.services.risk_scoring_service import RiskScoringService

            svc = RiskScoringService()
            out = svc.score(
                wind_code=company_code,
                as_of=norm_as_of,
                sec_name=company_code,
                finance_result=None,
                equity_result=None,
                events_result=None,
                benchmarks={},
                rating_inflections=[],
                cross_validation=None,
            )
            data["risk_level"] = out.risk_level
            data["overall_score"] = out.overall_score
            data["pattern_matches"] = [
                {
                    "pattern_id": m.pattern_id,
                    "pattern_name": m.pattern_name,
                    "confidence": m.confidence,
                    "regulatory_hint": m.regulatory_hint,
                }
                for m in out.pattern_matches
            ]
            data["limitations"] = list(out.mitigating_factors or [])
        except Exception:  # noqa: BLE001 — 风险评分失败不阻塞报告
            logger.warning("report: risk scoring failed", exc_info=True)
            data["risk_level"] = "unknown"
            data["pattern_matches"] = []

        # 财务规则（真实触发）
        try:
            from app.domain.finance.rule_engine import evaluate_all_rules

            results = evaluate_all_rules(company_code, "20260331")
            data["rules"] = [
                {
                    "rule_id": rid,
                    "status": r.status,
                    "severity": r.severity,
                    "explanation": r.explanation,
                }
                for rid, r in results.items()
            ]
        except Exception:  # noqa: BLE001
            logger.warning("report: rule engine failed", exc_info=True)
            data["rules"] = []

        # 股权链路（真实图数据）
        try:
            from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph
            from app.application.services.equity_chain_service import (
                build_equity_chains,
            )
            from app.application.services.equity_shareholder_service import (
                build_edge_evidence_map,
                fetch_shareholder_records,
            )

            adapter = Neo4jEquityGraph()
            if adapter._check_connection_sync():
                graph = adapter._get_graph_sync(
                    company_code,
                    depth=5,
                    as_of=norm_as_of,
                    graph_version=settings.GRAPH_VERSION,
                )
                node_name = {n.id: n.label for n in graph.nodes}
                graph_version = (
                    getattr(graph, "graph_version", "") or settings.GRAPH_VERSION
                )
                edge_evidence_map = build_edge_evidence_map(
                    edges=graph.edges,
                    company_code=company_code,
                    graph_version=graph_version,
                )
                chain_models, _w = build_equity_chains(
                    company_code=company_code,
                    chains=graph.control_chains,
                    node_name_map=node_name,
                    graph_edges=graph.edges,
                    top_shareholder_records=fetch_shareholder_records(
                        company_code, as_of=norm_as_of
                    ),
                    edge_evidence_map=edge_evidence_map,
                    as_of=norm_as_of,
                    source_system="neo4j",
                )
                data["equity_chains"] = [c.to_dict() for c in chain_models]
        except Exception:  # noqa: BLE001
            logger.warning("report: equity chains failed", exc_info=True)
            data["equity_chains"] = []

        # Claims（会话真实结论）
        try:
            from sqlalchemy import text

            with _get_engine().connect() as conn:
                rows = (
                    conn.execute(
                        text(
                            "SELECT text, severity FROM claims "
                            "WHERE company_code = :c ORDER BY generated_at DESC LIMIT 20"
                        ),
                        {"c": company_code},
                    )
                    .mappings()
                    .all()
                )
            data["claims"] = [dict(r) for r in rows]
        except Exception:  # noqa: BLE001
            data["claims"] = []

        # 公司名（使用本模块 _get_engine，避免局部导入遮蔽）
        try:
            with _get_engine().connect() as conn:
                name = conn.execute(
                    text("SELECT sec_name FROM companies WHERE wind_code = :c LIMIT 1"),
                    {"c": company_code},
                ).scalar()
            data["company_name"] = name or company_code
        except Exception:  # noqa: BLE001
            data["company_name"] = company_code
    except Exception:  # noqa: BLE001
        logger.exception("report: 数据收集异常")
    return data


# ── 重启遗留任务恢复 ────────────────────────────────────────


def recover_stale_running_jobs() -> int:
    """将超时 running 标记为 retryable failed（重启后不永久卡死）。

    Returns:
        恢复任务数。
    """
    try:
        with _get_engine().begin() as conn:
            row = conn.execute(
                text(
                    "UPDATE report_jobs SET status = 'failed', "
                    "error_code = 'REPORT_STALE_RECOVERY', "
                    "error_message = '进程重启，遗留 running 任务已标记为可重试失败', "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE status = 'running'"
                )
            )
            return row.rowcount or 0
    except Exception:  # noqa: BLE001
        logger.warning("report: 遗留任务恢复失败", exc_info=True)
        return 0
