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

Phase D #10（真流式）：
  - 构造四层回答时，每完成一个真实分段立即 push 到按 turn_id 注册的
    DeltaSink（app.agents.delta_sink），由 WsTurnRunner 转成 answer.delta。
  - 分段在生成过程中实时产生，绝不在最终答案完成后拆句冒充流式。
  - 无 sink（REST）时行为不变。
"""

import logging
import re
from datetime import datetime, timezone

from app.agents.delta_sink import get_sink
from app.agents.llm_sync import run_llm_chat
from app.agents.state import (
    MAX_MULTI_COMPARISON_PARTICIPANTS,
    AgentState,
    Claim,
    EvidenceRef,
    FinalResponse,
)
from app.core.config import settings
from app.domain.finance.parent_scope import (
    NO_SIGNAL_IN_SCOPE,
    RISK_SIGNAL_IN_SCOPE,
)
from app.domain.finance.statement_type import PARENT_STATEMENT_TYPE
from app.domain.provenance.id_factory import (
    NS_COMPANY_REGISTRY,
    NS_FINANCE,
    NS_REPORT,
    NS_WEB_SEARCH,
    make_claim_id,
    make_evidence_id,
)

logger = logging.getLogger(__name__)

_THANKS_KW = ("谢谢", "感谢", "辛苦了")
_FAREWELL_KW = ("再见", "拜拜", "回头见")
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
_CONTEXT_REQUEST_KW = ("它", "该公司", "这家公司", "继续", "再看", "刚才", "前面")

# 已触发规则 → 对应指标追问（V12 §2.6 示例："查看应收账款近 8 季度趋势"）
# R7 不在静态表：#10 动态生成——仅当扣非字段可用时才推荐扣非对比
_RULE_FOLLOW_UP: dict[str, str] = {
    "R1": "查看应收账款近 8 季度趋势",
    "R2": "查看经营现金流与净利润对比",
    "R3": "查看存贷双高明细",
    "R4": "查看存货周转趋势",
    "R6": "查看其他应收款明细",
}
_R7_FOLLOW_UP_FULL = "查看扣非净利润与归母净利润对比"
_R7_FOLLOW_UP_SIMPLIFIED = "查看净利润、营收与经营现金流增速对比"

# 严重度排序（V12 §2.4：red > orange > yellow > blue > green）
_SEVERITY_ORDER: tuple[str, ...] = ("red", "orange", "yellow", "blue", "green")

# 风险信号等级
_RISK_SEVERITIES: frozenset[str] = frozenset({"red", "orange", "yellow"})

# #9 免责声明：问题含"造假/舞弊"或存在叶子风险时追加
CHAT_RISK_DISCLAIMER = (
    "【重要说明】规则信号不等同于造假事实认定，需结合审计和监管文件核验，"
    "不构成投资建议。"
)

# 造假/舞弊关键词（触发 fraud_diagnosis 模式与免责）
_FRAUD_KEYWORDS = ("造假", "舞弊", "欺诈")


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


def _research_evidence_and_claims(
    insights: list[dict],
    *,
    company_code: str,
    turn_id: str,
    trace_id: str,
) -> tuple[list[EvidenceRef], list[Claim], list[dict]]:
    """研报结果 → 可回查 Evidence + 事实性 research Claim（#4）。

    - Evidence: NS_REPORT + make_evidence_id，source_type="research_report"，
      source_record_id=report_id，field_path="abstract"，period=publish_date；
    - Claim: claim_type="research"、severity=unknown、绑定对应 Evidence，
      limitations 注明"研报观点不代表系统事实结论"；
    - #2：Claim ID 纳入 report_id（同标题不同报告不冲突）；
    - P2-1：无 report_id 的条目不生成（不可回查 → 不落库），
      返回第三个元素 valid_insights——调用方只渲染这些（缺 ID 结果不得进回答）。
    """
    from app.core.config import settings

    evidence: list[EvidenceRef] = []
    claims: list[Claim] = []
    valid_insights: list[dict] = []
    for ordinal, it in enumerate(insights):
        report_id = str(it.get("report_id") or "").strip()
        if not report_id:
            continue
        valid_insights.append(it)
        title = str(it.get("source_title") or "")
        org = str(it.get("source_org") or "")
        content = str(it.get("content") or "")
        period = str(it.get("source_date") or "")[:10]
        evidence_id = make_evidence_id(
            source_namespace=NS_REPORT,
            source_type="research_report",
            source_record_id=report_id,
            field_path="abstract",
            period=period,
            dataset_version=settings.DATASET_VERSION,
            company_code=company_code or None,
        )
        evidence.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="research_report",
                source_record_id=report_id,
                source_table="research_reports",
                field_path="abstract",
                period=period,
                source_title=(title or "")[:120],
                source_uri=it.get("source_uri") or None,
                module="research",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company_code or "",
                dataset_version=settings.DATASET_VERSION,
            )
        )
        label = f"{org}·{title}" if org and title else (title or org or "研报")
        claims.append(
            Claim(
                claim_id=make_claim_id(
                    turn_id=turn_id,
                    company_code=company_code or "",
                    claim_type="research",
                    # P2-2：report_id 进入 Claim ID 输入——同标题不同报告不冲突
                    claim_text=f"研报观点：{label}（report:{report_id}）",
                    rule_version="",
                ),
                text=f"{label}：{content[:120]}",
                claim_type="research",
                severity="unknown",
                evidence_ids=[evidence_id],
                limitations=["研报观点不代表系统事实结论"],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company_code or "",
                module="research",
                generated_at="",
            )
        )
    return evidence, claims, valid_insights


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
        # 输出控制链细节（控制人/路径/持股），不只输出数量——
        # "股权维度发现 X 条控制链"无法回答用户"控制人是谁"。
        # 同路径多条 claim（主链与风险链为同一控制人，如厦门市建潘
        # 43.5%/41.5%）→ 展示只保留最终控制比例最大的一条，
        # 避免回答出现两条几乎相同的控制链。
        _by_path: dict[str, tuple] = {}
        for c in equity:
            # 8.09 四轮审查：兼容新旧 Claim 文案——ownership 链路 Claim 为
            # "股权链穿透/最终持股"，control 链路仍为"控制链穿透/最终控制"
            m = re.search(r"(?:控制链|股权链)穿透：(.+?)[，,]", c.text)
            key = m.group(1) if m else c.text
            pm = re.search(r"(?:最终控制|最终持股) ([\d.]+)%", c.text)
            pct = float(pm.group(1)) if pm else 0.0
            prev = _by_path.get(key)
            if prev is None or pct > prev[1]:
                _by_path[key] = (c, pct)
        details = "；".join(c.text for c, _ in list(_by_path.values())[:2])
        parts.append(f"股权维度：{details}")
    if event:
        details = "；".join(c.text for c in event[:2])
        parts.append(f"事件维度存在 {len(event)} 项信号：{details}")
    if cross:
        parts.append(f"交叉验证发现 {len(cross)} 处模块间不一致")
    # 综合风险
    if risk_output is not None:
        rl = getattr(risk_output, "risk_level", "")
        if rl in ("red", "orange", "yellow"):
            from app.domain.risk.severity import risk_level_label

            parts.append(f"综合风险等级：{risk_level_label(rl)}")
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


def _build_interpretation_segments(state: AgentState, claims: list) -> list[str]:
    """确定性四段解读（#7/#12/#9）：仅消费规则引擎与 pattern_matches，无 LLM 自由生成。

    段落：
      【预警点】触发规则的真实 explanation；
      【数据对比】只格式化 rule_details.current（数值按单位舍入）；
      【可能模式】只消费 pattern_matches（phase/alternative_explanation/regulatory_hint）；
      【限制说明】母公司口径、数据覆盖、缺失字段与模块降级状态；
      【重要说明】问题含"造假/舞弊"或存在叶子风险时追加免责（#9）。
    """
    results = state.get("results")
    finance = results.finance if results else None
    segs: list[str] = []

    # 【预警点】：触发规则的真实 explanation
    triggers: list[str] = []
    if finance and finance.rule_details:
        for rid in sorted(finance.rule_details):
            if finance.rule_statuses.get(rid) != "triggered":
                continue
            expl = str((finance.rule_details[rid] or {}).get("explanation") or "")
            if expl:
                triggers.append(f"{rid}：{expl}")
    if triggers:
        segs.append("【预警点】" + "；".join(triggers) + "。")

    # 【数据对比】：只格式化 rule_details.current
    pairs: list[str] = []
    if finance and finance.rule_details:
        for rid in sorted(finance.rule_details):
            if finance.rule_statuses.get(rid) != "triggered":
                continue
            d = finance.rule_details[rid] or {}
            for k, v in (d.get("current") or {}).items():
                if not isinstance(v, dict):
                    continue
                label = _METRIC_LABELS.get(k, k)
                val = v.get("value")
                unit = _METRIC_UNITS.get(str(v.get("unit", "")), "")
                if val is None:
                    continue
                pairs.append(f"{label} {_format_number_value(val, unit)}{unit}")
    if pairs:
        segs.append("【数据对比】" + "、".join(pairs) + "。")

    # 财务解读场景（有预警点或数据对比）才保证四段完整（P2-5）
    has_content = bool(triggers or pairs)

    # 【可能模式】：只消费 pattern_matches（不新增任何推断）
    pattern_matches = state.get("pattern_matches", [])
    if pattern_matches:
        parts: list[str] = []
        for m in pattern_matches:
            name = m.get("pattern_name") or m.get("pattern_id") or ""
            conf = m.get("confidence") or ""
            phase = m.get("phase") or ""
            alt = m.get("alternative_explanation") or ""
            reg = m.get("regulatory_hint") or ""
            s = f"{name}（{conf}）"
            if phase:
                s += f"，阶段：{phase}"
            if alt:
                s += f"，替代解释：{alt}"
            if reg:
                s += f"，监管提示：{reg}"
            parts.append(s)
        segs.append("【可能模式】" + "；".join(parts) + "。")
    elif has_content:
        # P2-5：无模式命中时输出占位（不得省略导致四段缺失）
        segs.append("【可能模式】当前规则组合未匹配预定义模式，需进一步验证。")

    # 【限制说明】：口径/覆盖/降级状态（去重保序）
    limitations: list[str] = []
    if finance and finance.warnings:
        for w in finance.warnings:
            if w and w not in limitations:
                limitations.append(w)
    for name, ms in (state.get("module_status") or {}).items():
        if getattr(ms, "state", "") in ("partial", "failed"):
            w = f"模块 {name} 状态: {getattr(ms, 'state', '')}"
            if w not in limitations:
                limitations.append(w)
    if limitations:
        segs.append("【限制说明】" + "；".join(limitations) + "。")
    elif has_content:
        # P2-5：限制为空时输出默认口径说明（不得省略）
        segs.append("【限制说明】分析基于母公司报表及当前数据覆盖范围，结果仅供参考。")

    # 【重要说明】免责（#9）：造假/舞弊问题或存在叶子风险时追加
    user_query = state.get("user_query", "")
    if any(kw in user_query for kw in _FRAUD_KEYWORDS) or _leaf_risk_claims(claims):
        segs.append(CHAT_RISK_DISCLAIMER)

    return segs


def _select_answer_mode(
    state: AgentState, claims: list, finance_ran: bool, finance_blocked: bool
) -> str:
    """#11 AnswerMode：按问题意图与状态确定性选择回答模式。

    纯函数判定（关键词/claim 类型/模块状态），同一请求可稳定重放。
    """
    user_query = state.get("user_query", "")
    plan = state.get("plan")
    if plan is not None and plan.requested_modules == ["equity"]:
        return "equity"
    if any(kw in user_query for kw in _FRAUD_KEYWORDS):
        return "fraud_diagnosis"
    if finance_blocked:
        return "insufficient_data"
    ctypes = {c.claim_type for c in claims}
    if not finance_ran and ctypes and ctypes <= {"equity"}:
        return "equity"
    if not finance_ran and ctypes and ctypes <= {"event"}:
        return "events"
    if finance_ran and "financial" in ctypes:
        return "finance"
    return "simple"


def _build_equity_overview(state: AgentState) -> str:
    """从 EquityResult 生成股东/控制链确定性摘要（Phase D #3C）。"""
    results = state.get("results")
    equity = results.equity if results else None
    if equity is None:
        return "股权数据覆盖不足，未取得可展示的股东或控制链记录。"

    parts: list[str] = []
    shareholders = equity.shareholders or []
    if shareholders:
        period = str(shareholders[0].get("report_period") or "")
        period_text = (
            f"{period[:4]}-{period[4:6]}-{period[6:]}" if len(period) == 8 else "最新期"
        )
        items = []
        for item in shareholders[:5]:
            name = item.get("holder_name") or "未命名股东"
            pct = item.get("ownership_pct")
            items.append(f"{name} {pct:.2f}%" if pct is not None else str(name))
        parts.append(f"主要股东（{period_text}）：" + "、".join(items))

    chains = equity.chain_details or []
    if chains:
        chain = max(
            chains,
            key=lambda item: float(item.get("final_control_pct") or 0.0),
        )
        names = [str(name) for name in (chain.get("path_names") or []) if name]
        if names:
            chain_text = " → ".join(names)
            pct = chain.get("final_control_pct")
            if pct is not None:
                chain_text += f"（最终持股 {float(pct):.2f}%）"
            # 8.09 三轮审查：十大股东链路是"持股路径"而非"控制链"——
            # 基金/少数持股不等于实际控制，不得过度断言
            parts.append(f"股权链：{chain_text}")

    # ── Phase E 会2：隐含关系解读段（交叉持股/隐含持股链）──
    # 确定性检测结果（可回查），"不只列链条、说明'说明了什么'"。
    insights = equity.insights or []
    if insights:
        insight_parts: list[str] = []
        for ins in insights[:5]:
            detail = str(ins.get("detail") or "").strip()
            if detail:
                insight_parts.append(detail)
        if insight_parts:
            parts.append("隐含关系解读：" + "；".join(insight_parts))

    if not parts:
        return "股权数据覆盖不足，未取得可展示的股东或控制链记录。"
    # 8.09 审查：诚实覆盖说明——严格 4 跳+ 为 0 时如实说明数据源覆盖边界，
    # 不推断"不存在更深控制关系"。
    note = (
        (equity.graph or {}).get("coverage_note")
        if isinstance(equity.graph, dict)
        else ""
    )
    if note and note not in parts:
        parts.append(note)
    return "；".join(parts) + "。"


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


# ── B2 第二阶段：舆情影响结论段 ──────────────────────────

_IMPACT_TYPE_LABELS: dict[str, str] = {
    "equity_structure": "股权结构",
    "operation": "经营",
    "financing": "融资",
    "market": "市场",
}
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


def _build_impact_conclusions_segment(state: AgentState) -> str:
    """B2 第二阶段（方案 §4.2.3）：事件回答追加「舆情影响结论」段。

    每条结论展示 display_tag（已发生/推断/风险推演，后端确定性渲染）+
    impact_type/direction/severity + conclusion + 因果链步骤 + evidence
    引用；无 impacts 则返回空串（不渲染该段）。因果链措辞保持「风险推演」
    （由 display_tag 体现），不把推断写成已发生事实。
    """
    results = state.get("results")
    evt = results.events if results else None
    impacts = getattr(evt, "impacts", None) if evt is not None else None
    if not impacts:
        return ""
    # B2 批次 A（方案 §二.5）：渲染前必须再次校验 plan.impact_requested，
    # 不能只看 impacts 非空——即使上游状态被错误注入 impacts，也不得把
    # 舆情影响段追加到普通财务/事件回答中。
    plan = state.get("plan")
    if plan is None or not getattr(plan, "impact_requested", False):
        return ""

    lines: list[str] = []
    for idx, imp in enumerate(impacts, start=1):
        if isinstance(imp, dict):
            tag = imp.get("display_tag") or "推断"
            itype = imp.get("impact_type") or "operation"
            direction = imp.get("direction") or "neutral"
            severity = imp.get("severity") or "low"
            conclusion = imp.get("conclusion") or ""
            chain = imp.get("causality_chain") or []
            evidence_ids = imp.get("evidence_ids") or []
        else:
            tag = getattr(imp, "display_tag", "") or "推断"
            itype = getattr(imp, "impact_type", "") or "operation"
            direction = getattr(imp, "direction", "") or "neutral"
            severity = getattr(imp, "severity", "") or "low"
            conclusion = getattr(imp, "conclusion", "") or ""
            chain = getattr(imp, "causality_chain", []) or []
            evidence_ids = getattr(imp, "evidence_ids", []) or []

        header = (
            f"{idx}.【{tag}】{_IMPACT_TYPE_LABELS.get(itype, itype)}·"
            f"{_IMPACT_DIRECTION_LABELS.get(direction, direction)}·"
            f"{_IMPACT_SEVERITY_LABELS.get(severity, severity)}影响：{conclusion}"
        )
        lines.append(header)
        if chain:
            steps = []
            for s in chain:
                text = (
                    s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "")
                )
                if text:
                    steps.append(text)
            if steps:
                lines.append("因果链：" + " → ".join(steps))
        if evidence_ids:
            lines.append("证据引用：" + "、".join(str(e) for e in evidence_ids))
    if not lines:
        return ""
    return "舆情影响结论：\n" + "\n".join(lines) + "\n"


# ── Phase D #13: LLM 问答润色 ─────────────────────────────


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

    # 段落标记校验：模板含【】标记（解读段等）时，润色必须全部保留
    src_markers = _extract_markers(answer)
    if src_markers and not src_markers <= _extract_markers(polished):
        logger.warning("polish: LLM 输出删除段落标记（%s），回退模板", src_markers)
        return answer

    return polished


def _build_follow_ups(state: AgentState) -> list[str]:
    """追问建议：已触发规则 + 行业分位 + 缺失模块（V12 §2.6）。"""
    claims = state.get("claims", [])
    results = state.get("results")
    plan = state.get("plan")
    module_status = state.get("module_status", {})

    follow_ups: list[str] = []

    # 已触发规则 → 对应指标追问（R7 按扣非字段可用性动态选择，#10）
    for c in claims:
        if c.rule_id and c.rule_id in _RULE_FOLLOW_UP:
            follow_ups.append(_RULE_FOLLOW_UP[c.rule_id])
        elif c.rule_id == "R7":
            r7_quality = (
                (results.finance.rule_details or {}).get("R7", {}).get("quality", {})
                if results and results.finance
                else {}
            )
            if r7_quality.get("core_profit_available", True):
                follow_ups.append(_R7_FOLLOW_UP_FULL)
            else:
                follow_ups.append(_R7_FOLLOW_UP_SIMPLIFIED)

    # 股权/事件 claim → 对应追问
    if any(c.claim_type == "equity" for c in claims):
        follow_ups.append("查看实控人控制的其他上市公司")
    if any(c.claim_type == "event" for c in claims):
        follow_ups.append("查看公司事件时间线")

    # 缺失数据维度：规则状态 insufficient_data → 追问对应数据
    if results and results.finance and results.finance.rule_statuses:
        if results.finance.rule_statuses.get("R5") == "insufficient_data":
            follow_ups.append("查看费用明细数据")
    if results and results.finance:
        percentiles = (results.finance.industry_benchmark or {}).get(
            "percentiles"
        ) or {}
        triggered_rule_ids = {
            claim.rule_id for claim in claims if claim.rule_id is not None
        }
        if percentiles and triggered_rule_ids:
            from app.domain.benchmarks.metric_registry import all_metrics

            for metric in all_metrics():
                if (
                    metric.rule_id in triggered_rule_ids
                    and percentiles.get(metric.metric_id) is not None
                ):
                    follow_ups.append(f"查看{metric.name}的行业分位对比")
                    break

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


# 企业类型中文标签（P1-2）：复用 domain 常量函数，避免 3/4 写反
# （1=非金融、2=银行、3=保险、4=证券）
# 交易所代码（Wind exchange_code）→ 中文标签
_EXCHANGE_LABELS = {
    "XSHG": "上海证券交易所",
    "XSHE": "深圳证券交易所",
    "XBEI": "北京证券交易所",
}
# 公司事实回答模板：事实键 → (展示名, 取值函数, registry field_path)
# P2-2（核验修订）：Evidence.field_path 必须与 SourceResolver 返回字段一致
# （industry_l1 / comp_type_code），字段级定位才能命中。
_FACT_KEYS: dict[str, tuple[str, str, str]] = {
    "industry": ("所属行业", "industry", "industry_l1"),
    "exchange": ("上市交易所", "exchange", "exchange_code"),
    "listing_date": ("上市日期", "listing_date", "listing_date"),
    "comp_type": ("企业类型", "comp_type", "comp_type_code"),
    "business": ("主营业务", "business", "business"),
    "total_shares": ("总股本", "total_shares", "total_shares"),
}

# Phase E 会5：可联网回填的公司事实键（首个示范触发点 = listing_date）。
# 仅库内无值时触发；默认 off 时 web_search 返回 []，行为与现状完全一致。
_WEB_SEARCHABLE_FACTS: frozenset[str] = frozenset({"listing_date"})


def _web_search_fill_company_fact(
    *,
    sec_name: str,
    wind_code: str,
    fact_key: str,
    label: str,
    turn_id: str,
    trace_id: str,
) -> tuple[str | None, EvidenceRef | None]:
    """会5：公司事实库内无值 → 联网检索 → 解析 → 构建来源标注证据.

    Returns:
        (value, evidence)：value 为解析出的值（无命中/解析失败 → None）；
        evidence 为 source_type="web_search" 的 EvidenceRef（同上 → None）。
        默认 off 时 web_search 返回 []，本函数返回 (None, None)——
        调用方走原「未覆盖」分支，行为与现状完全一致。
    """
    from app.application.services.web_search_fact_fill import (
        extract_listing_date_from_hits,
    )
    from app.application.services.web_search_service import web_search

    # 8/19 审查：query 带 wind_code + 交易所，提升同名公司消歧（如平安银行/
    # 中国平安/平安电工）；库内已有值时不进入本函数（调用方 gate），不会把
    # Web Search 变成每次问答都搜索。
    hits = web_search(f"{sec_name} {wind_code} {label} 交易所")
    if not hits:
        return None, None

    value: str | None = None
    field = ""
    if fact_key == "listing_date":
        value = extract_listing_date_from_hits(hits)
        field = "listing_date"
    if not value:
        return None, None

    hit = next((h for h in hits if (h.snippet or h.title)), None)
    evidence = EvidenceRef(
        evidence_id=make_evidence_id(
            source_namespace=NS_WEB_SEARCH,
            source_type="web_search",
            source_record_id=wind_code,
            field_path=field,
            company_code=wind_code,
        ),
        source_type="web_search",
        source_record_id=wind_code,
        field_path=field,
        value=value,
        source_title=(
            (hit.title or f"联网检索 · {label}") if hit else f"联网检索 · {label}"
        ),
        source_uri=hit.url if hit else None,
        source_excerpt=(hit.snippet or "") if hit else "",
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=wind_code,
        module="company_fact",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    return value, evidence


def _answer_company_fact(state: AgentState, fact_key: str) -> dict:
    """R9/R11：公司事实轻量回答（精确模板命中，不跑三大模块）。

    诚实边界：
      - 结构化已覆盖字段（行业/交易所/企业类型/上市日期）直接回答；
      - 未覆盖字段（主营业务/总股本无字段）明确回答"当前数据范围未覆盖"，
        不从股东持股等推算，**不生成虚假 Evidence**；
      - 有真实值 → company_fact Claim（verified）+ company_registry Evidence，
        顶层 claims/evidence 返回（persist_turn 只读顶层，P2-1）。
    """
    company = state.get("company")
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    wind_code = company.wind_code
    sec_name = company.sec_name

    if fact_key not in _FACT_KEYS:
        fact_key = "industry"  # 未知键兜底
    label, source_field, registry_field = _FACT_KEYS[fact_key]

    if source_field == "industry":
        value = (company.industry_l1 or "").strip() or None
    elif source_field == "exchange":
        value = _EXCHANGE_LABELS.get(company.exchange, company.exchange) or None
    elif source_field == "comp_type":
        from app.domain.company.models import company_type_label_from_code

        code_str = (company.comp_type_code or "").strip()
        code_int = int(code_str) if code_str.isdigit() else None
        value = company_type_label_from_code(code_int)
    elif source_field == "listing_date":
        # P2-1：直接消费 company.listing_date（resolve_entity 已一并填充）
        value = (company.listing_date or "").strip() or None
    else:  # business / total_shares：无结构化字段
        value = None

    # Phase E 会5：公司事实库内无值 → 触发联网检索（首个示范触发点：
    # 上市日期等公司事实；默认 off 时 web_search 返回 []，走原分支）
    web_evidence: EvidenceRef | None = None
    if not value and fact_key in _WEB_SEARCHABLE_FACTS:
        value, web_evidence = _web_search_fill_company_fact(
            sec_name=sec_name,
            wind_code=wind_code,
            fact_key=fact_key,
            label=label,
            turn_id=turn_id,
            trace_id=trace_id,
        )

    if value:
        if web_evidence is not None:
            answer = (
                f"{sec_name}（{wind_code}）的{label}为：{value}。"
                "（该信息来自联网检索，来源链接见证据，建议以官方披露为准。）"
            )
        else:
            answer = f"{sec_name}（{wind_code}）的{label}为：{value}。"
    else:
        answer = (
            f"{sec_name}（{wind_code}）的{label}：当前结构化数据范围未覆盖。"
            "如需进一步核验，请前往企业画像页查看详情。"
        )

    _emit_segment(state, answer)

    # P2-1：无真实值 → 不生成虚假 Evidence/Claim（三者全空）
    if not value:
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=[],
                evidence=[],
            ),
        }

    if web_evidence is not None:
        source_evidence = web_evidence
        limitations = ["联网检索来源，建议以官方披露为准核验"]
    else:
        evidence_id = make_evidence_id(
            source_namespace=NS_COMPANY_REGISTRY,
            source_type="company_registry",
            source_record_id=wind_code,
            field_path=registry_field,
            company_code=wind_code,
        )
        source_evidence = EvidenceRef(
            evidence_id=evidence_id,
            source_type="company_registry",
            source_record_id=wind_code,
            field_path=registry_field,
            value=value,
            source_title=f"{sec_name} · 公司注册信息",
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=wind_code,
            module="company_fact",
        )
        limitations = ["公司注册信息（证券主表）"]
    fact_claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=wind_code,
            claim_type="company_fact",
            claim_text=f"{label}：{value}",
            rule_version="",
        ),
        text=f"{label}为：{value}",
        claim_type="company_fact",
        severity="unknown",
        evidence_ids=[source_evidence.evidence_id],
        verification_status="verified",  # 真实值；来源类型见 source_type/limitations
        limitations=limitations,
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=wind_code,
        module="company_fact",
    )
    return {
        "claims": [fact_claim],
        "evidence": [source_evidence],
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[fact_claim],
            evidence=[source_evidence],
        ),
    }


def _evidence_for_observations(
    state: AgentState, company, observations: list
) -> list[EvidenceRef]:
    """逐 observation 生成 EvidenceRef（双期间契约，v3.3.3 批次 C 提取）。

    指标短答与轻量比较共用；每条 observation 用自己的 period 生成
    source_record_id/evidence_id。
    """
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence: list[EvidenceRef] = []
    for observation in observations:
        obs_period = getattr(observation, "period", "") or ""
        field_path = getattr(observation, "field_path", "")
        source_table = getattr(observation, "source_table", "")
        value = getattr(observation, "value", "")
        source_record_id = f"{company.wind_code}|{obs_period}|{PARENT_STATEMENT_TYPE}"
        evidence_id = make_evidence_id(
            source_namespace=NS_FINANCE,
            source_type="financial_statement",
            source_record_id=source_record_id,
            field_path=field_path,
            period=obs_period,
            dataset_version=settings.DATASET_VERSION,
            company_code=company.wind_code,
        )
        evidence.append(
            EvidenceRef(
                evidence_id=evidence_id,
                source_type="financial_statement",
                source_record_id=source_record_id,
                source_table=source_table,
                field_path=field_path,
                period=obs_period,
                value=str(value),
                unit="CNY",
                source_title=f"{company.sec_name} · 母公司报表",
                statement_scope="parent_company",
                module="finance",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                dataset_version=settings.DATASET_VERSION,
            )
        )
    return evidence


def _format_indicator_value(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:.2f}%"
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


def _answer_indicator(state: AgentState, indicator: str) -> dict:
    """Phase D #3A：基础财务指标确定性短答与可回查证据。"""
    company = state.get("company")
    if company is None:
        return {}
    # 裸 unsupported（无法识别基础指标，如周转率）走兜底文案
    if indicator == "unsupported":
        answer = "该指标暂未覆盖。当前可查询基础报表指标与资产负债率。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    require_exact = bool(plan and plan.as_of_kind == "report_period")
    # v3.3.3 批次 B：统一入口——registry 指标（r4/r5）与基础指标同构返回
    from app.application.services.indicator_query_service import query_metric

    result = query_metric(
        company.wind_code,
        indicator,
        as_of=as_of,
        require_exact_period=require_exact,
    )
    name_code = f"{company.sec_name}（{company.wind_code}）"
    # 2026-08-12 三轮审查修订：带 label 的 unsupported（环比/双字段增速）
    # 与 insufficient_data 分开，不再一律答"数据不足"
    if result.status == "unsupported":
        answer = f"{name_code}的{result.label}：暂不支持该指标的同比/环比计算。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if result.status != "ok" or result.value is None:
        answer = f"{name_code}的{result.label}：数据不足，无法按母公司口径计算。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    # v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类问句走 assessment，
    # 只答数值时不得用泛化话术冒充判断
    plan = state.get("plan")
    answer_operation = getattr(plan, "answer_operation", "") if plan else ""
    if answer_operation == "assessment":
        return _answer_indicator_assessment(state, company, result)

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    value_text = _format_indicator_value(result.value, result.unit)
    period_text = f"{result.period[:4]}-{result.period[4:6]}-{result.period[6:]}"
    # 同比增速答案：正负文案 + 对比基准期（2026-08-12 修订）
    if indicator.endswith("_growth"):
        comparison_text = (
            f"{result.comparison_period[:4]}-{result.comparison_period[4:6]}"
            f"-{result.comparison_period[6:]}"
        )
        answer = (
            f"{name_code}的{result.label}为 {_format_growth(result.value)}"
            f"（{period_text} 较 {comparison_text}，母公司口径）。"
        )
        claim_value_text = _format_growth(result.value)
    else:
        answer = (
            f"{name_code}的{result.label}为 {value_text}"
            f"（{period_text}，母公司口径）。"
        )
        claim_value_text = value_text

    # 双期间契约（2026-08-12 修订）：逐 observation 用自己的 period 生成
    # source_record_id/evidence_id——同比查询含当前期与去年同期两条证据，
    # 不再共用 result.period 导致两条 evidence_id 相同。
    # v3.3.3 批次 C：构造逻辑提取为 _evidence_for_observations，供指标短答
    # 与轻量比较共用。
    evidence: list[EvidenceRef] = _evidence_for_observations(
        state, company, result.observations
    )
    evidence_ids = [item.evidence_id for item in evidence]
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="indicator",
            claim_text=f"{result.label}：{claim_value_text}",
        ),
        text=f"{result.label}为 {claim_value_text}",
        claim_type="indicator",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["母公司报表口径"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="finance",
    )
    _emit_segment(state, answer)
    return {
        "claims": [claim],
        "evidence": evidence,
        # v3.3.3 批次 B（方案 §5.4）：成功执行的规范指标写入 state，
        # persist_turn 落 response_meta.executed_metrics；失败/unsupported
        # 轮不返回本字段（不得覆盖最近成功指标）
        "executed_metric": {
            "metric_id": indicator,
            "period": result.period,
            "unit": result.unit,
            "status": "ok",
            # v3.3.3 收口批次 B（方案 §3.4）：指标所属公司，防跨主体串用
            "company_code": company.wind_code,
        },
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[claim],
            evidence=evidence,
        ),
    }


def _answer_indicator_assessment(state, company, result) -> dict:
    """v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类 assessment。

    输出：当前值 + 报告期 + 行业基准分位/中位数 + 样本数 + 偏离结论；
    无可靠行业基准 → 明确「已查到当前值，但缺少可比较基准，无法判断
    正常性」，不得用泛化风险话术冒充判断。值本身照常生成 claim/evidence。
    """
    from app.application.services.indicator_query_service import (
        query_industry_benchmark,
    )
    from app.domain.benchmarks.calculator import MIN_PEER_SAMPLE

    name_code = f"{company.sec_name}（{company.wind_code}）"
    value_text = _format_indicator_value(result.value, result.unit)
    period_text = f"{result.period[:4]}-{result.period[4:6]}-{result.period[6:]}"
    base_answer = (
        f"{name_code}的{result.label}为 {value_text}" f"（{period_text}，母公司口径）。"
    )
    industry = getattr(company, "industry_l1", "") or ""
    bench = query_industry_benchmark(industry, result.indicator, result.period)
    sample_count = (bench or {}).get("sample_count") or 0
    if bench is None or sample_count < MIN_PEER_SAMPLE:
        answer = base_answer + "当前数据缺少可比较的行业基准，无法判断是否「正常」。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    # 基准表存 registry 原始口径（ratio 小数/days/pp），展示前换算
    def _bench_display(raw) -> str:
        if raw is None:
            return "—"
        if result.unit == "percent":
            return f"{float(raw) * 100:.2f}%"
        return f"{float(raw):.2f}"

    value_raw = result.value / 100 if result.unit == "percent" else result.value
    p50 = bench.get("p50")
    p75 = bench.get("p75")
    if p50 is None or p75 is None:
        answer = base_answer + "行业基准分位缺失，无法判断是否「正常」。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    if value_raw <= p50:
        band = (
            f"不高于行业中位数（中位数 {_bench_display(p50)}，"
            f"{sample_count} 家可比公司），处于行业较低水平"
        )
    elif value_raw <= p75:
        band = (
            f"位于行业中位数与 75 分位之间（p75 {_bench_display(p75)}，"
            f"{sample_count} 家可比公司），处于行业中等水平"
        )
    else:
        band = (
            f"高于行业 75 分位（p75 {_bench_display(p75)}，"
            f"{sample_count} 家可比公司），处于行业较高水平"
        )
    answer = base_answer + f"{result.label}相对行业：{band}。"

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence: list[EvidenceRef] = _evidence_for_observations(
        state, company, result.observations
    )
    evidence_ids = [item.evidence_id for item in evidence]
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="indicator",
            claim_text=f"{result.label}：{value_text}",
        ),
        text=f"{result.label}为 {value_text}",
        claim_type="indicator",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["母公司报表口径", "行业基准判断"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="finance",
    )
    _emit_segment(state, answer)
    return {
        "claims": [claim],
        "evidence": evidence,
        "executed_metric": {
            "metric_id": result.indicator,
            "period": result.period,
            "unit": result.unit,
            "status": "ok",
            "company_code": company.wind_code,
        },
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[claim],
            evidence=evidence,
        ),
    }


def _answer_light_comparison(state: AgentState) -> dict:
    """v3.3.3 批次 C/D（方案 §5.6）：消费 ComparisonSpec 的轻量比较回答。

    查询与算术在 light_comparison_service，本函数只渲染结构化结果并
    组装 claim/evidence；missing_dimension/full 不得启动数值查询。
    """
    plan = state.get("plan")
    spec = getattr(plan, "comparison", None) if plan is not None else None
    company = state.get("company")
    if spec is None:
        return {}
    if spec.scope == "same_company_cross_indicator" and spec.mode == "indicator":
        if company is None:
            return {}
        return _answer_same_company_comparison(state, company, spec)
    if spec.scope == "cross_company":
        return _answer_cross_company_comparison(state, spec)
    return {}


def _answer_same_company_comparison(state: AgentState, company, spec) -> dict:
    """同主体两指标轻量比较：共同期间 + 单位校验 + 程序差值（批次 C）。"""
    from app.application.services.light_comparison_service import (
        compare_same_company_indicators,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_same_company_indicators(
        company.wind_code, company.sec_name, spec, as_of=as_of
    )
    name_code = f"{company.sec_name}（{company.wind_code}）"

    def _finish(answer: str, claims: list, evidence: list, executed: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "executed_metrics": executed,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
        }

    if result.status == "ok":
        runtime = state.get("runtime")
        turn_id = getattr(runtime, "turn_id", "") if runtime else ""
        trace_id = getattr(runtime, "trace_id", "") if runtime else ""
        evidence: list[EvidenceRef] = []
        for participant in result.participants:
            evidence.extend(
                _evidence_for_observations(state, company, participant.observations)
            )
        evidence_ids = [item.evidence_id for item in evidence]
        claim = Claim(
            claim_id=make_claim_id(
                turn_id=turn_id,
                company_code=company.wind_code,
                claim_type="indicator_comparison",
                claim_text=result.conclusion,
            ),
            text=result.conclusion,
            claim_type="indicator_comparison",
            severity="unknown",
            evidence_ids=evidence_ids,
            verification_status="verified",
            limitations=["母公司报表口径", "共同期间"],
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=company.wind_code,
            module="finance",
        )
        executed = [
            {
                "metric_id": p.metric_id,
                "period": p.period,
                "unit": p.unit,
                "status": "ok",
                "company_code": p.company_code,
            }
            for p in result.participants
        ]
        return _finish(result.conclusion, [claim], evidence, executed)

    if result.status == "partial":
        parts = []
        for p in result.participants:
            parts.append(f"{p.metric_label}为 {p.value:.2f}（期间 {p.period}）")
        answer = (
            f"{name_code}仅有一侧指标可用：{'；'.join(parts)}。"
            "另一侧指标数据不可用，无法比较高低（母公司口径）。"
        )
        return _finish(answer, [], [], [])

    if result.status == "unsupported":
        answer = (
            f"{name_code}的两项指标单位不兼容，无法直接相减"
            f"（{'；'.join(result.warnings)}）。请指定同一量纲的指标对比。"
        )
        return _finish(answer, [], [], [])

    # insufficient_data：无共同期间/两侧无数据，不得输出高低结论
    answer = (
        f"{name_code}：{'；'.join(result.warnings) or '数据不足'}，"
        "无法完成两项指标的比较（母公司口径）。"
    )
    return _finish(answer, [], [], [])


def _light_comparison_payload(
    spec,
    targets,
    *,
    comparison_mode: str,
    overview_rows: list | None = None,
    llm_analysis: str = "",
) -> dict:
    """v3.3.4 方案 §3.3/§6.1：已执行比较的 light_comparison 载荷。

    next_steps 由程序按 requested_scope 生成（只提供导航动作，不改变任何
    数值、主体、证据或结论）；主体代码直接取已校验的 finalized targets
    （去重保序），禁止掺入未经校验的主体。
    Phase E 会6：llm_analysis 为跨公司对比大模型整体分析段落（空串表示
    未生成/降级，前端不渲染）。
    """
    from app.application.services.light_comparison_service import (
        build_preview_next_steps,
    )

    codes: list[str] = []
    for t in targets or []:
        code = str(getattr(t, "wind_code", "") or "")
        if code and code not in codes:
            codes.append(code)
    scope = getattr(spec, "requested_scope", "indicator") or "indicator"
    return {
        "comparison_mode": comparison_mode,
        "overview_rows": list(overview_rows or []),
        "requested_scope": scope,
        "next_steps": [s.model_dump() for s in build_preview_next_steps(scope, codes)],
        "llm_analysis": llm_analysis,
    }


def _answer_cross_company_comparison(state: AgentState, spec) -> dict:
    """v3.3.3 批次 D：双公司轻量比较渲染（方案 §2.4/§5.6）。"""
    targets = state.get("comparison_targets") or []

    def _plain(answer: str) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    if spec.mode == "missing_dimension":
        return _plain(
            "请指定要比较的维度（例如毛利率、存货周转天数或风险等级），"
            "我会给出双方数值与差异。"
        )
    if spec.mode == "risk":
        return _answer_cross_company_risk(state, targets, spec)
    if spec.mode == "indicator":
        return _answer_cross_company_indicator(state, targets, spec)
    if spec.mode == "overview":
        return _answer_cross_company_overview(state, targets, spec)
    if spec.mode == "company_fact":
        return _answer_cross_company_fact(state, targets, spec)
    return {}


def _answer_cross_company_overview(state, targets, spec) -> dict:
    """双公司轻量整体概览（v3.3.4 方案 §3/§5/§6）。

    服务端固定维度 profile 逐指标比较；claims/evidence 只引用成功行
    （缺失行不伪造事实）；不生成综合评分与整体优劣结论；
    requested_scope=full/industry 时明确声明有限预览，结构化 next_steps
    按请求范围由程序生成。
    """
    from app.application.services.light_comparison_service import (
        compare_cross_company_overview,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_overview(targets, spec, as_of=as_of)
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    company_by_code = {str(t.wind_code): t for t in targets}

    def _fmt(value, unit: str) -> str:
        if unit in ("percent", "ratio", "pp"):
            return f"{value:.2f}%"
        if unit == "days":
            return f"{value:.2f}天"
        return f"{value:,.2f}元"

    ok_rows = [r for r in result.overview_rows if r.status == "ok"]
    claims: list[Claim] = []
    evidence: list[EvidenceRef] = []
    executed: list[dict] = []
    for row in ok_rows:
        if len(row.values) != 2:
            continue  # 防御：ok 行必须携带双方值，否则不为其生成事实 claim
        row_evidence: list[EvidenceRef] = []
        for participant in row.values:
            ref = company_by_code.get(participant.company_code)
            if ref is None:
                continue
            row_evidence.extend(
                _evidence_for_observations(state, ref, participant.observations)
            )
        evidence.extend(row_evidence)
        first, second = row.values
        text = (
            f"{row.metric_label}：{first.sec_name}"
            f"{_fmt(first.value, row.unit)}；{second.sec_name}"
            f"{_fmt(second.value, row.unit)}；{row.conclusion}"
            f"（共同期间 {row.period}，母公司口径）"
        )
        primary_code = str(targets[0].wind_code) if targets else ""
        claims.append(
            Claim(
                claim_id=make_claim_id(
                    turn_id=turn_id,
                    company_code=primary_code,
                    claim_type="overview_comparison",
                    claim_text=text,
                ),
                text=text,
                claim_type="overview_comparison",
                severity="unknown",
                evidence_ids=[ev.evidence_id for ev in row_evidence],
                verification_status="verified",
                limitations=["母公司报表口径", "共同期间", "轻量概览"],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=primary_code,
                module="finance",
            )
        )
        executed.extend(
            {
                "metric_id": v.metric_id,
                "period": v.period,
                "unit": v.unit,
                "status": "ok",
                "company_code": v.company_code,
            }
            for v in row.values
        )

    names = "、".join(str(getattr(t, "sec_name", "") or "") for t in targets[:2])
    if result.conclusion:
        answer = f"{names}概览\n\n{result.conclusion}"
    else:
        answer = (
            f"{names}概览：{'；'.join(result.warnings) or '数据不足'}，"
            "无法完成概览比较（母公司口径）。"
        )
    # v3.3.4 方案 §6.1：requested_scope 感知的预览声明——
    # 全面/行业请求必须明确当前结果是有限预览而非完整结论/行业分位。
    if spec.requested_scope == "industry":
        answer += (
            "\n\n当前对话仅展示基础财务预览，未执行行业分位或行业基准计算；"
            "行业对比请点击「查看行业对比」。"
        )
    elif spec.requested_scope == "full":
        answer += (
            "\n\n以上为有限预览，不代表完整画像；风险、股权、行业等更多维度"
            "请点击「查看完整对比」。"
        )
    else:
        answer += (
            "\n\n这是基础指标预览，不代表完整画像；可继续指定「毛利率」"
            "「存货周转」或「风险等级」进行单项比较，完整对比请点击"
            "「查看完整对比」。"
        )

    # ── Phase E 会6：跨公司对比大模型整体分析段落 ──
    # 只读结构化数据做整体解读（不覆盖/不篡改）；失败/降级时模板兜底，
    # 空串则前端不渲染该段。
    llm_analysis = ""
    try:
        from app.application.services.comparison_analysis_service import (
            build_comparison_analysis,
        )

        names_list = [str(getattr(t, "sec_name", "") or "") for t in targets[:2]]
        llm_analysis, _analysis_warnings = build_comparison_analysis(
            result=result,
            company_names=names_list,
        )
        if llm_analysis:
            answer += "\n\n大模型整体分析：" + llm_analysis
    except Exception:  # noqa: BLE001 — 分析失败不影响结构化比较
        logger.warning("comparison_analysis 失败，跳过 LLM 段落", exc_info=True)

    _emit_segment(state, answer)
    return {
        "claims": claims,
        "evidence": evidence,
        "executed_metrics": executed,
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=claims,
            evidence=evidence,
        ),
        # v3.3.4 方案 §3.3/§6.1：结构化概览载荷（REST/WS 只读追加，向后兼容）。
        # overview_rows 用 mode="json" 序列化（Decimal → float/str），
        # WS _ws_sender 的 json.dumps 不接受 Decimal。
        "light_comparison": _light_comparison_payload(
            spec,
            targets,
            comparison_mode=result.comparison_mode,
            overview_rows=[r.model_dump(mode="json") for r in result.overview_rows],
            llm_analysis=llm_analysis,
        ),
    }


def _answer_cross_company_risk(state, targets, spec) -> dict:
    """两家公司窄风险比较（收口批次 D，方案 §3.7）。

    按既有评估等级排序回答；任一侧无记录/口径不一致 → partial 诚实
    说明；显式历史截止期（as_of）→ unsupported（方案 §5 D2：当前仅
    支持最新风险评估，不静默取未来记录）。触发信号详情继续页面
    （不在此伪造）。等级比较不生成数值 claim（避免无证据数值结论），
    页面承载详情。
    """
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_risk(targets, spec, as_of=as_of)
    if result.status == "ok":
        answer = result.conclusion
    elif result.status == "partial":
        answer = (
            f"风险比较：{'；'.join(result.warnings)}。"
            "全面风险画像请使用页面跨公司对比。"
        )
    else:
        answer = f"风险比较：{'；'.join(result.warnings) or '数据不足'}。"
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": [],
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", claims=[], evidence=[]
        ),
        # v3.3.4 方案 §2.1/§6.1：风险比较附带完整对比页下一步
        "light_comparison": _light_comparison_payload(
            spec, targets, comparison_mode="risk"
        ),
    }


def _answer_cross_company_indicator(state, targets, spec) -> dict:
    """双公司单指标：共同期间 + 程序差值 + 双方原始值（批次 D）。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_indicators,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_indicators(targets, spec, as_of=as_of)
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""

    def _finish(answer: str, claims: list, evidence: list, executed: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "executed_metrics": executed,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
            # v3.3.4 方案 §2.1/§6.1：单指标比较附带完整对比页下一步
            "light_comparison": _light_comparison_payload(
                spec, targets, comparison_mode="indicator"
            ),
        }

    if result.status == "ok":
        company_by_code = {str(t.wind_code): t for t in targets}
        evidence: list[EvidenceRef] = []
        for participant in result.participants:
            ref = company_by_code.get(participant.company_code)
            if ref is None:
                continue
            evidence.extend(
                _evidence_for_observations(state, ref, participant.observations)
            )
        evidence_ids = [item.evidence_id for item in evidence]
        primary_code = str(targets[0].wind_code) if targets else ""
        claim = Claim(
            claim_id=make_claim_id(
                turn_id=turn_id,
                company_code=primary_code,
                claim_type="indicator_comparison",
                claim_text=result.conclusion,
            ),
            text=result.conclusion,
            claim_type="indicator_comparison",
            severity="unknown",
            evidence_ids=evidence_ids,
            verification_status="verified",
            limitations=["母公司报表口径", "共同期间"],
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=primary_code,
            module="finance",
        )
        executed = [
            {
                "metric_id": p.metric_id,
                "period": p.period,
                "unit": p.unit,
                "status": "ok",
                "company_code": p.company_code,
            }
            for p in result.participants
        ]
        return _finish(
            result.conclusion
            + "\n\n更多维度的对比请点击「查看完整对比」进入跨公司对比页面。",
            [claim],
            evidence,
            executed,
        )

    if result.status == "partial":
        names = "、".join(p.sec_name for p in result.participants)
        return _finish(
            f"仅{names}的该指标数据可用，另一侧不可用，无法比较高低（母公司口径）。",
            [],
            [],
            [],
        )

    if result.status == "unsupported":
        return _finish(f"该比较暂不支持：{'；'.join(result.warnings)}。", [], [], [])

    return _finish(
        f"双方数据不足或无共同期间：{'；'.join(result.warnings)}，"
        "无法比较（母公司口径）。",
        [],
        [],
        [],
    )


def _answer_cross_company_fact(state, targets, spec) -> dict:
    """双公司公司事实比较（批次 D 仅 listing_date）。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_facts,
    )

    result = compare_cross_company_facts(targets, spec)
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""

    def _finish(answer: str, claims: list, evidence: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
            # v3.3.4 方案 §2.1/§6.1：公司事实比较附带完整对比页下一步
            "light_comparison": _light_comparison_payload(
                spec, targets, comparison_mode="company_fact"
            ),
        }

    if result.status != "ok":
        return _finish(
            f"上市日期比较：{'；'.join(result.warnings) or '数据不足'}。",
            [],
            [],
        )

    evidence: list[EvidenceRef] = []
    for target in targets:
        date_value = str(getattr(target, "listing_date", "") or "")
        if not date_value:
            continue
        evidence.append(
            EvidenceRef(
                evidence_id=make_evidence_id(
                    source_namespace=NS_COMPANY_REGISTRY,
                    source_type="company_registry",
                    source_record_id=str(target.wind_code),
                    field_path="listing_date",
                    company_code=str(target.wind_code),
                ),
                source_type="company_registry",
                source_record_id=str(target.wind_code),
                field_path="listing_date",
                value=date_value,
                source_title=f"{target.sec_name} · 公司注册信息",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=str(target.wind_code),
                module="company_fact",
            )
        )
    evidence_ids = [item.evidence_id for item in evidence]
    primary_code = str(targets[0].wind_code) if targets else ""
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=primary_code,
            claim_type="company_fact_comparison",
            claim_text=result.conclusion,
        ),
        text=result.conclusion,
        claim_type="company_fact_comparison",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["公司注册信息（证券主表）"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=primary_code,
        module="company_fact",
    )
    return _finish(result.conclusion, [claim], evidence)


def _answer_comparison_guide(state: AgentState) -> dict:
    """比较意图页面引导（P2-2 + v3.3.3 批次 D + v3.3.4 §2.4/§6.1）。

    按 0/1/≥2 家候选区分文案，绝不静默退化为单公司分析；
    批次 D 起聊天内已支持双公司单指标/公司事实轻量比较。
    三家及以上（v3.3.4）：不查询指标、不静默截断——
    - 3..MAX 家 → 结构化保底 next_steps（多主体页面可用 →
      open_multi_company_comparison 全代码；否则 choose_comparison_pair）；
    - 超过 MAX → 纯文案要求缩小范围，next_steps 为空、不携带任何代码。
    """
    from app.agents.nodes.plan_modules import _FULL_COMPARISON_CUES
    from app.application.services.light_comparison_service import (
        build_multi_company_next_steps,
    )

    user_query = state.get("user_query", "")
    targets = state.get("comparison_targets", [])
    company = state.get("company")

    def _finish(answer: str, payload: dict | None = None) -> dict:
        _emit_segment(state, answer)
        out: dict = {
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            )
        }
        if payload is not None:
            out["light_comparison"] = payload
        return out

    def _requested_scope_from_query() -> str:
        if any(cue in user_query for cue in _FULL_COMPARISON_CUES):
            return "full"
        if "行业" in user_query:
            return "industry"
        return "overview"

    # v3.3.3 批次 D + v3.3.4：单主体行业/全面对比（company 已识别、targets 为空）
    if not targets and company is not None:
        if any(cue in user_query for cue in _FULL_COMPARISON_CUES):
            return _finish(
                f"{company.sec_name}（{company.wind_code}）目前只有一家公司，"
                "无法进行跨公司对比。请补充另一家公司的名称或代码；"
                "完整对比请使用页面「跨公司对比」功能。"
            )
        return _finish(
            f"{company.sec_name}（{company.wind_code}）的行业分位对比请使用"
            "页面「行业对标」功能（企业画像页/跨公司对比页提供行业基准与"
            "分位），对话内暂不执行行业分位计算。"
        )

    if len(targets) >= 2:
        names = "、".join(f"{item.sec_name}（{item.wind_code}）" for item in targets)
        codes: list[str] = []
        for item in targets:
            code = str(getattr(item, "wind_code", "") or "")
            if code and code not in codes:
                codes.append(code)

        # v3.3.4 §2.4：三家及以上保底——不查询、不截断、不默认取前两家
        if len(codes) >= 3:
            next_steps = build_multi_company_next_steps(
                codes,
                multi_page_enabled=settings.COMPARISON_MULTI_PAGE_ENABLED,
            )
            if len(codes) > MAX_MULTI_COMPARISON_PARTICIPANTS:
                answer = (
                    f"你提到了 {names} 共 {len(codes)} 家公司，超过一次对比的"
                    f"上限 {MAX_MULTI_COMPARISON_PARTICIPANTS} 家。请缩小到"
                    f" {MAX_MULTI_COMPARISON_PARTICIPANTS} 家以内再发起对比；"
                    "本次未执行任何指标查询，也没有默认选择其中几家。"
                )
            elif settings.COMPARISON_MULTI_PAGE_ENABLED:
                answer = (
                    f"已识别 {names} 共 {len(codes)} 家公司，尚未执行数值比较。"
                    "多主体对比页已支持一次对比全部公司，请点击「多公司对比」"
                    "；或指定其中两家与具体指标（如毛利率）在对话内比较。"
                )
            else:
                answer = (
                    f"已识别 {names} 共 {len(codes)} 家公司，尚未执行数值比较。"
                    "一期对话预览仅支持两家，请点击「选择两家对比」或直接"
                    "指定其中两家与具体指标（如毛利率）在对话内比较。"
                )
            return _finish(
                answer,
                {
                    "comparison_mode": "",
                    "overview_rows": [],
                    "requested_scope": _requested_scope_from_query(),
                    "next_steps": [s.model_dump() for s in next_steps],
                },
            )

        # 恰好两家（防御性兜底：正常路径已在 plan 层进入 overview/轻量比较）
        if "行业" in user_query:
            return _finish(
                f"行业分位对比请使用页面「行业对标/跨公司对比」功能"
                f"（{names} 的指标行业分位在页面展示）。"
                "对话内可回答两家公司同一指标或同一公司事实的数值比较。"
            )
        return _finish(
            f"你提到了 {names}。全面/多维度对比请使用"
            "页面上方的「跨公司对比」功能；单个指标（如毛利率、"
            "存货周转天数）或公司事实（如上市日期）的两两比较"
            "可直接在对话中提问。"
        )
    if len(targets) == 1:
        t0 = targets[0]
        if "行业" in user_query:
            return _finish(
                f"{t0.sec_name}（{t0.wind_code}）的行业分位对比请使用"
                "页面「行业对标」功能（企业画像页/跨公司对比页提供"
                "行业基准与分位），对话内暂不执行行业分位计算。"
            )
        return _finish(
            f"已识别 {t0.sec_name}（{t0.wind_code}），另一家公司未匹配到"
            "数据。请补充另一家公司的名称或代码；跨公司对比请使用页面"
            "上方的「跨公司对比」功能。"
        )
    return _finish(
        "请提供两家公司的名称或代码（例如「康美药业和金牌家居的"
        "差距」），以便进行跨公司对比。"
    )


def _answer_risk_level(state: AgentState) -> dict:
    """Phase D #3B：只回答综合等级、截止日和覆盖状态。"""
    risk_output = state.get("risk_output")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    level = getattr(risk_output, "risk_level", "unknown") if risk_output else "unknown"
    labels = {
        "green": "正常",
        "yellow": "黄色",
        "orange": "橙色",
        "red": "红色",
        "blue": "蓝色",
        "unknown": "数据不足",
    }
    if level not in labels:
        level = "unknown"

    plan = state.get("plan")
    as_of = getattr(risk_output, "as_of", "") if risk_output else ""
    if not as_of and plan and plan.as_of:
        as_of = plan.as_of.strftime("%Y%m%d")

    def _fmt(period: str) -> str:
        return (
            f"{period[:4]}-{period[4:6]}-{period[6:]}"
            if len(period) == 8 and period.isdigit()
            else "未知"
        )

    # WARN-1-3（核验修订 + 8.09 二轮审查）：区分请求截止日与数据实际截止日。
    #   - 证据期次经 normalize_period 解析（跳过无法解析的），按解析值比较；
    #   - data_as_of < requested → 双期提示"请求截至 X，最新可用数据截至 Y"；
    #   - data_as_of > requested → 异常（证据期晚于请求期）明确标记，
    #     不得当作正常展示；
    #   - 无任何证据期 → "实际数据截止日未知"，不得把请求期冒充为数据截止日。
    from app.domain.finance.period import normalize_period

    data_as_of = ""
    ev_periods = sorted(
        {p for p in (normalize_period(getattr(e, "period", "")) for e in evidence) if p}
    )
    if ev_periods:
        data_as_of = ev_periods[-1]
    if not as_of:
        as_of_text = _fmt(data_as_of) if data_as_of else "未知"
    elif data_as_of and data_as_of < as_of:
        as_of_text = f"请求截至 {_fmt(as_of)}，最新可用数据截至 {_fmt(data_as_of)}"
    elif data_as_of and data_as_of > as_of:
        as_of_text = (
            f"请求截至 {_fmt(as_of)}（异常：存在晚于请求期的证据，"
            f"最新 {_fmt(data_as_of)}）"
        )
    elif data_as_of:
        as_of_text = _fmt(data_as_of)
    else:
        as_of_text = f"请求截至 {_fmt(as_of)}（实际数据截止日未知）"

    coverage = getattr(risk_output, "data_coverage", None) if risk_output else None
    ratio = getattr(coverage, "coverage_ratio", None) if coverage else None
    missing = getattr(coverage, "missing_modules", []) if coverage else []
    coverage_text = f"数据覆盖率 {ratio:.0%}" if ratio is not None else "数据覆盖未知"
    if missing:
        coverage_text += f"，缺失模块：{', '.join(missing)}"
    answer = (
        f"综合风险等级：{labels[level]}"
        f"（数据截止日：{as_of_text}；{coverage_text}）。"
    )
    if level == "unknown":
        answer += "当前数据不足，不能据此判断为正常。"
    _emit_segment(state, answer)
    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level=level,
            claims=claims,
            evidence=evidence,
        )
    }


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    finance_ran, finance = _finance_executed(state)
    finance_blocked = _finance_all_blocked(finance)
    finance_unknown_type = finance_blocked and any(
        "公司类型缺失" in (w or "") for w in (finance.warnings or [])
    )
    # 流式模式：存在 DeltaSink（由 WsTurnRunner 注册）。
    # 流式下跳过整段 LLM 润色——润色会整体重写回答，导致
    # "delta 拼接 == 最终答案" 无法成立；润色仅作为 REST 增强保留。
    streaming = get_sink(_stream_turn_id(state) or "") is not None

    if company is None:
        user_query = state.get("user_query", "")
        plan = state.get("plan")
        intent = getattr(plan, "intent", "") if plan else ""

        # 2026-08-12 批 1.5 补做：实体解析失败/候选截断明确告知，
        # 替代通用引导（"请提供公司名称或股票代码"）——用户能知道
        # 系统"看到了"疑似公司但库内无匹配。
        if state.get("candidates_truncated"):
            answer = "候选公司过多（已截断展示）。请补充更完整的公司名称或代码后重试。"
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if state.get("entity_resolution_error") == "company_not_found":
            frags = state.get("unresolved_fragments") or []
            frag_text = "「" + "」「".join(frags[:3]) + "」" if frags else ""
            answer = (
                f"检测到疑似公司{frag_text}但未能识别，请提供完整名称或股票代码。"
                if frags
                else "未能识别到公司，请提供完整名称或股票代码。"
            )
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        if intent == "relation_clarify":
            # v3.1 P0-3：身份已确认但关系不可执行（reference/sequence/
            # ambiguous）→ 澄清主次/先后，不启动模块执行、不进比较引导
            resolution = state.get("entity_resolution_result")
            names = ""
            if resolution is not None and getattr(
                resolution, "selected_companies", None
            ):
                names = "、".join(c.sec_name for c in resolution.selected_companies[:3])
            answer = (
                f"已识别 {names}，但你问题的表述中这些公司的主次或先后关系"
                "不够明确（如'提到''先看''再看'）。请换一种表述，例如"
                "「分析康美药业，顺带看下贵州茅台的公告」或「对比康美药业"
                "和贵州茅台」，我会按明确的主次关系分析。"
                if names
                else "你提到了多家公司，但这些公司的主次或先后关系不够明确，"
                "请换一种表述明确先后（如「先看A，再看B」）或主次（如"
                "「分析A，顺带看B」），我会按明确的关系分析。"
            )
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        if intent == "comparison_guide":
            return _answer_comparison_guide(state)

        # v3.3.3 收口批次 F：comparison 场景 Resolver 派生 company=None
        # （targets 承载两家公司），light_comparison 必须在无 company
        # 分支也可达，否则官方双公司原题落通用 fallback
        if intent == "light_comparison":
            return _answer_light_comparison(state)

        if intent == "company_disambiguation":
            candidates = state.get("company_candidates", [])
            options = "、".join(
                f"{item.sec_name}（{item.wind_code}）" for item in candidates
            )
            # 8/16 语义裁决启用（suggest）：LLM 消歧推荐展示，不自动绑定
            suggested = state.get("suggested_company_code", "")
            hint = ""
            if suggested:
                for item in candidates:
                    if item.wind_code == suggested:
                        hint = f"（建议选择：{item.sec_name} {item.wind_code}）"
                        break
            answer = f"找到多个可能的公司：{options}。请选择一家后继续分析。"
            if hint:
                answer = f"找到多个可能的公司：{options}。{hint}请选择一家后继续分析。"
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        # 寒暄/引导意图：先于研报检索处理（同学反馈"你好"答非所问）
        if intent == "chitchat":
            ql = user_query.lower()
            if any(kw in ql for kw in _THANKS_KW):
                chitchat_answer = (
                    "不客气。需要继续核查时，请告诉我上市公司名称或股票代码。"
                )
            elif any(kw in ql for kw in _FAREWELL_KW):
                chitchat_answer = "再见。之后需要核查财务、股权或公告风险时，随时回来。"
            else:
                intro = (
                    "我是织网鉴真，面向个人投资者的财报反欺诈助手。"
                    if any(kw in ql for kw in _CAPABILITY_KW)
                    else "你好！我是织网鉴真。"
                )
                chitchat_answer = (
                    f"{intro}我可以核查财务勾稽、股权控制链和公告舆情。\n"
                    "你可以这样问：\n"
                    "- 分析康美药业 2025 年报的财务异常\n"
                    "- 查看金牌家居的实际控制人链路\n"
                    "- 核对贵州茅台近期公告与财务数据\n"
                    "请输入上市公司名称或股票代码开始分析。"
                )
            _emit_segment(state, chitchat_answer)
            return {
                "final_response": FinalResponse(
                    answer=chitchat_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if intent == "guide":
            ql = user_query.lower()
            if any(kw in ql for kw in _CONTEXT_REQUEST_KW):
                guide_answer = (
                    "我没有找到可延续的公司上下文。请补充上市公司名称或股票代码，"
                    "例如“继续分析康美药业的现金流”。"
                )
            elif any(kw in ql for kw in _CAPABILITY_KW):
                guide_answer = (
                    "我可以核查上市公司的财务勾稽、股权控制链和公告舆情。"
                    "例如可以问“分析康美药业 2025 年报”或“查看金牌家居的实控人链路”。"
                    "请输入上市公司名称或股票代码开始分析。"
                )
            else:
                guide_answer = (
                    "我不直接推荐股票，但可以核查你指定上市公司的财务、股权与公告风险。"
                    "请提供公司名称或股票代码，例如“分析康美药业”或“600518”。"
                )
            _emit_segment(state, guide_answer)
            return {
                "final_response": FinalResponse(
                    answer=guide_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if intent == "unsupported":
            unsupported_answer = (
                "这个问题超出了织网鉴真的服务范围。"
                "我专注于上市公司财务勾稽、股权穿透、公告舆情和行业研报核查。"
                "请输入公司名称、股票代码或具体行业。"
            )
            _emit_segment(state, unsupported_answer)
            return {
                "final_response": FinalResponse(
                    answer=unsupported_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        # Phase D #10: 行业级研报问题（无公司也能检索，如"白酒行业近期研报观点"）
        runtime = state.get("runtime")
        turn_id = getattr(runtime, "turn_id", "") if runtime else ""
        trace_id = getattr(runtime, "trace_id", "") if runtime else ""
        as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
        try:
            from app.application.services.research_search import (
                is_research_query,
                report_insights_enabled,
                search_research_insights_sync,
            )

            if (
                intent == "research" or is_research_query(user_query)
            ) and report_insights_enabled():
                insights = search_research_insights_sync(
                    user_query, top_k=3, as_of=as_of
                )
                # P2-1：先过滤可回查结果——只渲染成功生成 Evidence 的 insight
                research_evidence, research_claims, valid_insights = (
                    _research_evidence_and_claims(
                        insights,
                        company_code="",
                        turn_id=turn_id,
                        trace_id=trace_id,
                    )
                )
                if valid_insights:
                    parts = []
                    for it in valid_insights[:3]:
                        src = it.get("source_title") or "研报"
                        org = it.get("source_org", "")
                        label = f"{org}·{src}" if org else src
                        parts.append(f"{it.get('content', '')[:120]}（来源：{label}）")
                    answer = (
                        "未匹配到具体公司，以下是相关研报观点摘要："
                        + "；".join(parts)
                        + "。如需针对某家公司分析，请提供公司名称或股票代码。"
                    )
                    # #4：研报可回查 Evidence + research Claim（写入 AgentState + FinalResponse）
                    _emit_segment(state, answer)
                    return {
                        "final_response": FinalResponse(
                            answer=answer,
                            risk_level="unknown",
                            claims=research_claims,
                            evidence=research_evidence,
                        ),
                        "claims": research_claims,
                        "evidence": research_evidence,
                    }
        except Exception:  # noqa: BLE001 — 研报检索失败不影响主流程
            logger.warning(
                "generate_answer: 行业研报检索失败，回退提示语", exc_info=True
            )

        if intent == "research":
            fallback = (
                "当前数据覆盖范围内未找到与该主题匹配且可回查的研报。"
                "请补充更具体的行业、公司名称或研报关键词后重试。"
            )
            _emit_segment(state, fallback)
            return {
                "final_response": FinalResponse(
                    answer=fallback,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        fallback = "未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。"
        _emit_segment(state, fallback)
        return {
            "final_response": FinalResponse(
                answer=fallback,
                risk_level="unknown",
                claims=[],
                evidence=[],
            )
        }

    # R9：公司事实轻量回答（company_fact plan：requested_modules=[]，
    # 未执行 finance/equity/events/risk；诚实回答 + registry Evidence）
    plan = state.get("plan")
    # v3.3.3 批次 D：company 已识别但比较维度走页面的场景（单主体行业
    # 对比 → comparison_guide）——guide 分支在 company None 块内，
    # 此处补 company 非 None 的调用
    if getattr(plan, "intent", "") == "comparison_guide":
        return _answer_comparison_guide(state)
    if getattr(plan, "intent", "") == "indicator":
        return _answer_indicator(state, getattr(plan, "indicator", "") or "")
    # v3.3.3 批次 C：结构化轻量比较（同主体跨指标；批次 D 扩展跨公司）
    if getattr(plan, "intent", "") == "light_comparison":
        return _answer_light_comparison(state)
    if getattr(plan, "intent", "") == "company_fact":
        return _answer_company_fact(state, getattr(plan, "fact_key", "") or "")
    if getattr(plan, "answer_target", "") == "risk_level":
        return _answer_risk_level(state)

    # ① 一句话结论（Phase C：Finance 执行时限定母公司报表口径；
    # #11 AnswerMode：按意图选择开场模板，不再一律"综合分析完成"）
    # #8：风险计数只统计叶子信号（排除综合 risk Claim 与绿色控制链）
    risk_count = len(_leaf_risk_claims(claims))
    mode = _select_answer_mode(state, claims, finance_ran, finance_blocked)
    name_code = f"{company.sec_name}（{company.wind_code}）"
    if mode == "fraud_diagnosis":
        if risk_count:
            conclusion = (
                name_code + f"针对造假/舞弊疑点，共检测到 {risk_count} 项规则信号。"
            )
        else:
            conclusion = name_code + "针对造假/舞弊疑点，当前证据未能认定存在造假事实。"
    elif mode == "equity":
        conclusion = (
            name_code
            + "股权穿透分析完成，"
            + (
                f"发现 {risk_count} 项股权风险信号。"
                if risk_count
                else "未发现股权风险信号。"
            )
        )
    elif mode == "events":
        conclusion = (
            name_code
            + "舆情与事件分析完成，"
            + (
                f"检测到 {risk_count} 项风险信号。"
                if risk_count
                else "未发现明显异常信号。"
            )
        )
    elif risk_count:
        if finance_ran:
            # 口径限定：本分析基于母公司报表及当前数据覆盖
            conclusion = (
                name_code + "综合分析完成，" + RISK_SIGNAL_IN_SCOPE.format(n=risk_count)
            )
        else:
            conclusion = name_code + f"综合分析完成，共检测到 {risk_count} 项风险信号。"
    elif finance_unknown_type:
        # 公司类型缺失：不得输出"未发现风险"
        conclusion = (
            name_code
            + "公司类型信息缺失，无法执行非金融财务规则，无法确认是否存在财务风险。"
        )
    elif finance_blocked:
        conclusion = (
            name_code + "在母公司报表及当前数据覆盖范围内，财务规则因不适用/数据不足"
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

    # 分段组装（真流式：每构造完一个真实分层立即 push，再拼接完整 answer）
    segments: list[str] = []
    segments.append(conclusion)
    _emit_segment(state, conclusion)
    if summary:
        seg = summary + "。"
        segments.append(seg)
        _emit_segment(state, seg)
    if mode == "equity":
        equity_overview = _build_equity_overview(state)
        segments.append(equity_overview)
        _emit_segment(state, equity_overview)
    # B2 第二阶段：舆情影响结论段（事件模块有 impacts 才渲染；无则不渲染）
    impact_seg = _build_impact_conclusions_segment(state)
    if impact_seg:
        segments.append(impact_seg)
        _emit_segment(state, impact_seg)
    if rule_details:
        segments.append(rule_details)
        _emit_segment(state, rule_details)
    # #7/#12：确定性四段解读（无 LLM 自由生成；仅消费规则引擎 explanation/
    # current 与 pattern_matches；含 #9 免责段）
    for seg in _build_interpretation_segments(state, claims):
        segments.append(seg)
        _emit_segment(state, seg)

    # Phase D #10: 研报/公告语义检索（问题涉及研报/行业/评级时可选调用）
    user_query = state.get("user_query", "")
    research_seg = ""
    research_claims: list = []
    research_evidence: list = []
    try:
        from app.application.services.research_search import (
            is_research_query,
            report_insights_enabled,
            search_research_insights_sync,
        )

        if is_research_query(user_query) and report_insights_enabled():
            plan_r = state.get("plan")
            as_of_r = plan_r.as_of.strftime("%Y%m%d") if plan_r and plan_r.as_of else ""
            insights = search_research_insights_sync(user_query, top_k=3, as_of=as_of_r)
            # P2-1：先过滤可回查结果，只渲染成功生成 Evidence 的 insight
            company_code_r = company.wind_code if company else ""
            runtime_r = state.get("runtime")
            research_evidence, research_claims, valid_insights = (
                _research_evidence_and_claims(
                    insights,
                    company_code=company_code_r,
                    turn_id=getattr(runtime_r, "turn_id", "") if runtime_r else "",
                    trace_id=getattr(runtime_r, "trace_id", "") if runtime_r else "",
                )
            )
            if valid_insights:
                parts = []
                for it in valid_insights[:3]:
                    src = it.get("source_title") or "研报"
                    org = it.get("source_org", "")
                    label = f"{org}·{src}" if org else src
                    parts.append(f"{it.get('content', '')[:80]}（来源：{label}）")
                research_seg = "近期研报观点：" + "；".join(parts) + "。"
                segments.append(research_seg)
                _emit_segment(state, research_seg)
    except Exception:  # noqa: BLE001 — 检索失败不影响主回答
        logger.warning("generate_answer: 研报检索段失败，跳过", exc_info=True)

    answer = "".join(segments)

    # #7：LLM 润色默认关闭（确定性输出优先，避免自由生成引入无证据推断）；
    # 保留 _polish_answer（含事实校验回退）供 ANSWER_POLISH_ENABLED 开关启用
    if not streaming and getattr(settings, "ANSWER_POLISH_ENABLED", False):
        answer = _polish_answer(answer)

    # 风险等级：优先使用 risk 节点输出（否则回退 claim 最高严重度）
    risk_level = (
        (getattr(risk_output, "risk_level", "") or _highest_severity(claims))
        if (risk_output is not None or claims)
        else "unknown"
    )

    # #4：研报 Claim/Evidence 合并进 FinalResponse（reducer 会再合并进
    # AgentState，validate_evidence → persist_turn 因此可完整落库/回查）
    final_claims = _merge_unique(claims + research_claims, key=lambda c: c.claim_id)
    final_evidence = _merge_unique(
        evidence + research_evidence, key=lambda e: e.evidence_id
    )

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level=risk_level,
            claims=final_claims,
            evidence=final_evidence,
            follow_ups=_build_follow_ups(state),
        ),
        "claims": research_claims,
        "evidence": research_evidence,
    }
