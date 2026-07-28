"""公告 fcode 分类共享模块。

供 announcement_sentiment.py 和 events.py 共用，避免两份映射漂移。

基于 data/3/ditct.txt 29 个真实 10 位 Wind fcode。
"""

from __future__ import annotations

SENTIMENT_MAP_VERSION = "3.0.0"

# 基于赛题真实 fcode 字典（29 个 10 位编码）
# negative: 质押冻结、特别处理、终止上市、风险提示、法律纠纷、违纪违规
# positive: 回购股权
# neutral:  其余常规公告

FCODE_SENTIMENT_MAP: dict[str, str] = {
    "5107000000": "neutral",   # 利润分配
    "5203000000": "negative",  # 质押冻结
    "5219000000": "positive",  # 回购股权
    "5230000000": "neutral",   # 权益变动
    "5404000000": "neutral",   # 补充更正
    "5406000000": "neutral",   # 业绩预告
    "5502010000": "negative",  # 特别处理
    "5502040000": "negative",  # 终止上市
    "5506010000": "neutral",   # 股东大会
    "5506040000": "negative",  # 风险提示
    "5506050000": "neutral",   # 重大合同
    "5506100000": "neutral",   # 澄清公告
    "5506140000": "neutral",   # 停牌提示
    "5506160000": "neutral",   # 中介公告
    "5506170000": "negative",  # 法律纠纷
    "5506180000": "neutral",   # 公司资料变更
    "5506190000": "neutral",   # 个股其他公告
    "5506200000": "neutral",   # 其他补充更正
    "5506220000": "neutral",   # 员工持股
    "5507040000": "neutral",   # 关联交易
    "5507060000": "negative",  # 违纪违规
    "5507200000": "neutral",   # 股份增减持
    "5507210000": "neutral",   # 资金投向
    "5507220000": "neutral",   # 资产重组
    "5507230000": "neutral",   # 收购兼并
    "5507240000": "neutral",   # 借贷担保
    "5507260000": "neutral",   # 政策影响
    "5507270000": "neutral",   # 人事变动
    "5508000000": "neutral",   # 函件
}

_FCODE_CATEGORY_LABELS: dict[str, str] = {
    "5107000000": "利润分配",
    "5203000000": "质押冻结",
    "5219000000": "回购股权",
    "5230000000": "权益变动",
    "5404000000": "补充更正",
    "5406000000": "业绩预告",
    "5502010000": "特别处理",
    "5502040000": "终止上市",
    "5506010000": "股东大会",
    "5506040000": "风险提示",
    "5506050000": "重大合同",
    "5506100000": "澄清公告",
    "5506140000": "停牌提示",
    "5506160000": "中介公告",
    "5506170000": "法律纠纷",
    "5506180000": "公司资料变更",
    "5506190000": "个股其他",
    "5506200000": "其他补充更正",
    "5506220000": "员工持股",
    "5507040000": "关联交易",
    "5507060000": "违纪违规",
    "5507200000": "增减持",
    "5507210000": "资金投向",
    "5507220000": "资产重组",
    "5507230000": "收购兼并",
    "5507240000": "借贷担保",
    "5507260000": "政策影响",
    "5507270000": "人事变动",
    "5508000000": "函件",
}


def fcode_category_label(fcode: str) -> str:
    """fcode → 简短中文类别标签。"""
    return _FCODE_CATEGORY_LABELS.get(fcode, f"未知(fcode_{fcode})")


def classify_sentiment(fcodes_raw: str) -> tuple[str, str, float]:
    """根据 fcode 字符串判定情绪。

    多 fcode 用 '|' 分隔时按负面优先。
    返回 (label, method, confidence)。

    优先级：negative > unknown > positive > neutral
    """
    import pandas as pd

    if pd.isna(fcodes_raw) or not str(fcodes_raw).strip():
        return ("unknown", "no_fcode", 0.3)

    codes = [c.strip() for c in str(fcodes_raw).split("|") if c.strip()]
    if not codes:
        return ("unknown", "no_fcode", 0.3)

    labels: list[str] = []
    unknown_count = 0

    for c in codes:
        label = FCODE_SENTIMENT_MAP.get(c)
        if label is not None:
            labels.append(label)
        else:
            labels.append("unknown")
            unknown_count += 1

    if "negative" in labels:
        return ("negative", "fcode_map", 0.9)
    if unknown_count > 0:
        return ("unknown", "unknown_fcode", 0.3)
    if "positive" in labels:
        return ("positive", "fcode_map", 0.8)
    return ("neutral", "fcode_map", 0.8)
