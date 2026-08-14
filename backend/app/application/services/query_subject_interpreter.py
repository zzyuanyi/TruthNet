"""QuerySubjectInterpreter — v3.3.2-R1 §6：低置信 query 的主体语义解析（一次 LLM）.

职责边界（§6.1）：
- 提取当前 query 中真正的公司原文 span；
- 判断当前轮指向新主体 / 历史主体 / 无主体 / 不确定；
- 判断公司 mention 之间的关系；
- 给 Plan 一个粗粒度 plan_hint（避免同一 query 二次语义 LLM）。

不负责（§6.1/§15）：
- 不输出或补全股票代码（schema 无 wind_code 字段）；
- 不查库、不从候选中选公司、不计算指标、不生成回答；
- 不覆盖精确代码/名称/唯一锁定结果（调用策略见 Resolver）。

发布模式（§7.4）：off=零调用（生产默认）；shadow=调用并记录、权威不变；
fallback=低置信路径应用通过 verifier 的解释。单次硬预算 5s，不 repair。

公司身份仍由 Repository 二次链接（§7.3）：Interpreter 只提出原文 span。
"""

from __future__ import annotations

import json as _json
import logging
import re
import time

from app.application.models.company_resolution import (
    ProposedCompanySpan,
    QuerySubjectInterpretation,
    UnresolvedMentionInput,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# 合法 Wind Code 原文（6 位数字 ± 后缀）
_WIND_CODE_RE = re.compile(r"^\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?$", re.IGNORECASE)


def _is_cn(ch: str) -> bool:
    return "一" <= ch <= "龥"


def _all_company_spans(interp: QuerySubjectInterpretation) -> list[ProposedCompanySpan]:
    spans: list[ProposedCompanySpan] = list(interp.additional_company_spans)
    for d in interp.input_span_dispositions:
        spans.extend(d.proposed_company_spans)
    return spans


def verify_interpretation(
    interp: QuerySubjectInterpretation,
    query: str,
    unresolved_mentions: list[UnresolvedMentionInput],
    has_current_subject: bool,
) -> tuple[bool, str]:
    """v3.3.2-R1 §6.3：不变量校验，全部通过才允许 Resolver 使用。

    失败不 repair、不重试——调用方直接 fail-closed。
    """
    q = query or ""

    # 0（中间验收 P1-1）. 输入 mention 与原文一致：text == query 切片、
    # 边界合法、mention_id 唯一
    input_ids: set[str] = set()
    parents: dict[str, UnresolvedMentionInput] = {}
    for m in unresolved_mentions:
        if m.mention_id in input_ids:
            return False, f"重复输入 mention: {m.mention_id}"
        input_ids.add(m.mention_id)
        parents[m.mention_id] = m
        if not (0 <= m.start < m.end <= len(q)):
            return False, f"输入 mention 越界: {m.mention_id} ({m.start}:{m.end})"
        if q[m.start : m.end] != m.text:
            return False, f"输入 mention 与原文不符: {m.text!r}"

    # 4/5. 每个输入 unresolved mention_id 恰好一个 disposition，无未知/重复/遗漏
    seen: set[str] = set()
    for d in interp.input_span_dispositions:
        if d.mention_id in seen:
            return False, f"重复 disposition: {d.mention_id}"
        seen.add(d.mention_id)
        if d.mention_id not in input_ids:
            return False, f"未知 mention_id: {d.mention_id}"
        # 15（中间验收 P1-1）. disposition 提出的 span 必须位于其输入
        # mention 范围内（只有 additional_company_spans 允许越出）
        pm = parents[d.mention_id]
        for s in d.proposed_company_spans:
            if not (pm.start <= s.start and s.end <= pm.end):
                return False, (
                    f"proposed span 越出输入 mention: {s.text!r} "
                    f"({s.start}:{s.end}) 超出 {pm.text!r} ({pm.start}:{pm.end})"
                )
    if input_ids != seen:
        missing = sorted(input_ids - seen)
        return False, f"遗漏 mention_id: {missing}"

    for d in interp.input_span_dispositions:
        # 6. kind=company 必须至少一个 company span
        if d.kind == "company" and not d.proposed_company_spans:
            return False, f"company disposition 无 span: {d.mention_id}"
        # 7. kind=context 不得携带 company span
        if d.kind == "context" and d.proposed_company_spans:
            return False, f"context disposition 携带 span: {d.mention_id}"

    all_spans = _all_company_spans(interp)
    # 1/2/3. span 必须等于原文切片、边界合法、≥2 中文字符或 Wind Code
    for s in all_spans:
        if not (0 <= s.start < s.end <= len(q)):
            return False, f"span 越界: {s.text!r} ({s.start}:{s.end})"
        if q[s.start : s.end] != s.text:
            return False, f"span 与原文不符: {s.text!r} != {q[s.start:s.end]!r}"
        if not _WIND_CODE_RE.match(s.text) and sum(1 for c in s.text if _is_cn(c)) < 2:
            return False, f"公司 span 过短: {s.text!r}"

    # 8. new 必须至少一个 company span
    if interp.subject_reference == "new" and not all_spans:
        return False, "subject_reference=new 但无公司 span"
    # 9. previous 必须存在 current subject
    if interp.subject_reference == "previous" and not has_current_subject:
        return False, "subject_reference=previous 但无 current subject"
    # 10. previous 时所有输入 unresolved 必须是 context（防串核心：
    # LLM 不能仅输出 previous 就把疑似新公司吞掉）
    if interp.subject_reference == "previous":
        for d in interp.input_span_dispositions:
            if d.kind != "context":
                return False, f"previous 但 span 非 context: {d.mention_id}"
        # 10b（中间验收 P0-1）：previous 不得携带任何公司 span——
        # additional_company_spans 同样构成新主体证据，禁止吞掉
        if all_spans:
            return False, "previous 但携带公司 span"
    # 11. none/uncertain 不得携带公司 span（中间验收 P0-1：uncertain
    # 与 none 同语义——不确定时不输出任何公司证据）
    if interp.subject_reference in ("none", "uncertain") and all_spans:
        return False, f"subject_reference={interp.subject_reference} 但携带公司 span"
    # 12. 两个以上公司 span 才允许 comparison/reference/sequence
    # （最终续审 §4 A1：include_current_subject=True 时当前主体作为
    # 第二个参与者，新公司 span 至少一个即可）
    min_spans = 1 if interp.include_current_subject else 2
    if (
        interp.company_relation in ("comparison", "reference", "sequence")
        and len(all_spans) < min_spans
    ):
        return False, f"relation={interp.company_relation} 但公司 span 不足 {min_spans}"
    # 16（最终续审 §4 A1）：include_current_subject 的语义约束——
    # 必须存在 current subject、只允许 new + comparison
    if interp.include_current_subject:
        if not has_current_subject:
            return False, "include_current_subject 但无 current subject"
        if interp.subject_reference != "new":
            return False, "include_current_subject 只允许 subject_reference=new"
        if interp.company_relation != "comparison":
            return False, "include_current_subject 只允许 company_relation=comparison"
    # 13. span 不得互相非法重叠
    ordered = sorted(all_spans, key=lambda s: (s.start, s.end))
    for a, b in zip(ordered, ordered[1:]):
        if a.end > b.start:
            return False, f"span 重叠: {a.text!r} / {b.text!r}"
    return True, ""


class QuerySubjectInterpreter:
    """低置信 query 主体语义解析器（同步；一次 LLM structured output）。

    模式（§7.4）：off 零调用；shadow 调用但由 Resolver 决定不应用；
    fallback 低置信路径应用。单次硬预算 budget_seconds（默认 5s），
    不 repair、不重试。
    """

    def __init__(
        self,
        mode: str | None = None,
        budget_seconds: float | None = None,
    ) -> None:
        self._mode = mode or settings.ENTITY_QUERY_INTERPRETER_MODE
        self._budget = (
            budget_seconds
            if budget_seconds is not None
            else float(settings.ENTITY_QUERY_INTERPRETER_BUDGET_SECONDS)
        )
        self.last_status: str = "not_needed"
        self.last_interpretation: QuerySubjectInterpretation | None = None
        # 最终续审 §6 C2：调用审计（elapsed/backend/model/budget）
        self.last_elapsed_ms: float | None = None
        self.last_backend: str = settings.LLM_BACKEND
        self.last_model: str = self._current_model_name()

    @staticmethod
    def _current_model_name() -> str:
        """当前主 LLM 模型名（用于审计；无法取到则为空）。"""
        return getattr(settings, "DEEPSEEK_MODEL", "")

    @property
    def mode(self) -> str:
        return self._mode

    def interpret(
        self,
        *,
        query: str,
        unresolved_mentions: list[UnresolvedMentionInput],
        has_current_subject: bool,
    ) -> tuple[str, QuerySubjectInterpretation | None]:
        """单次受约束解析（off/mock 零调用；失败 fail-closed）。

        Returns:
            (status, interpretation|None)
            disabled | completed | invalid | timeout | failed
        """
        self.last_status = "not_needed"
        self.last_interpretation = None
        if settings.LLM_BACKEND == "mock" or self._mode == "off":
            self.last_status = "disabled"
            return "disabled", None
        if not query.strip():
            return "disabled", None

        from app.agents.llm_sync import run_llm_structured

        # 中间验收 P1-1：完整原文信息进结构化 JSON payload（mention_id/
        # text/start/end），LLM 才有多 span 裁决的必要输入
        span_payload = [
            {
                "mention_id": m.mention_id,
                "text": m.text,
                "start": m.start,
                "end": m.end,
            }
            for m in unresolved_mentions
        ]
        span_lines = (
            _json.dumps(span_payload, ensure_ascii=False) if span_payload else "（无）"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是财报问答系统的主体语义解析器。给定用户问题和若干"
                    "未能在公司库检索到候选的原文片段（JSON 格式，含 "
                    "mention_id/text/start/end，start/end 是片段在用户"
                    "问题原文中的字符坐标），判断：\n"
                    "1. 本轮指向新公司主体、历史主体、无主体还是不确定"
                    "（subject_reference）；\n"
                    "2. 每个输入片段的性质（company/context/uncertain），"
                    "company 时必须给出该片段内的原文公司 span（span 坐标"
                    "必须落在该输入片段范围内）；\n"
                    "3. 额外识别输入片段之外的公司原文 span（只能放"
                    "additional_company_spans）；\n"
                    "4. 公司间关系（两个以上公司 span 才允许 comparison/"
                    "reference/sequence）；\n"
                    "5. 粗粒度意图 plan_hint。\n"
                    "约束：\n"
                    "- 只能返回用户问题原文的子串，start/end 必须与原文"
                    "完全对应，不得改写或补全任何文字；\n"
                    "- 绝不输出股票代码或公司全称补全；\n"
                    "- 不确定就输出 uncertain，不要猜测；\n"
                    "- 仅当明确指代历史主体（如'毛利率正常吗''总结一下"
                    "这家公司'）时输出 previous；含疑似新公司（如"
                    "'台泥''小米'）时不得输出 previous。\n"
                    "示例：\n"
                    "- 有没有存贷双高的风险 -> previous，输入片段为 context；\n"
                    "- 毛利率正常吗 -> previous，无公司 span；\n"
                    "- 那茅台呢 -> new，公司 span 为茅台；\n"
                    "- 回到康美 -> new，公司 span 为康美；\n"
                    "- 台泥的营收 -> new，公司 span 为台泥；\n"
                    "- 康美提到茅台 -> new，两个公司 span，relation=reference。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{query}\n"
                    f"未检索到候选的片段：\n{span_lines}\n"
                    f"历史主体：{'存在' if has_current_subject else '不存在'}"
                ),
            },
        ]
        started = time.perf_counter()
        remaining = self._budget - (time.perf_counter() - started)
        if remaining <= 0:
            self.last_status = "timeout"
            self._audit_call("timeout", started)
            return "timeout", None
        try:
            interp = run_llm_structured(
                messages, QuerySubjectInterpretation, timeout=remaining
            )
        except Exception:  # noqa: BLE001 — 失败 fail-closed
            self._audit_call("failed", started)
            logger.warning("Interpreter: LLM 调用异常", exc_info=True)
            self.last_status = "failed"
            return "failed", None
        if interp is None:
            self._audit_call("timeout", started)
            self.last_status = "timeout"
            return "timeout", None
        ok, reason = verify_interpretation(
            interp, query, unresolved_mentions, has_current_subject
        )
        if not ok:
            self._audit_call("invalid", started)
            logger.warning(
                "Interpreter: 解释未通过 verifier（%s），fail-closed", reason
            )
            self.last_status = "invalid"
            return "invalid", None
        self._audit_call("completed", started)
        self.last_status = "completed"
        self.last_interpretation = interp
        return "completed", interp

    def _audit_call(self, status: str, started: float) -> None:
        """最终续审 §6 C2：记录调用审计（elapsed/backend/model/budget）。"""
        self.last_elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "Interpreter audit: status=%s elapsed_ms=%.1f backend=%s "
            "model=%s budget_s=%s mode=%s",
            status,
            self.last_elapsed_ms,
            self.last_backend,
            self.last_model,
            self._budget,
            self._mode,
        )
