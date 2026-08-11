"""ProvenanceService.persist_evidence 冲突校验 — ⑥（2026-08-11）.

覆盖 v3.1 要求：新增 / 幂等复用 / 同 ID 不同内容冲突回滚 / 批量回滚 /
空值兼容（一方为空视为可补全，与 persist_turn 同语义）。
使用临时 SQLite 引擎，无外部依赖。
"""

import pytest
from sqlalchemy import create_engine, text

from app.application.services.provenance_service import (
    EvidenceConflictError,
    ProvenanceService,
    _evidence_core_conflict,
)

_MIN_EVIDENCE_SCHEMA = """
CREATE TABLE evidence_refs (
    evidence_id VARCHAR(128) PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL,
    source_record_id VARCHAR(255),
    company_code VARCHAR(16),
    field_path VARCHAR(128),
    period VARCHAR(16),
    value VARCHAR(255),
    unit VARCHAR(16),
    statement_scope VARCHAR(32),
    source_title VARCHAR(255),
    dataset_version VARCHAR(64),
    retrieved_at DATETIME,
    turn_id VARCHAR(64),
    trace_id VARCHAR(64),
    module VARCHAR(32),
    source_table VARCHAR(64)
)
"""


@pytest.fixture
def service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as conn:
        conn.execute(text(_MIN_EVIDENCE_SCHEMA))
    svc = ProvenanceService(engine=engine)
    yield svc
    engine.dispose()


def _draft(
    eid="ev_fin_abc",
    field_path="rule_R1",
    company_code="600518.SH",
    period="20260331",
    value=None,
):
    return {
        "evidence_id": eid,
        "source_type": "financial_statement",
        "source_record_id": "600518.SH|20260331",
        "company_code": company_code,
        "field_path": field_path,
        "period": period,
        "dataset_version": "mock-v12",
        "module": "finance",
        "value": value,
    }


def test_insert_new(service):
    written = service.persist_evidence([_draft()], trace_id="t", turn_id="t")
    assert written == ["ev_fin_abc"]


def test_idempotent_reuse_same_content(service):
    service.persist_evidence([_draft()], trace_id="t", turn_id="t")
    written = service.persist_evidence([_draft()], trace_id="t", turn_id="t")
    assert written == ["ev_fin_abc"]  # 复用不重复写入


def test_conflict_raises_and_rolls_back(service):
    service.persist_evidence([_draft()], trace_id="t", turn_id="t")
    conflicting = _draft(field_path="rule_R2")  # 同 ID 不同内容
    with pytest.raises(EvidenceConflictError):
        service.persist_evidence([conflicting], trace_id="t", turn_id="t")


def test_batch_conflict_rolls_back_all(service):
    """批量中一条冲突 → 整批回滚（新插入的也不得残留）。"""
    ev1 = _draft(eid="ev_fin_new_1")
    service.persist_evidence([_draft()], trace_id="t", turn_id="t")
    ev2 = _draft(eid="ev_fin_abc", field_path="rule_R2")  # 冲突
    with pytest.raises(EvidenceConflictError):
        service.persist_evidence([ev1, ev2], trace_id="t", turn_id="t")
    # ev1 未残留（整批回滚）
    engine = service._engine
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM evidence_refs")).scalar()
    assert n == 1  # 只有最初的 ev_fin_abc


def test_null_gap_is_compatible(service):
    """一方为空（NULL/''）视为兼容可补全，不冲突。"""
    assert not _evidence_core_conflict(
        (
            "financial_statement",
            "600518.SH|20260331",
            None,
            None,
            "mock-v12",
            "600518.SH",
        ),
        (
            "financial_statement",
            "600518.SH|20260331",
            "rule_R1",
            "20260331",
            "mock-v12",
            "600518.SH",
        ),
    )


def test_both_nonempty_different_conflicts():
    assert _evidence_core_conflict(
        (
            "financial_statement",
            "600518.SH|20260331",
            "rule_R1",
            "20260331",
            "mock-v12",
            "600518.SH",
        ),
        (
            "financial_statement",
            "600518.SH|20260331",
            "rule_R2",
            "20260331",
            "mock-v12",
            "600518.SH",
        ),
    )


def test_gap_fill_updates_empty_fields(service):
    """④：已有记录空字段被补全（不只是"不冲突"）。"""
    from sqlalchemy import text

    # 先插入空字段记录
    service.persist_evidence(
        [{"evidence_id": "ev_fin_gap", "source_type": "financial_statement"}],
        trace_id="t",
        turn_id="t",
    )
    # 再次 persist 带完整内容 → 空字段应被 UPDATE 补全
    service.persist_evidence(
        [
            {
                "evidence_id": "ev_fin_gap",
                "source_type": "financial_statement",
                "source_record_id": "600518.SH|20260331",
                "company_code": "600518.SH",
                "field_path": "acct_rcv",
                "period": "20260331",
                "value": "45.5",
                "unit": "percent",
            }
        ],
        trace_id="t",
        turn_id="t",
    )
    engine = service._engine
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT source_record_id, company_code, field_path, period, "
                "value, unit FROM evidence_refs WHERE evidence_id='ev_fin_gap'"
            )
        ).first()
    assert tuple(row) == (
        "600518.SH|20260331",
        "600518.SH",
        "acct_rcv",
        "20260331",
        "45.5",
        "percent",
    )


def test_value_conflict_raises(service):
    """④：双方 value 均非空且不同 → 冲突。"""
    service.persist_evidence(
        [_draft(eid="ev_fin_val", value="10.0")], trace_id="t", turn_id="t"
    )
    with pytest.raises(EvidenceConflictError):
        service.persist_evidence(
            [_draft(eid="ev_fin_val", value="99.9")], trace_id="t", turn_id="t"
        )


def test_unknown_source_type_treated_missing(service):
    """④：source_type='unknown' 视为缺失（补全为 financial_statement）。"""
    from sqlalchemy import text

    service.persist_evidence(
        [{"evidence_id": "ev_fin_unk", "source_type": "unknown"}],
        trace_id="t",
        turn_id="t",
    )
    service.persist_evidence(
        [
            {
                "evidence_id": "ev_fin_unk",
                "source_type": "financial_statement",
                "source_record_id": "600518.SH|20260331",
            }
        ],
        trace_id="t",
        turn_id="t",
    )
    engine = service._engine
    with engine.connect() as conn:
        st = conn.execute(
            text("SELECT source_type FROM evidence_refs WHERE evidence_id='ev_fin_unk'")
        ).scalar()
    assert st == "financial_statement"
