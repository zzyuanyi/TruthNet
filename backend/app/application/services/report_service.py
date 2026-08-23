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
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.core.config import settings

logger = logging.getLogger(__name__)

_MD_BOLD_RE = re.compile(r"\*\*([^*]+?)\*\*")

_semaphore: asyncio.Semaphore | None = None
_running_tasks: set[asyncio.Task] = set()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _get_engine() -> Engine:
    """8/19 全面审查：改用完整 profile key + 切 profile 即 dispose 旧 Engine。

    原实现以 SQL_BACKEND 作缓存键，进程内切库后（conftest 运行时改写
    MYSQL_DATABASE、验收双库探针）会复用旧库 Engine，把报告任务写进错误库。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


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
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
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


def retry_failed_report_job(report_id: str) -> bool:
    """原子重置 failed 任务为 queued（8.11 C6：PDF 失败重试）。

    仅当当前状态为 failed 时才重置（WHERE status='failed'），并清理旧的
    progress/error/file 字段；并发重试时仅 rowcount=1 的一方真正重置，
    其余返回 False（不会重复启动）。
    """
    from app.core.write_guard import assert_db_writable

    assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
    with _get_engine().begin() as conn:
        result = conn.execute(
            text(
                "UPDATE report_jobs SET "
                "status = 'queued', progress = 0, "
                "error_code = NULL, error_message = NULL, "
                "file_path = NULL, file_sha256 = NULL, "
                "started_at = NULL, completed_at = NULL, "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE report_id = :rid AND status = 'failed'"
            ),
            {"rid": report_id},
        )
    return result.rowcount == 1


def get_report_job(report_id: str) -> dict | None:
    """读取报告任务状态。"""
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT report_id, session_id, company_code, status, progress, "
                    "idempotency_key, file_path, file_sha256, error_code, "
                    "error_message, trace_id, request_payload, created_at, "
                    "started_at, completed_at "
                    "FROM report_jobs WHERE report_id = :rid"
                ),
                {"rid": report_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    result = dict(row)
    payload = result.get("request_payload")
    if isinstance(payload, str):
        try:
            result["request_payload"] = json.loads(payload)
        except json.JSONDecodeError:
            result["request_payload"] = {}
    return result


def _update_status(
    report_id: str,
    *,
    status: str,
    progress: int = None,
    expected_status: str | tuple[str, ...] | None = None,
    **extra,
) -> bool:
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
    from app.core.write_guard import assert_db_writable

    assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
    where = "WHERE report_id = :rid"
    if expected_status is not None:
        allowed = (
            (expected_status,)
            if isinstance(expected_status, str)
            else tuple(expected_status)
        )
        placeholders = []
        for index, value in enumerate(allowed):
            key = f"expected_status_{index}"
            placeholders.append(f":{key}")
            params[key] = value
        where += f" AND status IN ({', '.join(placeholders)})"
    with _get_engine().begin() as conn:
        result = conn.execute(
            text(f"UPDATE report_jobs SET {', '.join(sets)} {where}"), params
        )
    return (result.rowcount or 0) == 1


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
        claimed = _update_status(
            report_id,
            status="running",
            progress=5,
            started_at=None,
            expected_status="queued",
        )
        if not claimed:
            return
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
                expected_status="running",
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
                expected_status="running",
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

# 8/23 报告规整：风险等级/规则状态中文化（PDF 不展示内部英文枚举）
_RISK_LEVEL_CN: dict[str, str] = {
    "red": "红色",
    "orange": "橙色",
    "yellow": "黄色",
    "green": "绿色",
    "unknown": "未知",
    "normal": "正常",
    "high": "高",
    "medium": "中",
    "low": "低",
    "not_applicable": "不适用",
    "insufficient_data": "数据不足",
    "not_triggered": "未触发",
    "triggered": "已触发",
}

_RULE_STATUS_CN: dict[str, str] = {
    "triggered": "已触发",
    "not_triggered": "未触发",
    "insufficient_data": "数据不足",
    "not_applicable": "不适用",
    "error": "错误",
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
    # 2026-08-16 口径整改：未传时从库内真实期次推导，禁止硬编码默认
    as_of = ((job.get("request_payload") or {}).get("as_of")) or ""
    if not as_of:
        try:
            from app.domain.finance.data_as_of import resolve_company_data_as_of

            as_of = resolve_company_data_as_of(company_code)
        except Exception:  # noqa: BLE001
            as_of = ""
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
    from app.application.services.report_charts import (
        extract_trend_points,
        holding_bar_drawing,
        pick_trend_rules,
        risk_badge_drawing,
        trend_drawing,
        trend_title,
        truncate_holder,
    )

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
    cell = ParagraphStyle(
        "cell",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=8.5,
        leading=12,
        wordWrap="CJK",
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

    # 风险等级（8/23 图表化：风险色块 + 五级图例；绘制失败降级回文字）
    story.append(Paragraph("一、综合风险", h2))
    try:
        badge = risk_badge_drawing(
            data.get("risk_level", "unknown"),
            data.get("overall_score", "—"),
        )
        story.append(Spacer(1, 2))
        story.append(badge)
    except Exception:  # noqa: BLE001 — 图表失败不阻塞报告
        logger.warning("report: risk badge drawing failed", exc_info=True)
        story.append(
            Paragraph(
                f"风险等级：{_RISK_LEVEL_CN.get(data.get('risk_level', 'unknown'), data.get('risk_level', 'unknown'))}；"
                f"综合分：{data.get('overall_score', '—')}",
                body,
            )
        )

    # 财务规则结果（8/23 规整：状态/等级中文化）
    story.append(Paragraph("二、财务规则结果", h2))
    rules = data.get("rules") or []
    if rules:
        rows = [["规则", "状态", "等级", "说明"]]
        for r in rules[:15]:
            status = _RULE_STATUS_CN.get(r.get("status", ""), r.get("status", ""))
            severity = _RISK_LEVEL_CN.get(r.get("severity", ""), r.get("severity", ""))
            rows.append(
                [
                    Paragraph(r.get("rule_id", ""), cell),
                    Paragraph(status, cell),
                    Paragraph(severity, cell),
                    Paragraph((r.get("explanation") or "" or "未触发")[:150], cell),
                ]
            )
        t = Table(rows, colWidths=[30, 55, 40, 320])
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t)
    else:
        story.append(Paragraph("无规则触发或数据不足。", body))

    # 8/23 图表化：关键指标趋势折线（复用 rule.history，2 列布局；失败/无数据跳过）
    try:
        trend_rules = pick_trend_rules(rules, limit=4)
        if trend_rules:
            story.append(Spacer(1, 8))
            story.append(Paragraph("关键指标趋势", h2))
            cells: list[object] = []
            for r in trend_rules:
                pts = extract_trend_points(r)
                if not pts:
                    continue
                title = trend_title(r)
                cells.append(
                    trend_drawing(title, pts, str(r.get("severity") or "unknown"))
                )
            for i in range(0, len(cells), 2):
                row = cells[i : i + 2]
                row = row + [Paragraph("", body)] * (2 - len(row))
                t2 = Table([row], colWidths=[238, 238])
                t2.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ]
                    )
                )
                story.append(t2)
    except Exception:  # noqa: BLE001 — 图表失败不阻塞报告
        logger.warning("report: trend drawing failed", exc_info=True)

    # 股权链路（8.09 四轮/五轮审查：措辞随 path_type——ownership 是持股关系，
    # 不得一律称"控制链/最终控制"；内部英文 risk_label 渲染为中文，不直接展示）
    # 8/23 规整：risk_level 中文化 + 显示股东名称（path_names）+ 过滤
    # 无意义微比例（<1% 且非风险链），按最终持股比例降序。
    story.append(Paragraph("三、股权持股链", h2))
    chains = data.get("equity_chains") or []
    if chains:
        # 排序：风险链优先（非 green），其次按比例降序
        def _chain_key(c: dict):
            risk_rank = {"red": 0, "orange": 1, "yellow": 2, "green": 3}
            return (
                risk_rank.get(str(c.get("risk_level", "")), 4),
                -float(c.get("final_control_pct") or 0),
            )

        ordered = sorted(chains, key=_chain_key)
        shown = 0
        for c in ordered:
            pct = float(c.get("final_control_pct") or 0)
            # 过滤：微比例（<1%）且无风险提示的链不展示（噪音）
            if pct < 1.0 and str(c.get("risk_level", "green")) in (
                "green",
                "unknown",
            ):
                continue
            if shown >= 10:
                break
            is_control = c.get("path_type") == "control"
            chain_term = "控制链" if is_control else "持股链"
            pct_term = "最终控制比例" if is_control else "最终持股比例"
            label_cn = _RISK_LABEL_CN.get(c.get("risk_label"), c.get("risk_label"))
            level_cn = _RISK_LEVEL_CN.get(c.get("risk_level"), c.get("risk_level"))
            # 股东名称：path_names 去掉目标公司本身，取路径主体
            path_names = c.get("path_names") or []
            holder = (
                " → ".join(str(n) for n in path_names[:-1])
                if len(path_names) > 1
                else (path_names[0] if path_names else c.get("chain_id"))
            )
            story.append(
                Paragraph(
                    f"• {chain_term}：{holder}（{pct_term} {pct:.2f}%，"
                    f"风险提示：{label_cn}·{level_cn}）",
                    body,
                )
            )
            shown += 1
        if shown == 0:
            story.append(Paragraph("无显著持股链（≥1% 或无风险提示链）。", body))

        # 8/23 图表化：主要股东持股比例条形图（前 5，复用 ordered 风险排序）
        try:
            holders: list[tuple[str, float, str]] = []
            for c in ordered:
                pct = float(c.get("final_control_pct") or 0)
                if pct < 1.0:
                    continue
                path_names = c.get("path_names") or []
                holder = (
                    path_names[-2]
                    if len(path_names) > 1
                    else (path_names[0] if path_names else c.get("chain_id"))
                )
                holders.append(
                    (
                        truncate_holder(str(holder)),
                        pct,
                        str(c.get("risk_level") or "green"),
                    )
                )
                if len(holders) >= 5:
                    break
            bar = holding_bar_drawing(holders)
            if bar:
                story.append(Spacer(1, 6))
                story.append(bar)
        except Exception:  # noqa: BLE001 — 图表失败不阻塞报告
            logger.warning("report: holding bar drawing failed", exc_info=True)
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

    # Claims / Evidence（8/23 规整：去重 + 完整展示不截断；等级未知不显示冗余）
    story.append(Paragraph("五、结论声明与证据", h2))
    claims = data.get("claims") or []
    if claims:
        seen: set[str] = set()
        shown = 0
        for c in claims:
            ctext = str(c.get("text", "") or "").strip()
            if not ctext or ctext in seen:
                continue
            seen.add(ctext)
            if shown >= 15:
                break
            severity = str(c.get("severity", "") or "")
            sev_cn = _RISK_LEVEL_CN.get(severity, severity)
            if severity and severity != "unknown":
                story.append(Paragraph(f"• {ctext}（等级 {sev_cn}）", body))
            else:
                story.append(Paragraph(f"• {ctext}", body))
            shown += 1
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

    # 七、影响与建议（LLM 生成，8/23 新增：复用画像页 impact_advice）
    story.append(Paragraph("七、影响与建议（综合画像指标）", h2))
    advice = data.get("impact_advice") or ""
    if advice:
        # 分段渲染（Markdown 分节 → 纯文本段落，剥离 ** 粗体标记）
        for para in [p.strip() for p in advice.split("\n") if p.strip()]:
            if para.startswith("#"):
                story.append(Paragraph(para.lstrip("# ").strip(), h2))
            else:
                clean = _MD_BOLD_RE.sub(r"\1", para)
                clean = clean.replace("**", "").replace("`", "")
                story.append(Paragraph(clean, body))
    else:
        story.append(
            Paragraph("影响与建议生成失败或数据不足，请结合画像页查看。", body)
        )

    doc.build(story)
    return pdf_path


def _collect_report_data(company_code: str, as_of: str = "") -> dict:
    """从真实持久化数据收集报告内容（不编造）。

    as_of：报告任务实际期次（YYYYMMDD 或可解析格式），统一传给风险、
    股权图与股东记录，保证报告内各模块同期次口径。
    未传/空时从库内真实期次推导（2026-08-16 口径整改，禁止硬编码默认）。
    """
    data: dict = {"company_code": company_code}
    try:
        from app.domain.finance.data_as_of import resolve_company_data_as_of
        from app.domain.finance.period import normalize_period

        norm_as_of = (
            normalize_period(as_of) or resolve_company_data_as_of(company_code) or ""
        )
    except Exception:  # noqa: BLE001
        norm_as_of = ""
    try:
        # 风险（真实数据：复用 assemble_and_score 收集四模块并评分；
        # 2026-08-16 修复：此前用空模块调 score()，综合风险恒为 unknown/0.0，
        # 与画像页 red/yellow 矛盾。本函数运行于 to_thread 的工作线程，
        # 该线程无运行中的事件循环，asyncio.run 是安全的。）
        try:
            from app.application.services.risk_scoring_service import (
                assemble_and_score,
            )

            out = asyncio.run(assemble_and_score(company_code, norm_as_of or ""))
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

            results = evaluate_all_rules(company_code, norm_as_of or None)
            data["rules"] = [
                {
                    "rule_id": rid,
                    "status": r.status,
                    "severity": r.severity,
                    "explanation": r.explanation,
                    # 8/23 图表化：收 history/current 供趋势折线绘制
                    "history": list(getattr(r, "history", []) or []),
                    "current": dict(getattr(r, "current", {}) or {}),
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

        # 影响与建议（LLM 生成，8/23 新增：复用画像页 impact_advice 四路聚合）
        try:
            from app.application.services.impact_advice_service import (
                assemble_impact_advice,
            )

            adv = asyncio.run(assemble_impact_advice(company_code, norm_as_of or ""))
            data["impact_advice"] = adv.overall_advice or ""
        except Exception:  # noqa: BLE001 — LLM 建议失败不阻塞报告
            logger.warning("report: impact advice failed", exc_info=True)
            data["impact_advice"] = ""

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
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
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
