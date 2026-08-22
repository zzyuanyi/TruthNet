"""_answer_research — generate_answer 拆分模块（重构生成，函数体与原文件逐字节一致）。"""

from __future__ import annotations

import logging
from ._answer_common import _emit_segment
from app.agents.state import AgentState, Claim, EvidenceRef, FinalResponse
from app.domain.provenance.id_factory import NS_REPORT, make_claim_id, make_evidence_id
import re

logger = logging.getLogger(__name__)


def _research_evidence_and_claims(
    insights: list[dict],
    *,
    company_code: str,
    turn_id: str,
    trace_id: str,
) -> tuple[list[EvidenceRef], list[Claim], list[dict]]:
    """研报结果 → 可回查 Evidence + 事实性 research Claim（#4）。

    - Evidence: NS_REPORT + make_evidence_id，source_type="research_report"，
      source_record_id=report_id，field_path="abstract"，period=publish_date；
    - Claim: claim_type="research"、severity=unknown、绑定对应 Evidence，
      limitations 注明"研报观点不代表系统事实结论"；
    - #2：Claim ID 纳入 report_id（同标题不同报告不冲突）；
    - P2-1：无 report_id 的条目不生成（不可回查 → 不落库），
      返回第三个元素 valid_insights——调用方只渲染这些（缺 ID 结果不得进回答）。
    """
    from app.core.config import settings

    evidence: list[EvidenceRef] = []
    claims: list[Claim] = []
    valid_insights: list[dict] = []
    for ordinal, it in enumerate(insights):
        report_id = str(it.get("report_id") or "").strip()
        if not report_id:
            continue
        valid_insights.append(it)
        title = str(it.get("source_title") or "")
        org = str(it.get("source_org") or "")
        content = str(it.get("content") or "")
        period = str(it.get("source_date") or "")[:10]
        evidence_id = make_evidence_id(
            source_namespace=NS_REPORT,
            source_type="research_report",
            source_record_id=report_id,
            field_path="abstract",
            period=period,
            dataset_version=settings.DATASET_VERSION,
            company_code=company_code or None,
        )
        evidence.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="research_report",
                source_record_id=report_id,
                source_table="research_reports",
                field_path="abstract",
                period=period,
                source_title=(title or "")[:120],
                source_uri=it.get("source_uri") or None,
                module="research",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company_code or "",
                dataset_version=settings.DATASET_VERSION,
            )
        )
        label = f"{org}·{title}" if org and title else (title or org or "研报")
        claims.append(
            Claim(
                claim_id=make_claim_id(
                    turn_id=turn_id,
                    company_code=company_code or "",
                    claim_type="research",
                    # P2-2：report_id 进入 Claim ID 输入——同标题不同报告不冲突
                    claim_text=f"研报观点：{label}（report:{report_id}）",
                    rule_version="",
                ),
                text=f"{label}：{content[:120]}",
                claim_type="research",
                severity="unknown",
                evidence_ids=[evidence_id],
                limitations=["研报观点不代表系统事实结论"],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company_code or "",
                module="research",
                generated_at="",
            )
        )
    return evidence, claims, valid_insights


def _research_relevant_excerpt(query: str, content: str) -> str:
    """从研报摘要中保留与问题相关的句子，避免把相邻营销信息当结论。"""
    normalized = " ".join(str(content or "").replace("\n", " ").split())
    if not normalized:
        return "暂无摘要"
    if not any(
        cue in query
        for cue in (
            "行业表现",
            "行业整体",
            "整体表现",
            "行业趋势",
            "发展趋势",
            "研发技术",
            "正在研发",
            "技术趋势",
            "新技术",
        )
    ):
        return normalized[:160].strip("。；; ")

    technology_query = any(
        cue in query for cue in ("研发技术", "正在研发", "技术趋势", "新技术", "AI医疗")
    )
    industry_query = any(
        cue in query
        for cue in ("行业表现", "行业整体", "整体表现", "行业趋势", "发展趋势")
    )
    cues = (
        (
            "技术",
            "研发",
            "产品",
            "人工智能",
            "AI",
            "机器人",
            "影像",
            "材料",
            "设备",
            "专利",
            "工艺",
        )
        if technology_query
        else (
            "行业",
            "市场",
            "规模",
            "增速",
            "增长",
            "需求",
            "竞争",
            "集采",
            "利润",
            "景气",
            "政策",
            "出口",
        )
    )
    noise = (
        "营销渠道",
        "销售渠道",
        "渠道拓展",
        "目标价",
        "买入评级",
        "增持评级",
        "估值",
        "评级",
        "EPS",
    )
    sentences = [
        part.strip(" 。；;，,")
        for part in re.split(r"[。！？；;\n]", normalized)
        if part.strip(" 。；;，, ")
    ]
    selected = [
        sentence
        for sentence in sentences
        if any(cue.lower() in sentence.lower() for cue in cues)
        and not any(term in sentence for term in noise)
        and not (industry_query and "公司" in sentence)
    ]
    if not selected:
        return normalized[:160].strip("。；; ")
    return "；".join(selected[:2])[:160].strip("。；; ")


def _format_research_insights(query: str, insights: list[dict]) -> str:
    """按问题类型整理研报结果，避免只拼接截断段落。"""
    if any(
        cue in query
        for cue in (
            "哪些个股",
            "竞争者",
            "竞争对手",
            "新兴公司",
            "新兴企业",
            "有哪些公司",
            "公司有哪些",
            "板块有哪些",
            "行业有哪些",
        )
    ):
        names: list[str] = []
        for item in insights:
            name = str(item.get("sec_name") or "").strip()
            if name and name not in names:
                names.append(name)
        if names:
            basic = "相关研报涉及的公司包括：" + "、".join(names[:8]) + "。"
            # 只有带可回查报告信息时才展开摘要；纯名称输入保持兼容，
            # 避免把没有来源的公司名包装成竞争关系或事实结论。
            rich_items = [
                item
                for item in insights
                if item.get("source_title") or item.get("report_id")
            ]
            if not rich_items:
                return basic
            rows = ["| 公司 | 研报依据 | 摘要 |", "|---|---|---|"]
            for item in rich_items[:8]:
                name = str(item.get("sec_name") or "暂无明确公司")
                source = str(item.get("source_title") or "研报").replace("|", "｜")
                content = _research_relevant_excerpt(
                    query, item.get("content") or "暂无摘要"
                )
                rows.append(
                    f"| {name} | {source[:80]} | {content[:160].replace('|', '｜')} |"
                )
            return basic + "\n\n" + "\n".join(rows)
    if any(cue in query for cue in ("研报", "机构评级", "券商评级")):
        rows = ["| 日期 | 机构 / 研报 | 核心观点 |", "|---|---|---|"]
        for item in insights[:5]:
            date_text = str(item.get("source_date") or "暂无数据")[:10]
            org = str(item.get("source_org") or "").strip()
            title = str(item.get("source_title") or "研报").strip()
            source = f"{org} · {title}" if org else title
            content = (
                str(item.get("content") or title).replace("\n", " ").replace("|", "｜")
            )
            rows.append(
                f"| {date_text} | {source.replace('|', '｜')} | {content[:140]} |"
            )
        return "\n".join(rows)
    parts = []
    for item in insights[:3]:
        src = item.get("source_title") or "研报"
        org = item.get("source_org", "")
        label = f"{org}·{src}" if org else src
        content = _research_relevant_excerpt(query, item.get("content") or "")
        if not content:
            content = str(item.get("source_title") or "暂无摘要").strip("。；; ")
        parts.append(f"{content}（来源：{label}）")
    result = "；".join(parts)
    if result and any(
        cue in query
        for cue in ("行业表现", "行业整体", "整体表现", "行业趋势", "发展趋势")
    ):
        return "研报样本显示：" + result + "。研报样本有限，不能代表全行业全部公司。"
    return result


def _answer_company_research(state: AgentState) -> dict:
    """直接回答单公司研报/评级问题，不先输出无关的综合风险模板。"""
    company = state.get("company")
    if company is None:
        return {}
    plan = state.get("plan")
    query = state.get("user_query", "")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    try:
        from app.application.services.research_search import (
            report_insights_enabled,
            search_research_insights_sync,
        )

        insights = (
            search_research_insights_sync(
                f"{company.sec_name} {company.wind_code} {query}",
                top_k=5,
                as_of=as_of,
            )
            if report_insights_enabled()
            else []
        )
        evidence, claims, valid = _research_evidence_and_claims(
            insights,
            company_code=company.wind_code,
            turn_id=turn_id,
            trace_id=trace_id,
        )
    except Exception:  # noqa: BLE001 - 检索失败按无可回查数据降级
        logger.warning("generate_answer: 单公司研报检索失败", exc_info=True)
        evidence, claims, valid = [], [], []

    name_code = f"{company.sec_name}（{company.wind_code}）"
    if valid:
        answer = f"{name_code}可回查的近期研报/评级：\n\n" + _format_research_insights(
            query, valid
        )
    else:
        answer = f"当前数据覆盖范围内未找到{name_code}可回查的近期研报或评级记录。"
    _emit_segment(state, answer)
    return {
        "claims": claims,
        "evidence": evidence,
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=claims,
            evidence=evidence,
        ),
    }
