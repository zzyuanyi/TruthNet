"""BuildClaimsAndEvidence — V12 §9.2 + Phase C 任务 16.

从模块结果构建 Claims：
  - 使用统一 make_claim_id()（确定性，同 turn 重试相同，不同 turn 不冲突）；
  - 绑定真实 Evidence ID（财务字段 / 股权 relationship_id / 公告 object_id）；
  - 无完整证据不得生成 verified Claim；
  - 证据去重但保留顺序。
"""

from app.agents.state import AgentState, Claim, EvidenceRef
from app.domain.finance.parent_scope import CLAIM_PARENT_SCOPE_LIMITATION
from app.domain.provenance.id_factory import make_claim_id


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


def _mk_claim(
    state: AgentState,
    *,
    text: str,
    claim_type: str,
    severity: str,
    evidence_ids: list[str],
    rule_id: str | None = None,
    rule_version: str | None = None,
    event_cluster_id: str | None = None,
    ordinal: int = 0,
    limitations: list[str] | None = None,
) -> Claim:
    """统一构造 Claim（确定性 ID + 追溯字段）。"""
    runtime = state.get("runtime")
    company = state.get("company")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    company_code = company.wind_code if company else ""

    claim_id = make_claim_id(
        turn_id=turn_id,
        company_code=company_code,
        claim_type=claim_type,
        rule_id=rule_id,
        event_cluster_id=event_cluster_id,
        ordinal=ordinal,
        claim_text=text,
        rule_version=rule_version or "",
    )
    return Claim(
        claim_id=claim_id,
        text=text,
        claim_type=claim_type,
        severity=severity,
        rule_id=rule_id,
        rule_version=rule_version,
        evidence_ids=list(evidence_ids),
        limitations=limitations or [],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company_code,
        module=claim_type,
        generated_at="",
    )


def build_claims_node(state: AgentState) -> dict:
    results = state.get("results")
    company = state.get("company")
    company_name = company.sec_name if company else "目标公司"
    claims: list[Claim] = []

    # 收集 evidence 并建立索引（按 evidence_id 去重，保留顺序）
    evidence = _collect_evidence(results)
    evidence_index: dict[str, EvidenceRef] = {}
    for ev in evidence:
        if ev.evidence_id not in evidence_index:
            evidence_index[ev.evidence_id] = ev

    # ── 财务 Claim ───────────────────────────────────────
    if results and results.finance and results.finance.rule_statuses:
        rule_details = results.finance.rule_details or {}
        for ordinal, (rule_id, status) in enumerate(
            results.finance.rule_statuses.items()
        ):
            if status != "triggered":
                continue
            # 直接绑定本规则实际生成的证据（finance_node 生成时记录于
            # rule_details[rid].evidence_ids；rule_id 已入 Evidence ID，
            # 跨规则同字段（如 R1/R4 共用 oper_rev）不再互相污染）
            generated_ids = (rule_details.get(rule_id) or {}).get("evidence_ids") or []
            actual_ev_ids = [eid for eid in generated_ids if eid in evidence_index]
            if not actual_ev_ids:
                continue

            text = _build_rule_text(rule_id, company_name, status)
            claims.append(
                _mk_claim(
                    state,
                    text=text,
                    claim_type="financial",
                    severity="red" if rule_id in ("R1", "R2", "R3", "R7") else "orange",
                    evidence_ids=actual_ev_ids,
                    rule_id=rule_id,
                    rule_version="1.0.0",
                    ordinal=ordinal,
                    limitations=[CLAIM_PARENT_SCOPE_LIMITATION],
                )
            )

    # ── 股权 Claim（绑定真实 relationship 证据） ──────────
    if results and results.equity and results.equity.chains:
        chains = results.equity.chains
        if chains:
            top_chain = chains[0]
            # 优先绑定顶层控制链边上的真实 relationship 证据
            rel_ids = set(top_chain.get("edge_ids") or [])
            all_eq_ev = results.equity.evidence or []
            if rel_ids:
                eq_ev_ids = [
                    ev.evidence_id for ev in all_eq_ev if ev.source_record_id in rel_ids
                ]
            else:
                eq_ev_ids = [ev.evidence_id for ev in all_eq_ev]
            if eq_ev_ids:
                path_names = "→".join(
                    top_chain.get("path_names") or top_chain.get("path", [])
                )
                stake = top_chain.get("total_stake", 0)
                text = (
                    f"{company_name}控制链穿透: {path_names}, "
                    f"最终控制{stake * 100:.1f}%"
                )
                claims.append(
                    _mk_claim(
                        state,
                        text=text,
                        claim_type="equity",
                        severity="red",
                        evidence_ids=eq_ev_ids,
                        ordinal=0,
                    )
                )

    # ── 事件 Claim（绑定事件簇 + 负面来源证据） ───────────
    if results and results.events and results.events.timeline:
        timeline = results.events.timeline
        negative_events = [
            e for e in timeline if e.get("sentiment", "neutral") == "negative"
        ]
        if negative_events:
            # 事件簇提供的 evidence_ids
            cluster_ev_ids: list[str] = []
            for cluster in results.events.clusters or []:
                cluster_ev_ids.extend(cluster.get("evidence_ids") or [])
            # 负面公告来源证据（source_record_id == object_id）
            neg_object_ids = {str(e.get("object_id", "")) for e in negative_events}
            ev_ev_ids = []
            for ev in results.events.evidence or []:
                if (
                    ev.source_record_id in neg_object_ids
                    and ev.evidence_id not in ev_ev_ids
                ):
                    ev_ev_ids.append(ev.evidence_id)
            # 合并事件簇证据，去重保留顺序
            combined: list[str] = []
            for eid in ev_ev_ids + [c for c in cluster_ev_ids if c in evidence_index]:
                if eid not in combined:
                    combined.append(eid)

            if combined:
                negative_count = len(negative_events)
                categories = set(e.get("category", "") for e in negative_events)
                cat_desc = "、".join(sorted(categories)) if categories else "多种类型"
                text = (
                    f"{company_name}存在{negative_count}项负面事件（{cat_desc}），"
                    f"含风险信号"
                )
                claims.append(
                    _mk_claim(
                        state,
                        text=text,
                        claim_type="event",
                        severity="red",
                        evidence_ids=combined,
                        ordinal=0,
                    )
                )

    return {
        "claims": claims,
        "evidence": evidence,
    }
