"""相似案例节点接线 + panel_data 透出单元测试 — 任务①.

覆盖：
- finance_node：触发规则写入 similar_cases / 非触发不写该键 /
  comp_type_code=2 → not_supported / Provider 抛异常 → error 且节点不崩；
- persist_turn._build_panel_data：triggered_rules 条目带 similar_cases（若存在）。
全部通过 FakeProvider + monkeypatch，不访问真实 MySQL/规则引擎 DB。
"""

import pytest

from app.agents.nodes import finance as finance_node_module
from app.agents.nodes import persist_turn as persist_turn_module
from app.agents.state import (
    AgentState,
    CompanyRef,
    ExecutionPlan,
    FinalResponse,
    FinanceResult,
    ModuleResults,
    RuntimeState,
)
from app.api.v1.schemas.finance import SimilarCasesResult
from app.domain.finance.models import RuleResult


class FakeProvider:
    """可编程相似案例 Provider。"""

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = []

    def find(self, rule_id, company_code, metric_value, industry, as_of):
        self.calls.append((rule_id, company_code, metric_value, industry, as_of))
        if self._exc is not None:
            raise self._exc
        if self._result is not None:
            return self._result
        return SimilarCasesResult(status="ok", reason="", cases=[])


@pytest.fixture(autouse=True)
def _reset_similar_case_provider():
    yield
    finance_node_module.set_similar_case_provider(None)


def _fake_evaluate_all_rules(triggered=True):
    def _evaluate(code, as_of):
        return {
            "R1": RuleResult(
                rule_id="R1",
                rule_name="应收–营收背离",
                status="triggered" if triggered else "not_triggered",
                severity="red" if triggered else "green",
                current={"gap": {"value": 12.0, "unit": "percentage_point"}},
                evidence_ids=[],
                warnings=[],
            ),
            "R2": RuleResult(
                rule_id="R2",
                rule_name="现金流–利润背离",
                status="not_triggered",
                severity="green",
                current={},
                evidence_ids=[],
                warnings=[],
            ),
        }

    return _evaluate


def _fake_fetch_company_field(comp_type=1, industry="医药生物"):
    def _fetch(code, field):
        return {"comp_type_code": comp_type, "industry_l1": industry}.get(field)

    return _fetch


def _make_state() -> AgentState:
    return {
        "user_query": "康美有风险吗",
        "company": CompanyRef(
            entity_id="company_600017_SH",
            wind_code="600017.SH",
            sec_name="测试公司",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["finance"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def _patch_rule_engine(monkeypatch, triggered=True):
    monkeypatch.setattr(
        "app.domain.finance.rule_engine.evaluate_all_rules",
        _fake_evaluate_all_rules(triggered=triggered),
    )


def _patch_fetch(monkeypatch, comp_type=1, industry="医药生物"):
    monkeypatch.setattr(
        "app.domain.finance.parent_scope.fetch_company_field",
        _fake_fetch_company_field(comp_type=comp_type, industry=industry),
    )


# ══════════════════════════════════════════════════════════
# finance_node 接线
# ══════════════════════════════════════════════════════════


def test_triggered_rule_writes_similar_cases(monkeypatch):
    _patch_rule_engine(monkeypatch, triggered=True)
    _patch_fetch(monkeypatch, comp_type=1)
    # 2026-08-16 口径整改：未传期次时 as_of 从库内真实期次推导（禁硬编码）；
    # 单测锁定推导结果为固定期，保持本文件「不访问真实 DB」约束。
    monkeypatch.setattr(
        "app.domain.finance.data_as_of.resolve_company_data_as_of",
        lambda code: "20260331",
    )
    provider = FakeProvider()
    finance_node_module.set_similar_case_provider(provider)

    out = finance_node_module.finance_node(_make_state())
    details = out["results"].finance.rule_details

    assert details["R1"]["similar_cases"]["status"] == "ok"
    # 非触发规则不写该键
    assert "similar_cases" not in details["R2"]
    # metric_value 来自 RuleResult.current（gap=12.0），不内部自算
    assert provider.calls == [
        ("R1", "600017.SH", {"gap": 12.0}, "医药生物", "20260331")
    ]


def test_comp_type_2_writes_not_supported(monkeypatch):
    _patch_rule_engine(monkeypatch, triggered=True)
    _patch_fetch(monkeypatch, comp_type=2)
    provider = FakeProvider()
    finance_node_module.set_similar_case_provider(provider)

    out = finance_node_module.finance_node(_make_state())
    details = out["results"].finance.rule_details

    assert details["R1"]["similar_cases"]["status"] == "not_supported"
    # 金融企业不调用 Provider
    assert provider.calls == []


def test_provider_exception_writes_error_not_blocking(monkeypatch):
    _patch_rule_engine(monkeypatch, triggered=True)
    _patch_fetch(monkeypatch, comp_type=1)
    provider = FakeProvider(exc=RuntimeError("boom"))
    finance_node_module.set_similar_case_provider(provider)

    out = finance_node_module.finance_node(_make_state())  # 不抛异常
    details = out["results"].finance.rule_details

    assert details["R1"]["similar_cases"]["status"] == "error"
    assert "boom" in details["R1"]["similar_cases"]["reason"]
    # 节点仍正常产出 module_status
    assert out["module_status"]["finance"].state == "success"


# ══════════════════════════════════════════════════════════
# persist_turn._build_panel_data 透出
# ══════════════════════════════════════════════════════════


def test_panel_data_triggered_rules_carry_similar_cases():
    sc = SimilarCasesResult(status="ok", reason="", cases=[])
    finance = FinanceResult(
        rule_statuses={"R1": "triggered", "R2": "not_triggered"},
        rule_details={
            "R1": {
                "rule_name": "应收–营收背离",
                "evidence_ids": ["ev_fin_x"],
                "similar_cases": sc.model_dump(mode="json"),
            },
            "R2": {"rule_name": "现金流–利润背离", "evidence_ids": []},
        },
    )
    state: AgentState = {
        "final_response": FinalResponse(answer="有风险", risk_level="red"),
        "results": ModuleResults(finance=finance),
    }
    panel = persist_turn_module._build_panel_data(state)
    assert panel is not None
    assert len(panel["triggered_rules"]) == 1
    entry = panel["triggered_rules"][0]
    assert entry["rule_id"] == "R1"
    assert entry["similar_cases"]["status"] == "ok"


def test_panel_data_omits_similar_cases_when_absent():
    finance = FinanceResult(
        rule_statuses={"R1": "triggered"},
        rule_details={
            "R1": {"rule_name": "应收–营收背离", "evidence_ids": ["ev_fin_x"]}
        },
    )
    state: AgentState = {
        "final_response": FinalResponse(answer="有风险", risk_level="red"),
        "results": ModuleResults(finance=finance),
    }
    panel = persist_turn_module._build_panel_data(state)
    assert panel is not None
    entry = panel["triggered_rules"][0]
    assert "similar_cases" not in entry
