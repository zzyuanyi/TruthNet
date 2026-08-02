"""Finance — V12 §8.1. 财务分析节点。

Phase C 集成修正: 调用真实规则引擎（evaluate_all_rules），移除 Phase B Mock。
- 规则引擎内部实现"合并报表(408001000)优先、母公司(408006000)降级并显式标记"，
  每条规则输出 statement_scope / coverage / warning。
- 规则引擎不可用（无 DB / 异常）时返回 failed + 明确 warning，绝不返回 Mock 触发结果。
- 全部规则因数据不足/不适用而无有效信号时返回 partial，标注数据真实缺失。
"""

from app.agents.state import (
    AgentState,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
    ModuleStatus,
)

_RULES = [f"R{i}" for i in range(1, 8)]


def _resolve_as_of(state: AgentState) -> str:
    plan = state.get("plan")
    if plan is not None and plan.as_of:
        return plan.as_of.strftime("%Y%m%d")
    try:
        from app.core.config import settings

        if settings.DEFAULT_AS_OF:
            return settings.DEFAULT_AS_OF
    except Exception:
        pass
    return "20260331"


def finance_node(state: AgentState) -> dict:
    company = state.get("company")
    plan = state.get("plan")

    # 未选中 → no-op（plan 缺失时保守执行）
    if plan is not None and "finance" not in plan.requested_modules:
        return {
            "module_status": {"finance": ModuleStatus(state="skipped")},
            "results": ModuleResults(finance=None),
        }

    if company is None:
        return {
            "module_status": {"finance": ModuleStatus(state="skipped")},
            "results": ModuleResults(finance=None),
        }

    code = company.wind_code or company.entity_id
    as_of = _resolve_as_of(state)

    try:
        from app.domain.finance.rule_engine import evaluate_all_rules

        results = evaluate_all_rules(code, as_of)
    except Exception as e:  # noqa: BLE001 — 规则引擎异常降级，不伪造结果
        return {
            "module_status": ModuleStatus(
                state="failed",
                error_code="RULE_ENGINE_ERROR",
                recoverable=True,
            ),
            "results": ModuleResults(
                finance=FinanceResult(
                    rule_statuses={},
                    warnings=[f"财务规则引擎执行失败，财务模块降级: {e}"],
                    evidence=[],
                )
            ),
        }

    rule_statuses: dict[str, str] = {}
    warnings: list[str] = []
    evidence: list[EvidenceRef] = []

    for rid in _RULES:
        r = results.get(rid)
        if r is None:
            continue
        rule_statuses[rid] = r.status
        for w in r.warnings:
            if w and w not in warnings:
                warnings.append(w)
        q = r.quality or {}
        scope = q.get("statement_scope", "")
        stmt_type = q.get("statement_type", "")
        for ev_id in r.evidence_ids:
            evidence.append(
                EvidenceRef(
                    evidence_id=ev_id,
                    source_type=stmt_type or "finance_rule",
                    source_record_id=f"{rid}@{as_of}",
                    field_path=rid,
                    period=as_of,
                    value="",
                    source_title=f"财务反欺诈规则 {rid}（{scope}）",
                )
            )

    if not rule_statuses:
        status = "failed"
        warnings.append("财务规则引擎未返回任何结果")
    elif any(s == "triggered" for s in rule_statuses.values()):
        status = "success"
    elif all(
        s in ("insufficient_data", "not_applicable") for s in rule_statuses.values()
    ):
        status = "partial"
        warnings.append(
            "财务规则因数据不足/不适用未产出有效信号（statement_scope/coverage 见各规则 quality）"
        )
    else:
        status = "success"

    return {
        "module_status": {"finance": ModuleStatus(state=status)},
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses=rule_statuses,
                warnings=warnings,
                evidence=evidence,
            )
        ),
    }
