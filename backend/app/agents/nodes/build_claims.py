"""BuildClaimsAndEvidence — V12 §9.2. 从模块结果构建 Claims。

Bug fix:
  - 使用 state 中的公司名称，不再硬编码"康美药业"
  - 根据规则绑定对应 Evidence（不再所有规则都引用 ev_bs_01）
  - 收集模块 evidence 到 state["evidence"]
"""

from app.agents.state import AgentState, Claim, EvidenceRef

# 规则 → 所需字段证据映射（证据必须覆盖 Claim 声明的全部字段，RULES_SPEC 字段-规则矩阵）
# R1 背离 = 应收 + 营收；R2 背离 = 经营现金流 + 净利润；R3 存贷双高 = 货币资金 + 有息负债
_RULE_EVIDENCE_MAP: dict[str, list[str]] = {
    "R1": ["ev_bs_01", "ev_is_01"],  # acct_rcv + oper_rev
    "R2": ["ev_cf_01", "ev_is_02"],  # net_cash_flows_oper_act + net_profit
    "R3": ["ev_bs_02", "ev_bs_03"],  # monetary_cap + st_borrow
    # TODO(任务 1): R4-R7 依赖真实化后的字段证据，当前 mock 无对应字段
    "R4": ["ev_bs_01"],  # 需 inventories
    "R5": ["ev_is_01"],  # 需费用类字段
    "R6": ["ev_bs_01"],  # 需 oth_rcv
    "R7": ["ev_cf_01"],  # 需 net_profit（扣非对比）
}


def _collect_evidence(results) -> list[EvidenceRef]:
    """从模块结果中汇总所有 Evidence。"""
    evidence: list[EvidenceRef] = []
    if results:
        if results.finance and results.finance.evidence:
            evidence.extend(results.finance.evidence)
        if results.equity and results.equity.evidence:
            evidence.extend(results.equity.evidence)
        if results.events and results.events.evidence:
            evidence.extend(results.events.evidence)
    return evidence


def _build_rule_text(rule_id: str, company_name: str, status: str) -> str:
    """为每条规则生成描述文本。"""
    descriptions = {
        "R1": f"规则 R1 触发：{company_name} 应收账款增速与营业收入增速存在显著背离",
        "R2": f"规则 R2 触发：{company_name} 经营活动现金流与净利润严重背离",
        "R3": f"规则 R3 触发：{company_name} 存贷双高，货币资金与有息负债同时处于高位",
        "R4": f"规则 R4 触发：{company_name} 存货增速与营收增速背离，存货周转异常",
        "R5": f"规则 R5 触发：{company_name} 毛利率或费用率出现异常偏离",
        "R6": f"规则 R6 触发：{company_name} 其他应收款占比过高，可能存在资金占用",
        "R7": f"规则 R7 触发：{company_name} 盈利质量差，扣非净利润显著低于归母净利润",
    }
    return descriptions.get(
        rule_id, f"规则 {rule_id} 触发：{company_name} 存在财务异常信号"
    )


def build_claims_node(state: AgentState) -> dict:
    results = state.get("results")
    company = state.get("company")
    company_name = company.sec_name if company else "目标公司"
    claims: list[Claim] = []

    # 收集 evidence
    evidence = _collect_evidence(results)

    # 为 evidence 建立索引
    evidence_index: dict[str, EvidenceRef] = {}
    for ev in evidence:
        if ev.evidence_id not in evidence_index:
            evidence_index[ev.evidence_id] = ev

    if results and results.finance and results.finance.rule_statuses:
        for rule_id, status in results.finance.rule_statuses.items():
            if status == "triggered":
                # 为每条规则选择语义匹配的 evidence
                ev_ids = _RULE_EVIDENCE_MAP.get(rule_id, ["ev_bs_01"])
                # 证据必须完整覆盖 Claim 声明的全部字段（部分匹配不足以支撑结论）
                if any(eid not in evidence_index for eid in ev_ids):
                    continue
                actual_ev_ids = ev_ids

                claims.append(
                    Claim(
                        claim_id=f"claim_{rule_id}_01",
                        text=_build_rule_text(rule_id, company_name, status),
                        claim_type="financial",
                        severity="red"
                        if rule_id in ("R1", "R2", "R3", "R7")
                        else "orange",
                        rule_id=rule_id,
                        rule_version="1.0.0",
                        evidence_ids=actual_ev_ids,
                    )
                )

    if results and results.equity and results.equity.chains:
        chains = results.equity.chains
        if chains:
            # 绑定实际存在的 equity 证据（上游 equity.py 产出 ev_eq_01）
            eq_ev_ids = [ev.evidence_id for ev in (results.equity.evidence or [])]
            if eq_ev_ids:
                top_chain = chains[0]
                path_names = "→".join(top_chain.get("path", []))
                stake = top_chain.get("total_stake", 0)
                claims.append(
                    Claim(
                        claim_id="claim_eq_01",
                        text=f"{company_name}控制链穿透: {path_names}, 最终控制{stake * 100:.1f}%",
                        claim_type="equity",
                        severity="red",
                        evidence_ids=eq_ev_ids,
                    )
                )

    if results and results.events and results.events.timeline:
        timeline = results.events.timeline
        # 仅负面公告构成风险信号（events.py timeline 含全部公告，中性/正面不计）
        negative_events = [
            e for e in timeline if e.get("sentiment", "neutral") == "negative"
        ]
        if negative_events:
            # 绑定实际存在的事件证据（上游 events.py 产出 ann_{object_id}）
            ev_ev_ids = [ev.evidence_id for ev in (results.events.evidence or [])]
            if ev_ev_ids:
                negative_count = len(negative_events)
                categories = {e.get("category", "") for e in negative_events}
                cat_desc = "、".join(sorted(categories)) if categories else "多种类型"
                claims.append(
                    Claim(
                        claim_id="claim_events_01",
                        text=f"{company_name}存在{negative_count}项负面事件（{cat_desc}），含风险信号",
                        claim_type="event",
                        severity="red",
                        evidence_ids=ev_ev_ids,
                    )
                )

    return {
        "claims": claims,
        "evidence": evidence,
    }
