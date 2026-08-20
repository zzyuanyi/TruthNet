"""跨公司对比大模型整体分析 — Phase E 会6（8/16 会议整改第⑥条）.

在既有结构化对比（light_comparison_service，v3.3.4 已收口）之上追加
LLM 整体分析段落：比较不再是纯数值罗列，输出"说明了什么"的整体判断。

铁律（会6）：
- 分析不覆盖、不篡改结构化数据：LLM 只读程序生成的 facts（指标/值/
  期间/差异，数字锁定），输出文本解读段落；结构化 overview_rows 独立
  保留、独立渲染；
- 每段结论可溯源：段落携带 metric_ids（引用指标），与 overview_rows
  一一对应；
- 无 LLM / 超时 / 校验失败 → 确定性模板兜底（基于 ok_rows 生成小结），
  绝不返回空泛空洞的分析；
- 纯解读不荐股：整体判断基于指标对比事实，不输出投资建议。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 与 events_impact_service 同口径的 LLM 调用预算（单次解析总墙钟）
_ANALYSIS_TIMEOUT_SECONDS = 15.0


class ComparisonAnalysisParagraph(BaseModel):
    """单段整体分析（可溯源到具体指标）。"""

    text: str = Field(..., description="分析段落文本（只基于 facts，不输出新数字）")
    metric_ids: list[str] = Field(default_factory=list, description="引用指标 ID")


class ComparisonAnalysisOutput(BaseModel):
    """LLM 结构化输出：整体判断 + 分指标分析段落。"""

    overall: str = Field(..., description="一句话总体判断（基于指标对比事实）")
    paragraphs: list[ComparisonAnalysisParagraph] = Field(default_factory=list)


def _fmt_value(value: float, unit: str) -> str:
    if unit in ("percent", "ratio", "pp"):
        return f"{value:.2f}%"
    if unit == "days":
        return f"{value:.2f}天"
    return f"{value:,.2f}元"


def _build_facts(result: Any) -> list[str]:
    """从 overview_rows（ok 行）构建只读数字事实（数字锁定）。"""
    facts: list[str] = []
    for row in getattr(result, "overview_rows", None) or []:
        if row.status != "ok" or len(row.values) != 2:
            continue
        a, b = row.values
        unit = row.unit or ""
        facts.append(
            f"- {row.metric_label}（{row.metric_id}，共同期间 {row.period}）："
            f"{a.sec_name} {_fmt_value(float(a.value), unit)}；"
            f"{b.sec_name} {_fmt_value(float(b.value), unit)}；"
            f"差异 {_fmt_value(float(row.difference), row.difference_unit or unit)}"
        )
    if not facts:
        # 单指标比较（indicator 模式）：participants 承载双方值
        participants = getattr(result, "participants", None) or []
        if len(participants) >= 2:
            a, b = participants[0], participants[1]
            unit = getattr(result, "difference_unit", "") or a.unit or ""
            facts.append(
                f"- {a.metric_label}（{a.metric_id}，期间 {a.period}）："
                f"{a.sec_name} {_fmt_value(float(a.value), a.unit or '')}；"
                f"{b.sec_name} {_fmt_value(float(b.value), b.unit or '')}；"
                f"差异 {_fmt_value(float(result.difference), unit)}"
            )
    return facts


def _build_messages(company_names: list[str], facts: list[str]) -> list[dict]:
    system = (
        "你是财报问答系统的跨公司对比分析助手。用户比较了两家上市公司的"
        "财务指标，下方给出程序校验过的结构化数据（数字锁定，不得修改、"
        "不得新增数值）。你的任务：\n"
        "1. 基于给定指标事实做整体解读——两家公司各自特征、关键差异"
        "（如盈利质量、杠杆水平、经营现金流），说明'差异说明了什么'；\n"
        "2. 输出 overall（一句话总体判断）与 paragraphs（分维度分析段落，"
        "每段 text 只做定性解读，可携带 metric_ids 引用对应指标）；\n"
        "3. 约束：绝不输出 facts 之外的新数值、新期间或新公司名；绝不给出"
        "投资建议/买卖评级；分析基于母公司报表口径与共同期间。\n"
        "输出 JSON 必须严格符合给定 schema。"
    )
    user = (
        f"对比主体：{' vs '.join(company_names) or '两家公司'}\n"
        "结构化指标事实：\n" + ("\n".join(facts) if facts else "（无可比较指标）")
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _validate_output(
    output: ComparisonAnalysisOutput,
    facts_metric_ids: set[str],
    locked_facts: str = "",
) -> tuple[bool, str]:
    """校验必填字段、指标引用和 LLM 数字锁定。"""
    if not output.overall or not output.overall.strip():
        return False, "overall 为空"
    if not output.paragraphs:
        return False, "paragraphs 为空"
    for para in output.paragraphs:
        if not para.text or not para.text.strip():
            return False, "段落 text 为空"
        unknown = [mid for mid in para.metric_ids if mid not in facts_metric_ids]
        if unknown:
            return False, f"段落引用了事实之外的指标: {unknown}"
    from app.application.services._llm_numeric_lock import unlocked_numbers

    invented = unlocked_numbers(
        [output.overall, *(para.text for para in output.paragraphs)], locked_facts
    )
    if invented:
        return False, f"输出包含事实之外的数字: {sorted(invented)}"
    return True, ""


def _template_analysis(result: Any) -> str:
    """确定性模板兜底：基于 ok_rows 生成'谁高谁低'小结（无 LLM 也可用）。"""
    lines: list[str] = []
    for row in getattr(result, "overview_rows", None) or []:
        if row.status != "ok" or len(row.values) != 2:
            continue
        a, b = row.values
        unit = row.unit or ""
        if float(a.value) > float(b.value):
            cmp_word = "高于"
        elif float(a.value) < float(b.value):
            cmp_word = "低于"
        else:
            cmp_word = "接近"
        lines.append(
            f"{a.sec_name} 的{row.metric_label}{cmp_word}{b.sec_name}"
            f"（{a.sec_name} {_fmt_value(float(a.value), unit)}；"
            f"{b.sec_name} {_fmt_value(float(b.value), unit)}；共同期间 {row.period}）"
        )
    participants = getattr(result, "participants", None) or []
    if not lines and len(participants) >= 2:
        a, b = participants[0], participants[1]
        unit = getattr(result, "difference_unit", "") or a.unit or ""
        if float(a.value) > float(b.value):
            cmp_word = "高于"
        elif float(a.value) < float(b.value):
            cmp_word = "低于"
        else:
            cmp_word = "接近"
        lines.append(
            f"{a.sec_name} 的{a.metric_label}{cmp_word}{b.sec_name}"
            f"（{a.sec_name} {_fmt_value(float(a.value), a.unit or '')}；"
            f"{b.sec_name} {_fmt_value(float(b.value), b.unit or '')}）"
        )
    if not lines:
        return "两家公司在可比较指标上数据不足，无法给出整体分析。"
    return "；".join(lines)


def build_comparison_analysis(
    *,
    result: Any,
    company_names: list[str],
) -> tuple[str, list[str]]:
    """生成跨公司对比整体分析段落。

    Returns:
        (analysis_text, warnings)：analysis_text 为 LLM 段落或模板兜底；
        warnings 记录 LLM 降级原因（空列表表示 LLM 成功）。
    """
    warnings: list[str] = []
    facts = _build_facts(result)
    if not facts:
        # 无任何可比较事实 → 不调用 LLM，直接诚实兜底
        return _template_analysis(result), []

    from app.agents.llm_guard import llm_with_fallback
    from app.core.config import settings

    if settings.LLM_BACKEND == "mock":
        return _template_analysis(result), ["LLM mock 环境，使用确定性模板分析"]

    facts_metric_ids: set[str] = set()
    for row in getattr(result, "overview_rows", None) or []:
        if row.status == "ok":
            facts_metric_ids.add(row.metric_id)
    for p in getattr(result, "participants", None) or []:
        facts_metric_ids.add(p.metric_id)

    def _validate(output) -> tuple[bool, str]:
        return _validate_output(output, facts_metric_ids, "\n".join(facts))

    def _template_fallback() -> str:
        warnings.append("LLM 分析降级，使用确定性模板")
        return _template_analysis(result)

    started = time.perf_counter()
    output, used = llm_with_fallback(
        _build_messages(company_names, facts),
        ComparisonAnalysisOutput,
        fallback=_template_fallback,
        validate=_validate,
        timeout=_ANALYSIS_TIMEOUT_SECONDS,
    )
    if not used:
        return output, warnings  # output = 模板兜底

    elapsed = time.perf_counter() - started
    parts = [output.overall]
    for para in output.paragraphs:
        parts.append(para.text)
    logger.info(
        "comparison_analysis: LLM 成功（%.2fs，%d 段）", elapsed, len(output.paragraphs)
    )
    return "；".join(parts), []
