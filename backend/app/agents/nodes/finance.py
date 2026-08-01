"""Finance — V12 §8.1. 财务分析节点。

Phase B mock: 返回康美药业 fixture 规则结果。
Bug fix: 提供多种报表 evidence 以支持不同规则的 evidence 绑定。
"""

from app.agents.state import (
    AgentState,
    ModuleStatus,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
)


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

    # Phase B mock: Kangmei fixture rule results
    return {
        "module_status": {"finance": ModuleStatus(state="success", duration_ms=120)},
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={
                    "R1": "triggered",
                    "R2": "triggered",
                    "R3": "triggered",
                    "R4": "not_triggered",
                    "R5": "insufficient_data",
                    "R6": "not_applicable",
                    "R7": "not_triggered",
                },
                warnings=["R1 应收-营收背离: 47.2% vs 12.1%", "R2 现金流-利润背离"],
                evidence=[
                    EvidenceRef(
                        evidence_id="ev_bs_01",
                        source_type="balance_sheet",
                        field_path="acct_rcv",
                        period="2025Q3",
                        value="47.2%",
                        source_title="资产负债表",
                    ),
                    EvidenceRef(
                        evidence_id="ev_is_01",
                        source_type="income_statement",
                        field_path="oper_rev",
                        period="2025Q3",
                        value="12.1%",
                        source_title="利润表",
                    ),
                    EvidenceRef(
                        evidence_id="ev_cf_01",
                        source_type="cash_flow",
                        field_path="net_cash_flows_oper_act",
                        period="2025Q3",
                        value="-2.3亿",
                        source_title="现金流量表",
                    ),
                    # R2 背离结论需要净利润字段
                    EvidenceRef(
                        evidence_id="ev_is_02",
                        source_type="income_statement",
                        field_path="net_profit",
                        period="2025Q3",
                        value="8.5亿",
                        source_title="利润表",
                    ),
                    # R3 存贷双高需要货币资金与有息负债字段
                    EvidenceRef(
                        evidence_id="ev_bs_02",
                        source_type="balance_sheet",
                        field_path="monetary_cap",
                        period="2025Q3",
                        value="358.0亿",
                        source_title="资产负债表",
                    ),
                    EvidenceRef(
                        evidence_id="ev_bs_03",
                        source_type="balance_sheet",
                        field_path="st_borrow",
                        period="2025Q3",
                        value="330.0亿",
                        source_title="资产负债表",
                    ),
                ],
            )
        ),
    }
