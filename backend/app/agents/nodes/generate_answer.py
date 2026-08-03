"""GenerateAnswer — V12 §7.2. 生成最终回答。

V12 §2.6 四层回答结构：
  ① 一句话结论 → ② 三类核心信号摘要 → ③ 证据图表（由
     FinalResponse.claims/evidence 承载，不重复进文本）
     → ④ 贴合当前结论的追问建议。

注意：本节点在 validate_evidence 之前执行，verification_status
尚未生成，不得统计"已核实/部分核实"数量。
"""

from app.agents.state import AgentState, FinalResponse
from app.domain.finance.parent_scope import (
    NO_SIGNAL_IN_SCOPE,
    RISK_SIGNAL_IN_SCOPE,
)

# 已触发规则 → 对应指标追问（V12 §2.6 示例："查看应收账款近 8 季度趋势"）
_RULE_FOLLOW_UP: dict[str, str] = {
    "R1": "查看应收账款近 8 季度趋势",
    "R2": "查看经营现金流与净利润对比",
    "R3": "查看存贷双高明细",
    "R4": "查看存货周转趋势",
    "R6": "查看其他应收款明细",
    "R7": "查看扣非净利润与归母净利润对比",
}

# 严重度排序（V12 §2.4：red > orange > yellow > blue > green）
_SEVERITY_ORDER: tuple[str, ...] = ("red", "orange", "yellow", "blue", "green")

# 风险信号等级
_RISK_SEVERITIES: frozenset[str] = frozenset({"red", "orange", "yellow"})


def _highest_severity(claims: list) -> str:
    """取 claims 最高严重度（red > orange > ... > green）。"""
    for sev in _SEVERITY_ORDER:
        if any(c.severity == sev for c in claims):
            return sev
    return "green"


def _build_signal_summary(claims: list, results=None, risk_output=None) -> str:
    """多类核心信号摘要（V12 §2.6 第二层，B5 扩展评级/交叉验证）。"""
    financial = [c for c in claims if c.claim_type == "financial"]
    equity = [c for c in claims if c.claim_type == "equity"]
    event = [c for c in claims if c.claim_type == "event"]
    cross = [c for c in claims if c.claim_type == "cross_validation"]

    parts: list[str] = []
    if financial:
        rule_ids = sorted({c.rule_id for c in financial if c.rule_id})
        rules = "、".join(rule_ids) or "多条规则"
        parts.append(f"财务维度检测到 {len(financial)} 项规则信号（{rules}）")
    if equity:
        parts.append(f"股权维度发现 {len(equity)} 条控制链")
    if event:
        parts.append(f"事件维度存在 {len(event)} 项信号")
    if cross:
        parts.append(f"交叉验证发现 {len(cross)} 处模块间不一致")
    # 评级拐点（来自 events 结果）
    if results is not None and results.events is not None:
        rating = getattr(results.events, "rating_changes", []) or []
        if rating:
            downs = sum(1 for r in rating if r.get("direction") == "down")
            if downs:
                parts.append(f"研报评级存在 {downs} 次下调")
    # 综合风险
    if risk_output is not None:
        rl = getattr(risk_output, "risk_level", "")
        if rl in ("red", "orange", "yellow"):
            parts.append(f"综合风险等级：{rl}")
    return "；".join(parts)


def _dedup(items: list[str]) -> list[str]:
    """去重保持顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _build_follow_ups(state: AgentState) -> list[str]:
    """追问建议：已触发规则 + 缺失数据/缺失模块生成（V12 §2.6）。

    行业分位对标追问依赖数据组行业分位产物，Phase C 留 TODO。
    """
    claims = state.get("claims", [])
    results = state.get("results")
    plan = state.get("plan")
    module_status = state.get("module_status", {})

    follow_ups: list[str] = []

    # 已触发规则 → 对应指标追问
    for c in claims:
        if c.rule_id and c.rule_id in _RULE_FOLLOW_UP:
            follow_ups.append(_RULE_FOLLOW_UP[c.rule_id])

    # 股权/事件 claim → 对应追问
    if any(c.claim_type == "equity" for c in claims):
        follow_ups.append("查看实控人控制的其他上市公司")
    if any(c.claim_type == "event" for c in claims):
        follow_ups.append("查看公司事件时间线")

    # 缺失数据维度：规则状态 insufficient_data → 追问对应数据
    if results and results.finance and results.finance.rule_statuses:
        if results.finance.rule_statuses.get("R5") == "insufficient_data":
            follow_ups.append("查看费用明细数据")
    # TODO(Phase C): 行业分位对标追问（依赖数据组行业分位产物）

    # 缺失模块维度：plan 请求但 skipped/failed/partial 的模块 → 追问
    # （partial：部分数据缺失，lite 模式 events 常见）
    requested = plan.requested_modules if plan else []
    for mod in requested:
        ms = module_status.get(mod)
        if ms is not None and getattr(ms, "state", "") in (
            "skipped",
            "failed",
            "partial",
        ):
            if mod == "events":
                follow_ups.append("查看公司事件时间线")
            elif mod == "finance":
                follow_ups.append("查看财务规则详情")

    if not follow_ups:
        follow_ups = ["查看企业画像详情"]

    return _dedup(follow_ups)


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


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    finance_ran, finance = _finance_executed(state)
    finance_blocked = _finance_all_blocked(finance)
    finance_unknown_type = finance_blocked and any(
        "公司类型缺失" in (w or "") for w in (finance.warnings or [])
    )

    if company is None:
        return {
            "final_response": FinalResponse(
                answer="未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。",
                risk_level="unknown",
                claims=[],
                evidence=[],
            )
        }

    # ① 一句话结论（Phase C：Finance 执行时限定母公司报表口径）
    risk_count = sum(1 for c in claims if c.severity in _RISK_SEVERITIES)
    name_code = f"{company.sec_name}（{company.wind_code}）综合分析完成，"
    if risk_count:
        if finance_ran:
            # 口径限定：本分析基于母公司报表及当前数据覆盖
            conclusion = name_code + RISK_SIGNAL_IN_SCOPE.format(n=risk_count)
        else:
            conclusion = name_code + f"共检测到 {risk_count} 项风险信号。"
    else:
        if finance_unknown_type:
            # 公司类型缺失：不得输出"未发现风险"
            conclusion = (
                name_code
                + "公司类型信息缺失，无法执行非金融财务规则，无法确认是否存在财务风险。"
            )
        elif finance_blocked:
            conclusion = (
                name_code
                + "在母公司报表及当前数据覆盖范围内，财务规则因不适用/数据不足"
                "未产出有效信号，未发现可确认的异常信号。"
            )
        elif finance_ran:
            conclusion = name_code + NO_SIGNAL_IN_SCOPE
        else:
            conclusion = name_code + "未发现明显异常信号。"

    # ② 多类核心信号摘要（含评级/交叉验证/综合风险）
    risk_output = state.get("risk_output")
    results = state.get("results")
    summary = _build_signal_summary(claims, results=results, risk_output=risk_output)

    answer = conclusion + (summary + "。" if summary else "")

    # 风险等级：优先使用 risk 节点输出（否则回退 claim 最高严重度）
    risk_level = (
        (getattr(risk_output, "risk_level", "") or _highest_severity(claims))
        if (risk_output is not None or claims)
        else "unknown"
    )

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level=risk_level,
            claims=claims,
            evidence=evidence,
            follow_ups=_build_follow_ups(state),
        )
    }
