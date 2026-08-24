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
from app.domain.risk.severity import event_signal_severity, highest_risk_level

# 合法严重度（V12 §2.4 等级序列；引擎输出非法值时回退 unknown，不猜测）
_VALID_SEVERITIES = frozenset({"red", "orange", "yellow", "blue", "green", "unknown"})


def _requested_modules(state: AgentState) -> set[str]:
    """返回本轮明确请求的模块；空集表示非模块型问答或综合兼容路径。"""
    plan = state.get("plan")
    return set(getattr(plan, "requested_modules", []) or [])


def _collect_evidence(results, requested_modules: set[str]) -> list[EvidenceRef]:
    """从本轮请求范围内的模块结果汇总 Evidence。"""
    evidence: list[EvidenceRef] = []
    if results:
        if (
            results.finance
            and results.finance.evidence
            and (not requested_modules or "finance" in requested_modules)
        ):
            evidence.extend(results.finance.evidence)
        if (
            results.equity
            and results.equity.evidence
            and (not requested_modules or "equity" in requested_modules)
        ):
            evidence.extend(results.equity.evidence)
        if (
            results.events
            and results.events.evidence
            and (not requested_modules or "events" in requested_modules)
        ):
            evidence.extend(results.events.evidence)
    return evidence


_R7_LIMITATION = "扣非净利润字段不可用，采用简化判断"


def _build_rule_text(
    rule_id: str,
    company_name: str,
    detail: dict,
) -> tuple[str, list[str]]:
    """为每条规则生成描述文本（#1/#2：文案与规则引擎 explanation 同源）。

    触发规则的真实 explanation 优先（含"净利润增速与现金流/营收增速
    背离"等简化模式表述）；仅在 core_profit_available 时 R7 才可能提到
    扣非净利润，否则追加 limitations 说明采用简化判断。
    """
    explanation = str((detail or {}).get("explanation") or "")
    if explanation:
        text = f"{company_name}：{explanation}"
    else:
        text = f"规则 {rule_id} 触发：{company_name} 存在财务异常信号"
    limitations: list[str] = []
    if rule_id == "R7" and not (detail or {}).get("quality", {}).get(
        "core_profit_available", True
    ):
        # 简化模式（无扣非字段）：文案不得声称扣非对比
        limitations.append(_R7_LIMITATION)
    return text, limitations


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


_SEVERITY_RANK = {
    "red": 5,
    "orange": 4,
    "yellow": 3,
    "blue": 2,
    "green": 1,
    "unknown": 0,
}


def _chain_claim_text(chain: dict, company_name: str) -> str:
    """股权链路 Claim 文本（final_control_pct 为 0-100 百分比）。

    8.09 四轮审查：措辞随 path_type 区分——ownership 是持股关系，只能说
    "股权链穿透/最终持股"；只有 path_type=="control"（存在明确控制证据）
    才使用"控制链穿透/最终控制"。
    8.09 五轮审查：final_control_pct 缺失时回退 total_stake（0-1）兜底，
    降级/历史载荷同样经此函数统一措辞（不再各写一套"控制链"文本）。
    """
    path_names = "→".join(chain.get("path_names") or chain.get("path") or [])
    pct = chain.get("final_control_pct")
    if pct is None:
        stake = chain.get("total_stake")
        pct = float(stake) * 100 if stake else None
    is_control = chain.get("path_type") == "control"
    if pct is None:
        pct_txt = ""
    else:
        term = "最终控制" if is_control else "最终持股"
        pct_txt = f"，{term} {float(pct):.1f}%"
    chain_term = "控制链" if is_control else "股权链"
    return f"{company_name}{chain_term}穿透：{path_names}{pct_txt}"


def _append_equity_claims(
    state: AgentState,
    claims: list[Claim],
    evidence_index: dict[str, EvidenceRef],
    company_name: str,
) -> None:
    """股权 Claim（#3）：主控制链（最终控制比例最大）事实 Claim + 最高风险链风险 Claim。

    规则：
      - 优先消费 chain_details（含 risk_level/evidence_ids）；主链与最高风险链
        为同一条链时只生成一条 Claim（取两者语义并集）。
      - 普通绿色控制链 severity=green 保留展示，不计入风险信号（#8 由调用方过滤）。
      - chain_details 缺失时回退旧 chains：只生成事实 Claim，severity=unknown
        （不得默认为 red）。
      - 无 canonical evidence_ids 的链不生成 Claim（validate_evidence 不得标记 verified）。
    """
    results = state.get("results")
    eq = results.equity if results else None
    if eq is None:
        return
    chain_details = eq.chain_details or []
    chains = eq.chains or []

    # 同路径不同报告期的股东快照去重：同路径多条链且全部为非风险链
    # （green/unknown，如厦门市建潘 43.5%/41.5% 两个期次）→ 只保留
    # 最终控制比例最大的一条；含风险链（red/orange/yellow）时全部保留
    # （主链与最高风险链并存的既有语义，见 test_high_risk_chain_not_first）。
    _by_path: dict[str, list[dict]] = {}
    for cd in chain_details:
        _by_path.setdefault("→".join(cd.get("path_names") or []), []).append(cd)
    _deduped: list[dict] = []
    for items in _by_path.values():
        risks = [
            it
            for it in items
            if str(it.get("risk_level") or "unknown") in ("red", "orange", "yellow")
        ]
        if risks:
            _deduped.extend(items)
        else:
            _deduped.append(
                max(items, key=lambda d: float(d.get("final_control_pct") or 0.0))
            )
    chain_details = _deduped

    # 收集可回查证据（canonical ev_*）
    def _valid_ev_ids(ids: list[str]) -> list[str]:
        return [eid for eid in ids if eid in evidence_index]

    if chain_details:
        main_chain = max(
            chain_details,
            key=lambda d: (
                d.get("final_control_pct") is not None,
                float(d.get("final_control_pct") or 0.0),
            ),
        )
        # P2-3：风险链只从非 green 链中选择——全绿时只输出主控制链一条，
        # 避免"最高风险链=另一条绿色链"导致重复生成两条绿色 Claim
        risk_chains = [
            d
            for d in chain_details
            if str(d.get("risk_level") or "unknown") in ("red", "orange", "yellow")
        ]
        risk_chain = (
            max(
                risk_chains,
                key=lambda d: _SEVERITY_RANK.get(
                    str(d.get("risk_level") or "unknown"), 0
                ),
            )
            if risk_chains
            else None
        )
        seen_chain_ids: set[str] = set()
        for chain in (main_chain, risk_chain):
            if chain is None:
                continue
            cid = chain.get("chain_id") or ""
            if cid and cid in seen_chain_ids:
                continue
            if cid:
                seen_chain_ids.add(cid)
            ev_ids = _valid_ev_ids(chain.get("evidence_ids") or [])
            if not ev_ids:
                continue  # 无 canonical 证据 → 不生成 Claim
            severity = str(chain.get("risk_level") or "unknown")
            if severity not in _VALID_SEVERITIES:
                severity = "unknown"
            # 8.09 四轮审查：ownership 链路是持股关系事实展示，不得称"控制关系"
            is_control = chain.get("path_type") == "control"
            limitations = [
                (
                    "股权链路为事实性控制关系展示，不构成风险认定"
                    if is_control
                    else "股权链路为持股关系事实展示，不构成控制关系或风险认定"
                )
                if severity == "green"
                else "股权风险信号不等同于造假事实认定"
            ]
            reasons = chain.get("risk_reasons") or []
            text = _chain_claim_text(chain, company_name)
            if reasons:
                text += "；" + "；".join(str(r) for r in reasons)
            claims.append(
                _mk_claim(
                    state,
                    text=text,
                    claim_type="equity",
                    severity=severity,
                    evidence_ids=ev_ids,
                    ordinal=0,
                    limitations=limitations,
                )
            )
        return

    # 回退：chain_details 缺失 → 旧 chains 事实 Claim（severity=unknown，不默认 red）
    if chains:
        top_chain = chains[0]
        rel_ids = set(top_chain.get("edge_ids") or [])
        all_eq_ev = eq.evidence or []
        if rel_ids:
            eq_ev_ids = [
                ev.evidence_id for ev in all_eq_ev if ev.source_record_id in rel_ids
            ]
        else:
            eq_ev_ids = [ev.evidence_id for ev in all_eq_ev]
        eq_ev_ids = _valid_ev_ids(eq_ev_ids)
        if eq_ev_ids:
            # 8.09 五轮审查：降级/历史载荷统一走 _chain_claim_text()——
            # 曾硬编码"控制链穿透/最终控制"，与 ownership 语义冲突
            text = _chain_claim_text(top_chain, company_name)
            claims.append(
                _mk_claim(
                    state,
                    text=text,
                    claim_type="equity",
                    severity="unknown",  # 降级载荷：不默认 red（#3）
                    evidence_ids=eq_ev_ids,
                    ordinal=0,
                )
            )


def _append_event_claims(
    state: AgentState,
    claims: list[Claim],
    evidence_index: dict[str, EvidenceRef],
    company_name: str,
) -> None:
    """Build evidence-backed announcement, rating and cluster claims."""
    results = state.get("results")
    events = results.events if results else None
    if events is None:
        return

    negative_events = [
        item
        for item in (events.timeline or [])
        if item.get("sentiment", "neutral") == "negative"
    ]
    announcement_ids: list[str] = []
    object_ids = {str(item.get("object_id") or "") for item in negative_events}
    for evidence in events.evidence or []:
        if (
            evidence.source_type == "announcement"
            and evidence.source_record_id in object_ids
            and evidence.evidence_id in evidence_index
            and evidence.evidence_id not in announcement_ids
        ):
            announcement_ids.append(evidence.evidence_id)
    if negative_events and announcement_ids:
        categories = sorted(
            {str(item.get("category") or "") for item in negative_events} - {""}
        )
        severity = highest_risk_level(
            [event_signal_severity(item) for item in negative_events],
            default="orange",
        )
        claims.append(
            _mk_claim(
                state,
                text=(
                    f"{company_name}存在{len(negative_events)}项负面事件"
                    f"（{'、'.join(categories) if categories else '多种类型'}）"
                ),
                claim_type="event",
                severity=severity,
                evidence_ids=announcement_ids,
                ordinal=0,
                limitations=["负面公告信号需结合公告原文判断实际影响"],
            )
        )

    down_ratings = [
        item
        for item in (events.rating_changes or [])
        if item.get("direction") == "down"
    ]
    rating_ids: list[str] = []
    for item in down_ratings:
        evidence_id = str(item.get("evidence_id") or "")
        if evidence_id in evidence_index and evidence_id not in rating_ids:
            rating_ids.append(evidence_id)
    if down_ratings and rating_ids:
        claims.append(
            _mk_claim(
                state,
                text=f"{company_name}在数据截止日前出现{len(down_ratings)}次研报评级下调",
                claim_type="event",
                severity="orange" if len(down_ratings) >= 3 else "yellow",
                evidence_ids=rating_ids,
                ordinal=1,
                limitations=["机构评级属于外部观点，不代表系统事实认定"],
            )
        )

    for ordinal, cluster in enumerate(events.clusters or [], start=2):
        severity = event_signal_severity(cluster)
        if severity not in ("red", "orange", "yellow"):
            continue
        evidence_ids = [
            evidence_id
            for evidence_id in (cluster.get("evidence_ids") or [])
            if evidence_id in evidence_index
        ]
        if not evidence_ids:
            continue
        cluster_id = str(cluster.get("event_cluster_id") or "")
        topic = str(cluster.get("topic") or "负面事件簇")
        claims.append(
            _mk_claim(
                state,
                text=f"{company_name}存在负面事件簇：{topic}",
                claim_type="event",
                severity=severity,
                evidence_ids=evidence_ids,
                event_cluster_id=cluster_id or None,
                ordinal=ordinal,
                limitations=["事件簇为多来源聚合信号，需回查原始来源核验"],
            )
        )


def build_claims_node(state: AgentState) -> dict:
    results = state.get("results")
    company = state.get("company")
    company_name = company.sec_name if company else "目标公司"
    claims: list[Claim] = []
    requested_modules = _requested_modules(state)

    # 收集 evidence 并建立索引（按 evidence_id 去重，保留顺序）
    evidence = _collect_evidence(results, requested_modules)
    evidence_index: dict[str, EvidenceRef] = {}
    for ev in evidence:
        if ev.evidence_id not in evidence_index:
            evidence_index[ev.evidence_id] = ev

    # ── 财务 Claim ───────────────────────────────────────
    if (
        results
        and results.finance
        and results.finance.rule_statuses
        and (not requested_modules or "finance" in requested_modules)
    ):
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

            detail = rule_details.get(rule_id) or {}
            # #2：严重度与规则引擎同源；非法等级回退 unknown（不猜测）
            engine_severity = str(detail.get("severity") or "")
            severity = (
                engine_severity if engine_severity in _VALID_SEVERITIES else "unknown"
            )
            text, extra_limitations = _build_rule_text(rule_id, company_name, detail)
            claims.append(
                _mk_claim(
                    state,
                    text=text,
                    claim_type="financial",
                    severity=severity,
                    evidence_ids=actual_ev_ids,
                    rule_id=rule_id,
                    rule_version="1.0.0",
                    ordinal=ordinal,
                    limitations=[CLAIM_PARENT_SCOPE_LIMITATION] + extra_limitations,
                )
            )

    # ── 股权 Claim（绑定真实 relationship 证据，#3：按 chain_details 分级） ──
    if (
        results
        and results.equity
        and (results.equity.chains or results.equity.chain_details)
        and (not requested_modules or "equity" in requested_modules)
    ):
        _append_equity_claims(state, claims, evidence_index, company_name)

    # ── 事件 Claim（公告、评级、事件簇各自只绑定可回查证据） ──
    if (
        results
        and results.events
        and (not requested_modules or "events" in requested_modules)
    ):
        _append_event_claims(state, claims, evidence_index, company_name)

    # ── 交叉验证 Claim（读取 state.cross_validation，B4/B3 联动） ──
    cross_validation = state.get("cross_validation")
    if cross_validation is not None and len(requested_modules) != 1:
        checks = cross_validation.checks or []
        for ordinal, check in enumerate(checks):
            if check.status != "fail":
                continue
            check_evidence_ids = [
                eid for eid in check.evidence_ids if eid in evidence_index
            ]
            text = (
                f"{company_name}交叉验证发现不一致"
                f"（{check.check_type}：{check.left_module} vs {check.right_module}）"
                f"{': ' + check.warning if check.warning else ''}"
            )
            claims.append(
                _mk_claim(
                    state,
                    text=text,
                    claim_type="cross_validation",
                    severity="orange",
                    evidence_ids=check_evidence_ids,
                    ordinal=ordinal,
                    limitations=["交叉验证仅标记模块间不一致，不做深度因果推断"],
                )
            )

    return {
        "claims": claims,
        "evidence": evidence,
    }
