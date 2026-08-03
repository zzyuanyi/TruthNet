"""交叉验证节点单元测试 — Phase C 后端任务 3.

覆盖:
- equity_vs_events 模块缺失 → partial + warning
- equity_vs_events 股权事件与图谱一致 → pass
- financial_vs_cashflow 利润/现金流证据齐全 → pass
- financial_vs_cashflow 缺现金流 → partial
- 请求模块依赖检查
- 公司身份一致
- warnings 去重
- 结果进入 State
"""

from app.agents.nodes.cross_validate import cross_validate_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    CrossValidationResult,
    EquityResult,
    EventsResult,
    EvidenceRef,
    ExecutionPlan,
    FinanceResult,
    ModuleResults,
    RuntimeState,
)


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


def _ev(
    evidence_id,
    source_table="income_statement",
    period="20260331",
    company_code="600518.SH",
):
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type="financial_statement",
        source_record_id="600518.SH|20260331",
        source_table=source_table,
        period=period,
        company_code=company_code,
        module="finance",
    )


def test_equity_vs_events_missing_modules_partial():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance", "equity", "events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(events=None, equity=None),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["equity_vs_events"].status == "partial"
    assert "equity" in checks["equity_vs_events"].warning
    assert "events" in checks["equity_vs_events"].warning


def test_equity_vs_events_pass_when_aligned():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance", "equity", "events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(
            finance=None,
            equity=EquityResult(
                graph={"nodes": [{"id": "company_600518_SH"}]},
                chains=[{"target": "company_600518_SH"}],
            ),
            events=EventsResult(
                timeline=[{"date": "2026-03-01", "category": "权益变动", "title": "x"}],
            ),
        ),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["equity_vs_events"].status == "pass"


def test_financial_vs_cashflow_full_pass():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={"R2": "triggered"},
                evidence=[
                    _ev("ev_is_profit_1", source_table="income_statement"),
                    _ev("ev_cf_oper_1", source_table="cash_flow"),
                ],
            ),
            equity=None,
            events=None,
        ),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["financial_vs_cashflow"].status == "pass"
    assert len(cv.warnings) >= 1  # equity/events 缺失 warning


def test_financial_vs_cashflow_missing_cashflow_partial():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={"R1": "triggered"},
                evidence=[_ev("ev_is_rev_1", source_table="income_statement")],
            ),
        ),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["financial_vs_cashflow"].status == "partial"
    assert "现金流" in checks["financial_vs_cashflow"].warning


def test_warnings_deduped():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance", "equity", "events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(finance=None, equity=None, events=None),
    }
    out1 = cross_validate_node(state)
    out2 = cross_validate_node(state)
    # 第二次运行时 runtime.warnings 已含第一次的 warning，不得重复追加
    rt = out2["runtime"]
    assert rt.warnings == out1["runtime"].warnings
    cv = out1["cross_validation"]
    assert len(cv.warnings) == len(set(cv.warnings))


def test_plan_dependency_missing_partial():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["events"]),
        "module_status": {"events": None},
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["dependency"].status == "partial"


def test_company_identity_mismatch_fail():
    state: AgentState = {
        "user_query": "交叉验证",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={},
                evidence=[_ev("ev_x", company_code="999999.SZ")],
            ),
        ),
    }
    out = cross_validate_node(state)
    cv: CrossValidationResult = out["cross_validation"]
    checks = {c.check_type: c for c in cv.checks}
    assert checks["identity"].status == "fail"
