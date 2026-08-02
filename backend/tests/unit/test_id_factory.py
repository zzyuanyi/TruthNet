"""ID 工厂单元测试 — Phase C 任务 16.

确定性 / 可重放 / 全局唯一 / 不碰撞。
"""

from app.domain.provenance.id_factory import (
    is_legacy_claim_id,
    is_legacy_evidence_id,
    make_claim_id,
    make_evidence_id,
)


def test_evidence_id_deterministic():
    a = make_evidence_id(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id="600518.SH|20260331|408006000",
        field_path="acct_rcv",
        period="20260331",
        dataset_version="competition-2026",
        company_code="600518.SH",
    )
    b = make_evidence_id(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id="600518.SH|20260331|408006000",
        field_path="acct_rcv",
        period="20260331",
        dataset_version="competition-2026",
        company_code="600518.SH",
    )
    assert a == b
    assert a.startswith("ev_fin_")
    assert len(a) > len("ev_fin_")


def test_evidence_id_differs_across_companies():
    a = make_evidence_id(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id="600518.SH|20260331|408006000",
        field_path="acct_rcv",
        company_code="600518.SH",
    )
    b = make_evidence_id(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id="600519.SH|20260331|408006000",
        field_path="acct_rcv",
        company_code="600519.SH",
    )
    assert a != b


def test_claim_id_same_turn_retry():
    kwargs = dict(
        turn_id="turn_01",
        company_code="600518.SH",
        claim_type="financial",
        rule_id="R1",
        ordinal=0,
        claim_text="康美药业应收账款增速与营业收入增速存在显著背离",
        rule_version="1.0.0",
    )
    assert make_claim_id(**kwargs) == make_claim_id(**kwargs)


def test_claim_id_differs_across_turns():
    a = make_claim_id(
        turn_id="turn_01",
        company_code="600518.SH",
        claim_type="financial",
        rule_id="R1",
        ordinal=0,
        claim_text="t",
    )
    b = make_claim_id(
        turn_id="turn_02",
        company_code="600518.SH",
        claim_type="financial",
        rule_id="R1",
        ordinal=0,
        claim_text="t",
    )
    assert a != b


def test_claim_id_differs_across_companies():
    a = make_claim_id(
        turn_id="turn_01",
        company_code="600518.SH",
        claim_type="equity",
        ordinal=0,
        claim_text="控制链穿透",
    )
    b = make_claim_id(
        turn_id="turn_01",
        company_code="600519.SH",
        claim_type="equity",
        ordinal=0,
        claim_text="控制链穿透",
    )
    assert a != b


def test_claim_id_no_collision_multiple_rules_same_turn():
    ids = {
        make_claim_id(
            turn_id="turn_01",
            company_code="600518.SH",
            claim_type="financial",
            rule_id=rid,
            ordinal=i,
            claim_text=f"rule {rid}",
        )
        for i, rid in enumerate(["R1", "R2", "R3"])
    }
    assert len(ids) == 3


def test_legacy_id_detection():
    assert is_legacy_claim_id("claim_R1_01")
    assert is_legacy_claim_id("claim_eq_01")
    assert is_legacy_claim_id("claim_events_01")
    assert not is_legacy_claim_id("clm_0123456789abcdef")
    assert is_legacy_evidence_id("ev_eq_01")
    assert is_legacy_evidence_id("ann_001")
    assert not is_legacy_evidence_id("ev_eq_0123456789abcdef")
