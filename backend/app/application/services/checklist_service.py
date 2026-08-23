"""核查导航服务 — L2 行动建议（规则→核查动作映射，答辩叙事「核查导航+人机协作」落地）。

8/23 叙事定稿（竞赛管理 docs/records/答辩叙事-核查导航与人机协作-2026-08-23.md）：
系统输出风险点（L0 告警）+ 原因解读（L1）+ 可执行的核查动作（L2），
专业判断留给人——「核查导航员」定位。

约束（结论可落地性分析框架 §六 边界硬性约定）：
- 动作是「常识级核查指引」，不做定性（是否造假）、不做处置建议（买卖/申报/清仓）、
  不做预测（下期是否爆雷）、不做伪精确量化；
- 措辞用「核/核对/关注」，不用「存在造假/应予处置」；
- 纯静态映射 + 确定性渲染，无 LLM——动作由映射表锁定，杜绝编造；
- 未知规则 fail-closed 返回空（不硬凑动作）。

当前动作为技术侧按 RULES_SPEC 语义草拟的常识级版本，
金融侧按框架 §六 复核措辞后可直接替换。
"""

from __future__ import annotations

_RULE_NAMES: dict[str, str] = {
    "R1": "应收–营收背离",
    "R2": "现金流–利润背离",
    "R3": "存贷双高",
    "R4": "存货–营收背离",
    "R5": "毛利率/费用率异常",
    "R6": "其他应收款与关联占用",
    "R7": "盈利质量与非经常性依赖",
}

# 每条规则 3 条常识级核查动作（RULES_SPEC 语义 + 财务报表核查常识）。
RULE_ACTIONS: dict[str, tuple[str, str, str]] = {
    "R1": (
        "核母公司报表应收账款明细：账龄结构、前五大欠款方、是否存在关联方欠款",
        "结合销售回款（收现比）核对收入确认节奏，判断收入是否真实转化为现金",
        "关注后续季度应收/营收比是否延续，跟踪坏账计提与回收情况",
    ),
    "R2": (
        "核经营活动现金流明细：销售商品收到的现金与营业收入匹配度（收现比）",
        "核净利润中非现金项目（折旧摊销、存货变动、应收/应付变动）的贡献",
        "关注后续期现金流是否改善，结合应收账款周转判断利润含金量",
    ),
    "R3": (
        "核货币资金明细：是否存在受限资金/保证金/结构性存款（资金真实性）",
        "核有息负债成本与存款收益是否异常背离、借款用途是否合理",
        "结合大股东/关联方往来款（股权穿透图已标注）核查资金是否被占用",
    ),
    "R4": (
        "核存货明细构成：原材料/在产品/产成品比例，识别积压品类",
        "核存货跌价准备计提是否充分、存货周转天数变化趋势",
        "结合产销数据与下游需求（研报/公告）判断存货积压风险",
    ),
    "R5": (
        "核毛利率波动来源：产品结构、成本、价格变化（结合研报）",
        "核销售/管理费用明细：是否存在异常摊销、关联交易输送",
        "与同行业毛利率对比（行业分位），判断是行业性还是公司特有",
    ),
    "R6": (
        "核其他应收款明细：欠款方名单、账龄、是否关联方（股权穿透图已标注）",
        "核往来款发生额与交易背景：是否存在资金占用/非经营性往来",
        "结合公告/事件簇核查质押、担保等关联风险信号",
    ),
    "R7": (
        "核非经常性损益明细：政府补助、资产处置收益等占净利润比例",
        "核核心利润（收入-成本-三费）与净利润的差距，判断主业盈利质量",
        "关注后续期扣非净利润趋势，判断盈利可持续性",
    ),
}

_SEVERITY_RANK = {"red": 0, "orange": 1, "yellow": 2}


def build_rule_actions(rule_id: str) -> list[str]:
    """单规则核查动作（未知规则 → 空列表，fail-closed 不编造）。"""
    return list(RULE_ACTIONS.get(rule_id, ()))


def pick_checklist_rules(
    triggered: list[tuple[str, str]], limit: int = 3
) -> list[tuple[str, str]]:
    """选择进入核查清单的规则：severity 排序（red>orange>yellow），最多 limit 条。

    triggered 元素为 (rule_id, severity)；同规则重复触发只保留 severity 最高
    的一条（按排序后首次出现即最高）；防止多规则全展开刷屏。
    """
    ranked = sorted(
        (r for r in triggered if r[0] in RULE_ACTIONS),
        key=lambda item: (_SEVERITY_RANK.get(str(item[1]), 9), item[0]),
    )
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for rid, sev in ranked:
        if rid in seen:
            continue
        seen.add(rid)
        deduped.append((rid, sev))
    return deduped[:limit]


def render_checklist_markdown(triggered: list[tuple[str, str]]) -> str:
    """渲染「核查建议」段落（无 LLM，纯映射；无有效触发规则 → 空串）。

    输出形如：
        【核查建议】
        1. R6 其他应收款与关联占用 · 核其他应收款明细：……
        2. R6 其他应收款与关联占用 · 核往来款发生额与交易背景：……
    """
    items: list[str] = []
    for rid, _sev in pick_checklist_rules(triggered):
        name = _RULE_NAMES.get(rid, rid)
        for action in build_rule_actions(rid):
            items.append(f"{rid} {name} · {action}")
    if not items:
        return ""
    return "【核查建议】\n" + "\n".join(
        f"{i}. {t}" for i, t in enumerate(items, start=1)
    )
