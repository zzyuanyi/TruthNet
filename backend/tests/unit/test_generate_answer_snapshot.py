"""generate_answer 行为快照测试（重构 characterization 基线）。

用途：generate_answer.py（3600+ 行）拆分重构前锁定当前行为。
原则（收口清单 §7.1）：先补 characterization tests，再移动函数；
不改模板语义、不同时新增数据源、不做全局抽象层。

本测试对每个场景调用 generate_answer_node，把 final_response 完整
序列化后与 golden 文件逐字节比较。重构前后 golden 必须完全一致；
任何"顺手的文案微调"都会在此暴露。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.agents.nodes.generate_answer import generate_answer_node
from app.agents.state import (
    AgentState,
    Claim,
    CompanyRef,
    ExecutionPlan,
    FinanceResult,
    ModuleResults,
    ModuleStatus,
    RuntimeState,
)

_GOLDEN = Path(__file__).parent / "golden" / "generate_answer_snapshot.json"


class _PassthroughProvider:
    """透传 provider：返回用户原文（等效不润色，隔离真实 LLM）。"""

    provider_name = "test"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return messages[-1]["content"]

    async def chat_stream(self, messages, **kwargs):
        yield await self.chat(messages, **kwargs)

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """所有快照场景禁用真实 LLM（与 test_generate_answer.py 同款）。"""
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _PassthroughProvider(),
    )


def _company(name: str = "康美药业", code: str = "600518.SH") -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code.replace('.', '_')}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
    )


def _claim(
    claim_id: str,
    claim_type: str = "financial",
    severity: str = "red",
    rule_id: str | None = "R1",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=f"{claim_id} 结论",
        claim_type=claim_type,
        severity=severity,
        rule_id=rule_id,
    )


def _make_state(
    company: CompanyRef | None = None,
    claims: list | None = None,
    plan: ExecutionPlan | None = None,
    module_status: dict | None = None,
    results: ModuleResults | None = None,
    user_query: str = "测试",
    **extra,
) -> AgentState:
    state: AgentState = {
        "user_query": user_query,
        "company": company,
        "claims": claims or [],
        "evidence": [],
        "plan": plan,
        "module_status": module_status or {},
        "results": results or ModuleResults(),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    state.update(extra)
    return state


def _snapshot(result: dict) -> str:
    """把 generate_answer_node 返回序列化为稳定字符串。"""
    fr = result["final_response"]
    payload = {
        "answer": fr.answer,
        "risk_level": fr.risk_level,
        "claims": [
            c.model_dump() if hasattr(c, "model_dump") else str(c) for c in fr.claims
        ],
        "evidence": [
            e.model_dump() if hasattr(e, "model_dump") else str(e) for e in fr.evidence
        ],
        "follow_ups": list(fr.follow_ups or []),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


# ── 场景构造：无 company 分发分支 ─────────────────────────────


def _s_chitchat_generic():
    return _make_state(
        company=None,
        user_query="你好",
        plan=ExecutionPlan(intent="chitchat", requested_modules=[]),
    )


def _s_chitchat_thanks():
    return _make_state(
        company=None,
        user_query="谢谢",
        plan=ExecutionPlan(intent="chitchat", requested_modules=[]),
    )


def _s_chitchat_capability():
    return _make_state(
        company=None,
        user_query="你是谁",
        plan=ExecutionPlan(intent="chitchat", requested_modules=[]),
    )


def _s_unsupported_indicator():
    return _make_state(
        company=None,
        user_query="查询市盈率",
        plan=ExecutionPlan(intent="unsupported_indicator", requested_modules=[]),
    )


def _s_investment_advice():
    return _make_state(
        company=None,
        user_query="可以买吗",
        plan=ExecutionPlan(intent="investment_advice", requested_modules=[]),
    )


def _s_trade_execution():
    return _make_state(
        company=None,
        user_query="帮我买入",
        plan=ExecutionPlan(intent="trade_execution", requested_modules=[]),
    )


def _s_causal_query():
    return _make_state(
        company=None,
        user_query="为什么涨",
        plan=ExecutionPlan(intent="causal_query", requested_modules=[]),
    )


def _s_unsupported_scope():
    return _make_state(
        company=None,
        user_query="合并口径数据",
        plan=ExecutionPlan(intent="unsupported_scope", requested_modules=[]),
    )


def _s_event_list_requested():
    return _make_state(
        company=None,
        user_query="全市场质押公告",
        plan=ExecutionPlan(
            intent="simple_query", requested_modules=[], event_list_requested=True
        ),
    )


def _s_candidates_truncated():
    return _make_state(
        company=None,
        user_query="茅台",
        candidates_truncated=True,
    )


def _s_company_not_found():
    return _make_state(
        company=None,
        user_query="火星科技",
        entity_resolution_error="company_not_found",
    )


def _s_company_not_found_with_frags():
    return _make_state(
        company=None,
        user_query="火星科技怎么样",
        entity_resolution_error="company_not_found",
        unresolved_fragments=["火星科技"],
    )


def _s_company_not_found_market_query():
    return _make_state(
        company=None,
        user_query="买入茅台",
        entity_resolution_error="company_not_found",
    )


def _s_relation_clarify():
    return _make_state(
        company=None,
        user_query="分析康美和茅台",
        plan=ExecutionPlan(intent="relation_clarify", requested_modules=[]),
    )


def _s_company_disambiguation():
    cand = [
        CompanyRef(
            entity_id="c1", wind_code="000001.SZ", sec_name="平安银行", exchange="XSHE"
        ),
        CompanyRef(
            entity_id="c2", wind_code="601318.SH", sec_name="中国平安", exchange="XSHG"
        ),
        CompanyRef(
            entity_id="c3", wind_code="000660.SZ", sec_name="平安电工", exchange="XSHE"
        ),
    ]
    return _make_state(
        company=None,
        user_query="分析平安",
        plan=ExecutionPlan(intent="company_disambiguation", requested_modules=[]),
        company_candidates=cand,
    )


def _s_company_disambiguation_suggested():
    cand = [
        CompanyRef(
            entity_id="c1", wind_code="000001.SZ", sec_name="平安银行", exchange="XSHE"
        ),
        CompanyRef(
            entity_id="c2", wind_code="601318.SH", sec_name="中国平安", exchange="XSHG"
        ),
    ]
    return _make_state(
        company=None,
        user_query="分析平安",
        plan=ExecutionPlan(intent="company_disambiguation", requested_modules=[]),
        company_candidates=cand,
        suggested_company_code="601318.SH",
    )


def _s_comparison_guide():
    return _make_state(
        company=None,
        user_query="对比一下",
        plan=ExecutionPlan(intent="comparison_guide", requested_modules=[]),
    )


def _s_light_comparison_no_company():
    from app.agents.state import ComparisonSpec

    return _make_state(
        company=None,
        user_query="康美和茅台对比",
        plan=ExecutionPlan(
            intent="light_comparison",
            requested_modules=[],
            comparison=ComparisonSpec(
                scope="cross_company",
                mode="missing_dimension",
                requested_scope="indicator",
            ),
        ),
        comparison_targets=[],
    )


def _s_industry_benchmark_no_company():
    return _make_state(
        company=None,
        user_query="行业对比",
        plan=ExecutionPlan(intent="industry_benchmark", requested_modules=[]),
    )


# ── 场景构造：有 company 主分析路径 ──────────────────────────


def _s_diagnose_no_risk():
    fin = FinanceResult(rule_statuses={"R1": "not_triggered"}, warnings=[], evidence=[])
    return _make_state(
        company=_company(),
        user_query="分析康美药业财务风险",
        plan=ExecutionPlan(
            intent="diagnose", requested_modules=["finance"], as_of=date(2025, 9, 30)
        ),
        claims=[_claim("c1", "financial", "green", None)],
        results=ModuleResults(finance=fin),
    )


def _s_diagnose_with_risk():
    fin = FinanceResult(rule_statuses={"R1": "triggered"}, warnings=[], evidence=[])
    return _make_state(
        company=_company(),
        user_query="分析康美药业财务风险",
        plan=ExecutionPlan(
            intent="diagnose", requested_modules=["finance"], as_of=date(2025, 9, 30)
        ),
        claims=[_claim("c1", "financial", "red", "R1")],
        results=ModuleResults(finance=fin),
    )


def _s_equity_only():
    return _make_state(
        company=_company(),
        user_query="康美的股权结构",
        plan=ExecutionPlan(intent="equity", requested_modules=["equity"]),
        claims=[_claim("e1", "equity", "red", None)],
    )


def _s_unknown_company_type():
    fin = FinanceResult(
        rule_statuses={f"R{i}": "insufficient_data" for i in range(1, 8)},
        warnings=["公司类型缺失，无法判断是否适用非金融财务规则，规则未执行"],
        evidence=[],
    )
    return _make_state(
        company=_company(),
        user_query="分析康美药业财务风险",
        plan=ExecutionPlan(intent="diagnose", requested_modules=["finance"]),
        results=ModuleResults(finance=fin),
    )


def _s_finance_failed():
    return _make_state(
        company=_company(),
        user_query="分析康美药业财务风险",
        plan=ExecutionPlan(
            intent="diagnose", requested_modules=["finance", "equity", "events"]
        ),
        module_status={
            "finance": ModuleStatus(state="failed", error_code="FINANCE_FAILED")
        },
    )


SCENARIOS = {
    "chitchat_generic": _s_chitchat_generic,
    "chitchat_thanks": _s_chitchat_thanks,
    "chitchat_capability": _s_chitchat_capability,
    "unsupported_indicator": _s_unsupported_indicator,
    "investment_advice": _s_investment_advice,
    "trade_execution": _s_trade_execution,
    "causal_query": _s_causal_query,
    "unsupported_scope": _s_unsupported_scope,
    "event_list_requested": _s_event_list_requested,
    "candidates_truncated": _s_candidates_truncated,
    "company_not_found": _s_company_not_found,
    "company_not_found_with_frags": _s_company_not_found_with_frags,
    "company_not_found_market_query": _s_company_not_found_market_query,
    "relation_clarify": _s_relation_clarify,
    "company_disambiguation": _s_company_disambiguation,
    "company_disambiguation_suggested": _s_company_disambiguation_suggested,
    "comparison_guide": _s_comparison_guide,
    "light_comparison_no_company": _s_light_comparison_no_company,
    "industry_benchmark_no_company": _s_industry_benchmark_no_company,
    "diagnose_no_risk": _s_diagnose_no_risk,
    "diagnose_with_risk": _s_diagnose_with_risk,
    "equity_only": _s_equity_only,
    "unknown_company_type": _s_unknown_company_type,
    "finance_failed": _s_finance_failed,
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_answer_snapshot(name: str):
    """每个分发场景的 final_response 快照必须与 golden 完全一致。"""
    assert _GOLDEN.exists(), f"golden 文件缺失: {_GOLDEN}"
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert name in golden, f"golden 缺少场景 {name}"
    result = generate_answer_node(SCENARIOS[name]())
    actual = _snapshot(result)
    assert actual == golden[name], (
        f"场景 {name} 行为与 golden 不一致——重构/改动改变了输出，"
        "请先确认是否有意为之，再更新 golden（禁止为绕过测试而改 golden）"
    )
