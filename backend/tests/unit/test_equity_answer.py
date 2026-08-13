from app.agents.nodes.equity import _latest_shareholders
from app.agents.nodes.generate_answer import (
    _build_equity_overview,
    _select_answer_mode,
    generate_answer_node,
)
from app.agents.state import (
    AgentState,
    CompanyRef,
    EquityResult,
    ExecutionPlan,
    ModuleResults,
)


def _state(equity: EquityResult) -> AgentState:
    return {
        "user_query": "康美药业的股权结构怎么样",
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(intent="simple_query", requested_modules=["equity"]),
        "results": ModuleResults(equity=equity),
        "claims": [],
        "evidence": [],
        "module_status": {},
    }


def test_latest_shareholders_only_keeps_latest_period():
    rows = [
        {
            "holder_name": "旧股东",
            "pct": 10,
            "report_period": "20240930",
            "source_record_id": "old",
        },
        {
            "holder_name": "新股东A",
            "pct": 20,
            "report_period": "20241231",
            "source_record_id": "new-a",
        },
        {
            "holder_name": "新股东B",
            "pct": 25,
            "report_period": "2024-12-31",
            "source_record_id": "new-b",
        },
        {
            "holder_name": "新股东B",
            "pct": 24,
            "report_period": "20241231",
            "source_record_id": "new-b-duplicate",
        },
    ]
    out = _latest_shareholders(rows)
    assert [item["holder_name"] for item in out] == ["新股东B", "新股东A"]
    assert all(item["report_period"] == "20241231" for item in out)


def test_equity_mode_uses_plan_even_without_claims():
    state = _state(EquityResult())
    assert _select_answer_mode(state, [], False, False) == "equity"


def test_equity_overview_shows_shareholders_and_chain():
    state = _state(
        EquityResult(
            shareholders=[
                {
                    "holder_name": "康美实业投资控股有限公司",
                    "ownership_pct": 32.5,
                    "report_period": "20251231",
                }
            ],
            chain_details=[
                {
                    "path_names": ["马兴田", "康美实业", "康美药业"],
                    "final_control_pct": 32.5,
                }
            ],
        )
    )
    overview = _build_equity_overview(state)
    assert "主要股东（2025-12-31）" in overview
    assert "康美实业投资控股有限公司 32.50%" in overview
    assert "马兴田 → 康美实业 → 康美药业" in overview


def test_equity_answer_never_falls_back_to_generic_no_signal():
    out = generate_answer_node(_state(EquityResult()))
    answer = out["final_response"].answer
    assert "股权穿透分析完成" in answer
    assert "股权数据覆盖不足" in answer
    assert "未发现明显异常信号" not in answer
