"""Finance — V12 §8.1. 财务分析节点。

Phase C 口径修正: 调用真实规则引擎（evaluate_all_rules），固定母公司报表口径。
- 项目财务规则固定采用母公司报表（statement_type=408006000，scope=parent_company），
  不再使用"合并报表优先、母公司降级"，不再输出"降级" warning。
- 模块执行时始终将统一口径说明（SCOPE_NOTE）放入 results.finance.warnings，恰好一次；
  规则 field 级 warning 去重（保持顺序）后追加。
- 规则证据 source_type=408006000、source_title 标记"母公司报表"。
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
from app.domain.finance.parent_scope import (
    PARENT_STATEMENT_TYPE,
    SCOPE_NOTE,
    W_COMPANY_TYPE_UNKNOWN,
)

_RULES = [f"R{i}" for i in range(1, 8)]


def _dedup(items: list[str]) -> list[str]:
    """去重并保持原顺序（禁止 set() 导致顺序随机）。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


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
    rule_details: dict[str, dict] = {}
    warnings: list[str] = []
    evidence: list[EvidenceRef] = []
    unknown_type = False

    for rid in _RULES:
        r = results.get(rid)
        if r is None:
            continue
        rule_statuses[rid] = r.status
        # 规则明细（含触发解释/严重度/指标数值，供回答展开规则清单）
        rule_details[rid] = {
            "rule_name": r.rule_name or "",
            "explanation": str(r.explanation or ""),
            "severity": r.severity or "",
            "current": dict(getattr(r, "current", None) or {}),
        }
        if r.status == "insufficient_data" and W_COMPANY_TYPE_UNKNOWN in r.warnings:
            unknown_type = True
        for w in r.warnings:
            if w:
                warnings.append(w)
        for ev_id in r.evidence_ids:
            evidence.append(
                EvidenceRef(
                    evidence_id=ev_id,
                    source_type=PARENT_STATEMENT_TYPE,
                    source_record_id=f"{rid}@{as_of}",
                    field_path=rid,
                    period=as_of,
                    value=str(r.explanation or "")[:200],
                    source_title=f"母公司报表 · 财务反欺诈规则 {rid}",
                )
            )

    # 统一口径说明恰好一次（规则实际执行时才有意义）
    if rule_statuses:
        warnings.insert(0, SCOPE_NOTE)
    # 规则级去重（保持顺序）
    warnings = _dedup(warnings)

    if not rule_statuses:
        status = "failed"
        warnings.append("财务规则引擎未返回任何结果")
    elif any(s == "triggered" for s in rule_statuses.values()):
        status = "success"
    elif unknown_type:
        # 公司类型未知 → 数据不足，不得标记 success / 输出"未发现风险"
        status = "partial"
        warnings.append("公司类型缺失，无法判断是否适用非金融财务规则，规则未执行")
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
                rule_details=rule_details,
                warnings=warnings,
                evidence=evidence,
            )
        ),
    }
