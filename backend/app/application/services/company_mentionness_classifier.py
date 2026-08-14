"""CompanyMentionnessClassifier — v3.3 批次 D / v3.3.1 §9.3：零候选 span 的 NIL 判定.

仅用于"全部合法 proposal 均零候选"的 span，输出三态：

    company_mention | non_company_context | abstain

约束（v3.3 §4.5 / v3.3.1 §9.3）：

- 输出不得包含 wind_code、公司名补全或自由文本实体（schema 不含这些
  字段）；
- off（生产默认）：零次 LLM 调用，保持现有确定性路径；
- suggest/auto：显式构造启用；批量判定——一条 query 最多一次 LLM
  调用（classify_many），程序校验每个输入 span_id 恰好一个 verdict；
- 超时/异常/校验失败 → 确定性 not_found（绝不沿用历史主体）；
- 仅离线 runner 注入，生产 Agent 不注入 classifier。

与 CompanySemanticSelector 的边界：Selector 只处理候选/分段/关系歧义，
本 classifier 只处理零候选片段的"是否像公司 mention"判断——两者均不
得生成候选集之外的代码。
"""

from __future__ import annotations

import logging
import time

from app.application.models.company_resolution import (
    MentionnessDecision,
    MentionnessVerdict,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class CompanyMentionnessClassifier:
    """零候选片段 mentionness 判定器（同步；LLM structured output）。"""

    def __init__(
        self, mode: str | None = None, total_budget_seconds: float | None = None
    ) -> None:
        self._mode = mode or settings.ENTITY_SEMANTIC_SELECTION_MODE
        # v3.3.1 §9.4：构造参数统一为 query 级总预算（不再有独立的
        # 每次调用 5s 上限——单次调用直接使用剩余 deadline）
        self._total_budget = (
            total_budget_seconds
            if total_budget_seconds is not None
            else float(settings.ENTITY_SEMANTIC_SELECTION_TOTAL_BUDGET_SECONDS)
        )
        self.last_attempts = 0
        self.last_validation_error = ""

    @property
    def mode(self) -> str:
        return self._mode

    def classify_many(
        self, *, user_query: str, spans: list[dict]
    ) -> tuple[str, MentionnessDecision | None]:
        """批量判定零候选 span（v3.3.1 §9.3：一条 query 一次调用）。

        spans: [{"span_id", "span_text"}]。
        校验：每个输入 span_id 恰好一个 verdict；无未知/重复/遗漏 ID。
        timeout/invalid 只记录失败，不改变确定性 not_found。

        Returns:
            (status, decision|None)
            disabled（off/mock，零调用）| failed | timeout | invalid | completed
        """
        self.last_attempts = 0
        self.last_validation_error = ""
        if settings.LLM_BACKEND == "mock" or self._mode not in ("suggest", "auto"):
            return "disabled", None
        if not spans:
            return "disabled", None
        from app.agents.llm_sync import run_llm_structured

        span_lines = "\n".join(
            f"- span_id={s['span_id']} 原文='{s['span_text']}'" for s in spans
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是财报问答系统的公司片段判定器。给定用户问题和若干"
                    "未能在公司库中检索到任何候选的文本片段，判断每个片段：\n"
                    "- company_mention：疑似公司名但库内无记录（用户可能写了"
                    "新公司/错别字/简称）；\n"
                    "- non_company_context：明确不是公司（行业/研报/报表/指标"
                    "等业务上下文）；\n"
                    "- abstain：无法确定。\n"
                    "每个输入 span_id 必须恰好输出一个 verdict；只能输出三态"
                    "之一；不得输出股票代码、不得补全公司名、不得输出其他"
                    "文本实体。输出 JSON 必须严格符合 schema。"
                ),
            },
            {
                "role": "user",
                "content": f"用户问题：{user_query}\n片段列表：\n{span_lines}",
            },
        ]
        started = time.perf_counter()
        remaining = self._total_budget - (time.perf_counter() - started)
        if remaining <= 0:
            return "timeout", None
        self.last_attempts = 1
        try:
            decision = run_llm_structured(
                messages, MentionnessDecision, timeout=remaining
            )
        except Exception:  # noqa: BLE001
            logger.warning("Mentionness: LLM 调用异常，确定性 not_found", exc_info=True)
            return "failed", None
        if decision is None:
            return "timeout", None
        # 程序校验：每个输入 span_id 恰好一个 verdict（无未知/重复/遗漏）
        input_ids = {s["span_id"] for s in spans}
        if len(input_ids) != len(spans):
            self.last_validation_error = "输入 span_id 重复"
            return "invalid", None
        out_ids = [v.span_id for v in decision.verdicts]
        if len(out_ids) != len(set(out_ids)):
            self.last_validation_error = "输出 span_id 重复"
            return "invalid", None
        if set(out_ids) != input_ids:
            self.last_validation_error = (
                f"verdict 与输入 span 不一一对应: 输入 {sorted(input_ids)} "
                f"输出 {sorted(out_ids)}"
            )
            return "invalid", None
        for v in decision.verdicts:
            if v.verdict not in (
                "company_mention",
                "non_company_context",
                "abstain",
            ):
                self.last_validation_error = f"非法 verdict: {v.verdict}"
                return "invalid", None
        return "completed", decision

    def classify(
        self, *, user_query: str, span_id: str, span_text: str
    ) -> tuple[str, MentionnessVerdict | None]:
        """单 span 便捷包装（委托 classify_many，同样一次调用）。"""
        status, decision = self.classify_many(
            user_query=user_query, spans=[{"span_id": span_id, "span_text": span_text}]
        )
        if status != "completed" or decision is None:
            return status, None
        return "completed", decision.verdicts[0]
