"""V12 核心模型单元测试."""

from app.core.enums import ModuleStatus, RiskLevel
from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.domain.company.models import CompanyRef
from app.domain.evidence.models import Claim, EvidenceRef
from app.domain.risk.models import RiskScore


class TestEvidenceRef:
    """EvidenceRef 序列化测试（canonical 字段）."""

    def test_evidence_ref_creation(self):
        ref = EvidenceRef(
            evidence_id="ev_001",
            source_type="financial_statement",
            source_record_id="2023_annual_bs",
            source_title="2023年报 利润表",
            field_path="营业收入",
            value="1505.60亿",
            dataset_version="2026-07-19",
        )
        assert ref.evidence_id == "ev_001"
        assert ref.source_type == "financial_statement"
        assert ref.field_path == "营业收入"

    def test_evidence_ref_serialization(self):
        ref = EvidenceRef(
            evidence_id="ev_001",
            source_type="financial_statement",
            source_title="2023年报 利润表",
            field_path="营业收入",
            value="1505.60亿",
        )
        data = ref.model_dump()
        assert data["evidence_id"] == "ev_001"
        assert data["source_type"] == "financial_statement"
        assert data["source_title"] == "2023年报 利润表"


class TestClaim:
    """Claim 序列化测试（canonical 字段）."""

    def test_claim_creation(self):
        claim = Claim(
            claim_id="cl_001",
            text="营业收入与现金流匹配良好",
            claim_type="financial",
            confidence=0.85,
            evidence_ids=["ev_001"],
        )
        assert claim.claim_id == "cl_001"
        assert claim.confidence == 0.85
        assert claim.evidence_ids == ["ev_001"]

    def test_claim_serialization(self):
        claim = Claim(
            claim_id="cl_001",
            text="测试声明",
            confidence=0.5,
        )
        data = claim.model_dump()
        assert data["claim_id"] == "cl_001"
        assert data["confidence"] == 0.5
        assert data["evidence_ids"] == []
        assert "generated_at" in data


class TestEvidenceModelUnity:
    """Agent 与 domain 必须使用同一 canonical 模型类（防双模型漂移）."""

    def test_agents_state_reuses_domain_model(self):
        from app.agents.state import Claim as StateClaim
        from app.agents.state import EvidenceRef as StateEvidenceRef

        assert StateEvidenceRef is EvidenceRef
        assert StateClaim is Claim


class TestChatEvidenceV1:
    """ChatEvidenceV1.from_evidence 映射细节."""

    def test_source_prefers_readable_title(self):
        from app.api.v1.schemas.chat import ChatEvidenceV1

        item = ChatEvidenceV1.from_evidence(
            {
                "source_type": "financial_statement",
                "source_title": "2023年报 利润表",
                "field_path": "营业收入",
                "value": "1505.60亿",
            }
        )
        assert item.source == "2023年报 利润表", "source 应优先可读标题而非机器值"

    def test_value_none_renders_empty_not_string(self):
        from app.api.v1.schemas.chat import ChatEvidenceV1

        item = ChatEvidenceV1.from_evidence({"source_type": "x", "value": None})
        assert item.value == "", "value=None 不得输出字符串 'None'"

    def test_from_evidence_model_object(self):
        from app.api.v1.schemas.chat import ChatEvidenceV1

        ref = EvidenceRef(
            evidence_id="ev_001",
            source_type="financial_statement",
            source_record_id="600519_2023_bs",
            source_title="2023年报 利润表",
            field_path="营业收入",
            value="1505.60亿",
            period="2023-12-31",
            unit="亿元",
            dataset_version="2026-07-19",
        )
        item = ChatEvidenceV1.from_evidence(ref)
        assert item.evidence_id == "ev_001"
        assert item.source_record_id == "600519_2023_bs"
        assert item.period == "2023-12-31"
        assert item.dataset_version == "2026-07-19"


class TestCompanyRef:
    """CompanyRef 测试."""

    def test_company_ref_creation(self):
        c = CompanyRef(code="600519", name="贵州茅台酒股份有限公司")
        assert c.code == "600519"
        assert c.name == "贵州茅台酒股份有限公司"
        assert c.status == "active"

    def test_company_ref_serialization(self):
        c = CompanyRef(code="600519", name="贵州茅台")
        data = c.model_dump()
        assert data["code"] == "600519"


class TestRiskScore:
    """RiskScore 测试."""

    def test_risk_score_defaults(self):
        rs = RiskScore()
        assert rs.overall == 0.0
        assert rs.level == RiskLevel.LOW

    def test_risk_score_bounds(self):
        rs = RiskScore(overall=0.5, financial=0.8)
        assert 0.0 <= rs.overall <= 1.0
        assert 0.0 <= rs.financial <= 1.0


class TestApiMeta:
    """ApiMeta 测试."""

    def test_meta_creation(self):
        meta = ApiMeta(request_id="req_01", trace_id="trace_01")
        assert meta.request_id == "req_01"
        assert meta.schema_version == "1.0"
        assert meta.generated_at  # auto-generated


class TestV12Response:
    """V12Response envelope 测试."""

    def test_v12_response_structure(self):
        resp = V12Response(
            data={"key": "value"},
            meta=ApiMeta(request_id="r1", trace_id="t1"),
        )
        data = resp.model_dump()
        assert "data" in data
        assert "meta" in data
        assert "warnings" in data
        assert data["data"]["key"] == "value"

    def test_v12_response_with_warnings(self):
        resp = V12Response(
            data=None,
            meta=ApiMeta(request_id="r1", trace_id="t1"),
            warnings=[WarningItem(code="W001", message="测试警告")],
        )
        assert len(resp.warnings) == 1
        assert resp.warnings[0].code == "W001"


class TestEnums:
    """枚举测试."""

    def test_risk_level_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_module_status_values(self):
        assert ModuleStatus.COMPLETED == "completed"
        assert ModuleStatus.FAILED == "failed"
