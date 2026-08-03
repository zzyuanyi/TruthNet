"""评级 Evidence ID 确定性 + RatingChange schema 契约（问题 3 收口）.

要求:
- 同一研报（report_id）重复构建得到相同 Evidence ID（确定性）
- ID 前缀 ev_report_（NS_REPORT 命名空间）
- RatingChange schema 携带可选 evidence_id（REST/Agent 可返回）
"""

from app.api.v1.schemas.events import RatingChange
from app.domain.provenance.id_factory import NS_REPORT, make_evidence_id


def _kwargs(**over):
    base = dict(
        source_namespace=NS_REPORT,
        source_type="research_report",
        source_record_id="RP202606010001",
        field_path="rating_change",
        period="2026-06-01",
        dataset_version="official-2026-07-12",
        company_code="603180.SH",
    )
    base.update(over)
    return base


def test_same_report_same_evidence_id():
    a = make_evidence_id(**_kwargs())
    b = make_evidence_id(**_kwargs())
    assert a == b


def test_different_report_different_id():
    a = make_evidence_id(**_kwargs(source_record_id="RP202606010001"))
    b = make_evidence_id(**_kwargs(source_record_id="RP202606010002"))
    assert a != b


def test_evidence_id_namespace_prefix():
    eid = make_evidence_id(**_kwargs())
    assert eid.startswith(f"ev_{NS_REPORT}_")
    assert len(eid.split("_")[-1]) == 16  # sha256 截断 16 位


def test_report_id_fallback_defensive():
    """report_id 缺失时回退组合键仍确定性（防御逻辑，不抛错）。"""
    a = make_evidence_id(
        **_kwargs(source_record_id="603180.SH|2026Q2|测试证券|2026-06-01")
    )
    b = make_evidence_id(
        **_kwargs(source_record_id="603180.SH|2026Q2|测试证券|2026-06-01")
    )
    assert a == b


def test_rating_change_schema_evidence_id_optional():
    rc = RatingChange(date="2026-06-01", org_name="测试证券")
    assert rc.evidence_id == ""  # 缺省为空串（兼容旧响应）

    rc2 = RatingChange(
        date="2026-06-01",
        org_name="测试证券",
        evidence_id="ev_report_abc123",
    )
    assert rc2.evidence_id == "ev_report_abc123"
