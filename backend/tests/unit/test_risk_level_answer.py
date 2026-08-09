from datetime import date

from app.agents.nodes.generate_answer import _answer_risk_level
from app.agents.nodes.plan_modules import detect_answer_target, plan_modules_node
from app.agents.state import CompanyRef, ExecutionPlan
from app.domain.risk.models import RiskDataCoverage, RiskOutput


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


def test_detect_risk_level_answer_target():
    assert detect_answer_target("康美药业的综合风险等级是什么") == "risk_level"
    assert detect_answer_target("康美药业是什么等级") == "risk_level"
    assert detect_answer_target("分析康美药业的财务风险") is None


def test_risk_level_plan_still_runs_risk_modules():
    out = plan_modules_node(
        {
            "user_query": "康美药业的综合风险等级是什么",
            "company": _company(),
            "request_context": None,
        }
    )
    plan = out["plan"]
    assert plan.answer_target == "risk_level"
    assert plan.requested_modules == ["finance", "equity", "events"]


def test_answer_risk_level_green_is_normal_with_coverage():
    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2025, 12, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20251231",
                risk_level="green",
                data_coverage=RiskDataCoverage(coverage_ratio=0.75),
            ),
            "claims": [],
            "evidence": [],
        }
    )
    answer = out["final_response"].answer
    assert "综合风险等级：正常" in answer
    assert "数据截止日：2025-12-31" in answer
    assert "数据覆盖率 75%" in answer
    assert out["final_response"].risk_level == "green"


def test_answer_risk_level_unknown_is_data_shortage():
    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2025, 12, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20251231",
                risk_level="unknown",
                data_coverage=RiskDataCoverage(
                    coverage_ratio=0.25,
                    missing_modules=["equity", "events"],
                ),
            ),
            "claims": [],
            "evidence": [],
        }
    )
    answer = out["final_response"].answer
    assert "综合风险等级：数据不足" in answer
    assert "不能据此判断为正常" in answer
    assert "缺失模块：equity, events" in answer
