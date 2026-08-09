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
    from app.agents.state import EvidenceRef

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
            "evidence": [
                EvidenceRef(
                    evidence_id="ev_bs_acct_rcv_20251231",
                    source_table="balance_sheet",
                    period="20251231",
                )
            ],
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


def test_answer_risk_level_future_asof_shows_data_asof_gap():
    """WARN-1-3：请求未来期（20260331）而证据实际只到 20251231 →
    显示"请求截至 2026-03-31，最新可用数据截至 2025-12-31"，不得把
    请求截止日冒充为数据截止日。"""
    from app.agents.state import EvidenceRef

    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2026, 3, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20260331",
                risk_level="orange",
                data_coverage=RiskDataCoverage(coverage_ratio=0.8),
            ),
            "claims": [],
            "evidence": [
                EvidenceRef(
                    evidence_id="ev_bs_acct_rcv_20251231",
                    source_table="balance_sheet",
                    period="20251231",
                ),
                EvidenceRef(
                    evidence_id="ev_is_oper_rev_20251231",
                    source_table="income_statement",
                    period="20251231",
                ),
            ],
        }
    )
    answer = out["final_response"].answer
    assert "请求截至 2026-03-31" in answer
    assert "最新可用数据截至 2025-12-31" in answer
    assert "数据截止日：2026-03-31" not in answer  # 不再冒充数据截止日


def test_answer_risk_level_asof_matches_data_asof_shows_single_period():
    """请求期 == 证据实际期（默认 2025 年报口径）→ 只显示单一截止日。"""
    from app.agents.state import EvidenceRef

    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2025, 12, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20251231",
                risk_level="yellow",
                data_coverage=RiskDataCoverage(coverage_ratio=0.8),
            ),
            "claims": [],
            "evidence": [
                EvidenceRef(
                    evidence_id="ev_bs_acct_rcv_20251231",
                    source_table="balance_sheet",
                    period="20251231",
                )
            ],
        }
    )
    answer = out["final_response"].answer
    assert "数据截止日：2025-12-31" in answer
    assert "最新可用数据" not in answer


def test_answer_risk_level_no_evidence_shows_unknown_data_asof():
    """8.09 二轮审查：无任何证据期时不得把请求期冒充为数据截止日，
    应显示"实际数据截止日未知"。"""
    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2026, 3, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20260331",
                risk_level="orange",
                data_coverage=RiskDataCoverage(coverage_ratio=0.8),
            ),
            "claims": [],
            "evidence": [],
        }
    )
    answer = out["final_response"].answer
    assert "请求截至 2026-03-31" in answer
    assert "实际数据截止日未知" in answer
    assert "数据截止日：2026-03-31" not in answer  # 不得冒充数据截止日


def test_answer_risk_level_evidence_after_request_marks_anomaly():
    """8.09 二轮审查：证据期晚于请求期是数据完整性异常，必须明确标记。"""
    from app.agents.state import EvidenceRef

    out = _answer_risk_level(
        {
            "plan": ExecutionPlan(as_of=date(2026, 3, 31)),
            "risk_output": RiskOutput(
                wind_code="600518.SH",
                as_of="20260331",
                risk_level="orange",
                data_coverage=RiskDataCoverage(coverage_ratio=0.8),
            ),
            "claims": [],
            "evidence": [
                EvidenceRef(
                    evidence_id="ev_bs_acct_rcv_20260630",
                    source_table="balance_sheet",
                    period="20260630",
                )
            ],
        }
    )
    answer = out["final_response"].answer
    assert "异常：存在晚于请求期的证据" in answer
    assert "最新 2026-06-30" in answer
