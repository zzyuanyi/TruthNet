"""规范指标语义服务 — v3.3.3 批次 A（方案 §4.2/§4.3/§5.2）。

职责（严格限定，方案 §5.2）：
  - 维护中文短语/别名到 canonical metric ID 的映射（单一语义入口）；
  - 最长、最具体语义优先匹配（与词表声明顺序无关）；
  - 识别同比/增速/环比/最新季度等修饰；
  - 返回置信度、匹配文本、可执行性与原因；
  - unsupported 精确短语与指标短语同表竞争，命中后 executable=False。

不做（方案 §5.2）：不查数据库、不计算公式、不改公司身份、不生成答案。

LLM fallback：批次 A 仅实现确定性路径；受约束 LLM 接线另行批次
（方案 §5.7），off 模式恒零 LLM 调用。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 短语/别名 → canonical metric ID（方案 §4.2）。
# listing_date 属公司事实（ExecutionPlan.fact_key / R9），不在此表。
# (短语, canonical_id, confidence)
_METRIC_PHRASES: list[tuple[str, str, str]] = [
    ("存货周转天数", "r4_turnover_days", "exact"),
    ("存货周转情况", "r4_turnover_days", "alias"),
    ("销售毛利率", "r5_gross_margin", "alias"),
    ("毛利率", "r5_gross_margin", "exact"),
    ("应收账款余额", "accounts_receivable", "exact"),
    ("资产负债率", "debt_to_assets", "exact"),
    ("经营活动现金流", "operating_cash_flow", "exact"),
    ("经营现金流", "operating_cash_flow", "alias"),
    ("营业收入", "operating_revenue", "exact"),
    ("应收账款", "accounts_receivable", "exact"),
    ("总资产", "total_assets", "exact"),
    ("总负债", "total_liabilities", "exact"),
    ("净利润", "net_profit", "exact"),
    ("营收", "operating_revenue", "alias"),
    ("现金流", "operating_cash_flow", "alias"),
    ("负债率", "debt_to_assets", "alias"),
    ("存货", "inventories", "exact"),
]

# 已知但暂不支持的精确短语：与指标短语同表竞争（方案 §4.3 第 5 层），
# 不得先维护一张互相竞争的 unsupported 词表再被短词抢占。
_UNSUPPORTED_PHRASES: tuple[str, ...] = (
    "应收账款周转率",
    "存货周转率",
    "总资产周转率",
)

# 基础报表指标集合：与 indicator_query_service._INDICATORS 的键保持一致。
# 仅能力声明（哪些指标有同比/环比后缀语义），不复制任何公式。
_BASE_INDICATORS: frozenset[str] = frozenset(
    {
        "debt_to_assets",
        "total_assets",
        "total_liabilities",
        "accounts_receivable",
        "inventories",
        "operating_revenue",
        "net_profit",
        "operating_cash_flow",
    }
)

_MOM_WORDS: tuple[str, ...] = ("环比",)
_GROWTH_WORDS: tuple[str, ...] = ("同比", "增长", "增速")
_LATEST_QUARTER_WORDS: tuple[str, ...] = ("最新季度", "最新季")


class IndicatorSemanticResult(BaseModel):
    """规范指标语义解析结果（方案 §5.2 推荐结构）。"""

    metric_ids: list[str] = Field(default_factory=list)
    operation: str = ""  # "" / "yoy_growth" / "mom"
    period_hint: str = ""  # "" / "latest_quarter"
    confidence: Literal["exact", "alias", "llm", "none"] = "none"
    matched_texts: list[str] = Field(default_factory=list)
    executable: bool = False
    reason: str = ""  # "" / "unsupported" / "no_match" / "modifier_unsupported"


def _build_entries() -> list[tuple[str, str, str]]:
    """合并指标短语与 unsupported 短语，按最长优先稳定排序。

    方案 §4.3：解析顺序 = 完整规范短语 > 同义短语 > 基础+修饰 >
    LLM allowlist > unsupported；同一张表内最长匹配优先，
    结果与词表声明顺序无关。
    """
    entries = list(_METRIC_PHRASES)
    entries.extend((phrase, "", "exact") for phrase in _UNSUPPORTED_PHRASES)
    # 按短语长度降序；同长度保持声明顺序（稳定）。
    return sorted(entries, key=lambda item: -len(item[0]))


_ENTRIES: list[tuple[str, str, str]] = _build_entries()


def resolve_indicator_semantics(user_query: str) -> IndicatorSemanticResult:
    """确定性解析中文问题中的规范指标语义（纯函数，零 IO，零 LLM）。"""
    query = user_query or ""
    period_hint = (
        "latest_quarter" if any(word in query for word in _LATEST_QUARTER_WORDS) else ""
    )
    for phrase, canonical, confidence in _ENTRIES:
        if phrase not in query:
            continue
        matched = [phrase]
        if not canonical:
            # unsupported 精确短语命中（第 5 层，最具体语义优先）
            return IndicatorSemanticResult(
                matched_texts=matched,
                confidence=confidence,
                executable=False,
                reason="unsupported",
                period_hint=period_hint,
            )
        mom = any(word in query for word in _MOM_WORDS)
        growth = any(word in query for word in _GROWTH_WORDS)
        if canonical in _BASE_INDICATORS:
            # 基础指标 + 修饰后缀（与 indicator_query_service 能力对齐）
            if mom:
                return IndicatorSemanticResult(
                    metric_ids=[f"{canonical}_mom"],
                    operation="mom",
                    matched_texts=matched,
                    confidence=confidence,
                    executable=True,
                    period_hint=period_hint,
                )
            if growth:
                return IndicatorSemanticResult(
                    metric_ids=[f"{canonical}_growth"],
                    operation="yoy_growth",
                    matched_texts=matched,
                    confidence=confidence,
                    executable=True,
                    period_hint=period_hint,
                )
            return IndicatorSemanticResult(
                metric_ids=[canonical],
                matched_texts=matched,
                confidence=confidence,
                executable=True,
                period_hint=period_hint,
            )
        # registry 指标（r4/r5 等）：批次 A 无同比/环比查询能力，
        # 带修饰时不得伪造同比语义（诚实降级）。
        if mom or growth:
            return IndicatorSemanticResult(
                metric_ids=[canonical],
                matched_texts=matched,
                confidence=confidence,
                executable=False,
                reason="modifier_unsupported",
                period_hint=period_hint,
            )
        return IndicatorSemanticResult(
            metric_ids=[canonical],
            matched_texts=matched,
            confidence=confidence,
            executable=True,
            period_hint=period_hint,
        )
    return IndicatorSemanticResult(
        confidence="none", reason="no_match", period_hint=period_hint
    )
