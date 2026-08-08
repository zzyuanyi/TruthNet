"""REST /chat public contract regression tests.

历史缺陷: ChatDataV1 无 claims/module_status，前端 Phase D #1（partial 场景 UI）
与评测对外接口均被阻塞。修复: schema 追加两字段 + _build_chat_response 组装透出。

覆盖（外部审核要求）:
1. ClaimV1.from_claim 两种输入（dict / 模型对象），含 rule_version/limitations
2. ChatDataV1 默认值（空 → [] / {}）
3. _build_chat_response() 组装回归（固定 stub → c1 / partial）——缺陷真正发生点
4. _status_value 状态转换（对象/dict/字符串 × partial/failed/skipped）
5. REST 失败路径默认（claims=[] / module_status={}）
"""

import asyncio
import threading
import time

import pytest
from pydantic import ValidationError

from app.agents.state import (
    Claim,
    CompanyRef,
    ExecutionPlan,
    FinalResponse,
    ModuleResults,
    ModuleStatus,
)
from app.api.v1.routers.chat import _build_chat_response
from app.api.v1.schemas.chat import (
    ChatContextV1,
    ChatDataV1,
    ChatRequestV1,
    ClaimV1,
    ModuleStatusV1,
)


# ── 1. ClaimV1.from_claim 两种输入 ──────────────────────────


def test_claimv1_from_model_object():
    c = Claim(
        claim_id="c1",
        text="康美药业股权穿透存在关联方控制",
        claim_type="equity",
        severity="high",
        confidence=0.8,
        rule_id="R7",
        rule_version="1.0.0",
        evidence_ids=["ev_1", "ev_2"],
        verification_status="verified",
        limitations=["数据截至 2025 年报"],
    )
    dto = ClaimV1.from_claim(c)
    assert dto.claim_id == "c1"
    assert dto.rule_version == "1.0.0"
    assert dto.limitations == ["数据截至 2025 年报"]
    assert dto.evidence_ids == ["ev_1", "ev_2"]


def test_claimv1_from_dict():
    dto = ClaimV1.from_claim(
        {"claim_id": "c2", "text": "t", "severity": "medium", "rule_version": "2.0"}
    )
    assert dto.claim_id == "c2"
    assert dto.rule_version == "2.0"
    assert dto.verification_status == "pending"  # 缺省
    assert dto.limitations == []  # 缺省


# ── 2. ChatDataV1 默认值 ────────────────────────────────────


def test_chatdata_defaults():
    d = ChatDataV1(answer="a", trace_id="t")
    assert d.claims == []
    assert d.module_status == {}


def test_chat_request_strips_and_validates_boundaries():
    request = ChatRequestV1(question="  分析康美药业  ", session_id="ses_01")
    assert request.question == "分析康美药业"
    with pytest.raises(ValidationError):
        ChatRequestV1(question="   ")
    with pytest.raises(ValidationError):
        ChatRequestV1(question="q", session_id="bad session")


# ── 3. _build_chat_response 组装回归（缺陷真正发生点）───────


def _stub_result() -> dict:
    return {
        "final_response": None,
        "evidence": [],
        "module_status": {
            "finance": ModuleStatus(state="partial"),
            "equity": {"state": "success"},  # dict 输入
            "risk": "failed",  # 字符串输入
        },
        "results": None,
        "claims": [
            Claim(
                claim_id="c1",
                text="财务规则 R1 触发",
                claim_type="financial",
                rule_id="R1",
            )
        ],
        "risk_output": None,
        "runtime": None,
    }


def test_build_chat_response_assembles_claims_and_module_status():
    resp = _build_chat_response(_stub_result(), "tr_test")
    data = resp.data
    # claims 透出
    assert data.claims[0].claim_id == "c1"
    assert data.claims[0].rule_id == "R1"
    # module_status 透出（三种输入形态全部转换 → typed ModuleStatusV1）
    assert data.module_status["finance"].state == "partial"
    assert data.module_status["equity"].state == "success"
    assert data.module_status["risk"].state == "failed"
    # 无 claims 时默认空列表
    result_empty = _stub_result()
    result_empty["claims"] = []
    assert _build_chat_response(result_empty, "tr2").data.claims == []


def test_build_chat_response_exposes_intent():
    """前端必须能区分闲聊与分析，避免显示伪风险面板和证据缺失标签。"""
    result = _stub_result()
    result["plan"] = ExecutionPlan(intent="chitchat", requested_modules=[])

    assert _build_chat_response(result, "tr_intent").data.intent == "chitchat"


def test_build_chat_response_exposes_session_and_candidates():
    result = _stub_result()
    result["plan"] = ExecutionPlan(intent="company_disambiguation")
    result["company_candidates"] = [
        CompanyRef(
            entity_id="company_000001_SZ",
            wind_code="000001.SZ",
            sec_name="平安银行",
            exchange="XSHE",
        )
    ]
    data = _build_chat_response(result, "tr", "ses_generated").data
    assert data.session_id == "ses_generated"
    assert data.company_candidates[0].wind_code == "000001.SZ"


def test_rest_context_and_generated_session_propagate(monkeypatch):
    from app.api.v1.routers import chat as chat_router

    captured: list[dict] = []

    class FakeGraph:
        def invoke(self, state):
            captured.append(state)
            return {
                **state,
                "final_response": FinalResponse(answer="ok", risk_level="green"),
                "results": ModuleResults(),
            }

    monkeypatch.setattr(chat_router, "_get_graph", lambda: FakeGraph())
    first = asyncio.run(
        chat_router.chat_v1(
            ChatRequestV1(
                question="分析一下",
                context=ChatContextV1(company_code="600518.SH", fiscal_year=2025),
            )
        )
    )
    generated = first.data.session_id
    assert generated
    assert captured[0]["request_context"].company_code == "600518.SH"
    assert captured[0]["request_context"].as_of.strftime("%Y%m%d") == "20251231"

    second = asyncio.run(
        chat_router.chat_v1(ChatRequestV1(question="继续", session_id=generated))
    )
    assert second.data.session_id == generated
    assert captured[1]["runtime"].session_id == generated


def test_rest_same_session_turns_are_serialized(monkeypatch):
    """同一 REST 会话不得并行持久化并抢占相同 turn_index。"""
    from app.api.v1.routers import chat as chat_router

    active = 0
    max_active = 0
    state_lock = threading.Lock()

    class FakeGraph:
        def invoke(self, state):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.03)
            with state_lock:
                active -= 1
            return {
                **state,
                "final_response": FinalResponse(answer="ok", risk_level="green"),
                "results": ModuleResults(),
            }

    monkeypatch.setattr(chat_router, "_get_graph", lambda: FakeGraph())

    async def run_both():
        return await asyncio.gather(
            chat_router.chat_v1(
                ChatRequestV1(question="问题一", session_id="ses_same")
            ),
            chat_router.chat_v1(
                ChatRequestV1(question="问题二", session_id="ses_same")
            ),
        )

    responses = asyncio.run(run_both())
    assert [item.data.answer for item in responses] == ["ok", "ok"]
    assert max_active == 1
    assert "ses_same" not in chat_router._rest_session_gates


# ── 4. ModuleStatusV1.from_status 三种输入形态（typed 化后）──


def test_status_value_object():
    assert ModuleStatusV1.from_status(ModuleStatus(state="partial")).state == "partial"
    assert ModuleStatusV1.from_status(ModuleStatus(state="failed")).state == "failed"
    assert ModuleStatusV1.from_status(ModuleStatus(state="skipped")).state == "skipped"


def test_status_value_dict():
    assert ModuleStatusV1.from_status({"state": "partial"}).state == "partial"
    assert ModuleStatusV1.from_status({}).state == "pending"  # 缺 state 缺省 pending


def test_status_value_string():
    assert ModuleStatusV1.from_status("success").state == "success"


# ── 5. REST 失败路径默认（schema 默认值已保证）──────────────


def test_failure_path_defaults():
    # 异常分支构造 ChatDataV1 时仅填 answer —— 新字段回落默认值
    d = ChatDataV1(answer="处理请求时发生内部错误，请稍后重试。", trace_id="t")
    assert d.claims == []
    assert d.module_status == {}
    assert d.risk_level == "unknown"


# ── 6. risk_level 透出（最终阶段等级，不从 risk_score 换算）─


def _stub_risk_result(final_risk: str | None, risk_output_level=None) -> dict:
    from app.agents.state import FinalResponse

    return {
        "final_response": FinalResponse(answer="t", risk_level=final_risk or ""),
        "risk_output": (
            type(
                "RO",
                (),
                {
                    "risk_level": risk_output_level,
                    "sub_scores": [],
                    "overall_score": 0.8,
                },
            )()
            if risk_output_level
            else None
        ),
        "claims": [],
        "module_status": {},
        "evidence": [],
        "results": None,
        "runtime": None,
    }


def test_build_chat_response_exposes_risk_level():
    data = _build_chat_response(_stub_risk_result("orange"), "tr").data
    assert data.risk_level == "orange"


def test_risk_level_all_levels():
    for lv in ("green", "orange", "red", "yellow"):
        data = _build_chat_response(_stub_risk_result(lv), "tr").data
        assert data.risk_level == lv


def test_risk_level_fallback_to_risk_output():
    """final_response 缺失 → 回退 risk_output（异常/中间状态备用）。"""
    data = _build_chat_response(
        {
            "final_response": None,
            "risk_output": type(
                "RO", (), {"risk_level": "red", "sub_scores": [], "overall_score": 0.8}
            )(),
            "claims": [],
            "module_status": {},
            "evidence": [],
            "results": None,
            "runtime": None,
        },
        "tr",
    ).data
    assert data.risk_level == "red"


def test_risk_level_unknown_when_none():
    """两者都没有 → unknown（不伪造等级）。"""
    data = _build_chat_response(
        {
            "final_response": None,
            "risk_output": None,
            "claims": [],
            "module_status": {},
            "evidence": [],
            "results": None,
            "runtime": None,
        },
        "tr",
    ).data
    assert data.risk_level == "unknown"
