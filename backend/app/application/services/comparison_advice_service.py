"""跨公司 LLM 综合分析服务 — 8/23 会7 深化.

职责：基于两家以上公司的锁定事实（综合风险等级/评分/触发规则/信号），
调用大模型生成「跨公司对比分析」（整体差异 + 各自关注点 + 交叉核验建议），
供对比页综合分析区块消费。

铁律（与 impact_advice_service 一致）：
- LLM 只读锁定事实（数字/规则名/公司名锁定），不覆盖、不篡改、不新增；
- LLM 失败/校验失败 → 确定性模板兜底（不空洞）；
- 纯解读不荐股；数据不足如实说明。
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel, Field

from app.api.v1.schemas.comparisons import (
    ComparisonAnalysisCompany,
    ComparisonAnalysisData,
    ComparisonAnalysisSegment,
)

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 20.0
_RISK_CN = {
    "red": "高危",
    "orange": "中高危",
    "yellow": "中等",
    "green": "正常",
    "blue": "低风险",
    "unknown": "数据不足",
}


class _CompanySuggestion(BaseModel):
    company_code: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class _ComparisonOutput(BaseModel):
    overall: str = Field(..., min_length=1)
    suggestions: list[_CompanySuggestion] = Field(default_factory=list)


async def _company_fact(code: str) -> ComparisonAnalysisCompany:
    """单家公司锁定事实：综合评分/等级/触发规则（复用 risk 聚合链路）。"""
    from app.application.services.risk_scoring_service import assemble_and_score

    out = await assemble_and_score(code, "")
    rules: list[str] = []
    for chain in getattr(out, "derivation_chains", None) or []:
        if getattr(chain, "conclusion_type", "") != "rule_trigger":
            continue
        conclusion = getattr(chain, "conclusion", "") or ""
        if conclusion and conclusion not in rules:
            rules.append(conclusion)
    return ComparisonAnalysisCompany(
        wind_code=out.wind_code,
        sec_name=out.sec_name,
        risk_level=getattr(out, "risk_level", "") or "unknown",
        overall_score=getattr(out, "overall_score", None),
        triggered_rules=rules,
        as_of=getattr(out, "as_of", "") or "",
    )


def _locked_text(companies: list[ComparisonAnalysisCompany]) -> str:
    parts: list[str] = []
    for c in companies:
        level_cn = _RISK_CN.get(c.risk_level, c.risk_level)
        score = f"{c.overall_score:.3f}" if c.overall_score is not None else "—"
        rules = "、".join(c.triggered_rules) if c.triggered_rules else "无"
        parts.append(
            f"公司：{c.sec_name}（{c.wind_code}）｜综合风险等级："
            f"{c.risk_level}（{level_cn}）评分 {score}｜触发规则：{rules}"
            f"｜数据截止：{c.as_of or '—'}"
        )
    return "\n".join(parts)


def _build_messages(companies: list[ComparisonAnalysisCompany]) -> list[dict]:
    codes = [c.wind_code for c in companies]
    system = (
        "你是上市公司财报反欺诈问答系统的「跨公司对比分析」助手。"
        "下面给出程序校验过的结构化事实（每家公司综合风险等级/评分/触发规则——"
        "数字/规则/公司名均已锁定，不得修改、不得新增）。"
        "你的任务：\n"
        "1. 输出 overall：300-400 字的整体对比分析，按序覆盖——"
        "①各家公司风险画像与等级差异（引用具体公司名与评分/规则）；"
        "②共同风险信号与差异点（同行业共性问题或各家特有信号）；"
        "③各自最需关注的风险点（按风险等级排序说明）；"
        "④跨公司交叉核验建议（如行业共性问题下的核查方向，不荐股、不评级）；\n"
        "2. 输出 suggestions：按公司给出可执行建议（company_code 必须取自"
        "给定公司列表，text 每句必须引用事实中的具体规则或数字）；\n"
        "3. 约束：绝不输出 facts 之外的新数字/新公司名；绝不给出投资建议/"
        "买卖评级；数据不足时如实说明，不得虚构。\n"
        "输出 JSON 必须严格符合给定 schema。"
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "对比公司代码："
            + "、".join(codes)
            + "\n结构化事实：\n"
            + _locked_text(companies),
        },
    ]


def _template_advice(
    companies: list[ComparisonAnalysisCompany],
) -> tuple[str, list[ComparisonAnalysisSegment]]:
    """确定性模板兜底：等级/评分对比 + 各自触发规则 + 核查建议（不空洞）。"""
    ranked = sorted(
        companies,
        key=lambda c: (
            {
                "red": 5,
                "orange": 4,
                "yellow": 3,
                "blue": 2,
                "green": 1,
                "unknown": 0,
            }.get(c.risk_level, 0),
            -(c.overall_score if c.overall_score is not None else 0),
        ),
        reverse=True,
    )
    worst = ranked[0] if ranked else None
    lines: list[str] = []
    for c in companies:
        score = f"{c.overall_score:.3f}" if c.overall_score is not None else "—"
        rules = "、".join(c.triggered_rules) if c.triggered_rules else "无触发规则"
        lines.append(
            f"{c.sec_name}（{c.wind_code}）：综合风险等级 {_RISK_CN.get(c.risk_level, c.risk_level)}"
            f"（评分 {score}），触发规则 {rules}。"
        )
    overall_parts = [
        "跨公司对比结论：",
        "；".join(lines),
    ]
    if worst:
        level_cn = _RISK_CN.get(worst.risk_level, worst.risk_level)
        score_part = (
            f"评分 {worst.overall_score:.3f}）"
            if worst.overall_score is not None
            else "）"
        )
        overall_parts.append(
            f"其中 {worst.sec_name} 风险等级最高（{level_cn}{score_part}"
        )
        overall_parts.append(
            "，建议优先核查其触发规则对应的报表科目与披露明细，"
            "再横向比较各家公司共同信号以识别行业共性问题。"
        )
    else:
        overall_parts.append("本次无可对比公司。")
    overall = "".join(overall_parts)
    segments = [
        ComparisonAnalysisSegment(
            company_code=c.wind_code,
            title="公司建议",
            detail=(
                f"针对 {c.sec_name}（{c.wind_code}）："
                + (
                    "、".join(c.triggered_rules)
                    if c.triggered_rules
                    else "当前未触发财务预警规则，建议关注舆情与股权数据完整性。"
                )
                + "，建议结合画像页证据进一步核验。"
            ),
        )
        for c in companies
    ]
    return overall, segments


async def assemble_comparison_advice(codes: list[str]) -> ComparisonAnalysisData:
    """多公司锁定事实 → LLM 对比分析（失败 → 模板兜底）。"""
    warnings: list[str] = []
    companies: list[ComparisonAnalysisCompany] = []
    for code in codes:
        try:
            companies.append(await _company_fact(code))
        except Exception as exc:  # noqa: BLE001 — 单家失败不阻断整体
            logger.warning("comparison_advice: 公司 %s 分析失败: %s", code, exc)
            warnings.append(f"公司 {code} 风险分析失败，本次对比不含该公司")

    if not companies:
        return ComparisonAnalysisData(
            companies=[],
            overall="所选公司均无法完成风险分析，请稍后重试。",
            method="template",
            warnings=warnings,
        )

    overall_text, template_segments = _template_advice(companies)
    method = "template"

    from app.agents.llm_guard import llm_with_fallback
    from app.core.config import settings

    if settings.LLM_BACKEND not in ("", "mock"):
        valid_codes = {c.wind_code for c in companies}

        def _validate(output) -> tuple[bool, str]:
            if not output.overall.strip() or not output.suggestions:
                return False, "overall 或 suggestions 为空"
            for s in output.suggestions:
                if s.company_code not in valid_codes or not s.text.strip():
                    return False, f"非法公司代码（{s.company_code!r}）"
            from app.application.services._llm_numeric_lock import unlocked_numbers

            invented = unlocked_numbers(
                [output.overall, *(s.text for s in output.suggestions)],
                _locked_text(companies),
            )
            if invented:
                return False, f"输出包含事实之外的数字: {sorted(invented)}"
            return True, ""

        def _fallback():
            warnings.append("对比分析 LLM 降级，使用模板兜底")
            return overall_text

        output, used = await asyncio.to_thread(
            llm_with_fallback,
            _build_messages(companies),
            _ComparisonOutput,
            fallback=_fallback,
            validate=_validate,
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        if used:
            overall_text = output.overall.strip()
            method = "llm"
            template_segments = [
                ComparisonAnalysisSegment(
                    company_code=s.company_code,
                    title="公司建议",
                    detail=s.text.strip(),
                )
                for s in output.suggestions
            ]

    return ComparisonAnalysisData(
        companies=companies,
        overall=overall_text,
        segments=template_segments,
        method=method,
        warnings=warnings,
    )
