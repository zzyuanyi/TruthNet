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
    ("净资产", "net_assets", "exact"),
    ("净利润", "net_profit", "exact"),
    ("亏损", "net_profit", "exact"),
    ("营收", "operating_revenue", "alias"),
    ("现金流", "operating_cash_flow", "alias"),
    ("负债率", "debt_to_assets", "alias"),
    ("存货", "inventories", "exact"),
]

# 已知但暂不支持的精确短语：与指标短语同表竞争（方案 §4.3 第 5 层），
# 不得先维护一张互相竞争的 unsupported 词表再被短词抢占。
# 8/17 数据1 端到端（T02 等）：每股/股本类指标无数据字段支撑
# （income_statement/balance_sheet 无 eps/share 列），显式 unsupported
# 走诚实短答，不再落"未发现异常信号"综合诊断（答非所问）。
_UNSUPPORTED_PHRASES: tuple[str, ...] = (
    "应收账款周转率",
    "存货周转率",
    "总资产周转率",
    "资产周转率",
    "基本每股收益",
    "每股收益",
    "每股净资产",
    "每股经营现金流",
    "加权净资产收益率",
    "净资产收益率",
    "总资产报酬率",
    "总资产收益率",
    "每股资本公积",
    "净利润现金含量",
    "现金含量",
    "沪深港通持股数量",
    "持股数量",
    "主力净买入额",
    "融资买入额",
    "融资买入量",
    "融券卖出量",
    "融券卖出额",
    "总市值",
    "量价齐升",
    "主力资金",
    "压力位",
    "量价关系",
    "外盘",
    "研发投入占比",
    # 8/22 词表审查：均线/操盘已在 plan_modules._UNSUPPORTED_KW
    # （意图层，先命中走 unsupported），此处删除避免双源维护漂移。
    # 8/22 后测集分析（row 897）：股东户数/散户数量无数据列，
    # 显式 unsupported，避免落入股权穿透答非所问。
    "散户数量",
    "股东户数",
    "股东人数",
)

# 基础报表指标集合：与 indicator_query_service._INDICATORS 的键保持一致。
# 仅能力声明（哪些指标有同比/环比后缀语义），不复制任何公式。
_BASE_INDICATORS: frozenset[str] = frozenset(
    {
        "debt_to_assets",
        "total_assets",
        "total_liabilities",
        "net_assets",
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
    # 确定性 no_match → 受约束 LLM fallback（方案 §5.7 接线，8/17）。
    # 治本机制：任意指标变体（每股收益/股息率/摊薄EPS…）由 LLM 判定，
    # 不在能力集 → 诚实 unsupported，不再穷举词表；LLM 失败/关闭/非
    # 指标问法 → 保持 no_match（走其他意图）。
    llm_result = _indicator_llm_fallback(query)
    if llm_result is not None:
        return llm_result
    return IndicatorSemanticResult(
        confidence="none", reason="no_match", period_hint=period_hint
    )


# ── 方案 §5.7：受约束 LLM 指标 fallback（8/17 接线）────────────


class _IndicatorLLMOutput(BaseModel):
    """LLM 判定：查询是否包含财务指标问法 + 是否属于能力集。"""

    is_indicator: bool = False
    metric_phrase: str = Field(default="", description="识别到的指标短语")
    reason: Literal["unsupported", "mapped", "not_indicator"] = "not_indicator"


# 指标特征触发词（8/17 修订：收窄为"具体指标名特征"——泛化财务问法
# 如"利润如何/业绩如何"不含这些特征 → 不触发 LLM，保持原有
# finance/诊断路由，避免把核心财务问题误判为 unsupported 指标）。
# 仅当查询带明显指标名形态（率/额/收益/周转/每股…）且确定性词表
# 未命中时，才值得用 LLM 判定指标意图。
_LLM_FALLBACK_TRIGGER_WORDS: tuple[str, ...] = (
    "率",
    "额",
    "收益",
    "周转",
    "倍数",
    "占比",
    "天数",
    "账期",
    "每股",
    "EPS",
    "eps",
    "ROE",
    "roe",
    "市盈率",
    "市净率",
    "股息",
    "报酬",
    "回报率",
    "资产负债",
    "净利",
    "毛利",
    "应收",
    "应付",
    "存货",
    "现金流",
    # 8/17 词表优化方向 1：核心科目特征词（触发 LLM 判 unsupported，
    # 非穷举科目）——商誉/减值/摊销 属资产减值类、质押/担保/诉讼 属
    # 表外风险科目，确定性词表未命中时值得用 LLM 判定指标意图；
    # LLM 判 not_indicator 时保持原路由，行为安全。
    "商誉",
    "减值",
    "摊销",
    "质押",
    "担保",
    "诉讼",
)
_LLM_FALLBACK_TIMEOUT_SECONDS = 8.0


def _supported_canonical_ids() -> frozenset[str]:
    """能力集（allowlist）：指标短语表 canonical ∪ 基础报表指标。"""
    ids: set[str] = set(_BASE_INDICATORS)
    for _phrase, canonical, _conf in _METRIC_PHRASES:
        if canonical:
            ids.add(canonical)
    return frozenset(ids)


def _indicator_llm_fallback(
    user_query: str,
) -> IndicatorSemanticResult | None:
    """确定性 no_match 后的指标问法判定（方案 §5.7）。

    Returns:
        unsupported → IndicatorSemanticResult(executable=False, reason="unsupported")
        mapped（变体命中 allowlist）→ 可执行结果
        not_indicator / 未启用 / LLM 失败 → None（保持 no_match）
    """
    from app.core.config import settings

    if settings.ENTITY_SEMANTIC_SELECTION_MODE not in ("suggest", "auto"):
        return None
    if settings.LLM_BACKEND in ("", "mock"):
        return None
    query = user_query or ""
    if not any(word in query for word in _LLM_FALLBACK_TRIGGER_WORDS):
        return None

    supported = _supported_canonical_ids()
    support_lines = "\n".join(f"- {cid}" for cid in sorted(supported))
    system = (
        "你是财报问答系统的指标语义判定器。给定用户问题，判断它是否在询问"
        "某个财务指标（如每股收益、毛利率、资产负债率、周转天数、现金流、"
        "营业收入、净利润等）：\n"
        "1. 是指标问法但**不在下方能力集** → is_indicator=true, "
        "reason=unsupported（如每股收益/股息率/每股净资产/ROE 等）；\n"
        "2. 是指标问法且**属于能力集** → is_indicator=true, "
        "reason=mapped（如'销售毛利率'命中 r5_gross_margin 等）；\n"
        "3. 不是指标问法（寒暄/行情/交易/公司事实/对比无指标）→ "
        "is_indicator=false, reason=not_indicator。\n"
        "能力集（canonical ID）：\n" + support_lines + "\n"
        "输出 JSON 必须严格符合给定 schema。"
    )
    from app.agents.llm_guard import structured_llm

    output = structured_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"用户问题：{query}"},
        ],
        _IndicatorLLMOutput,
        timeout=_LLM_FALLBACK_TIMEOUT_SECONDS,
    )
    if output is None:
        return None
    if not output.is_indicator or output.reason == "not_indicator":
        return None
    if output.reason == "unsupported":
        return IndicatorSemanticResult(
            matched_texts=[output.metric_phrase] if output.metric_phrase else [],
            confidence="llm",
            executable=False,
            reason="unsupported",
        )
    # mapped：需回到 allowlist 判定实际 canonical（LLM 仅确认指标性，
    # canonical 由确定性词表决定，防止 LLM 编造 ID）
    for phrase, canonical, confidence in _ENTRIES:
        if canonical and phrase in query:
            return IndicatorSemanticResult(
                metric_ids=[canonical],
                matched_texts=[phrase],
                confidence=confidence,
                executable=True,
            )
    # LLM 说 mapped 但词表没命中（防御）→ 诚实 unsupported
    return IndicatorSemanticResult(
        matched_texts=[output.metric_phrase] if output.metric_phrase else [],
        confidence="llm",
        executable=False,
        reason="unsupported",
    )
