"""_answer_headline — generate_answer 拆分模块（重构生成，函数体与原文件逐字节一致）。"""

from __future__ import annotations

import logging
from ._answer_common import (
    CHAT_RISK_DISCLAIMER,
    _FRAUD_KEYWORDS,
    _IMPACT_DIRECTION_LABELS,
    _IMPACT_SEVERITY_LABELS,
    _IMPACT_TYPE_LABELS,
    _METRIC_LABELS,
    _METRIC_UNITS,
    _MODULE_LABELS,
    _MODULE_STATE_LABELS,
    _R7_FOLLOW_UP_FULL,
    _R7_FOLLOW_UP_SIMPLIFIED,
    _RISK_SEVERITIES,
    _RULE_FOLLOW_UP,
    _SEVERITY_LABELS,
    _dedup,
    _emit_segment,
    _extract_key_facts,
    _extract_markers,
    _format_metrics,
    _format_number_value,
    _highest_severity,
    _leaf_risk_claims,
    _module_state,
)
from app.agents.llm_sync import run_llm_chat
from app.agents.state import AgentState, FinalResponse
import re

logger = logging.getLogger(__name__)


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
    # 8/22 晚全量 1410（row 729/710）复盘：期次缺失提示已统一在
    # generate_answer 主流程（conclusion 后、summary 前）输出，覆盖
    # diagnose/analysis 全路径；此处不再重复提示（避免同一回答出现
    # 两段"请求期数据可能缺失"），仅保留数据截止日信息。
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

    # 【预警点】：触发规则的真实 explanation（8/23 编号换行，避免大段刷屏）
    triggers: list[str] = []
    if finance and finance.rule_details:
        for rid in sorted(finance.rule_details):
            if finance.rule_statuses.get(rid) != "triggered":
                continue
            expl = str((finance.rule_details[rid] or {}).get("explanation") or "")
            if expl:
                triggers.append(f"{rid}：{expl}")
    if triggers:
        segs.append(
            "【预警点】\n"
            + "\n".join(f"{i}. {t}" for i, t in enumerate(triggers, start=1))
        )

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

    # 【可能模式】：只消费 pattern_matches（8/23 编号换行，避免大段刷屏）
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
        segs.append(
            "【可能模式】\n"
            + "\n".join(f"{i}. {p}" for i, p in enumerate(parts, start=1))
        )
    elif has_content:
        # P2-5：无模式命中时输出占位（不得省略导致四段缺失）
        segs.append("【可能模式】当前规则组合未匹配预定义模式，需进一步验证。")

    # 【限制说明】：口径/覆盖/降级状态（去重保序；8/23 覆盖率聚合防刷屏）
    limitations: list[str] = []
    if finance and finance.warnings:
        # 覆盖率警告（"XX 覆盖率仅 38%（有效 3/8 期）"）按覆盖值聚合：
        # 相同覆盖率的多字段合并为一条"N 个字段覆盖率仅 X%（有效 a/b 期）"，
        # 避免 14+ 条字段级刷屏。其他 warning（口径/字段不可用等）保留原样。
        import re as _re

        cov_pattern = re.compile(r"^(\w+) 覆盖率仅 (\d+)%（有效 (\d+)/(\d+) 期）$")
        cov_buckets: dict[tuple[str, str, str], list[str]] = {}
        other_warnings: list[str] = []
        for w in finance.warnings:
            m = cov_pattern.match(w or "")
            if m:
                field, pct, valid, total = m.groups()
                bucket_key = (pct, valid, total)
                cov_buckets.setdefault(bucket_key, []).append(field)
            else:
                if w and w not in other_warnings:
                    other_warnings.append(w)
        for (pct, valid, total), fields in sorted(
            cov_buckets.items(), key=lambda kv: (int(kv[0][0]), -len(kv[1]))
        ):
            limitations.append(
                f"{len(fields)} 个字段覆盖率仅 {pct}%（有效 {valid}/{total} 期）"
            )
        limitations.extend(other_warnings)
    for name, ms in (state.get("module_status") or {}).items():
        if getattr(ms, "state", "") in ("partial", "failed"):
            # 8/23 可读性：模块状态转中文（"模块 events 状态: partial"
            # 用户看不懂 → "舆情事件模块部分完成，数据可能不完整"）
            module_label = _MODULE_LABELS.get(str(name), str(name))
            state_label = _MODULE_STATE_LABELS.get(
                str(getattr(ms, "state", "")), str(getattr(ms, "state", ""))
            )
            w = f"{module_label}模块{state_label}，相关数据可能不完整"
            if w not in limitations:
                limitations.append(w)
    if limitations:
        # 8/23：剥离每条末尾标点（warning 自带"。"，直接 join 会出
        # "数据。；模块"叠用），统一用"；"连接、末尾单个"。"
        joined = "；".join(str(lim).rstrip("。；；,，") for lim in limitations)
        segs.append("【限制说明】" + joined + "。")
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
        # 8/22 后测集 row 998：十大股东明细只列 5 家 → 展示上限与
        # _latest_shareholders（数据侧 10 家）对齐。
        for item in shareholders[:10]:
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

    # 8/23 follow-up 收敛：固定规则文案集，全部可定向路由——
    # 无任何可追问内容时不输出兜底发散项（如"查看企业画像详情"），
    # 避免用户点击后得不到对应数据（答非所问）。前端 follow_ups 为空
    # 时自动隐藏按钮区。
    return _dedup(follow_ups)


def _answer_rule_detail(state: AgentState, rule_id: str = "") -> dict:
    """8/23 follow-up 定向路由：直接渲染指定规则（或全部已触发规则）的
    指标明细，不重新执行综合分析模板（"查看其他应收款明细"等 follow-up
    点击后落 diagnose 答非所问的修复）。

    - rule_id 非空：只展示该规则；rule_id 空：展示全部已触发规则。
    - 规则未触发 / 数据不足：诚实说明，不伪造数值。
    - 依赖 finance 模块执行结果（plan.requested_modules=["finance"]）。
    """
    company = state.get("company")
    if company is None:
        return {}
    results = state.get("results")
    finance = results.finance if results else None
    name_code = f"{company.sec_name}（{company.wind_code}）"

    rule_details = (finance.rule_details or {}) if finance else {}
    rule_statuses = (finance.rule_statuses or {}) if finance else {}

    # 目标规则列表：指定 rule_id；空 → 全部已触发规则
    if rule_id:
        target_ids = [rule_id] if rule_id in rule_details else []
    else:
        target_ids = sorted(
            rid for rid, st in (rule_statuses or {}).items() if st == "triggered"
        )

    lines: list[str] = []
    for rid in target_ids:
        d = rule_details.get(rid) or {}
        status = rule_statuses.get(rid, "")
        rule_name = d.get("rule_name") or rid
        sev = _SEVERITY_LABELS.get(d.get("severity", ""), "")
        metrics = _format_metrics(d.get("current") or {})
        if status == "triggered":
            header = f"{rid} {rule_name}（{sev}）"
            lines.append(f"{header}：{metrics}。" if metrics else f"{header}：已触发。")
        elif status in ("insufficient_data", "not_applicable"):
            lines.append(
                f"{rid} {rule_name}：当前数据覆盖不足以计算该规则指标（{status}），"
                "无法给出明细。"
            )
        else:
            lines.append(f"{rid} {rule_name}：该规则未触发（{status}）。")

    if not lines:
        answer = (
            f"{name_code}：当前数据覆盖范围内未生成可展示的规则明细"
            "（规则未触发或数据不足）。"
        )
    else:
        answer = f"{name_code}规则明细：\n" + "\n".join(lines)
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": [],
        "final_response": FinalResponse(answer=answer, risk_level="unknown"),
    }


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
