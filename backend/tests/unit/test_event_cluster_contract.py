"""事件簇交接契约单元测试 — Phase C 任务 15.

覆盖：正例、缺字段、日期反转、sources/evidence_ids 为空、ID 前缀、
重复来源、JSON Schema 校验、ID 确定性。
"""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.events.contracts import (
    EventClusterRecord,
    EventSourceRef,
    make_event_cluster_id,
)


def _source(source_id: str = "ann_001") -> EventSourceRef:
    return EventSourceRef(
        source_id=source_id,
        source_type="announcement",
        source_record_id="ann_600518_001",
        title="公告标题",
        published_at=date(2025, 1, 15),
    )


def _valid() -> dict:
    return {
        "event_cluster_id": "evtcl_0123456789abcdef01234567",
        "entity_id": "company_600518_SH",
        "wind_code": "600518.SH",
        "topic": "重大合同与经营进展",
        "summary": "摘要",
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "event_count": 1,
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "sources": [_source().model_dump(mode="json")],
        "evidence_ids": ["ev_ann_0123456789abcdef"],
        "cluster_method": "llm_semantic_v1",
        "cluster_version": "1.0.0",
        "dataset_version": "phase-c-202608",
        "quality_flags": [],
        "created_at": "2026-08-02T12:00:00Z",
    }


def test_valid_record():
    rec = EventClusterRecord.model_validate(_valid())
    assert rec.event_cluster_id.startswith("evtcl_")
    assert rec.event_count == 1


def test_missing_required_field():
    payload = _valid()
    del payload["topic"]
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_date_reversed():
    payload = _valid()
    payload["start_date"] = "2025-04-01"
    payload["end_date"] = "2025-03-01"
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_sources_empty():
    payload = _valid()
    payload["sources"] = []
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_evidence_ids_empty():
    payload = _valid()
    payload["evidence_ids"] = []
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_id_not_evtcl_prefix():
    payload = _valid()
    payload["event_cluster_id"] = "cluster_负面公告"
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_event_count_mismatch():
    payload = _valid()
    payload["event_count"] = 3  # 但 sources 只有 1 条
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_duplicate_sources():
    payload = _valid()
    payload["sources"] = [
        _source().model_dump(mode="json"),
        _source().model_dump(mode="json"),
    ]
    payload["event_count"] = 2
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_sentiment_score_out_of_range():
    payload = _valid()
    payload["sentiment_score"] = 1.5
    with pytest.raises(ValidationError):
        EventClusterRecord.model_validate(payload)


def test_json_schema_validation():
    """JSON Schema 校验样例（与 docs/schemas 一致）。"""
    import jsonschema
    from pathlib import Path

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "schemas"
        / "event_cluster.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=_valid(), schema=schema)


def test_make_event_cluster_id_deterministic():
    a = make_event_cluster_id(
        wind_code="600518.SH",
        topic="重大合同",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        source_record_ids=["ann_001", "ann_002"],
        cluster_version="1.0.0",
    )
    b = make_event_cluster_id(
        wind_code="600518.SH",
        topic="重大合同",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        source_record_ids=["ann_002", "ann_001"],  # 顺序无关
        cluster_version="1.0.0",
    )
    assert a == b
    assert a.startswith("evtcl_")


def test_make_event_cluster_id_differs_by_company():
    a = make_event_cluster_id(
        wind_code="600518.SH",
        topic="负面",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        source_record_ids=["x"],
        cluster_version="1",
    )
    b = make_event_cluster_id(
        wind_code="600519.SH",
        topic="负面",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        source_record_ids=["x"],
        cluster_version="1",
    )
    assert a != b
