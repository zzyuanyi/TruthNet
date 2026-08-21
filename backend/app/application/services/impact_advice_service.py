"""影响与建议聚合服务 — Phase E 会3（8/16 会议整改第③条）.

职责：综合所有企业画像指标（财务规则信号 / 股权链路与隐含关系 / 舆情
影响 / 综合风险评分）生成整体「影响与建议」，串联异常与舆情数据、因果链
做厚，供画像页影响建议模块消费。

复用（不发明新机制）：
- 财务+风险路：risk_scoring_service.assemble_and_score（规则证据/模式/评分）；
- 股权路：Neo4j 图 + equity_chain_service（风险标签/理由）+ equity_insight_service
  （会2 交叉持股/隐含链解读）；
- 舆情路：events 路由的 _fetch_event_clusters/_fetch_rating_changes +
  events_impact_service.generate_impacts（影响结论 + 程序校验 + 缓存）。

铁律（会3）：
- 每句建议可溯源：segments 携带 evidence_ids / 指标引用；
- LLM 只读锁定事实（数字/规则名/公司名锁定），不覆盖、不篡改、不新增；
- LLM 失败/校验失败 → 确定性模板兜底（分模块建议，不空洞）；
- 纯解读不荐股；数据不足如实说明。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_IMPACT_MONTHS = 36
_LLM_TIMEOUT_SECONDS = 18.0


class ImpactAdviceSegment(BaseModel):
    """分模块建议段落（可溯源）。"""

    source_module: Literal["finance", "equity", "events", "overall"] = Field(
        ..., description="来源模块"
    )
    title: str = Field(default="", description="段落标题")
    detail: str = Field(default="", description="建议/结论（有数据依据）")
    evidence_ids: list[str] = Field(default_factory=list, description="可回查证据 ID")


class ImpactAdviceResult(BaseModel):
    """影响与建议聚合结果。"""

    wind_code: str = Field(default="")
    sec_name: str = Field(default="")
    risk_level: str = Field(default="unknown")
    overall_score: float | None = Field(default=None)
    as_of: str = Field(default="")
    overall_advice: str = Field(default="", description="整体建议（LLM 或模板）")
    method: str = Field(default="template", description="llm | template")
    segments: list[ImpactAdviceSegment] = Field(default_factory=list)
    evidence_count: int = Field(default=0)
    warnings: list[str] = Field(default_factory=list)


class _ImpactSuggestion(BaseModel):
    """LLM 单条建议（绑定来源模块）。"""

    source_module: Literal["finance", "equity", "events", "overall"]
    text: str = Field(..., min_length=1)


class _ImpactAdviceOutput(BaseModel):
    """LLM 结构化输出：整体建议 + 分模块建议。"""

    overall: str = Field(..., min_length=1)
    suggestions: list[_ImpactSuggestion] = Field(default_factory=list)


# ── 各模块确定性信号提取 ──────────────────────────────────


def _finance_signals(out: Any) -> tuple[list[ImpactAdviceSegment], list[str]]:
    """财务路：触发规则结论（rule_trigger 推导链）+ 造假模式。"""
    segments: list[ImpactAdviceSegment] = []
    evidence_ids: set[str] = set()
    lines: list[str] = []
    for chain in getattr(out, "derivation_chains", None) or []:
        if getattr(chain, "conclusion_type", "") != "rule_trigger":
            continue
        conclusion = getattr(chain, "conclusion", "") or ""
        expl = ""
        for sig in getattr(chain, "signals", []) or []:
            expl = getattr(sig, "explanation", "") or ""
            if expl:
                break
        evidence_ids.update(getattr(chain, "evidence_ids", []) or [])
        if conclusion:
            lines.append(f"{conclusion}：{expl}" if expl else conclusion)
    if lines:
        segments.append(
            ImpactAdviceSegment(
                source_module="finance",
                title="财务规则信号",
                detail="；".join(lines[:8]),
                evidence_ids=sorted(evidence_ids)[:20],
            )
        )
    patterns = []
    for m in getattr(out, "pattern_matches", None) or []:
        name = getattr(m, "pattern_name", "") or ""
        conf = getattr(m, "confidence", "") or ""
        if name:
            patterns.append(f"{name}（{conf}）")
    if patterns:
        segments.append(
            ImpactAdviceSegment(
                source_module="finance",
                title="疑似造假模式",
                detail="、".join(patterns),
                evidence_ids=[],
            )
        )
    return segments, sorted(evidence_ids)


def _equity_signals(
    wind_code: str, as_of: str, node_name_map: dict[str, str] | None = None
) -> tuple[list[ImpactAdviceSegment], list[str]]:
    """股权路：最高风险链理由 + 隐含关系解读（会2）。失败降级为空。"""
    segments: list[ImpactAdviceSegment] = []
    evidence_ids: set[str] = set()
    try:
        from app.core.config import settings
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        if settings.GRAPH_BACKEND != "neo4j":
            return segments, []
        adapter = Neo4jEquityGraph()
        if not adapter._check_connection_sync():
            return segments, []
        graph = adapter._get_graph_sync(
            wind_code,
            depth=5,
            as_of=as_of or None,
            graph_version=settings.GRAPH_VERSION,
        )
        node_name = {n.id: n.label for n in graph.nodes}
        if node_name_map:
            node_name.update(node_name_map)

        from app.application.services.equity_chain_service import build_equity_chains
        from app.application.services.equity_insight_service import (
            build_equity_insights,
        )
        from app.application.services.equity_shareholder_service import (
            build_edge_evidence_map,
        )

        edge_evidence_map = build_edge_evidence_map(
            edges=graph.edges,
            company_code=wind_code,
            graph_version=settings.GRAPH_VERSION,
        )
        chains, _warnings = build_equity_chains(
            company_code=wind_code,
            chains=graph.control_chains,
            node_name_map=node_name,
            graph_edges=graph.edges,
            top_shareholder_records=[],
            edge_evidence_map=edge_evidence_map,
            as_of=as_of,
            source_system="neo4j",
            merge_groups=[],
        )
        if chains:
            worst = max(
                chains,
                key=lambda c: {
                    "red": 5,
                    "orange": 4,
                    "yellow": 3,
                    "blue": 2,
                    "green": 1,
                }.get(c.risk_level, 0),
            )
            names = "→".join(worst.path_names or [])
            parts = [f"股权链：{names}"]
            parts.extend(worst.risk_reasons)
            evidence_ids.update(worst.evidence_ids)
            segments.append(
                ImpactAdviceSegment(
                    source_module="equity",
                    title=f"股权链路（{worst.risk_level}）",
                    detail="；".join(parts),
                    evidence_ids=worst.evidence_ids[:20],
                )
            )
        insights = build_equity_insights(
            graph=graph,
            node_name_map=node_name,
            edge_evidence_map=edge_evidence_map,
            company_code=wind_code,
            target_name="",
        )
        for ins in insights[:3]:
            evidence_ids.update(ins.evidence_ids)
            segments.append(
                ImpactAdviceSegment(
                    source_module="equity",
                    title=ins.title,
                    detail=ins.detail,
                    evidence_ids=ins.evidence_ids[:20],
                )
            )
    except Exception:  # noqa: BLE001 — 股权路失败不影响其他模块
        logger.warning("impact_advice: equity 路失败，跳过", exc_info=True)
    return segments, sorted(evidence_ids)


def _events_cutoff() -> tuple[date, str]:
    """36 个月窗口起点（date + YYYYMMDD 字符串两形态）。"""
    start = datetime.now() - timedelta(days=30 * _IMPACT_MONTHS)
    return start.date(), start.strftime("%Y%m%d")


async def _events_signals(
    wind_code: str, sec_name: str, as_of: str
) -> tuple[list[ImpactAdviceSegment], list[str], list[str]]:
    """舆情路：事件簇/评级变更 → 舆情影响结论（generate_impacts）。

    失败/无事实 → 空段 + warning，不阻断其他模块。
    """
    segments: list[ImpactAdviceSegment] = []
    evidence_ids: list[str] = []
    warnings: list[str] = []
    try:
        from app.api.v1.routers.events import (
            _fetch_event_clusters,
            _fetch_rating_changes,
        )
        from app.application.services.events_impact_service import (
            build_impact_facts,
            generate_impacts,
        )

        cutoff_date, cutoff_str = _events_cutoff()
        clusters, rating_changes = await asyncio.to_thread(
            lambda: (
                _fetch_event_clusters(wind_code, cutoff_date),
                _fetch_rating_changes(wind_code, cutoff_str),
            )
        )
        facts, input_evidence = build_impact_facts(
            event_clusters=clusters, timeline=[], rating_changes=rating_changes
        )
        if facts:
            impacts, impact_warnings = await generate_impacts(
                wind_code=wind_code,
                sec_name=sec_name,
                facts=facts,
                input_evidence_ids=input_evidence,
                months=_IMPACT_MONTHS,
                graph_version="",
            )
            warnings.extend(impact_warnings)
            for imp in impacts:
                detail = getattr(imp, "conclusion", "") or ""
                eids = list(getattr(imp, "evidence_ids", None) or [])
                if not detail:
                    continue
                evidence_ids.extend(eids)
                segments.append(
                    ImpactAdviceSegment(
                        source_module="events",
                        title=(
                            f"舆情影响（{getattr(imp, 'impact_type', '')}/"
                            f"{getattr(imp, 'direction', '')}/{getattr(imp, 'severity', '')}）"
                        ),
                        detail=detail,
                        evidence_ids=eids[:20],
                    )
                )
    except Exception:  # noqa: BLE001 — 舆情路失败不阻断
        logger.warning("impact_advice: events 路失败，跳过", exc_info=True)
        warnings.append("舆情影响分析失败，本次未并入舆情建议")
    return segments, evidence_ids, warnings


# ── 锁定事实 + LLM 生成 + 模板兜底 ─────────────────────────


def _locked_facts(
    out: Any,
    all_segments: list[ImpactAdviceSegment],
    events_segments: list[ImpactAdviceSegment],
) -> str:
    """构建只读锁定事实（数字/规则名/公司名锁定）。"""
    risk_cn = {
        "red": "高危",
        "orange": "中高危",
        "yellow": "中等",
        "green": "正常",
        "blue": "低风险",
        "unknown": "数据不足",
    }.get(out.risk_level, str(out.risk_level))
    parts = [
        f"公司：{out.sec_name}（{out.wind_code}）",
        f"综合风险等级：{out.risk_level}（{risk_cn}），评分 {out.overall_score:.3f}",
    ]
    for seg in all_segments:
        parts.append(f"[{seg.source_module}] {seg.title}：{seg.detail}")
    return "\n".join(parts)


def _build_messages(sec_name: str, locked: str) -> list[dict]:
    system = (
        "你是上市公司财报反欺诈问答系统的「影响与建议」聚合分析助手。"
        "下面给出程序校验过的结构化事实（财务规则信号、股权链路与隐含关系、"
        "舆情影响、综合风险评分——数字/规则/公司名均已锁定，不得修改、不得新增）。"
        "你的任务：\n"
        "1. 输出 overall：一句话整体影响判断（串联财务/股权/舆情信号，说明风险来源与传导）；\n"
        "2. 输出 suggestions：按模块给出可执行建议（source_module ∈ "
        "finance/equity/events/overall，text 每句必须引用事实中的具体信号或数字）；\n"
        "3. 约束：绝不输出 facts 之外的新数字/新公司名；绝不给出投资建议/买卖评级；"
        "数据不足时如实说明，不得虚构。\n"
        "输出 JSON 必须严格符合给定 schema。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"目标公司：{sec_name}\n结构化事实：\n{locked}"},
    ]


def _template_advice(
    out: Any,
    all_segments: list[ImpactAdviceSegment],
    events_segments: list[ImpactAdviceSegment],
) -> tuple[str, list[ImpactAdviceSegment]]:
    """确定性模板兜底：分模块建议（LLM 失败/关闭时使用，不空洞）。"""
    risk_cn = {
        "red": "高危",
        "orange": "中高危",
        "yellow": "中等",
        "green": "正常",
        "blue": "低风险",
        "unknown": "数据不足",
    }.get(out.risk_level, str(out.risk_level))
    overall = (
        f"{out.sec_name} 综合风险等级为{risk_cn}"
        f"（评分 {out.overall_score:.3f}），"
        f"财务规则信号 {len([s for s in all_segments if s.source_module == 'finance'])} 项、"
        f"股权信号 {len([s for s in all_segments if s.source_module == 'equity'])} 项、"
        f"舆情影响 {len(events_segments)} 项，建议结合下述分模块信号进一步核验。"
    )
    return overall, all_segments


async def assemble_impact_advice(code: str, as_of: str = "") -> ImpactAdviceResult:
    """四路聚合生成影响与建议（会3）。"""
    from app.application.services.risk_scoring_service import assemble_and_score

    warnings: list[str] = []
    out = await assemble_and_score(code, as_of or "")

    # 股权路（同步）——失败不影响财务
    try:
        equity_segments, _eq_ev = await asyncio.to_thread(
            _equity_signals, out.wind_code, as_of
        )
    except Exception:  # noqa: BLE001 — 股权路异常降级
        logger.warning("impact_advice: equity 路异常，跳过", exc_info=True)
        equity_segments, _eq_ev = [], []
        warnings.append("股权信号提取异常，本次未并入股权建议")

    # 舆情路（异步）——失败不影响财务/股权
    try:
        events_segments, events_ev, events_warn = await _events_signals(
            out.wind_code, out.sec_name, as_of
        )
    except Exception:  # noqa: BLE001 — 舆情路异常降级
        logger.warning("impact_advice: events 路异常，跳过", exc_info=True)
        events_segments, _events_ev, events_warn = (
            [],
            [],
            ["舆情信号提取异常，本次未并入舆情建议"],
        )
    warnings.extend(events_warn)

    # 财务路（从 out 提取）
    finance_segments, finance_ev = _finance_signals(out)

    all_segments = finance_segments + equity_segments + events_segments
    all_evidence: list[str] = []
    for seg in all_segments:
        for eid in seg.evidence_ids:
            if eid and eid not in all_evidence:
                all_evidence.append(eid)

    locked = _locked_facts(out, all_segments, events_segments)

    overall_text, _template_segments = _template_advice(
        out, all_segments, events_segments
    )
    method = "template"

    # LLM 生成（受约束结构化输出；失败/校验失败 → 模板兜底，8/17 收敛 C）
    from app.agents.llm_guard import llm_with_fallback
    from app.core.config import settings

    if settings.LLM_BACKEND not in ("", "mock") and all_segments:
        valid_modules = {"finance", "equity", "events", "overall"}

        def _validate(output) -> tuple[bool, str]:
            if not output.overall.strip() or not output.suggestions:
                return False, "overall 或 suggestions 为空"
            for s in output.suggestions:
                if s.source_module not in valid_modules or not s.text.strip():
                    return False, f"非法建议（{s.source_module}/{s.text[:20]!r}）"
            from app.application.services._llm_numeric_lock import unlocked_numbers

            invented = unlocked_numbers(
                [output.overall, *(s.text for s in output.suggestions)], locked
            )
            if invented:
                return False, f"输出包含事实之外的数字: {sorted(invented)}"
            return True, ""

        def _fallback():
            warnings.append("LLM 建议降级，使用模板兜底")
            return overall_text

        output, used = await asyncio.to_thread(
            llm_with_fallback,
            _build_messages(out.sec_name, locked),
            _ImpactAdviceOutput,
            fallback=_fallback,
            validate=_validate,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        if used:
            overall_text = output.overall.strip()
            method = "llm"
            module_evidence: dict[str, list[str]] = {
                module: [] for module in valid_modules
            }
            for segment in all_segments:
                for evidence_id in segment.evidence_ids:
                    if (
                        evidence_id
                        and evidence_id not in module_evidence[segment.source_module]
                    ):
                        module_evidence[segment.source_module].append(evidence_id)
            all_evidence_ids = list(all_evidence)
            for s in output.suggestions:
                evidence_ids = (
                    all_evidence_ids
                    if s.source_module == "overall"
                    else module_evidence.get(s.source_module, [])
                )
                all_segments.append(
                    ImpactAdviceSegment(
                        source_module=s.source_module,
                        title=(
                            "综合建议"
                            if s.source_module == "overall"
                            else {
                                "finance": "财务建议",
                                "equity": "股权建议",
                                "events": "舆情建议",
                            }.get(s.source_module, "建议")
                        ),
                        detail=s.text.strip(),
                        evidence_ids=evidence_ids[:20],
                    )
                )
    elif not all_segments:
        overall_text = (
            f"{out.sec_name} 当前数据覆盖范围内未检出财务/股权/舆情显著信号，"
            "综合风险等级为"
            + {
                "red": "高危",
                "orange": "中高危",
                "yellow": "中等",
                "green": "正常",
                "blue": "低风险",
                "unknown": "数据不足",
            }.get(out.risk_level, str(out.risk_level))
            + "。"
        )

    return ImpactAdviceResult(
        wind_code=out.wind_code,
        sec_name=out.sec_name,
        risk_level=out.risk_level,
        overall_score=out.overall_score,
        as_of=getattr(out, "as_of", "") or as_of,
        overall_advice=overall_text,
        method=method,
        segments=all_segments,
        evidence_count=len(all_evidence),
        warnings=warnings,
    )
