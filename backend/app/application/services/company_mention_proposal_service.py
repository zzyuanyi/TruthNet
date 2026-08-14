"""MentionProposalService — v3.3 批次 B / v3.3.1 批次 A：有界候选召回.

两阶段召回（v3.3.1 §5.2）：

  1. 顶层原始 span 预留（prime_originals）：所有顶层父 span 的原始
     文本先各获得一次查询机会，防止第一个复杂 span 占满预算；
  2. 剩余预算供 fallback 使用：后缀变体、所有格、谓语边界、连接词
     剥离与复合分段（变体枚举由 Resolver 按确定性顺序驱动）。

约束：

  - 每 query 最多 `limit` 次去重 lookup（默认 12），相同 normalized
    text memoize；
  - 预算耗尽返回 `BudgetedLookupOutcome(result=None,
    budget_exhausted=True)`——显式语义，调用方降级 needs_refinement
    并写 proposal_budget_exceeded issue，不得静默丢弃后继续自动绑定；
  - 顶层唯一 span 数超过 `budget.limit` 时由 Resolver 整句 fail
    closed（零部分绑定），阈值与本类 `limit` 单一来源。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.models.company_resolution import CandidateLookupResult
from app.application.ports.company_candidate_lookup import CompanyCandidateLookup

logger = logging.getLogger(__name__)

_MAX_LOOKUPS_PER_QUERY = 12


@dataclass(frozen=True)
class BudgetedLookupOutcome:
    """预算查询结果——禁止用 None 同时表示"零候选"与"预算耗尽"
    （v3.3.1 §5.1，P0：None 访问 .matches 崩溃）。

    - 正常（含零候选）：result=CandidateLookupResult(matches=[]),
      budget_exhausted=False；
    - 预算耗尽：result=None, budget_exhausted=True（调用方立即降级，
      禁止访问 result）。
    """

    result: CandidateLookupResult | None
    budget_exhausted: bool = False


class ProposalLookupBudget:
    """v3.3 §4.2 / v3.3.1 §5.2：每 query 的有界候选召回。

    - 相同 normalized text memoize（只查一次）；
    - 单 query 最多 limit 次去重 lookup；
    - prime_originals：顶层原始 span 预留查询（公平召回阶段 1）。
    """

    def __init__(
        self, lookup: CompanyCandidateLookup, limit: int = _MAX_LOOKUPS_PER_QUERY
    ):
        self._lookup = lookup
        self._limit = limit
        self._count = 0
        self._cache: dict[str, CandidateLookupResult] = {}

    @property
    def limit(self) -> int:
        """查询预算上限（v3.3.1 §5.2：fail-closed 阈值与测试单一来源）。"""
        return self._limit

    @property
    def exhausted(self) -> bool:
        return self._count >= self._limit

    def lookup(self, text: str) -> BudgetedLookupOutcome:
        """memoize 的候选查询；预算耗尽返回显式 Outcome（见类注释）。"""
        normalized = text.strip()
        if normalized in self._cache:
            return BudgetedLookupOutcome(result=self._cache[normalized])
        if self._count >= self._limit:
            return BudgetedLookupOutcome(result=None, budget_exhausted=True)
        self._count += 1
        result = self._lookup.lookup_mention(normalized)
        self._cache[normalized] = result
        return BudgetedLookupOutcome(result=result)

    def prime_originals(self, mentions) -> list[BudgetedLookupOutcome]:
        """v3.3.1 §5.2 阶段 1：顶层原始 span 预留查询。

        按 (start, end, normalized_text) 去重后各获得一次查询机会；
        命中进入 memoize 缓存，_finalize_span 首次查询直接读缓存，
        不重复访问 Repository。mentions 为 duck-typed
        (start/end/text)。超过 limit 时后到 span 得到 exhausted
        outcome（Resolver 在 prime 前先做整句 fail-closed 检查）。
        """
        outcomes: list[BudgetedLookupOutcome] = []
        seen: set[tuple] = set()
        for m in mentions:
            key = (m.start, m.end, (m.text or "").strip())
            if key in seen:
                continue
            seen.add(key)
            outcomes.append(self.lookup(m.text))
        return outcomes
