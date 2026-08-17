"""LLM-NER 公司子实体提取 — 8/17 Phase E 语义裁决扩展.

业界实体识别链路（NER → 链接）的提取层补充：Extractor 启发式 mask 是
"词典/规则快路径"，本服务是"LLM-NER 零样本提取"——对**长且未命中**的
零候选 span（含施事/介词结构，如"证券机构对金百泽"）提取片段内的
公司名原文子串，供 Resolver 二次链接。

约束（对齐 mentionness/selector 既有模式）：
- 单一任务：只输出 has_company + company_span（原文子串），不做主体/
  关系/意图多任务（interpreter 多任务实测不稳定，单任务 15/15 可靠）；
- 程序校验：company_span 必须是输入 span 的原文切片（query.find 复核）、
  长度 ≥2；非法/超时/异常 → 整体 fail-closed（返回空，保持原逻辑）；
- 批量：一条 query 最多一次 LLM 调用（extract_many）；
- off/mock：零调用；仅 suggest/auto 启用；
- 不输出股票代码、不补全公司全称（schema 无这些字段）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# 触发长度：只有长 span（含施事/介词结构）才需要子实体提取；
# 短 span（"金百泽""融资融券"）直接走既有 not_found 路径。
SPAN_EXTRACT_MIN_LEN = 5
_LLM_TIMEOUT_SECONDS = 10.0
_MAX_SUB_SPANS = 4


class SpanExtractionOutput(BaseModel):
    """LLM 输出：单 span 的公司子实体判定。"""

    has_company: bool = False
    company_span: str = Field(default="", description="片段内公司名原文子串（无则空）")


class SpanExtractionBatch(BaseModel):
    """批量外壳（按输入 span 顺序一一对应）。"""

    results: list[SpanExtractionOutput] = Field(default_factory=list)


class CompanySpanLLMExtractor:
    """受约束 LLM-NER 子实体提取器（同步；批量一次调用）。"""

    def __init__(
        self,
        mode: str | None = None,
        total_budget_seconds: float | None = None,
    ) -> None:
        self._mode = mode or settings.ENTITY_SEMANTIC_SELECTION_MODE
        self._budget = (
            total_budget_seconds
            if total_budget_seconds is not None
            else _LLM_TIMEOUT_SECONDS
        )
        self.last_status: str = "not_needed"
        self.last_attempts = 0
        self.last_validation_error = ""

    @property
    def mode(self) -> str:
        return self._mode

    def _disabled(self) -> dict[str, str]:
        self.last_status = "disabled"
        return {}

    def extract_many(
        self,
        *,
        user_query: str,
        mentions: list[Any],
    ) -> dict[str, str]:
        """批量提取 span 内公司子实体。

        Args:
            mentions: EntityMention 列表（not_found 且长 span）。

        Returns:
            {mention_id: 子实体原文子串}；LLM 无子实体/失败/关闭 → 空 dict。
        """
        self.last_attempts = 0
        self.last_validation_error = ""
        if settings.LLM_BACKEND in ("", "mock") or self._mode not in (
            "suggest",
            "auto",
        ):
            return self._disabled()
        long_mentions = [
            m for m in mentions if len(m.text or "") >= SPAN_EXTRACT_MIN_LEN
        ]
        if not long_mentions:
            return self._disabled()

        from app.agents.llm_sync import run_llm_structured

        span_lines = "\n".join(
            f"- span_id={m.mention_id} 原文='{m.text}'" for m in long_mentions
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是财报问答系统的公司片段提取器。给定用户问题原文片段"
                    "（可能是句子的一部分），判断每个片段内是否包含某个上市"
                    "公司的名称或简称：\n"
                    "- has_company=true 且 company_span 必须是从该片段中"
                    "**逐字摘出**的公司名子串（不得改写、不得补全，如"
                    "'证券机构对金百泽'→'金百泽'）；\n"
                    "- 片段只是施事主体/业务词（如'证券机构对''融资融券'）"
                    "→ has_company=false；\n"
                    "- 不确定 → has_company=false。\n"
                    "每个输入 span_id 必须恰好一个 verdict（输出 JSON 严格"
                    "符合 schema，无 span_id 字段——按输入顺序一一对应）。"
                ),
            },
            {
                "role": "user",
                "content": f"用户问题：{user_query}\n片段列表：\n{span_lines}",
            },
        ]

        started = time.perf_counter()
        remaining = self._budget - (time.perf_counter() - started)
        if remaining <= 0:
            self.last_status = "timeout"
            return {}
        self.last_attempts = 1
        try:
            batch: SpanExtractionBatch | None = run_llm_structured(
                messages,
                SpanExtractionBatch,
                timeout=remaining,
            )
        except Exception:  # noqa: BLE001 — 任何异常 fail-closed
            logger.warning("span_extractor: LLM 调用异常，保持原逻辑", exc_info=True)
            self.last_status = "failed"
            return {}
        if batch is None:
            self.last_status = "timeout"
            return {}
        outputs = batch.results
        if not outputs:
            self.last_status = "timeout"
            return {}

        # 程序校验：按输入顺序一一对应 + 子串必须是原文切片 + 长度 ≥2
        if len(outputs) != len(long_mentions):
            self.last_status = "invalid"
            self.last_validation_error = (
                f"输出 {len(outputs)} != 输入 {len(long_mentions)}"
            )
            return {}
        q = user_query or ""
        result: dict[str, str] = {}
        for m, out in zip(long_mentions, outputs):
            if not out.has_company or not out.company_span:
                continue
            span = str(out.company_span).strip()
            if len(span) < 2:
                continue
            # 子串必须位于输入 span 的原文范围内（防 LLM 编造）
            start = q.find(span, m.start or 0, m.end or len(q))
            if start < 0:
                self.last_validation_error = (
                    f"子实体非原文切片: {span!r}（{m.mention_id}）"
                )
                self.last_status = "invalid"
                return {}
            result[m.mention_id] = span
        self.last_status = "completed" if result else "no_span"
        return result
