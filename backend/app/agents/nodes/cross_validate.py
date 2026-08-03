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

from app.agents.state import (
    AgentState,
    CrossValidationCheck,
    CrossValidationResult,
)

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


def _check_period_consistency(
    state: AgentState, check_seq: int
) -> CrossValidationCheck:
    """as_of / period 一致：计划 as_of 与证据 period 一致性检查。"""
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
    if as_of and evidence_periods and as_of not in evidence_periods:
        status = "partial"
        warning = f"计划 as_of={as_of} 与证据 period={sorted(evidence_periods)} 不一致"
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

    return {
        "cross_validation": result,
        "runtime": runtime or state.get("runtime"),
        "messages": [],
    }
