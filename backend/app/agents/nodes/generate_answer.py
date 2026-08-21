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
_CONSOLIDATED_SCOPE_KW = ("合并口径", "合并报表")
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


def _is_unsupported_market_query(query: str) -> bool:
    return any(cue in (query or "") for cue in _UNSUPPORTED_MARKET_CUES)


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


def _build_company_brief_analysis(
    state: AgentState, claims: list, risk_output=None
) -> str:
    """公司宽泛提问的轻量综合分析：一句判断 + 少量事实，不扩成新模块。"""
    company = state.get("company")
    if company is None:
        return ""
    plan = state.get("plan")
    query = state.get("user_query", "")
    if getattr(plan, "intent", "") != "analysis" and not any(
        cue in query for cue in ("怎么样", "如何", "情况", "表现")
    ):
        return ""

    financial = [c for c in claims if c.claim_type == "financial"]
    equity = [c for c in claims if c.claim_type == "equity"]
    events = [c for c in claims if c.claim_type == "event"]
    risk_level = (
        getattr(risk_output, "risk_level", "") or _highest_severity(claims) or "unknown"
    )
    risk_label = _SEVERITY_LABELS.get(risk_level, "数据不足")
    if risk_level in ("red", "orange", "yellow"):
        stance = "偏谨慎，建议重点核验财务、股权和舆情是否同向"
    elif risk_level == "green":
        stance = "当前未见明显异常"
    else:
        stance = "数据覆盖仍有限，暂不能下定论"

    parts: list[str] = [f"【简要分析】{company.sec_name}整体判断：{stance}"]
    if risk_output is not None:
        as_of = getattr(risk_output, "as_of", "") or ""
        if as_of:
            parts.append(f"数据截止日 {as_of[:4]}-{as_of[4:6]}-{as_of[6:]}")
    if financial:
        rule_ids = sorted({c.rule_id for c in financial if c.rule_id})
        rule_text = "、".join(rule_ids[:3]) or "多条规则"
        parts.append(f"财务信号 {len(financial)} 项（{rule_text}）")
    if equity:
        parts.append(f"股权信号 {len(equity)} 项")
    if events:
        parts.append(f"事件信号 {len(events)} 项")
    if not financial and not equity and not events:
        parts.append(f"当前仅有综合风险等级 {risk_label}")
    return "；".join(parts) + "。"


def _build_cross_module_observation(state: AgentState, claims: list) -> str:
    """把多模块信号收敛为可行动的核验优先级，不推导未经验证的因果。"""
    plan = state.get("plan")
    if plan is None or len(getattr(plan, "requested_modules", []) or []) < 2:
        return ""
    financial = [
        c
        for c in claims
        if c.claim_type == "financial" and c.severity in _RISK_SEVERITIES
    ]
    equity = [
        c for c in claims if c.claim_type == "equity" and c.severity in _RISK_SEVERITIES
    ]
    events = [
        c for c in claims if c.claim_type == "event" and c.severity in _RISK_SEVERITIES
    ]
    cross = [c for c in claims if c.claim_type == "cross_validation"]
    observations: list[str] = []
    if financial and events:
        observations.append(
            "财务规则信号与负面事件同时出现，应优先核对事件日期是否覆盖财务异常期；"
            "[推断] 当前只能确认共现，不能确认因果"
        )
    if financial and equity:
        observations.append(
            "财务与股权维度同时出现风险信号，建议把控制关系、关联方和异常科目放在同一证据链中复核"
        )
    if cross:
        observations.append(
            f"已有 {len(cross)} 项跨模块不一致，结论应以原始披露核验为先"
        )
    if not observations:
        active = [
            label
            for label, items in (
                ("财务", financial),
                ("股权", equity),
                ("事件", events),
            )
            if items
        ]
        if active:
            observations.append(
                f"当前可确认信号主要集中在{'、'.join(active)}维度，尚未形成多模块一致指向"
            )
    return "【综合观察】" + "；".join(observations) + "。" if observations else ""


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

    # 【数据对比】：只格式化 rule_details.current；多条指标用表格便于核对。
    pairs: list[str] = []
    metric_rows: list[tuple[str, str, str]] = []
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
                value_text = f"{_format_number_value(val, unit)}{unit}"
                pairs.append(f"{label} {value_text}")
                raw_unit = str(v.get("unit", "") or "")
                table_unit = unit or {"ratio": "比值"}.get(raw_unit, raw_unit)
                row = (label, value_text, table_unit)
                if row not in metric_rows:
                    metric_rows.append(row)
    if pairs:
        if len(metric_rows) >= 2:
            table = [
                "【数据对比】",
                "",
                "| 指标 | 数值 | 单位 |",
                "|---|---:|---|",
                *[
                    f"| {label.replace('|', '｜')} | {value.replace('|', '｜')} | "
                    f"{table_unit or '暂无'} |"
                    for label, value, table_unit in metric_rows
                ],
            ]
            segs.append("\n".join(table))
        else:
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


def _module_state(status) -> str:
    if isinstance(status, dict):
        return str(status.get("state") or "")
    return str(getattr(status, "state", "") or "")


def _degraded_module_summary(state: AgentState) -> str:
    """返回本轮已请求但未成功模块的中文摘要，用于避免无信号 fail-open。"""
    module_status = state.get("module_status") or {}
    plan = state.get("plan")
    requested = list(getattr(plan, "requested_modules", []) or [])
    if not requested:
        requested = list(module_status.keys())

    degraded = []
    for module in requested:
        status = _module_state(module_status.get(module))
        if status in _MODULE_STATE_LABELS:
            module_label = _MODULE_LABELS.get(str(module), str(module))
            state_label = _MODULE_STATE_LABELS[status]
            degraded.append(f"{module_label}模块{state_label}")
    return "、".join(degraded)


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

# Phase E 会5：可联网回填的公司事实键（首个示范触发点 = listing_date）。
# 仅库内无值时触发；默认 off 时 web_search 返回 []，行为与现状完全一致。
_WEB_SEARCHABLE_FACTS: frozenset[str] = frozenset(
    {"listing_date", "executive_compensation", "ipo_price"}
)


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
        extract_executive_compensation_excerpt,
        extract_ipo_price_from_hits,
        extract_listing_date_from_hits,
    )
    from app.application.services.web_search_service import web_search

    # 8/19 审查：所有候选 query 均保留 wind_code，避免同名公司串线；
    # 不把公司事实降级到质量不稳定的无代码通用检索。
    queries = _company_fact_search_queries(sec_name, wind_code, fact_key, label)
    hits = []
    value: str | None = None
    field = ""
    for query in queries:
        candidate_hits = web_search(query)
        if fact_key == "listing_date":
            candidate_value = extract_listing_date_from_hits(candidate_hits)
            field = "listing_date"
        elif fact_key == "ipo_price":
            candidate_value = extract_ipo_price_from_hits(candidate_hits)
            field = "ipo_price"
        elif fact_key == "executive_compensation":
            candidate_value = extract_executive_compensation_excerpt(candidate_hits)
            field = "executive_compensation"
        else:
            candidate_value = None
        if candidate_value:
            hits = candidate_hits
            value = candidate_value
            break
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
        value=_clip_evidence_value(value),
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


def _clip_evidence_value(value: str | None, limit: int = 220) -> str | None:
    """证据值入库前做短截断，避免落库字段过长。"""
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _company_fact_search_queries(
    sec_name: str, wind_code: str, fact_key: str, label: str
) -> list[str]:
    """公司事实联网检索 query 列表。

    先走带代码的精确检索，再走仍带代码的补充检索。
    对于 IPO 价格/高管薪酬，第二条 query 显式补公告语义，避免只命中垂直
    行情/空结果。
    """
    base = f"{sec_name} {wind_code} {label} 交易所"
    if fact_key == "listing_date":
        return [
            base,
            f"{sec_name} {wind_code} 上市日期 上市公告书",
            f"{sec_name} {wind_code} 上市公告 上市日期",
        ]
    if fact_key == "ipo_price":
        return [
            f"{sec_name} {wind_code} 首发价格 发行价 公告",
            f"{sec_name} {wind_code} 首次公开发行 发行价格 上市公告",
        ]
    if fact_key == "executive_compensation":
        return [
            f"{sec_name} {wind_code} 高管薪酬 董监高薪酬 公告",
            f"{sec_name} {wind_code} 年报 高管薪酬 董监高报酬",
        ]
    return [base]


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
            if fact_key == "executive_compensation":
                answer = (
                    f"{sec_name}（{wind_code}）检索到高管薪酬相关公告摘要：{value}。"
                    "（来源链接见证据，具体人员和年度请以公告原文为准。）"
                )
            else:
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


def _answer_market_quote(state: AgentState, field: str) -> dict:
    """回答单个 AnySearch 行情字段，缺失时按字段诚实降级。"""
    from app.application.services.market_quote_service import (
        MARKET_FIELD_LABELS,
        format_market_value,
        query_market_quote,
    )

    company = state.get("company")
    label = MARKET_FIELD_LABELS.get(field, "行情字段")
    if company is None:
        answer = f"查询{label}需要先指定上市公司或股票代码。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    result = query_market_quote(
        sec_name=company.sec_name,
        wind_code=company.wind_code,
        field=field,
        user_query=state.get("user_query", ""),
    )
    name_code = f"{company.sec_name}（{company.wind_code}）"
    if result.status == "history_required":
        answer = (
            f"当前行情接口缺少回答{name_code}{label}所需的完整历史序列，"
            "无法用单日快照可靠替代。"
        )
    elif result.status == "field_missing":
        date_text = f" {result.trade_date}" if result.trade_date else ""
        answer = (
            f"已获取{name_code}{date_text}的行情快照，但数据源未返回{label}字段，"
            "无法可靠回答。"
        )
    elif result.status != "ok" or result.value is None:
        answer = f"当前未获取到{name_code}可回查的行情数据，无法可靠回答{label}。"
    else:
        rendered = format_market_value(field, result.value)
        date_text = result.trade_date
        if (
            any(word in state.get("user_query", "") for word in ("今天", "今日"))
            and not result.period_start
            and result.trade_date
        ):
            date_text = f"当前可获取的最近交易日为 {result.trade_date}"
        if result.period_start:
            date_text = f"{result.period_start}至{result.trade_date}"
        if field in ("amount", "volume"):
            answer = (
                f"{name_code} {date_text} 的{label}数据源原始值为{rendered}；"
                "接口规范未标明该字段单位。"
            )
        else:
            answer = f"{name_code} {date_text} 的{label}为{rendered}。"

    _emit_segment(state, answer)
    if result.status != "ok" or result.value is None or result.hit is None:
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    evidence_id = make_evidence_id(
        source_namespace=NS_WEB_SEARCH,
        source_type="web_search",
        source_record_id=f"{company.wind_code}:{result.trade_date}",
        field_path=f"market_quote.{field}",
        period=result.trade_date,
        company_code=company.wind_code,
    )
    quote_evidence = EvidenceRef(
        evidence_id=evidence_id,
        source_type="web_search",
        source_record_id=f"{company.wind_code}:{result.trade_date}",
        field_path=f"market_quote.{field}",
        period=result.trade_date,
        value=result.raw_value,
        source_title=result.hit.title or f"{company.sec_name} · AnySearch 行情",
        source_uri=result.hit.url or None,
        source_excerpt=result.hit.snippet or "",
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="market_quote",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    quote_claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="market_quote",
            claim_text=answer,
        ),
        text=answer,
        claim_type="market_quote",
        severity="unknown",
        evidence_ids=[evidence_id],
        verification_status="verified",
        limitations=["联网行情快照；交易日以数据源返回日期为准"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company.wind_code,
        module="market_quote",
    )
    return {
        "claims": [quote_claim],
        "evidence": [quote_evidence],
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=[quote_claim],
            evidence=[quote_evidence],
        ),
    }


def _answer_multi_metric(state: AgentState) -> dict:
    """一次返回并列指标，缺失字段逐项说明，不把问题强制拆开。"""
    company = state.get("company")
    plan = state.get("plan")
    if company is None:
        return {}
    query = state.get("user_query", "")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    require_exact = bool(plan and plan.as_of_kind == "report_period")
    requested: list[tuple[str, str]] = []
    if "总股本" in query:
        requested.append(("总股本", "unsupported"))
    if "营业收入" in query or "营收" in query:
        requested.append(("营业收入", "operating_revenue"))
    if "净资产" in query:
        requested.append(("净资产", "net_assets"))
    if "收盘价" in query or "收盘" in query:
        requested.append(("收盘价", "unsupported"))
    if "eps" in query.lower() or "每股收益" in query:
        requested.append(("EPS", "unsupported"))
    if not requested:
        answer = "未能识别并列指标，请补充具体财务指标名称。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    from app.application.services.indicator_query_service import query_metric

    lines = [
        f"{company.sec_name}（{company.wind_code}）并列指标结果：",
        "",
        "| 指标 | 数值 | 数据期与口径 |",
        "|---|---:|---|",
    ]
    all_evidence: list[EvidenceRef] = []
    for label, indicator in requested:
        if indicator == "unsupported":
            lines.append(f"| {label} | 暂无数据 | 当前数据范围未覆盖 |")
            continue
        result = query_metric(
            company.wind_code,
            indicator,
            as_of=as_of,
            require_exact_period=require_exact,
        )
        if result.status != "ok" or result.value is None:
            lines.append(f"| {label} | 暂无数据 | 母公司口径 |")
            continue
        period = result.period
        lines.append(
            f"| {label} | {_format_indicator_value(result.value, result.unit)} | "
            f"{period[:4]}-{period[4:6]}-{period[6:]}，母公司口径 |"
        )
        all_evidence.extend(
            _evidence_for_observations(state, company, result.observations)
        )
    answer = "\n".join(lines)
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": all_evidence,
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", evidence=all_evidence
        ),
    }


def _answer_directional_events(state: AgentState) -> dict | None:
    """只渲染用户请求方向的事件，避免混入相反情绪。"""
    plan = state.get("plan")
    direction = getattr(plan, "event_sentiment", "all") if plan else "all"
    list_requested = (
        bool(getattr(plan, "event_list_requested", False)) if plan else False
    )
    if direction == "all" and not list_requested:
        return None
    results = state.get("results")
    events = results.events if results else None
    if events is None:
        return None
    selected = sorted(
        (
            item
            for item in (events.timeline or [])
            if direction == "all" or str(item.get("sentiment", "") or "") == direction
        ),
        key=lambda item: str(item.get("date") or ""),
        reverse=True,
    )
    company = state.get("company")
    if company is None:
        return None
    name_code = f"{company.sec_name}（{company.wind_code}）"
    direction_label = {"positive": "利好", "negative": "利空"}.get(direction, "")
    query = str(state.get("user_query") or "")
    latest_requested = any(
        cue in query for cue in ("最新公告", "最新动态", "最近公告", "公告内容")
    )
    if not selected:
        label = f"{direction_label}事件" if direction_label else "公告或事件"
        answer = f"{name_code}近期未检出可回查的{label}。"
    else:
        rows = []
        for item in selected[:5]:
            date_text = str(item.get("date") or "")
            title = str(item.get("title") or item.get("category") or "公告")
            category = str(item.get("category") or "")
            evidence_id = ", ".join(
                str(i) for i in (item.get("evidence_ids") or []) if i
            )
            detail = f"{date_text} {title}".strip()
            if category and category not in title:
                detail += f"（{category}）"
            if evidence_id:
                detail += f" [证据: {evidence_id}]"
            rows.append(f"- {detail}")
        label = f"{direction_label}事件" if direction_label else "公告或事件"
        if latest_requested:
            latest_date = str(selected[0].get("date") or "未知")
            answer = (
                f"{name_code}数据集内最新可回查的{label}（截至 {latest_date}）：\n"
                + "\n".join(rows)
                + "\n当前事件数据仅保留公告标题和元数据，未取回公告正文；"
                "因此不能把上述记录表述为当前市场的最新公告。"
            )
        else:
            answer = f"{name_code}近期可回查的{label}：\n" + "\n".join(rows)
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": list(events.evidence or []),
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", evidence=list(events.evidence or [])
        ),
    }


def _research_relevant_excerpt(query: str, content: str) -> str:
    """从研报摘要中保留与问题相关的句子，避免把相邻营销信息当结论。"""
    normalized = " ".join(str(content or "").replace("\n", " ").split())
    if not normalized:
        return "暂无摘要"
    if not any(
        cue in query
        for cue in (
            "行业表现",
            "行业整体",
            "整体表现",
            "行业趋势",
            "发展趋势",
            "研发技术",
            "正在研发",
            "技术趋势",
            "新技术",
        )
    ):
        return normalized[:160].strip("。；; ")

    technology_query = any(
        cue in query for cue in ("研发技术", "正在研发", "技术趋势", "新技术", "AI医疗")
    )
    industry_query = any(
        cue in query
        for cue in ("行业表现", "行业整体", "整体表现", "行业趋势", "发展趋势")
    )
    cues = (
        (
            "技术",
            "研发",
            "产品",
            "人工智能",
            "AI",
            "机器人",
            "影像",
            "材料",
            "设备",
            "专利",
            "工艺",
        )
        if technology_query
        else (
            "行业",
            "市场",
            "规模",
            "增速",
            "增长",
            "需求",
            "竞争",
            "集采",
            "利润",
            "景气",
            "政策",
            "出口",
        )
    )
    noise = (
        "营销渠道",
        "销售渠道",
        "渠道拓展",
        "目标价",
        "买入评级",
        "增持评级",
        "估值",
        "评级",
        "EPS",
    )
    sentences = [
        part.strip(" 。；;，,")
        for part in re.split(r"[。！？；;\n]", normalized)
        if part.strip(" 。；;，, ")
    ]
    selected = [
        sentence
        for sentence in sentences
        if any(cue.lower() in sentence.lower() for cue in cues)
        and not any(term in sentence for term in noise)
        and not (industry_query and "公司" in sentence)
    ]
    if not selected:
        return normalized[:160].strip("。；; ")
    return "；".join(selected[:2])[:160].strip("。；; ")


def _format_research_insights(query: str, insights: list[dict]) -> str:
    """按问题类型整理研报结果，避免只拼接截断段落。"""
    if any(
        cue in query
        for cue in (
            "哪些个股",
            "竞争者",
            "竞争对手",
            "新兴公司",
            "新兴企业",
            "有哪些公司",
            "公司有哪些",
            "板块有哪些",
            "行业有哪些",
        )
    ):
        names: list[str] = []
        for item in insights:
            name = str(item.get("sec_name") or "").strip()
            if name and name not in names:
                names.append(name)
        if names:
            basic = "相关研报涉及的公司包括：" + "、".join(names[:8]) + "。"
            # 只有带可回查报告信息时才展开摘要；纯名称输入保持兼容，
            # 避免把没有来源的公司名包装成竞争关系或事实结论。
            rich_items = [
                item
                for item in insights
                if item.get("source_title") or item.get("report_id")
            ]
            if not rich_items:
                return basic
            rows = ["| 公司 | 研报依据 | 摘要 |", "|---|---|---|"]
            for item in rich_items[:8]:
                name = str(item.get("sec_name") or "暂无明确公司")
                source = str(item.get("source_title") or "研报").replace("|", "｜")
                content = _research_relevant_excerpt(
                    query, item.get("content") or "暂无摘要"
                )
                rows.append(
                    f"| {name} | {source[:80]} | {content[:160].replace('|', '｜')} |"
                )
            return basic + "\n\n" + "\n".join(rows)
    if any(cue in query for cue in ("研报", "机构评级", "券商评级")):
        rows = ["| 日期 | 机构 / 研报 | 核心观点 |", "|---|---|---|"]
        for item in insights[:5]:
            date_text = str(item.get("source_date") or "暂无数据")[:10]
            org = str(item.get("source_org") or "").strip()
            title = str(item.get("source_title") or "研报").strip()
            source = f"{org} · {title}" if org else title
            content = (
                str(item.get("content") or title).replace("\n", " ").replace("|", "｜")
            )
            rows.append(
                f"| {date_text} | {source.replace('|', '｜')} | {content[:140]} |"
            )
        return "\n".join(rows)
    parts = []
    for item in insights[:3]:
        src = item.get("source_title") or "研报"
        org = item.get("source_org", "")
        label = f"{org}·{src}" if org else src
        content = _research_relevant_excerpt(query, item.get("content") or "")
        if not content:
            content = str(item.get("source_title") or "暂无摘要").strip("。；; ")
        parts.append(f"{content}（来源：{label}）")
    result = "；".join(parts)
    if result and any(
        cue in query
        for cue in ("行业表现", "行业整体", "整体表现", "行业趋势", "发展趋势")
    ):
        return "研报样本显示：" + result + "。研报样本有限，不能代表全行业全部公司。"
    return result


def _answer_company_research(state: AgentState) -> dict:
    """直接回答单公司研报/评级问题，不先输出无关的综合风险模板。"""
    company = state.get("company")
    if company is None:
        return {}
    plan = state.get("plan")
    query = state.get("user_query", "")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    try:
        from app.application.services.research_search import (
            report_insights_enabled,
            search_research_insights_sync,
        )

        insights = (
            search_research_insights_sync(
                f"{company.sec_name} {company.wind_code} {query}",
                top_k=5,
                as_of=as_of,
            )
            if report_insights_enabled()
            else []
        )
        evidence, claims, valid = _research_evidence_and_claims(
            insights,
            company_code=company.wind_code,
            turn_id=turn_id,
            trace_id=trace_id,
        )
    except Exception:  # noqa: BLE001 - 检索失败按无可回查数据降级
        logger.warning("generate_answer: 单公司研报检索失败", exc_info=True)
        evidence, claims, valid = [], [], []

    name_code = f"{company.sec_name}（{company.wind_code}）"
    if valid:
        answer = f"{name_code}可回查的近期研报/评级：\n\n" + _format_research_insights(
            query, valid
        )
    else:
        answer = f"当前数据覆盖范围内未找到{name_code}可回查的近期研报或评级记录。"
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


def _indicator_impact_text(
    *, base_indicator: str, query: str, trend_rows: list, name_code: str
) -> str:
    """为影响类指标问题验证前提，再给出有限的财务解释。"""
    if base_indicator == "operating_cash_flow":
        return "问题未说明具体影响事件，当前数据无法建立该事件与现金流之间的因果关系。"
    if base_indicator != "accounts_receivable":
        return "仅凭该指标当前值无法确认实际影响，需要结合变化趋势和公告证据。"

    if len(trend_rows) >= 2 and trend_rows[-2].value:
        previous, current = trend_rows[-2], trend_rows[-1]
        growth = (current.value / abs(previous.value) - 1) * 100
        change = (
            f"{previous.period[:4]}年至{current.period[:4]}年{_format_growth(growth)}"
        )
        if "激增" in query and growth <= 20:
            return f"现有年度序列显示{change}，不支持“应收账款激增”这一前提。"
        return (
            f"现有年度序列显示{change}。"
            "[推断] 若应收账款增速持续高于营业收入，可能带来回款压力、"
            "坏账减值风险和利润现金含量下降；仍需结合账龄及客户集中度核验。"
        )
    return (
        f"当前数据不足以验证{name_code}应收账款是否激增。"
        "[推断] 若确有激增，可能带来回款压力、坏账减值风险和利润现金含量下降；"
        "不能仅凭单期余额确认。"
    )


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
    answer_operation = getattr(plan, "answer_operation", "") if plan else ""
    if not answer_operation:
        from app.agents.nodes.plan_modules import _detect_answer_operation

        answer_operation = _detect_answer_operation(state.get("user_query", ""))
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    require_exact = bool(plan and plan.as_of_kind == "report_period")
    # v3.3.3 批次 B：统一入口——registry 指标（r4/r5）与基础指标同构返回
    from app.application.services.indicator_query_service import (
        query_indicator_cagr,
        query_indicator_trend,
        query_metric,
        query_quarter_mom,
        query_quarter_value,
        query_quarter_yoy,
    )

    base_indicator = indicator.removesuffix("_growth").removesuffix("_mom")
    name_code = f"{company.sec_name}（{company.wind_code}）"
    # 趋势问题先读取年度序列，不能先查询最新单期再决定如何回答。
    if answer_operation in ("trend", "causal_trend", "loss_years"):
        query_text = state.get("user_query", "")
        quarterly_trend = bool(
            re.search(r"(?:第?[一二三四1-4]季度|Q[1-4])", query_text, re.IGNORECASE)
        )
        rows = query_indicator_trend(
            company.wind_code,
            base_indicator,
            as_of=as_of,
            annual_only=not quarterly_trend,
        )
        labels = {
            "operating_revenue": "营业收入",
            "net_profit": "净利润",
            "operating_cash_flow": "经营现金流",
            "total_assets": "总资产",
            "total_liabilities": "总负债",
            "accounts_receivable": "应收账款余额",
            "inventories": "存货",
            "r4_turnover_days": "存货周转天数",
            "r5_gross_margin": "毛利率",
        }
        label = labels.get(base_indicator, base_indicator)
        if len(rows) >= 2:
            from app.domain.benchmarks.metric_registry import REGISTRY

            trend_unit = "CNY"
            if base_indicator in REGISTRY:
                trend_unit = REGISTRY[base_indicator].unit

            def period_label(period: str) -> str:
                if quarterly_trend:
                    quarter = {"0331": "Q1", "0630": "Q2", "0930": "Q3", "1231": "Q4"}
                    return f"{period[:4]}{quarter.get(period[4:], period[4:])}"
                return f"{period[:4]}年"

            sequence_label = "季度" if quarterly_trend else "年度"
            table = [
                f"{name_code}的{label}{sequence_label}序列：",
                "",
                f"| {sequence_label} | {label} |",
                "|---|---:|",
                *[
                    f"| {period_label(row.period)} | "
                    f"{_format_indicator_value(row.value, trend_unit)} |"
                    for row in rows
                ],
            ]
            if answer_operation == "loss_years":
                consecutive = 0
                for row in reversed(rows):
                    if row.value < 0:
                        consecutive += 1
                    else:
                        break
                conclusion = (
                    f"截至最新可用年度，连续亏损 {consecutive} 年。"
                    if consecutive
                    else "截至最新可用年度，未处于连续亏损状态。"
                )
            else:
                conclusion = (
                    "持续下降。"
                    if all(a.value > b.value for a, b in zip(rows, rows[1:]))
                    else "未呈连续下降。"
                )
            answer = "\n".join(table) + "\n\n" + conclusion
            if answer_operation == "causal_trend":
                answer += "仅凭该指标序列无法确认原因，需要结合成本结构和公告证据。"
        else:
            answer = (
                f"{name_code}的{label}：暂不支持多年序列趋势，当前可用年度序列不足，"
                "不会用最新一期结果代替。"
            )
        _emit_segment(state, answer)
        trend_evidence = []
        for row in rows:
            trend_evidence.extend(
                _evidence_for_observations(
                    state, company, getattr(row, "observations", None) or []
                )
            )
        trend_evidence = _merge_unique(
            trend_evidence, key=lambda item: item.evidence_id
        )
        return {
            "claims": [],
            "evidence": trend_evidence,
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", evidence=trend_evidence
            ),
        }
    if answer_operation == "cagr":
        result = query_indicator_cagr(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_yoy":
        result = query_quarter_yoy(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_single":
        result = query_quarter_value(company.wind_code, base_indicator, as_of=as_of)
    elif answer_operation == "quarter_mom":
        result = query_quarter_mom(company.wind_code, base_indicator, as_of=as_of)
    else:
        result = query_metric(
            company.wind_code,
            indicator,
            as_of=as_of,
            require_exact_period=require_exact,
        )
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

    # 多年趋势不得退化成最新单期。基础指标有年度序列时直接展示序列；
    # registry 指标暂无序列时也明确说明缺口。
    if answer_operation in ("trend", "causal_trend"):
        rows = query_indicator_trend(company.wind_code, base_indicator, as_of=as_of)
        if len(rows) >= 2:
            values = "；".join(
                f"{row.period[:4]}年 {_format_indicator_value(row.value, result.unit)}"
                for row in rows
            )
            direction = (
                "持续下降"
                if all(a.value > b.value for a, b in zip(rows, rows[1:]))
                else "未呈连续下降"
            )
            answer = f"{name_code}的{result.label}年度序列：{values}。{direction}。"
            if answer_operation == "causal_trend":
                answer += "仅凭该指标序列无法确认原因，需要结合成本结构和公告证据。"
        else:
            answer = (
                f"{name_code}的{result.label}：当前可用年度序列不足，"
                "无法确认多年趋势或原因，不用最新一期代替。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }

    # v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类问句走 assessment，
    # 只答数值时不得用泛化话术冒充判断
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
    elif answer_operation == "turnaround":
        status_text = "已实现扭亏为盈" if result.value >= 0 else "尚未扭亏为盈"
        answer = (
            f"{name_code}的{result.label}为 {value_text}"
            f"（{period_text}，母公司口径），{status_text}。"
        )
        claim_value_text = value_text
    else:
        answer = (
            f"{name_code}的{result.label}为 {value_text}"
            f"（{period_text}，母公司口径）。"
        )
        claim_value_text = value_text

    if answer_operation == "cagr":
        start_period = result.observations[0].period if result.observations else ""
        end_period = (
            result.observations[-1].period if result.observations else result.period
        )
        answer = (
            f"{name_code}的{result.label}为 {result.value:.2f}%"
            f"（{start_period[:4]}-{end_period[:4]}年，母公司口径）。"
        )
        claim_value_text = f"{result.value:.2f}%"
    elif answer_operation == "causal":
        answer += "仅凭该指标当前值无法确认下降原因，需要结合期间序列和公告证据。"
    elif answer_operation == "impact":
        trend_rows = query_indicator_trend(
            company.wind_code,
            base_indicator,
            as_of=as_of,
            annual_only=True,
        )
        answer += _indicator_impact_text(
            base_indicator=base_indicator,
            query=state.get("user_query", ""),
            trend_rows=trend_rows,
            name_code=name_code,
        )

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
    query = state.get("user_query", "")
    if "平均" in query:
        mean_value = bench.get("mean_value")
        if mean_value is None:
            answer = base_answer + "行业平均值缺失，无法完成比较。"
        else:
            mean_text = _bench_display(mean_value)
            if "低于" in query:
                relation = "低于" if value_raw < mean_value else "不低于"
            else:
                relation = "高于" if value_raw > mean_value else "不高于"
            answer = (
                base_answer
                + f"{result.label}{relation}行业平均值"
                + f"（平均值 {mean_text}，{sample_count} 家可比公司）。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

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


def _answer_industry_benchmark(state: AgentState) -> dict:
    """回答无公司行业均值/趋势，使用真实基准行而非任意公司值。"""
    plan = state.get("plan")
    industry = getattr(plan, "industry_l1", "") if plan else ""
    indicator = getattr(plan, "indicator", "") if plan else ""
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    operation = getattr(plan, "answer_operation", "") if plan else ""
    if operation in ("industry_leader", "industry_total"):
        answer = (
            f"当前行业基准只提供行业均值和分位，未覆盖"
            f"{'行业营业收入总额' if operation == 'industry_total' else '按指标排序个股'}；"
            f"无法可靠回答「{industry}」的该问题。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    from app.application.services.indicator_query_service import (
        query_industry_benchmark_series,
    )

    rows = query_industry_benchmark_series(industry, indicator, as_of=as_of)
    try:
        from app.domain.benchmarks.metric_registry import get_metric

        metric_label = get_metric(indicator).name
    except KeyError:
        metric_label = indicator
    if not rows:
        answer = f"行业「{industry}」暂无{metric_label}的可用母公司口径基准数据。"
    else:
        try:
            from app.domain.benchmarks.metric_registry import get_metric

            is_ratio = get_metric(indicator).unit == "ratio"
        except KeyError:
            is_ratio = False

        def display(value) -> str:
            if value is None:
                return "—"
            return f"{float(value) * 100:.2f}%" if is_ratio else f"{float(value):.2f}"

        if operation == "trend" and len(rows) >= 2:
            values = "；".join(
                f"{row['period'][:4]}年 {display(row['mean_value'])}" for row in rows
            )
            answer = f"行业「{industry}」的{metric_label}年度均值：{values}。"
        else:
            row = rows[-1]
            answer = (
                f"行业「{industry}」最新可用期 {row['period']} 的{metric_label}平均值为 "
                f"{display(row['mean_value'])}（{row['sample_count']} 家可比公司，母公司口径）。"
            )
            if operation == "trend":
                answer += "可用年度序列不足，无法判断多年变化。"
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": [],
        "final_response": FinalResponse(answer=answer, risk_level="unknown"),
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
    if ok_rows:
        first_name = str(getattr(targets[0], "sec_name", "公司A"))
        second_name = str(getattr(targets[1], "sec_name", "公司B"))
        table = [
            f"{names}概览",
            "",
            f"| 指标 | {first_name} | {second_name} | 共同期间 | 对比结论 |",
            "|---|---:|---:|---|---|",
        ]
        for row in ok_rows:
            first, second = row.values
            conclusion = str(row.conclusion or "").replace("|", "｜")
            table.append(
                f"| {row.metric_label} | {_fmt(first.value, row.unit)} | "
                f"{_fmt(second.value, row.unit)} | {row.period} | {conclusion} |"
            )
        missing = [r.metric_label for r in result.overview_rows if r.status != "ok"]
        answer = "\n".join(table)
        if missing:
            answer += "\n\n暂无共同可比数据：" + "、".join(missing) + "。"
        if result.conclusion:
            answer += "\n\n" + result.conclusion
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

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""

    comparison_targets = list(targets)
    web_evidence_by_code: dict[str, EvidenceRef] = {}
    if getattr(spec, "fact_key", "") == "listing_date":
        for index, target in enumerate(comparison_targets):
            if str(getattr(target, "listing_date", "") or "").strip():
                continue
            value, web_evidence = _web_search_fill_company_fact(
                sec_name=str(target.sec_name),
                wind_code=str(target.wind_code),
                fact_key="listing_date",
                label="上市日期",
                turn_id=turn_id,
                trace_id=trace_id,
            )
            if value:
                comparison_targets[index] = target.model_copy(
                    update={"listing_date": value}
                )
            if web_evidence is not None:
                web_evidence_by_code[str(target.wind_code)] = web_evidence

    result = compare_cross_company_facts(comparison_targets, spec)

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
    for target in comparison_targets:
        date_value = str(getattr(target, "listing_date", "") or "")
        if not date_value:
            continue
        web_evidence = web_evidence_by_code.get(str(target.wind_code))
        if web_evidence is not None:
            evidence.append(web_evidence)
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

        if intent == "industry_benchmark":
            return _answer_industry_benchmark(state)
        if intent == "unsupported_indicator":
            answer = (
                f"当前数据覆盖范围暂不支持查询「{user_query}」，无法可靠返回该指标。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }
        if intent in ("investment_advice", "trade_execution"):
            answer = (
                "系统不能代为买卖证券或提交交易指令。"
                if intent == "trade_execution"
                else "系统不提供是否买入或卖出的投资建议。"
            )
            answer += "可以查询客观行情，或核查财务、股权与公告风险后自行判断。"
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }
        if intent in ("causal_query", "unsupported_scope"):
            answer = (
                "当前系统不接入行情价格因果归因，无法仅凭财报、股权和公告模块确认这次涨跌原因。"
                if intent == "causal_query"
                else "当前系统固定使用母公司报表口径，不能切换为合并口径；本轮不返回替代口径数值。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }

        if getattr(plan, "event_list_requested", False):
            answer = (
                "当前公告/事件列表查询需要先指定上市公司或股票代码；"
                "系统暂不提供全市场公告的完整索引，不能据此确认所有上市公司的股权质押公告。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }

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
            if _is_unsupported_market_query(user_query):
                answer = (
                    "当前只支持可识别的单只 A 股行情快照，未覆盖板块、指数、"
                    "期货、基金的行情，也不提供交易建议或市场资金流数据。"
                )
                _emit_segment(state, answer)
                return {
                    "final_response": FinalResponse(answer=answer, risk_level="unknown")
                }
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
                list_query = any(
                    cue in user_query
                    for cue in (
                        "哪些个股",
                        "竞争者",
                        "竞争对手",
                        "新兴公司",
                        "新兴企业",
                        "有哪些公司",
                        "公司有哪些",
                        "板块有哪些",
                        "行业有哪些",
                    )
                )
                insights = search_research_insights_sync(
                    user_query, top_k=8 if list_query else 3, as_of=as_of
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
                    parts = _format_research_insights(user_query, valid_insights)
                    answer = (
                        "当前问题未指定具体公司，以下是相关研报观点摘要："
                        + parts.rstrip("。")
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
    if getattr(plan, "intent", "") == "research":
        return _answer_company_research(state)
    if getattr(plan, "intent", "") == "industry_benchmark":
        return _answer_industry_benchmark(state)
    if getattr(plan, "intent", "") == "market_quote":
        return _answer_market_quote(state, getattr(plan, "market_field", "") or "")
    if getattr(plan, "intent", "") == "unsupported":
        answer = (
            "这个问题超出了织网鉴真的服务范围。我专注于上市公司财务勾稽、"
            "股权穿透、公告舆情和行业研报核查。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") in ("investment_advice", "trade_execution"):
        name_code = f"{company.sec_name}（{company.wind_code}）"
        boundary = (
            f"{name_code}：系统不能代为买卖证券或提交交易指令。"
            if plan.intent == "trade_execution"
            else f"{name_code}：系统不提供是否买入或卖出的投资建议。"
        )
        answer = (
            boundary + "可以继续查询客观行情，或核查财务、股权与公告风险后自行判断。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") == "causal_query":
        answer = "当前系统不接入行情价格因果归因，无法仅凭财报、股权和公告模块确认这次涨跌原因。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    query = state.get("user_query", "")
    if getattr(plan, "intent", "") == "unsupported_indicator":
        answer = f"当前数据覆盖范围暂不支持查询「{query}」，无法可靠返回该指标。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") == "unsupported_scope" or any(
        keyword in query for keyword in _CONSOLIDATED_SCOPE_KW
    ):
        if "行业" in query and re.search(r"所属|所在", query):
            answer = (
                "当前行业基准只提供行业均值和分位，未覆盖该行业的整体汇总或个股排名，"
                "无法可靠回答这项行业统计。"
            )
        else:
            answer = (
                "当前系统固定使用母公司报表口径，不能切换为合并口径。"
                "本轮不返回可能被误解为合并口径的分析结果。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    # v3.3.3 批次 D：company 已识别但比较维度走页面的场景（单主体行业
    # 对比 → comparison_guide）——guide 分支在 company None 块内，
    # 此处补 company 非 None 的调用
    if getattr(plan, "intent", "") == "comparison_guide":
        return _answer_comparison_guide(state)
    directional_events = _answer_directional_events(state)
    if directional_events is not None:
        return directional_events
    if getattr(plan, "intent", "") == "indicator":
        return _answer_indicator(state, getattr(plan, "indicator", "") or "")
    # v3.3.3 批次 C：结构化轻量比较（同主体跨指标；批次 D 扩展跨公司）
    if getattr(plan, "intent", "") == "light_comparison":
        return _answer_light_comparison(state)
    if getattr(plan, "intent", "") == "company_fact":
        return _answer_company_fact(state, getattr(plan, "fact_key", "") or "")
    if getattr(plan, "intent", "") == "multi_metric":
        return _answer_multi_metric(state)
    if getattr(plan, "answer_target", "") == "risk_level":
        return _answer_risk_level(state)

    # ① 一句话结论（Phase C：Finance 执行时限定母公司报表口径；
    # #11 AnswerMode：按意图选择开场模板，不再一律"综合分析完成"）
    # #8：风险计数只统计叶子信号（排除综合 risk Claim 与绿色控制链）
    risk_count = len(_leaf_risk_claims(claims))
    degraded_summary = _degraded_module_summary(state)
    mode = _select_answer_mode(state, claims, finance_ran, finance_blocked)
    name_code = f"{company.sec_name}（{company.wind_code}）"
    if mode == "fraud_diagnosis":
        if risk_count:
            conclusion = (
                name_code + f"针对造假/舞弊疑点，共检测到 {risk_count} 项规则信号。"
            )
        elif degraded_summary:
            conclusion = (
                name_code
                + f"针对造假/舞弊疑点，本轮分析未完整完成（{degraded_summary}），"
                + "无法确认是否存在造假事实或异常信号。"
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
                else (
                    f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在股权风险信号。"
                    if degraded_summary
                    else "未发现股权风险信号。"
                )
            )
        )
    elif mode == "events":
        conclusion = (
            name_code
            + "舆情与事件分析完成，"
            + (
                f"检测到 {risk_count} 项风险信号。"
                if risk_count
                else (
                    f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在明显异常信号。"
                    if degraded_summary
                    else "未发现明显异常信号。"
                )
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
    elif degraded_summary:
        conclusion = (
            name_code
            + f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在明显异常信号。"
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

    def append_segment(text: str) -> None:
        if not text:
            return
        rendered = text.strip()
        if segments:
            rendered = "\n\n" + rendered
        segments.append(rendered)
        _emit_segment(state, rendered)

    append_segment(conclusion)
    requested_period = getattr(plan, "requested_period_text", "") if plan else ""
    financial_claims = [
        c for c in claims if getattr(c, "claim_type", "") == "financial"
    ]
    if (
        requested_period
        and getattr(plan, "as_of_kind", "") == "report_period"
        and not financial_claims
    ):
        append_segment(
            f"未提取到{requested_period}可核验的财务指标；本次股权或事件信号"
            "不能替代该报告期的财务分析。"
        )
    if summary:
        seg = summary + "。"
        append_segment(seg)
    brief = _build_company_brief_analysis(state, claims, risk_output=risk_output)
    if brief:
        append_segment(brief)
    append_segment(_build_cross_module_observation(state, claims))
    if mode == "equity":
        equity_overview = _build_equity_overview(state)
        append_segment(equity_overview)
    # B2 第二阶段：舆情影响结论段（事件模块有 impacts 才渲染；无则不渲染）
    impact_seg = _build_impact_conclusions_segment(state)
    if impact_seg:
        append_segment(impact_seg)
    if rule_details:
        append_segment(rule_details)
    # #7/#12：确定性四段解读（无 LLM 自由生成；仅消费规则引擎 explanation/
    # current 与 pattern_matches；含 #9 免责段）
    for seg in _build_interpretation_segments(state, claims):
        append_segment(seg)

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
            list_query = any(
                cue in user_query
                for cue in (
                    "哪些个股",
                    "竞争者",
                    "竞争对手",
                    "新兴公司",
                    "新兴企业",
                    "值得关注",
                )
            )
            insights = search_research_insights_sync(
                user_query, top_k=8 if list_query else 3, as_of=as_of_r
            )
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
                research_seg = "近期研报观点：" + _format_research_insights(
                    user_query, valid_insights
                )
                append_segment(research_seg)
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
