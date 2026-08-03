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

from app.agents.state import AgentState, MemoryContext

logger = logging.getLogger(__name__)

# ── 指代消解关键词表 ────────────────────────────────────────
# 明确指代（直接指向上一轮主体）
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
    """检测 query 中是否包含指代词。"""
    if not query:
        return False
    all_keywords = _EXPLICIT_ANAPHORA + _VAGUE_ANAPHORA + _BACK_REFERENCE
    return any(kw in query for kw in all_keywords)


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
    for kw in _EXPLICIT_ANAPHORA:
        if kw in query:
            return "explicit"
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
) -> MemoryContext:
    """Lite Profile 确定性指代消解。

    1. 检测是否含指代词
    2. 从 messages 历史提取最近的公司实体
    3. 从 messages 历史提取最近提及的财务指标
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

    # 指代消解：如果含指代词且历史有公司，取最近的公司
    resolved_entity_name: str | None = None
    if is_anaphora and previous_companies:
        resolved_entity_name = previous_companies[0]  # 最近提到的公司
    elif is_anaphora and current_company_name:
        # 历史消息中没有公司但当前 state 有 company
        resolved_entity_name = current_company_name

    # 提取历史指标
    referenced_indicators: list[str] = []
    if messages:
        for msg in reversed(messages[:20]):  # 最近 20 条消息
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

    return MemoryContext(
        resolved_entity_name=resolved_entity_name,
        is_anaphora=is_anaphora,
        previous_companies=previous_companies[:10],
        referenced_indicators=referenced_indicators,
    )


def _build_context_message(context: MemoryContext) -> str | None:
    """根据 MemoryContext 生成上下文注入消息。

    用于注入到 messages 列表，帮助下游节点（resolve_entity / generate_answer）
    理解多轮语境。
    """
    parts: list[str] = []

    if context.resolved_entity_name:
        parts.append(f"当前分析对象: {context.resolved_entity_name}")

    if context.previous_companies and not context.resolved_entity_name:
        parts.append(f"历史涉及公司: {', '.join(context.previous_companies[:5])}")

    if context.referenced_indicators:
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

    context = _resolve_lite(user_query, messages, current_company_name)

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
