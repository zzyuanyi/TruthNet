"""_answer_common — generate_answer 拆分模块（重构生成，函数体与原文件逐字节一致）。"""

from __future__ import annotations

import logging
from app.agents.delta_sink import get_sink
from app.agents.state import AgentState
import re

logger = logging.getLogger(__name__)

CHAT_RISK_DISCLAIMER = (
    "【重要说明】规则信号不等同于造假事实认定，需结合审计和监管文件核验，"
    "不构成投资建议。"
)

_CAPABILITY_KW = (
    "你是谁",
    "你是什么",
    "能做什么",
    "会做什么",
    "有什么用",
    "怎么用",
    "介绍一下",
    "能帮我做什么",
    "有什么功能",
    "怎么开始",
    "如何开始",
)

_CONSOLIDATED_SCOPE_KW = ("合并口径", "合并报表")

_CONTEXT_REQUEST_KW = ("它", "该公司", "这家公司", "继续", "再看", "刚才", "前面")

_EXCHANGE_LABELS = {
    "XSHG": "上海证券交易所",
    "XSHE": "深圳证券交易所",
    "XBEI": "北京证券交易所",
}

_FACT_KEYS: dict[str, tuple[str, str, str]] = {
    "industry": ("所属行业", "industry", "industry_l1"),
    "subsidiary": ("旗下公司", "subsidiary", "subsidiary"),
    "project": ("项目事实", "project", "project"),
    "exchange": ("上市交易所", "exchange", "exchange_code"),
    "listing_date": ("上市日期", "listing_date", "listing_date"),
    "listing_status": ("上市状态", "listing_status", "listing_status"),
    "comp_type": ("企业类型", "comp_type", "comp_type_code"),
    "business": ("主营业务", "business", "business"),
    "total_shares": ("总股本", "total_shares", "total_shares"),
    "executive_compensation": (
        "高管薪酬",
        "executive_compensation",
        "executive_compensation",
    ),
    "ipo_price": ("首发价格", "ipo_price", "ipo_price"),
}

_FAREWELL_KW = ("再见", "拜拜", "回头见")

_FRAUD_KEYWORDS = ("造假", "舞弊", "欺诈")

_IMPACT_DIRECTION_LABELS: dict[str, str] = {
    "positive": "利好",
    "negative": "利空",
    "neutral": "中性",
}

_IMPACT_SEVERITY_LABELS: dict[str, str] = {
    "low": "低",
    "medium": "中",
    "high": "高",
}

_IMPACT_TYPE_LABELS: dict[str, str] = {
    "equity_structure": "股权结构",
    "operation": "经营",
    "financing": "融资",
    "market": "市场",
}

_METRIC_LABELS: dict[str, str] = {
    "acct_rcv_growth": "应收账款增速",
    "oper_rev_growth": "营业收入增速",
    "oper_rev_yoy": "营业收入同比",
    "gap": "增速差距",
    "growth_gap": "增速差距",
    "cf_to_profit_ratio": "现金流/利润比",
    "consec_neg_cf": "连续负现金流季度",
    "inventory_yoy": "存货同比增速",
    "inventory_turnover_days": "存货周转天数",
    "oth_rcv_to_assets": "其他应收款占总资产",
    "oth_rcv_yoy": "其他应收款同比",
    "oth_rcv_to_acct_rcv": "其他应收款/应收账款",
    "oth_rcv_large": "存在大额其他应收款",
    "net_profit_yoy": "净利润同比",
    "revenue_divergence": "营收增速差",
}

_METRIC_UNITS: dict[str, str] = {
    "percent": "%",
    "percentage_point": "pp",
    "quarters": "个季度",
    "days": "天",
    "ratio": "",
}

_MODULE_LABELS = {
    "finance": "财务",
    "equity": "股权",
    "events": "舆情事件",
    "risk": "综合风险",
}

_MODULE_STATE_LABELS = {
    "failed": "失败",
    "partial": "部分完成",
    "skipped": "跳过",
}

_R7_FOLLOW_UP_FULL = "查看扣非净利润与归母净利润对比"

_R7_FOLLOW_UP_SIMPLIFIED = "查看净利润、营收与经营现金流增速对比"

_RISK_SEVERITIES: frozenset[str] = frozenset({"red", "orange", "yellow"})

_RULE_FOLLOW_UP: dict[str, str] = {
    "R1": "查看应收账款近 8 季度趋势",
    "R2": "查看经营现金流与净利润对比",
    "R3": "查看存贷双高明细",
    "R4": "查看存货周转趋势",
    "R6": "查看其他应收款明细",
}

_SEVERITY_LABELS: dict[str, str] = {
    "red": "高风险",
    "orange": "中风险",
    "yellow": "关注",
    "green": "低风险",
}

_SEVERITY_ORDER: tuple[str, ...] = ("red", "orange", "yellow", "blue", "green")

_THANKS_KW = ("谢谢", "感谢", "辛苦了")

_UNSUPPORTED_MARKET_CUES = (
    "买入",
    "买",
    "涨跌",
    "涨幅",
    "上涨",
    "下跌",
    "成交量",
    "市值",
    "资金流",
    "走势",
    "预测",
    "换手率",
    "股息率",
    "最高价",
    "最低价",
    "港股通",
)

_WEB_SEARCHABLE_FACTS: frozenset[str] = frozenset(
    {"listing_date", "executive_compensation", "ipo_price"}
)


def _is_unsupported_market_query(query: str) -> bool:
    return any(cue in (query or "") for cue in _UNSUPPORTED_MARKET_CUES)


def _highest_severity(claims: list) -> str:
    """取 claims 最高严重度（red > orange > ... > green）。"""
    for sev in _SEVERITY_ORDER:
        if any(c.severity == sev for c in claims):
            return sev
    return "green"


def _leaf_risk_claims(claims: list) -> list:
    """叶子风险 Claim（#8 统一口径）。

    排除：
      - claim_type == "risk"（综合风险汇总 Claim，只用于总等级说明）；
      - severity in (green, unknown)（绿色控制链是事实展示，不计风险）。
    只统计 financial/event/cross_validation/非 green equity 等叶子信号。
    """
    return [
        c for c in claims if c.claim_type != "risk" and c.severity in _RISK_SEVERITIES
    ]


def _merge_unique(items: list, key) -> list:
    """按 key 去重保序（Claim 按 claim_id、Evidence 按 evidence_id）。"""
    seen: set[str] = set()
    out: list = []
    for it in items:
        k = key(it)
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        out.append(it)
    return out


def _dedup(items: list[str]) -> list[str]:
    """去重保持顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _format_number_value(val, unit: str) -> str:
    """数值按单位格式化（#12）：百分比/百分点 ≤1 位小数，禁止长浮点。

    - percent / percentage_point → 1 位小数（如 149.6%、166.2pp）
    - 其他数值 → 去掉尾零的紧凑格式（如 3、3.5、0.25）
    """
    if isinstance(val, bool):
        return "是" if val else "否"
    if isinstance(val, (int, float)):
        f = float(val)
        if unit in ("percent", "percentage_point"):
            return f"{f:.1f}"
        return f"{f:g}"
    return str(val)


def _format_metrics(current: dict) -> str:
    """规则指标数值展开："应收账款增速 149.6%、营业收入增速 -16.6%…" """
    parts: list[str] = []
    for k, v in (current or {}).items():
        if not isinstance(v, dict):
            continue
        label = _METRIC_LABELS.get(k, k)
        val = v.get("value")
        unit = _METRIC_UNITS.get(str(v.get("unit", "")), "")
        if val is None:
            continue  # 空值指标不输出（避免 "None%"）
        if isinstance(val, bool):
            parts.append(f"{label}：{_format_number_value(val, unit)}")
        else:
            parts.append(f"{label} {_format_number_value(val, unit)}{unit}")
    return "、".join(parts)


def _format_indicator_value(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:.2f}%"
    if unit == "ratio":
        return f"{value * 100:.2f}%"
    if unit == "days":
        return f"{value:.2f}天"
    absolute = abs(value)
    if absolute >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿元"
    if absolute >= 10_000:
        return f"{value / 10_000:.2f}万元"
    return f"{value:,.2f}元"


def _format_growth(growth: float) -> str:
    """同比增速正负文案（2026-08-12 三轮审查修订）。

    -8.50 → "同比下降 8.50%"；+8.50 → "同比增长 8.50%"；≈0 → "同比持平"。
    """
    if abs(growth) < 0.005:
        return "同比持平"
    if growth > 0:
        return f"同比增长 {growth:.2f}%"
    return f"同比下降 {abs(growth):.2f}%"


def _module_state(status) -> str:
    if isinstance(status, dict):
        return str(status.get("state") or "")
    return str(getattr(status, "state", "") or "")


def _stream_turn_id(state: AgentState) -> str | None:
    """取当前 turn_id（用于 DeltaSink 查找）；无 runtime 返回 None."""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    return getattr(runtime, "turn_id", "") or None


def _emit_segment(state: AgentState, text: str) -> None:
    """构造四层回答时实时 push 真实分段到 DeltaSink（仅流式模式生效）."""
    if not text:
        return
    turn_id = _stream_turn_id(state)
    if not turn_id:
        return
    sink = get_sink(turn_id)
    if sink is not None:
        sink.push(text)


def _clip_evidence_value(value: str | None, limit: int = 220) -> str | None:
    """证据值入库前做短截断，避免落库字段过长。"""
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _finance_executed(state: AgentState) -> tuple[bool, object]:
    """返回 (finance 模块是否实际执行, results.finance 对象).

    finance 模块执行 = results.finance 非空且包含规则状态。
    纯股权 / 纯事件查询（finance 未执行）不强制插入母公司口径说明。
    """
    results = state.get("results")
    if not results or results.finance is None:
        return False, None
    if not results.finance.rule_statuses:
        return False, results.finance
    return True, results.finance


def _finance_all_blocked(finance) -> bool:
    """财务规则全部因数据不足/不适用而无有效信号（不能得出"无风险"）。"""
    if not finance or not finance.rule_statuses:
        return False
    return all(
        s in ("insufficient_data", "not_applicable")
        for s in finance.rule_statuses.values()
    )


def _extract_markers(text: str) -> set[str]:
    """提取【】段落标记集合（如【预警点】），用于润色保留校验。"""
    return set(re.findall(r"【[^】]+】", text))


def _extract_key_facts(text: str) -> str:
    """提取关键事实指纹（规则 ID + 数值 + 单位 + 风险等级，去重）。

    用于润色前后一致性校验：LLM 不得改变这些内容。
    归一化：LLM 可能把 "166.2pp" 改写为 "166.2个百分点"（语义等价），
    先归一为 "166.2pp" 再提取，避免误判"数值被改"。
    去重：同一规则 ID 在摘要与明细中可能多次出现，润色合并后
    次数减少不视为改变——只要规则/数值/等级集合一致即可。
    """
    norm = re.sub(r"(-?\d+(?:\.\d+)?)\s*个百分点", r"\1pp", text)
    facts: list[str] = []
    facts.extend(re.findall(r"R\d+", norm))  # 规则 ID
    facts.extend(re.findall(r"-?\d+(?:\.\d+)?\s*%", norm))  # 百分比（容忍空格）
    facts.extend(re.findall(r"-?\d+(?:\.\d+)?\s*pp", norm))  # 百分点
    facts.extend(re.findall(r"\d+\s*个季度", norm))  # 季度数
    facts.extend(re.findall(r"\d+(?:\.\d+)?\s*天", norm))  # 天数
    facts.extend(re.findall(r"高风险|中风险|关注|低风险", norm))  # 风险等级
    return "|".join(_dedup(facts))
