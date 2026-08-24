"""研报 Evidence 最后一层解析回归（评级证据 → 原始研报）。

验收要求（第二轮外部验收 P1）:
- source.resolved is True
- source.record.report_id 正确
- 无 SOURCE_RECORD_NOT_FOUND

依赖 MySQL 真实数据；CI（SQLite）下自动跳过。
"""

import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql",
    reason="需要 MySQL 研报数据（CI 为 SQLite）",
)


def _first_report_id() -> str:
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            rid = conn.execute(
                text(
                    "SELECT report_id FROM research_reports "
                    "WHERE report_id IS NOT NULL AND report_id != '' LIMIT 1"
                )
            ).scalar()
    finally:
        engine.dispose()
    assert rid, "research_reports 无数据，无法回归"
    return str(rid)


def test_resolve_research_report_direct():
    """直接调用 resolve_source：resolved=True + report_id 正确。"""
    from app.application.services.source_resolver import resolve_source

    rid = _first_report_id()
    out = resolve_source(
        source_type="research_report",
        source_record_id=rid,
        source_table="research_reports",
    )
    assert out["resolved"] is True, out
    assert str(out["record"]["report_id"]) == rid
    assert out["record"]["title"]
    assert out["record"]["org_name"]


def _first_rating_evidence() -> tuple[str, str]:
    """取库中真实评级证据 (evidence_id, report_id)。"""
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT rc.evidence_id, er.source_record_id "
                    "FROM rating_changes rc "
                    "JOIN evidence_refs er ON er.evidence_id = rc.evidence_id "
                    "WHERE er.source_type = 'research_report' LIMIT 1"
                )
            ).first()
    finally:
        engine.dispose()
    if not row:
        pytest.skip("rating_changes 无研报评级证据夹具")
    return str(row[0]), str(row[1])


def test_evidence_endpoint_resolves_report():
    """Evidence 端点：source.resolved=True + 无 SOURCE_RECORD_NOT_FOUND。"""
    from fastapi.testclient import TestClient

    from app.main import app

    eid, rid = _first_rating_evidence()
    client = TestClient(app)
    r = client.get(f"/api/v1/evidence/{eid}")
    assert r.status_code == 200
    d = r.json()["data"]
    src = d.get("source", {})
    assert src.get("resolved") is True, d
    assert str(src.get("record", {}).get("report_id")) == rid
    codes = [w.get("code") for w in r.json().get("warnings", [])]
    assert "SOURCE_RECORD_NOT_FOUND" not in codes
