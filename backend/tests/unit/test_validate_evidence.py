"""ValidateEvidence 节点单元测试 — V12 §7.2.

覆盖：验证状态打标（verified/partial/unsupported）、runtime.warnings、
返回空增量（claims 不翻倍回归）。
"""

from app.agents.nodes.validate_evidence import validate_evidence_node
from app.agents.state import (
    AgentState,
    Claim,
    EvidenceRef,
    RuntimeState,
)


def _ev(evidence_id: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type="financial_statement",
        source_record_id=f"src_{evidence_id}",
        source_title=f"{evidence_id} 来源",
    )


def _claim(claim_id: str, evidence_ids: list[str]) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=f"{claim_id} 结论",
        evidence_ids=evidence_ids,
    )


def _make_state(claims: list, evidence: list) -> AgentState:
    return {
        "user_query": "测试",
        "claims": claims,
        "evidence": evidence,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def test_all_verified():
    """全部证据引用存在 → 全部 verified。"""
    claims = [_claim("c1", ["ev_01"]), _claim("c2", ["ev_02"])]
    state = _make_state(claims, [_ev("ev_01"), _ev("ev_02")])
    result = validate_evidence_node(state)

    assert all(c.verification_status == "verified" for c in claims)
    assert result["runtime"].warnings == []


def test_missing_evidence_partial():
    """引用不存在的证据 → partial + warnings。"""
    claims = [_claim("c1", ["ev_missing"])]
    state = _make_state(claims, [_ev("ev_01")])
    result = validate_evidence_node(state)

    assert claims[0].verification_status == "partial"
    assert "缺失证据" in claims[0].limitations[0]
    assert any("c1" in w for w in result["runtime"].warnings)


def test_empty_evidence_ids_unsupported():
    """无证据引用 → unsupported + warnings。"""
    claims = [_claim("c1", [])]
    state = _make_state(claims, [_ev("ev_01")])
    result = validate_evidence_node(state)

    assert claims[0].verification_status == "unsupported"
    assert "缺少证据引用" in claims[0].limitations[0]
    assert any("c1" in w for w in result["runtime"].warnings)


def test_returns_empty_claims_increment():
    """返回空 claims 增量（拼接 reducer 下不翻倍）。"""
    claims = [_claim("c1", ["ev_01"])]
    state = _make_state(claims, [_ev("ev_01")])
    result = validate_evidence_node(state)

    assert result["claims"] == []
