"""GenerateAnswer — V12 §7.2. 生成最终回答。

V12 §2.6 四层回答结构：
  ① 一句话结论 → ② 三类核心信号摘要 → ③ 证据图表（由
     FinalResponse.claims/evidence 承载，不重复进文本）
     → ④ 贴合当前结论的追问建议。

注意：本节点在 validate_evidence 之前执行，verification_status
尚未生成，不得统计"已核实/部分核实"数量。
"""

from app.agents.state import AgentState, FinalResponse

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


def _build_signal_summary(claims: list) -> str:
    """三类核心信号摘要（V12 §2.6 第二层）。"""
    financial = [c for c in claims if c.claim_type == "financial"]
    equity = [c for c in claims if c.claim_type == "equity"]
    event = [c for c in claims if c.claim_type == "event"]

    parts: list[str] = []
    if financial:
        rule_ids = sorted({c.rule_id for c in financial if c.rule_id})
        rules = "、".join(rule_ids) or "多条规则"
        parts.append(f"财务维度检测到 {len(financial)} 项规则信号（{rules}）")
    if equity:
        parts.append(f"股权维度发现 {len(equity)} 条控制链")
    if event:
        parts.append(f"事件维度存在 {len(event)} 项信号")
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


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])

    if company is None:
        return {
            "final_response": FinalResponse(
                answer="未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。",
                risk_level="unknown",
                claims=[],
                evidence=[],
            )
        }

    # ① 一句话结论
    risk_count = sum(1 for c in claims if c.severity in _RISK_SEVERITIES)
    if risk_count:
        conclusion = (
            f"{company.sec_name}（{company.wind_code}）综合分析完成，"
            f"共检测到 {risk_count} 项风险信号。"
        )
    else:
        conclusion = (
            f"{company.sec_name}（{company.wind_code}）综合分析完成，"
            "未发现明显异常信号。"
        )

    # ② 三类核心信号摘要
    summary = _build_signal_summary(claims)

    answer = conclusion + (summary + "。" if summary else "")

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level=_highest_severity(claims) if claims else "unknown",
            claims=claims,
            evidence=evidence,
            follow_ups=_build_follow_ups(state),
        )
    }
