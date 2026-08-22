"""Memory — V12 §7.6. 多轮实体提取与指代消解。

从 user_query 和 messages 历史中：
  1. 检测指代词（"它""上次那家""该公司"等）
  2. 从历史消息中提取最近涉及的公司实体
  3. 注入上下文消息供下游 resolve_entity 使用

Phase C 实现：Lite Profile 确定性关键词匹配 + 历史实体回溯。
"""

from __future__ import annotations

import logging
import re

from app.agents.state import AgentState, ExecutedMetricRef, MemoryContext
from app.core.config import settings

logger = logging.getLogger(__name__)


def _history_message_limit() -> int:
    """历史消息窗口上限（8/19 修复：对齐 MEMORY_RECENT_TURNS）。

    历史消息由 load_context 按轮成对注入（user + assistant 各 1 条），
    因此完整 N 轮 = N*2 条消息。旧实现硬编码 `messages[-20:]` 只覆盖
    最近 10 轮，与 20 轮回读窗口不一致——>20 轮会话中第 11~20 轮的
    指标文本提取会漏掉。改为读取配置，与回读窗口严格对齐。
    """
    return max(int(settings.MEMORY_RECENT_TURNS) * 2, 0)


# ── 指代消解关键词表 ────────────────────────────────────────
# 明确指代（直接指向上一轮主体）
# 8/19 审查修复：单字"它/他/她/其"用子串匹配会误伤"其他/其它/其余"
# 等财务术语（如"其他应收款占比如何"被判为指代），改用正则：
#   - "它/他/她"：前一个字符不是"其"（排除"其他/其它"）；
#   - "其"：后一个字符不是"他/它/余/次/中"（排除"其他/其它/其余/其次/其中"）。
_EXPLICIT_ANAPHORA_RE = re.compile(r"(?<!其)[它他她]|其(?![他它余次中])")

# 明确指代（保留列表供文档/调试；判定走 _EXPLICIT_ANAPHORA_RE）
_EXPLICIT_ANAPHORA: list[str] = [
    "它",
    "他",
    "她",
    "其",
]

# 模糊指代（上下文中的指代）
_VAGUE_ANAPHORA: list[str] = [
    "这家",
    "那家",
    "该公司",
    "这家公司",
    "那家公司",
    "这个",
    "那个",
]

# 追问指代（回指历史话题）
_BACK_REFERENCE: list[str] = [
    "上次",
    "刚才",
    "之前",
    "上面",
    "前面",
    "上回",
    "上一次",
    "上一轮",
    "刚刚",
    "刚刚那家",
    "前一轮",
]

# ── 公司名提取 ──────────────────────────────────────────────

# 常见上市公司简称模式（用于从消息中提取实体）
_COMPANY_NAME_RE = re.compile(
    r"(?:康美药业|贵州茅台|五粮液|宁德时代|海康威视|"
    r"平安银行|招商银行|万科|格力电器|美的集团|"
    r"比亚迪|中兴通讯|京东方|立讯精密|隆基绿能|阳光电源|"
    r"恒瑞医药|药明康德|迈瑞医疗|爱尔眼科|泰格医药|"
    r"中国平安|中信证券|东方财富|同花顺|"
    r"伊利股份|海天味业|金龙鱼|牧原股份|温氏股份|"
    r"[一-龥]{2,6}(?:控股|集团|股份|实业|科技|医药|能源|汽车|电子|通信|银行|证券|保险|地产|建筑|钢铁|化工|农业|食品|饮料|服装|传媒|旅游|航空|物流|环保|电力|水务|燃气|家居|家纺|建材|电气|机械|家电|家具|装备|材料|光电|软件|生物|乳业|珠宝|贸易|百货|电缆|重工|精密|国际|发展|建设)(?:股份)?)"
)


def _contains_anaphora(query: str | None) -> bool:
    """检测 query 中是否包含指代词。

    8/19 修复：单字指代走正则（排除"其他/其它/其余"等组合误伤），
    "其他应收款占比如何"不再误判为指代，而"它还有其他风险吗"
    （"它"独立指代 + "其他"是财务词）仍正确判 True。
    """
    if not query:
        return False
    all_keywords = _VAGUE_ANAPHORA + _BACK_REFERENCE
    if any(kw in query for kw in all_keywords):
        return True
    if _EXPLICIT_ANAPHORA_RE.search(query):
        return True
    # 8/22 后测集 row 703：无公司名的追问句式（"分别是哪几片研报"、
    # "都有哪些"、"具体是哪几篇"）回指上一轮主体——仅当 query 不含
    # 公司名且不含"介绍/分析/看下"等新请求动词时生效，避免
    # "分别介绍康美和茅台"（新请求，含明确对象）被误判指代。
    if (
        not _extract_companies_from_text(query)
        and not any(
            kw in query for kw in ("介绍", "分析", "看下", "看看", "说明", "讲")
        )
        and any(
            kw in query
            for kw in ("分别", "哪几", "几篇", "几片", "哪几篇", "哪几片", "具体是哪些")
        )
    ):
        return True
    return False


def _extract_anaphora_type(query: str | None) -> str:
    """判断指代类型。优先级：back_reference > vague > explicit"""
    if not query:
        return "none"
    for kw in _BACK_REFERENCE:
        if kw in query:
            return "back_reference"
    for kw in _VAGUE_ANAPHORA:
        if kw in query:
            return "vague"
    if _EXPLICIT_ANAPHORA_RE.search(query):
        return "explicit"
    # 8/22 row 703：无公司名追问句式归 back_reference（回指上一轮）
    if (
        not _extract_companies_from_text(query)
        and not any(
            kw in query for kw in ("介绍", "分析", "看下", "看看", "说明", "讲")
        )
        and any(
            kw in query
            for kw in ("分别", "哪几", "几篇", "几片", "哪几篇", "哪几片", "具体是哪些")
        )
    ):
        return "back_reference"
    return "none"


def _extract_companies_from_text(text: str) -> list[str]:
    """从文本中提取公司名称（去重保持顺序）。"""
    matches = _COMPANY_NAME_RE.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _extract_indicators_from_text(text: str) -> list[str]:
    """从文本中提取财务指标关键词。"""
    indicators_kw = [
        "营收",
        "收入",
        "利润",
        "净利润",
        "扣非",
        "现金流",
        "应收",
        "应付",
        "存货",
        "负债",
        "资产",
        "权益",
        "毛利率",
        "净利率",
        "ROE",
        "ROA",
        "资产负债率",
        "经营现金流",
        "自由现金流",
        "货币资金",
        "商誉",
        "营业成本",
        "销售费用",
        "管理费用",
        "财务费用",
    ]
    found: list[str] = []
    text_lower = text
    for kw in indicators_kw:
        if kw in text_lower and kw not in found:
            found.append(kw)
    return found


def _resolve_lite(
    user_query: str,
    messages: list,
    current_company_name: str | None,
    recent_company_codes: list[str] | None = None,
    summary: dict | None = None,
    recent_executed_metrics: list[dict] | None = None,
) -> MemoryContext:
    """Lite Profile 确定性指代消解。

    1. 检测是否含指代词
    2. 从 messages 历史提取最近的公司实体（文本）
    3. 从近期轮次 company_code / 远期摘要 last_company_code 恢复（代码）
    4. 从 messages 历史提取最近提及的财务指标
    5. v3.3.3 批次 B：结构化历史指标（load_context 注入的最近成功
       executed_metrics）优先，文本关键词仅作旧数据兼容 fallback

    指代优先级：近期明确公司（文本）> 当前 state 公司 > 近期轮次代码
    > 摘要 last_company_code。
    """
    is_anaphora = _contains_anaphora(user_query)
    anaphora_type = _extract_anaphora_type(user_query)

    logger.debug(
        "Memory lite: is_anaphora=%s type=%s company=%s",
        is_anaphora,
        anaphora_type,
        current_company_name,
    )

    # 从消息历史中提取公司名（最近优先）
    previous_companies: list[str] = []
    if messages:
        for msg in reversed(messages):
            if hasattr(msg, "content"):
                text = str(getattr(msg, "content", ""))
            elif isinstance(msg, dict):
                text = str(msg.get("content", ""))
            else:
                text = str(msg)
            previous_companies.extend(_extract_companies_from_text(text))

    # 去重保持最近优先
    seen: set[str] = set()
    unique_companies: list[str] = []
    for c in previous_companies:
        if c not in seen:
            seen.add(c)
            unique_companies.append(c)
    previous_companies = unique_companies

    # 近期轮次代码（最近优先，load_context 注入）与摘要兜底代码
    prev_codes: list[str] = list(recent_company_codes or [])
    summary_code = ""
    if summary and isinstance(summary, dict):
        summary_code = str(summary.get("last_company_code") or "").strip()

    # 指代消解优先级：近期明确公司（文本）> 当前 state 公司 >
    # 近期轮次代码 > 摘要 last_company_code
    resolved_entity_name: str | None = None
    resolved_company_code: str | None = None
    if is_anaphora and previous_companies:
        resolved_entity_name = previous_companies[0]  # 最近提到的公司
    elif is_anaphora and current_company_name:
        # 历史消息中没有公司但当前 state 有 company
        resolved_entity_name = current_company_name
    elif is_anaphora and prev_codes:
        resolved_company_code = prev_codes[0]  # 近期轮次的最近公司代码
    elif is_anaphora and summary_code:
        resolved_company_code = summary_code  # 近期窗口外记忆兜底（长程）

    # 提取历史指标（8/19 修复：窗口 = MEMORY_RECENT_TURNS*2 条消息，
    # 覆盖完整回读窗口；旧实现硬编码 20 条 = 10 轮，20 轮时漏掉前 10 轮）
    referenced_indicators: list[str] = []
    if messages:
        for msg in reversed(messages[-_history_message_limit() :]):
            if hasattr(msg, "content"):
                text = str(getattr(msg, "content", ""))
            elif isinstance(msg, dict):
                text = str(msg.get("content", ""))
            else:
                text = str(msg)
            referenced_indicators.extend(_extract_indicators_from_text(text))

    # 去重
    ind_seen: set[str] = set()
    unique_ind: list[str] = []
    for i in referenced_indicators:
        if i not in ind_seen:
            ind_seen.add(i)
            unique_ind.append(i)
    referenced_indicators = unique_ind[:10]

    # v3.3.2-R1 §5.1：结构化当前主体（会话状态，与 is_anaphora 无关）：
    # recent_company_codes[0]（load_context 已按 active_company_code 优先）
    # > 摘要 last_company_code > None
    current_company_code: str | None = None
    if prev_codes:
        current_company_code = prev_codes[0]
    elif summary_code:
        current_company_code = summary_code

    # v3.3.3 批次 B：结构化历史指标（最近成功、canonical ID/period/unit）
    # 优先于文本关键词提取（referenced_indicators 仅旧数据兼容）；
    # 收口批次 B（方案 §3.4）：带 company_code 归属
    executed_metrics: list[ExecutedMetricRef] = []
    for item in recent_executed_metrics or []:
        metric_id = str(item.get("metric_id") or "").strip()
        if not metric_id or item.get("status") != "ok":
            continue
        executed_metrics.append(
            ExecutedMetricRef(
                metric_id=metric_id,
                period=str(item.get("period") or ""),
                unit=str(item.get("unit") or ""),
                status="ok",
                company_code=str(item.get("company_code") or "").strip(),
            )
        )

    return MemoryContext(
        resolved_entity_name=resolved_entity_name,
        resolved_company_code=resolved_company_code,
        is_anaphora=is_anaphora,
        previous_companies=previous_companies[:10],
        previous_company_codes=prev_codes[:10],
        referenced_indicators=referenced_indicators,
        current_company_code=current_company_code,
        recent_executed_metrics=executed_metrics,
    )


def _build_context_message(context: MemoryContext) -> str | None:
    """根据 MemoryContext 生成上下文注入消息。

    用于注入到 messages 列表，帮助下游节点（resolve_entity / generate_answer）
    理解多轮语境。
    """
    parts: list[str] = []

    if context.resolved_entity_name:
        parts.append(f"当前分析对象: {context.resolved_entity_name}")
    elif context.resolved_company_code:
        parts.append(f"当前分析对象代码: {context.resolved_company_code}")

    if context.previous_companies and not context.resolved_entity_name:
        parts.append(f"历史涉及公司: {', '.join(context.previous_companies[:5])}")

    # v3.3.3 批次 B：结构化最近成功指标优先；文本提取仅旧数据 fallback
    if context.recent_executed_metrics:
        labels = [
            f"{m.metric_id}({m.period})"
            for m in context.recent_executed_metrics[:4]
            if m.metric_id
        ]
        if labels:
            parts.append(f"最近成功指标: {', '.join(labels)}")
    elif context.referenced_indicators:
        parts.append(f"关注指标: {', '.join(context.referenced_indicators[:8])}")

    if not parts:
        return None

    return "【对话上下文】" + "；".join(parts) + "。"


def memory_node(state: AgentState) -> dict:
    """记忆节点 — 多轮实体提取与指代消解。

    输入：
      - user_query: 当前问题
      - messages: 历史消息列表
      - company: 当前 state 中的公司（如有）

    输出：
      - memory_context: MemoryContext（指代消解结果）
      - messages: 追加上下文系统消息（如检测到指代）
    """
    user_query = state.get("user_query", "")
    messages = state.get("messages", [])
    company = state.get("company")
    current_company_name = company.sec_name if company else None

    context = _resolve_lite(
        user_query,
        messages,
        current_company_name,
        recent_company_codes=state.get("recent_company_codes") or [],
        summary=state.get("memory_summary"),
        recent_executed_metrics=state.get("recent_executed_metrics") or [],
    )

    logger.info(
        "Memory: is_anaphora=%s resolved=%s prev_companies=%d indicators=%d",
        context.is_anaphora,
        context.resolved_entity_name,
        len(context.previous_companies),
        len(context.referenced_indicators),
    )

    # 注入上下文消息（不含当前 user_query，避免重复）
    result_messages: list = []
    context_text = _build_context_message(context)
    if context_text and context.is_anaphora:
        result_messages.append({"role": "system", "content": context_text})

    return {
        "memory_context": context,
        "messages": result_messages,
    }
