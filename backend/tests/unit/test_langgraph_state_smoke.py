"""LangGraph AgentState smoke 测试."""

from app.agents.state import AgentState
from app.domain.evidence.models import Claim, ConfidenceLevel, EvidenceRef, EvidenceType


class TestAgentState:
    """AgentState 构造和基本操作."""

    def test_agent_state_creation(self):
        state = AgentState(question="测试问题", trace_id="trace_01")
        assert state.question == "测试问题"
        assert state.trace_id == "trace_01"
        assert state.answer == ""
        assert state.warnings == []

    def test_agent_state_defaults(self):
        state = AgentState()
        assert state.question == ""
        assert state.execution_plan == []
        assert state.module_status == {}
        assert state.evidence == []

    def test_agent_state_with_claims(self):
        claim = Claim(
            id="cl_001",
            statement="测试声明",
            confidence=ConfidenceLevel.HIGH,
        )
        state = AgentState(claims=[claim])
        assert len(state.claims) == 1
        assert state.claims[0].id == "cl_001"

    def test_agent_state_with_evidence(self):
        ev = EvidenceRef(
            id="ev_001",
            type=EvidenceType.FINANCIAL_STATEMENT,
            source="测试来源",
            field="测试字段",
            value="测试值",
        )
        state = AgentState(evidence=[ev.model_dump()])
        assert len(state.evidence) == 1

    def test_agent_state_module_status(self):
        state = AgentState(module_status={"mysql": "completed", "neo4j": "running"})
        assert state.module_status["mysql"] == "completed"
        assert state.module_status["neo4j"] == "running"

    def test_agent_state_roundtrip(self):
        state = AgentState(
            question="贵州茅台2023年营收是多少？",
            session_id="ses_01",
            intent="finance_analysis",
            trace_id="trace_01",
        )
        data = state.model_dump()
        assert data["question"] == "贵州茅台2023年营收是多少？"
        assert data["session_id"] == "ses_01"
        assert data["intent"] == "finance_analysis"


class TestClaimModel:
    """Claim 模型测试."""

    def test_claim_with_evidence(self):
        ev = EvidenceRef(
            id="ev_001",
            type=EvidenceType.FINANCIAL_STATEMENT,
            source="2023年报",
            field="营业收入",
            value="1505.60亿",
        )
        claim = Claim(
            id="cl_001",
            statement="营业收入1505.60亿",
            confidence=ConfidenceLevel.HIGH,
            evidence=[ev],
        )
        assert len(claim.evidence) == 1
        assert claim.evidence[0].field == "营业收入"

    def test_claim_counter_evidence(self):
        ev1 = EvidenceRef(
            id="ev_001",
            type=EvidenceType.FINANCIAL_STATEMENT,
            source="年报",
            field="营收",
            value="1500亿",
        )
        ev2 = EvidenceRef(
            id="ev_002",
            type=EvidenceType.NEWS_ARTICLE,
            source="媒体报道",
            field="质疑",
            value="营收有争议",
        )
        claim = Claim(
            id="cl_001",
            statement="测试",
            evidence=[ev1],
            counter_evidence=[ev2],
        )
        assert len(claim.counter_evidence) == 1
