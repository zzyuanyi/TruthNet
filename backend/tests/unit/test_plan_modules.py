"""plan_modules_node 交叉校验标签回归测试。

Bug 修复: need_finance and need_equity → need_equity and need_events
"""

from app.agents.nodes.plan_modules import plan_modules_node
from app.agents.state import CompanyRef


def _state(question: str) -> dict:
    return {
        "user_query": question,
        "company": CompanyRef(
            entity_id="ent_test",
            wind_code="000001.SZ",
            sec_name="测试公司",
            exchange="XSHE",
        ),
    }


def test_finance_equity_only_financial_crosscheck():
    """应收账款+股东 → finance + equity，仅 financial_vs_cashflow，不出现 equity_vs_events。"""
    result = plan_modules_node(_state("应收账款和股东情况"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"finance", "equity"}
    assert "financial_vs_cashflow" in plan.cross_checks
    assert "equity_vs_events" not in plan.cross_checks


def test_equity_events_only_equity_crosscheck():
    """股东变动+公告处罚 → equity + events，仅 equity_vs_events。"""
    result = plan_modules_node(_state("股东变动和公告处罚"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"equity", "events"}
    assert "equity_vs_events" in plan.cross_checks
    assert "financial_vs_cashflow" not in plan.cross_checks


def test_diagnosis_all_modules_both_crosschecks():
    """康美有造假风险吗 → 三模块，两个交叉校验都有。"""
    result = plan_modules_node(_state("康美有造假风险吗"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"finance", "equity", "events"}
    assert "equity_vs_events" in plan.cross_checks
    assert "financial_vs_cashflow" in plan.cross_checks


def test_finance_only_no_crosscheck():
    """营业收入如何 → 仅 finance，无交叉校验。"""
    result = plan_modules_node(_state("营业收入如何"))
    plan = result["plan"]
    assert plan.requested_modules == ["finance"]
    assert plan.cross_checks == []
