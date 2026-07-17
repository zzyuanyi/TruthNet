"""V12 核心模型单元测试."""

from app.core.enums import ModuleStatus, RiskLevel
from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.domain.company.models import CompanyRef
from app.domain.evidence.models import Claim, ConfidenceLevel, EvidenceRef, EvidenceType
from app.domain.risk.models import RiskScore


class TestEvidenceRef:
    """EvidenceRef 序列化测试."""

    def test_evidence_ref_creation(self):
        ref = EvidenceRef(
            id="ev_001",
            type=EvidenceType.FINANCIAL_STATEMENT,
            source="2023年报 利润表",
            field="营业收入",
            value="1505.60亿",
        )
        assert ref.id == "ev_001"
        assert ref.type == EvidenceType.FINANCIAL_STATEMENT
        assert ref.source == "2023年报 利润表"

    def test_evidence_ref_serialization(self):
        ref = EvidenceRef(
            id="ev_001",
            type=EvidenceType.FINANCIAL_STATEMENT,
            source="2023年报 利润表",
            field="营业收入",
            value="1505.60亿",
        )
        data = ref.model_dump()
        assert data["id"] == "ev_001"
        assert data["type"] == "financial_statement"
        assert data["source"] == "2023年报 利润表"


class TestClaim:
    """Claim 序列化测试."""

    def test_claim_creation(self):
        claim = Claim(
            id="cl_001",
            statement="营业收入与现金流匹配良好",
            confidence=ConfidenceLevel.HIGH,
            evidence=[
                EvidenceRef(
                    id="ev_001",
                    type=EvidenceType.FINANCIAL_STATEMENT,
                    source="2023年报 利润表",
                    field="营业收入",
                    value="1505.60亿",
                ),
            ],
        )
        assert claim.id == "cl_001"
        assert claim.confidence == ConfidenceLevel.HIGH
        assert len(claim.evidence) == 1

    def test_claim_serialization(self):
        claim = Claim(
            id="cl_001",
            statement="测试声明",
            confidence=ConfidenceLevel.MEDIUM,
        )
        data = claim.model_dump()
        assert data["id"] == "cl_001"
        assert data["confidence"] == "medium"
        assert "generated_at" in data


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
