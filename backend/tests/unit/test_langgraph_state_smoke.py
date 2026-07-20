"""LangGraph AgentState smoke tests — V12 TypedDict pattern."""

from app.agents.state import AgentState, Claim, EvidenceRef, ModuleStatus, RuntimeState


class TestAgentState:
    """AgentState TypedDict 构造和访问."""

    def test_agent_state_creation(self):
        state: AgentState = {
            "user_query": "测试问题",
            "runtime": RuntimeState(trace_id="trace_01"),
        }
        assert state["user_query"] == "测试问题"
        assert state["runtime"].trace_id == "trace_01"

    def test_agent_state_defaults(self):
        state: AgentState = {}
        assert state.get("user_query", "") == ""
        assert state.get("plan") is None
        assert state.get("module_status") is None

    def test_agent_state_with_claims(self):
        claim = Claim(claim_id="cl_001", text="测试声明", severity="high")
        state: AgentState = {"claims": [claim]}
        assert len(state["claims"]) == 1
        assert state["claims"][0].claim_id == "cl_001"

    def test_agent_state_with_evidence(self):
        ev = EvidenceRef(
            evidence_id="ev_001",
            source_type="financial_statement",
            source_title="测试来源",
            field_path="测试字段",
            value="测试值",
        )
        state: AgentState = {"evidence": [ev]}
        assert len(state["evidence"]) == 1
        assert state["evidence"][0].evidence_id == "ev_001"

    def test_agent_state_module_status(self):
        st = ModuleStatus(state="success", duration_ms=100)
        state: AgentState = {"module_status": {"finance": st}}
        assert state["module_status"]["finance"].state == "success"

    def test_agent_state_roundtrip(self):
        state: AgentState = {
            "user_query": "贵州茅台2023年营收是多少？",
            "runtime": RuntimeState(session_id="ses_01", trace_id="trace_01"),
        }
        data = dict(state)
        assert data["user_query"] == "贵州茅台2023年营收是多少？"
        assert data["runtime"].session_id == "ses_01"


class TestClaimModel:
    """Claim 模型测试."""

    def test_claim_with_evidence(self):
        claim = Claim(
            claim_id="cl_001",
            text="营业收入1505.60亿",
            evidence_ids=["ev_001"],
        )
        assert len(claim.evidence_ids) == 1
        assert claim.evidence_ids[0] == "ev_001"

    def test_claim_counter_evidence(self):
        claim = Claim(claim_id="cl_001", text="测试")
        assert claim.evidence_ids == []
