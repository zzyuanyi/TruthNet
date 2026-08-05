"""REST /chat 契约字段回归 — claims / module_status 透出（缺陷修复验证）.

历史缺陷: ChatDataV1 无 claims/module_status，前端 Phase D #1（partial 场景 UI）
与评测对外接口均被阻塞。修复: schema 追加两字段 + _build_chat_response 组装透出。

覆盖（外部审核要求）:
1. ClaimV1.from_claim 两种输入（dict / 模型对象），含 rule_version/limitations
2. ChatDataV1 默认值（空 → [] / {}）
3. _build_chat_response() 组装回归（固定 stub → c1 / partial）——缺陷真正发生点
4. _status_value 状态转换（对象/dict/字符串 × partial/failed/skipped）
5. REST 失败路径默认（claims=[] / module_status={}）
"""

from app.agents.state import Claim, ModuleStatus
from app.api.v1.routers.chat import _build_chat_response, _status_value
from app.api.v1.schemas.chat import ChatDataV1, ClaimV1


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
    # module_status 透出（三种输入形态全部转换）
    assert data.module_status["finance"] == "partial"
    assert data.module_status["equity"] == "success"
    assert data.module_status["risk"] == "failed"
    # 无 claims 时默认空列表
    result_empty = _stub_result()
    result_empty["claims"] = []
    assert _build_chat_response(result_empty, "tr2").data.claims == []


# ── 4. _status_value 状态转换 ───────────────────────────────


def test_status_value_object():
    assert _status_value(ModuleStatus(state="partial")) == "partial"
    assert _status_value(ModuleStatus(state="failed")) == "failed"
    assert _status_value(ModuleStatus(state="skipped")) == "skipped"


def test_status_value_dict():
    assert _status_value({"state": "partial"}) == "partial"
    assert _status_value({}) == "pending"  # 缺 state 缺省 pending


def test_status_value_string():
    assert _status_value("success") == "success"


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
