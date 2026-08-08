"""CrossValidate — V12 §7.4 + Phase C 任务 3.

结构化跨模块一致性检查：
  - equity_vs_events:    股权模块与事件模块的对应、身份一致、时间范围一致
  - financial_vs_cashflow:利润与现金流数据同时存在、报告期对齐、口径一致
  - dependency:           请求模块依赖存在检查
  - identity:             公司 entity_id / wind_code 一致
  - period:               as_of / period 一致

输出结构化 check 记录（check_id/check_type/status/left/right/time_range/
evidence_ids/warning/details），写入 State.cross_validation，warnings 去重后
合并到 runtime.warnings，供最终回答与审计日志使用。
"""

from __future__ import annotations

import logging

from app.agents.state import (
    AgentState,
    CrossValidationCheck,
    CrossValidationResult,
)

logger = logging.getLogger(__name__)

# 事件模块中与股权变动相关的 fcode 类别
_EQUITY_EVENT_CATEGORIES = {"权益变动", "增减持", "收购兼并", "资产重组", "股份增减持"}


def _check_company_identity(state: AgentState) -> CrossValidationCheck:
    """公司身份一致：entity_id / wind_code 与各模块证据一致。"""
    company = state.get("company")
    results = state.get("results")
    code = company.wind_code if company else None
    warnings: list[str] = []
    if results:
        for module, module_result in [
            ("finance", results.finance),
            ("equity", results.equity),
            ("events", results.events),
        ]:
            if module_result is None:
                continue
            for ev in getattr(module_result, "evidence", []):
                if ev.company_code and code and ev.company_code != code:
                    warnings.append(
                        f"公司身份不一致: {module} 证据公司 {ev.company_code} != {code}"
                    )
    return CrossValidationCheck(
        check_id="cv_identity_company",
        check_type="identity",
        status="fail" if warnings else "pass",
        left_module="company",
        right_module="all_modules",
        evidence_ids=[],
        warning="; ".join(warnings) if warnings else None,
        details={
            "company_code": code,
            "entity_id": company.entity_id if company else None,
        },
    )


def _check_plan_dependencies(state: AgentState) -> CrossValidationCheck:
    """请求模块依赖存在检查。"""
    plan = state.get("plan")
    module_status = state.get("module_status") or {}
    if plan is None or not plan.requested_modules:
        return CrossValidationCheck(
            check_id="cv_dependency_plan",
            check_type="dependency",
            status="skipped",
            left_module="plan",
            right_module="modules",
            warning="无计划请求模块，跳过依赖检查",
        )
    missing = [
        m
        for m in plan.requested_modules
        if module_status.get(m) is None
        or module_status[m].state not in ("success", "partial")
    ]
    status = "pass" if not missing else "partial"
    return CrossValidationCheck(
        check_id="cv_dependency_plan",
        check_type="dependency",
        status=status,
        left_module="plan",
        right_module="modules",
        evidence_ids=[],
        warning=f"请求模块存在缺失/失败: {missing}" if missing else None,
        details={"requested": plan.requested_modules},
    )


def _check_equity_vs_events(state: AgentState, check_seq: int) -> CrossValidationCheck:
    """equity_vs_events: 股权与事件的对应、身份、时间范围一致。"""
    company = state.get("company")
    results = state.get("results")
    equity = results.equity if results else None
    events = results.events if results else None

    evidence_ids: list[str] = []
    if events is not None:
        evidence_ids = [ev.evidence_id for ev in events.evidence]
    if equity is not None:
        evidence_ids += [ev.evidence_id for ev in equity.evidence]

    # 模块缺失
    if equity is None or events is None:
        missing = []
        if equity is None:
            missing.append("equity")
        if events is None:
            missing.append("events")
        return CrossValidationCheck(
            check_id=f"cv_equity_vs_events_{check_seq}",
            check_type="equity_vs_events",
            status="partial",
            left_module="equity",
            right_module="events",
            evidence_ids=evidence_ids,
            warning=f"模块缺失，无法完整交叉验证: {missing}",
            details={"missing_modules": missing},
        )

    # 事件时间范围
    timeline = events.timeline or []
    dates = [str(t.get("date", "")) for t in timeline if t.get("date")]
    time_range = {}
    if dates:
        time_range = {"start": min(dates), "end": max(dates)}

    # 股权相关事件类别 → 图谱对应
    equity_event_count = sum(
        1 for t in timeline if t.get("category") in _EQUITY_EVENT_CATEGORIES
    )
    chains = equity.chains or []
    detail = {
        "equity_event_count": equity_event_count,
        "control_chains": len(chains),
        "time_range": time_range,
        "company_code": company.wind_code if company else None,
    }

    warning = None
    status = "pass"
    if equity_event_count > 0 and not chains:
        warning = (
            f"存在 {equity_event_count} 条股权类公告但股权图无控制链，"
            f"事件与图谱覆盖不一致"
        )
        status = "partial"
    elif not equity_event_count and not chains:
        warning = "无股权类事件且无控制链，股权-事件维度信号均缺失"
        status = "partial"

    return CrossValidationCheck(
        check_id=f"cv_equity_vs_events_{check_seq}",
        check_type="equity_vs_events",
        status=status,
        left_module="equity",
        right_module="events",
        time_range=time_range,
        evidence_ids=evidence_ids,
        warning=warning,
        details=detail,
    )


def _check_financial_vs_cashflow(
    state: AgentState, check_seq: int
) -> CrossValidationCheck:
    """financial_vs_cashflow: 利润与现金流数据同时存在、报告期对齐、口径一致。"""
    results = state.get("results")
    finance = results.finance if results else None
    if finance is None:
        return CrossValidationCheck(
            check_id=f"cv_financial_vs_cashflow_{check_seq}",
            check_type="financial_vs_cashflow",
            status="partial",
            left_module="finance",
            right_module="finance",
            warning="财务模块缺失，无法检查利润/现金流依赖完整性",
        )

    evidence = finance.evidence or []
    is_evidence = [ev for ev in evidence if ev.source_table == "income_statement"]
    cf_evidence = [ev for ev in evidence if ev.source_table == "cash_flow"]

    # 报告期对齐与口径一致
    periods = {ev.period for ev in evidence if ev.period}
    scopes = {ev.statement_scope for ev in evidence if ev.statement_scope}
    periods_aligned = len(periods) <= 1  # 全部同一报告期（或仅有部分）
    scope_consistent = scopes <= {"parent_company"} or not scopes

    status = "pass"
    warning = None
    if not is_evidence or not cf_evidence:
        status = "partial"
        warning = "利润表或现金流证据缺失，financial_vs_cashflow 依赖不完整"
    elif not periods_aligned:
        status = "partial"
        warning = f"报告期未对齐: {sorted(periods)}"
    elif not scope_consistent:
        status = "partial"
        warning = f"报表口径不一致: {scopes}"

    return CrossValidationCheck(
        check_id=f"cv_financial_vs_cashflow_{check_seq}",
        check_type="financial_vs_cashflow",
        status=status,
        left_module="income_statement",
        right_module="cash_flow",
        time_range={"periods": sorted(periods)},
        evidence_ids=[ev.evidence_id for ev in evidence],
        warning=warning,
        details={
            "income_statement_evidence": len(is_evidence),
            "cash_flow_evidence": len(cf_evidence),
            "statement_scope": sorted(scopes),
        },
    )


def _parse_period(p: str):
    """期次文本 → datetime（兼容 YYYYMMDD / YYYY-MM-DD）；无法解析返回 None。"""
    from datetime import datetime

    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(p, fmt)
        except ValueError:
            continue
    return None


def _check_period_consistency(
    state: AgentState, check_seq: int
) -> CrossValidationCheck:
    """as_of / period 一致（#5 口径修正）：任何证据期不得晚于计划 as_of。

    早于截止期的最新已披露数据是合法的（如请求 2025 年报，
    实际数据到 20251231 已披露）；只有存在晚于 as_of 的证据才算不一致。
    """
    plan = state.get("plan")
    results = state.get("results")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else None
    evidence_periods: set[str] = set()
    if results:
        for module_result in (results.finance, results.equity, results.events):
            if module_result is None:
                continue
            for ev in getattr(module_result, "evidence", []):
                if ev.period:
                    evidence_periods.add(str(ev.period))
    status = "pass"
    warning = None
    as_of_dt = _parse_period(as_of) if as_of else None
    if as_of_dt is not None and evidence_periods:
        late = sorted(
            p
            for p in evidence_periods
            if (pd := _parse_period(p)) is not None and pd > as_of_dt
        )
        if late:
            status = "partial"
            warning = f"存在晚于计划 as_of={as_of} 的证据 period={late}"
    return CrossValidationCheck(
        check_id=f"cv_period_{check_seq}",
        check_type="period",
        status=status,
        left_module="plan",
        right_module="evidence",
        time_range={"as_of": as_of, "evidence_periods": sorted(evidence_periods)},
        evidence_ids=[],
        warning=warning,
    )


def _dedup(items: list[str]) -> list[str]:
    """去重并保持顺序。"""
    seen: set[str] = set()
    out = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ── Phase D #2: 深度数值冲突检测 ─────────────────────────────


def _run_numerical_conflicts(state: AgentState) -> list[dict]:
    """运行冻结的 CV-NUM-01/02 深度数值冲突检测，返回可序列化结果。

    数据读取失败不阻塞主流程（返回空列表 + warning）。
    """
    results: list[dict] = []
    try:
        from app.domain.conflicts.numerical import run_numerical_conflicts
        from app.domain.finance._fetch import fetch_series

        company = state.get("company")
        if company is None:
            return []

        code = company.wind_code or company.entity_id
        plan = state.get("plan")
        as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else "20260331"

        # CV-NUM-01 数据：母公司利润表净利润 + 现金流量表经营现金流
        profit = fetch_series(
            code, "net_profit_after_ded_nr_lp", periods=8, as_of=as_of
        )
        cashflow = fetch_series(code, "net_cash_flows_oper_act", periods=8, as_of=as_of)

        # CV-NUM-02 数据：MySQL 股东表 vs Neo4j 边比例（均按截止期过滤）
        shareholder_edges = _fetch_shareholder_edges(state, code, as_of=as_of)
        event_context = _fetch_equity_events(state, code)

        conflicts = run_numerical_conflicts(
            company_code=code,
            profit_values=profit.values,
            profit_periods=[str(p) for p in (profit.periods or [])],
            cashflow_values=cashflow.values,
            cashflow_periods=[str(p) for p in (cashflow.periods or [])],
            finance_evidence_ids=_finance_evidence_ids(state),
            shareholder_edges=shareholder_edges,
            equity_evidence_ids=_equity_evidence_ids(state),
            event_context=event_context,
        )
        results = [c.to_dict() for c in conflicts]
    except Exception:  # noqa: BLE001 — 深度冲突检测失败不阻塞主流程
        logger.warning("cross_validate: 深度数值冲突检测失败，跳过", exc_info=True)
    return results


def _fetch_shareholder_edges(
    state: AgentState, company_code: str, as_of: str = ""
) -> list[dict]:
    """MySQL top_shareholders + Neo4j 边比例 → 可比边列表。

    #5 期次传播：as_of（YYYYMMDD）存在时双方都只取截止期内数据。
    """
    edges: list[dict] = []
    try:
        from app.domain.finance._fetch import _get_engine
        from sqlalchemy import text

        engine = _get_engine()
        # MySQL 截止期内股东持股比例（按报告期去重取最新）
        sql = (
            "SELECT s_holder_name, s_holder_pct, report_period, source_record_id "
            "FROM top_shareholders WHERE wind_code = :c "
        )
        params: dict = {"c": company_code}
        if as_of:
            sql += "AND report_period <= :asof "
            params["asof"] = as_of
        sql += "ORDER BY report_period DESC LIMIT 50"
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().fetchall()

        # Neo4j 目标公司边（含 ownership_pct 与 relationship_id）
        neo_edges: list[dict] = []
        try:
            from app.core.config import settings

            if settings.GRAPH_BACKEND == "neo4j":
                from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

                adapter = Neo4jEquityGraph()
                if adapter._check_connection_sync():
                    graph = adapter._get_graph_sync(
                        company_code, depth=2, as_of=as_of or None
                    )
                    for e in graph.edges:
                        pct = e.effective_ownership_pct()
                        if pct is not None:
                            neo_edges.append(
                                {
                                    "entity_id": e.target,
                                    "owner_name": e.source,
                                    "neo4j_pct": pct,
                                    "report_period": e.report_period or "",
                                    "relationship_id": e.relationship_id or "",
                                }
                            )
        except Exception:  # noqa: BLE001 — 图数据缺失时只比对 MySQL 侧
            logger.warning("cross_validate: Neo4j 边获取失败（CV-NUM-02 部分降级）")

        # 按 owner_name 匹配（名称标准化后比对数值得出可比边）
        for r in rows:
            name = r["s_holder_name"] or ""
            pct = r["s_holder_pct"]
            if pct is None:
                continue
            matched = next(
                (
                    ne
                    for ne in neo_edges
                    if ne["owner_name"] == name or name in (ne["owner_name"] or "")
                ),
                None,
            )
            edges.append(
                {
                    "entity_id": r.get("holder_entity_id", ""),
                    "owner_name": name,
                    "mysql_pct": float(pct),
                    "neo4j_pct": matched["neo4j_pct"] if matched else None,
                    "report_period": str(r["report_period"] or ""),
                    "relationship_id": matched["relationship_id"] if matched else None,
                    "source_record_id": r["source_record_id"],
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "cross_validate: MySQL 股东表读取失败（CV-NUM-02 跳过）", exc_info=True
        )
    return edges


def _fetch_equity_events(state: AgentState, company_code: str) -> list[dict]:
    """事件模块产出中的股权变动事件（增减持/权益变动）作为时间差上下文。"""
    results = state.get("results")
    if results is None or results.events is None:
        return []
    events = results.events.timeline or []
    return [
        {"category": t.get("category", ""), "title": t.get("title", "")}
        for t in events
        if t.get("category") in _EQUITY_EVENT_CATEGORIES
    ]


def _finance_evidence_ids(state: AgentState) -> list[str]:
    results = state.get("results")
    if results is None or results.finance is None:
        return []
    return [ev.evidence_id for ev in (results.finance.evidence or []) if ev.evidence_id]


def _equity_evidence_ids(state: AgentState) -> list[str]:
    results = state.get("results")
    if results is None or results.equity is None:
        return []
    return [ev.evidence_id for ev in (results.equity.evidence or []) if ev.evidence_id]


def cross_validate_node(state: AgentState) -> dict:
    """执行结构化交叉验证，结果写入 State.cross_validation。"""
    plan = state.get("plan")
    if plan is not None and plan.cross_checks:
        pass  # 有明确 cross_checks 请求 → 执行
    elif plan is not None and not plan.requested_modules:
        # 无任何模块请求 → no-op
        return {"messages": []}

    checks: list[CrossValidationCheck] = []
    seq = 0

    checks.append(_check_company_identity(state))
    seq += 1
    checks.append(_check_plan_dependencies(state))
    seq += 1
    checks.append(_check_period_consistency(state, seq))
    seq += 1
    checks.append(_check_equity_vs_events(state, seq))
    seq += 1
    checks.append(_check_financial_vs_cashflow(state, seq))
    seq += 1

    # 聚合 warnings（去重）
    raw_warnings = [c.warning for c in checks if c.warning]
    deduped = _dedup(raw_warnings)
    result = CrossValidationResult(checks=checks, warnings=deduped)

    # 合并到 runtime.warnings（去重）
    runtime = state.get("runtime")
    if runtime is not None and hasattr(runtime, "warnings"):
        for w in deduped:
            if w not in runtime.warnings:
                runtime.warnings.append(w)

    # Phase D #2: 深度数值冲突检测（不阻塞主流程）
    numerical_conflicts = _run_numerical_conflicts(state)
    for c in numerical_conflicts:
        if c.get("status") == "conflict" and c.get("explanation"):
            warn = f"数值冲突 {c.get('conflict_type')}: {c.get('explanation')}"
            if (
                runtime is not None
                and hasattr(runtime, "warnings")
                and warn not in runtime.warnings
            ):
                runtime.warnings.append(warn)

    return {
        "cross_validation": result,
        "numerical_conflicts": numerical_conflicts,
        "runtime": runtime or state.get("runtime"),
        "messages": [],
    }
