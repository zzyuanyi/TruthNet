"""GenerateAnswer — V12 §7.2. 生成最终回答。

V12 §2.6 四层回答结构：
  ① 一句话结论 → ② 三类核心信号摘要 → ③ 证据图表（由
     FinalResponse.claims/evidence 承载，不重复进文本）
     → ④ 贴合当前结论的追问建议。

注意：本节点在 validate_evidence 之前执行，verification_status
尚未生成，不得统计"已核实/部分核实"数量。

Phase D #13（问答润色）：
  - 模板生成 answer 后 → LLM 只做语言润色（流畅段落）
  - 不得改变风险等级、规则状态、规则 ID、数值
  - LLM 失败 / 关键信息被改 → 原样回退模板输出
  - LLM 调用走独立线程 asyncio.run（REST asyncio.to_thread 与 WS
    事件循环线程两条路径均安全），超时 ~3s
"""

import logging
import re

from app.agents.llm_sync import run_llm_chat
from app.agents.state import AgentState, FinalResponse
from app.domain.finance.parent_scope import (
    NO_SIGNAL_IN_SCOPE,
    RISK_SIGNAL_IN_SCOPE,
)

logger = logging.getLogger(__name__)

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


# 指标字段 → 中文标签（展示层映射，规则引擎字段名保持英文）
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
_SEVERITY_LABELS: dict[str, str] = {
    "red": "高风险",
    "orange": "中风险",
    "yellow": "关注",
    "green": "低风险",
}


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
            parts.append(f"{label}：{'是' if val else '否'}")
        else:
            parts.append(f"{label} {val}{unit}")
    return "、".join(parts)


def _build_rule_details(state: AgentState) -> str:
    """财务触发规则明细（规则名称/风险等级/指标数值/解释，V12 §4.3 规则触发清单）。"""
    results = state.get("results")
    if not results or not results.finance or not results.finance.rule_details:
        return ""
    lines: list[str] = []
    for rid in sorted(results.finance.rule_details):
        if results.finance.rule_statuses.get(rid) != "triggered":
            continue
        d = results.finance.rule_details[rid]
        name = d.get("rule_name", "") or rid
        sev = _SEVERITY_LABELS.get(d.get("severity", ""), "")
        metrics = _format_metrics(d.get("current") or {})
        line = f"{rid} {name}（{sev}）"
        if metrics:
            line += f"：{metrics}"
        lines.append(line)
    if not lines:
        return ""
    return "触发规则明细：" + "；".join(lines) + "。"


# ── Phase D #13: LLM 问答润色 ─────────────────────────────


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


def _polish_answer(answer: str) -> str:
    """LLM 润色模板回答为流畅段落；失败或改变关键信息 → 回退模板。"""
    if not answer:
        return answer

    messages = [
        {
            "role": "system",
            "content": (
                "你是资深财报分析师。请将以下分析回答润色为流畅、专业的段落。"
                "铁律：只做语言润色，绝对不得改变任何规则 ID（R1-R7）、"
                "风险等级（高风险/中风险/关注/低风险）、数字及其单位"
                "（如 149.6%、166.2pp、2个季度、20天）、"
                "必须原样保留【预警点】【数据对比】【可能模式】【限制说明】"
                "等段落标记，不得改写或删除；"
                "不得增删或改写任何事实与结论。直接输出润色后的完整回答，"
                "不要任何解释或前缀。"
            ),
        },
        {"role": "user", "content": answer},
    ]

    polished = run_llm_chat(messages)
    if not polished:
        return answer  # LLM 失败/超时 → 回退模板

    # 关键信息一致性校验：润色改变规则 ID/数值/等级 → 回退模板
    if _extract_key_facts(polished) != _extract_key_facts(answer):
        logger.warning("polish: LLM 输出改变关键信息（规则ID/数值/等级），回退模板")
        return answer

    return polished


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
        # Phase D #10: 行业级研报问题（无公司也能检索，如"白酒行业近期研报观点"）
        user_query = state.get("user_query", "")
        try:
            from app.application.services.research_search import (
                is_research_query,
                report_insights_enabled,
                search_research_insights_sync,
            )

            if is_research_query(user_query) and report_insights_enabled():
                insights = search_research_insights_sync(user_query, top_k=3)
                if insights:
                    parts = []
                    for it in insights[:3]:
                        src = it.get("source_title") or "研报"
                        org = it.get("source_org", "")
                        label = f"{org}·{src}" if org else src
                        parts.append(f"{it.get('content', '')[:120]}（来源：{label}）")
                    answer = (
                        "未匹配到具体公司，以下是相关研报观点摘要："
                        + "；".join(parts)
                        + "。如需针对某家公司分析，请提供公司名称或股票代码。"
                    )
                    return {
                        "final_response": FinalResponse(
                            answer=answer,
                            risk_level="unknown",
                            claims=[],
                            evidence=[],
                        )
                    }
        except Exception:  # noqa: BLE001 — 研报检索失败不影响主流程
            logger.warning(
                "generate_answer: 行业研报检索失败，回退提示语", exc_info=True
            )

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
    # ③ 财务触发规则明细（V12 §4.3 规则触发清单）
    rule_details = _build_rule_details(state)

    answer = conclusion + (summary + "。" if summary else "")
    if rule_details:
        answer += rule_details
    # Phase D #12: LLM 财务解读段（finance 节点产出；失败时为空则跳过）
    if results and getattr(results, "finance", None) and results.finance.interpretation:
        answer += results.finance.interpretation
    # Phase D #11: 疑似造假模式段（pattern_match 节点产出；命中时回答含模式名）
    pattern_matches = state.get("pattern_matches", [])
    if pattern_matches:
        answer += (
            "疑似模式："
            + "；".join(
                f"{m.get('pattern_name', m.get('pattern_id', ''))}"
                f"（{m.get('confidence', '')}）"
                for m in pattern_matches
            )
            + "。"
        )

    # Phase D #10: 研报/公告语义检索（问题涉及研报/行业/评级时可选调用）
    user_query = state.get("user_query", "")
    try:
        from app.application.services.research_search import (
            is_research_query,
            report_insights_enabled,
            search_research_insights_sync,
        )

        if is_research_query(user_query) and report_insights_enabled():
            insights = search_research_insights_sync(user_query, top_k=3)
            if insights:
                parts = []
                for it in insights[:3]:
                    src = it.get("source_title") or "研报"
                    org = it.get("source_org", "")
                    label = f"{org}·{src}" if org else src
                    parts.append(f"{it.get('content', '')[:80]}（来源：{label}）")
                answer += "近期研报观点：" + "；".join(parts) + "。"
    except Exception:  # noqa: BLE001 — 检索失败不影响主回答
        logger.warning("generate_answer: 研报检索段失败，跳过", exc_info=True)

    # Phase D #13: LLM 润色（失败/改变关键信息 → 自动回退模板）
    answer = _polish_answer(answer)

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
