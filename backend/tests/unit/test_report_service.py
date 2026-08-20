"""Report task state and request payload regressions."""

import asyncio

import pytest
from sqlalchemy import create_engine, text

from app.application.services import report_service


def test_get_report_job_restores_request_payload(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'report.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE report_jobs ("
                "report_id TEXT PRIMARY KEY, session_id TEXT, company_code TEXT, "
                "status TEXT, progress INTEGER, idempotency_key TEXT, file_path TEXT, "
                "file_sha256 TEXT, error_code TEXT, error_message TEXT, trace_id TEXT, "
                "request_payload TEXT, created_at DATETIME, started_at DATETIME, "
                "completed_at DATETIME, updated_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO report_jobs "
                "(report_id, company_code, status, progress, request_payload) "
                "VALUES ('report_1', '600518.SH', 'queued', 0, :payload)"
            ),
            {"payload": '{"as_of": "20241231"}'},
        )
    monkeypatch.setattr(report_service, "_get_engine", lambda: engine)
    job = report_service.get_report_job("report_1")
    assert job is not None
    assert job["request_payload"] == {"as_of": "20241231"}
    engine.dispose()


@pytest.mark.asyncio
async def test_report_generation_stops_when_queue_claim_fails(monkeypatch):
    monkeypatch.setattr(report_service, "_sem", lambda: asyncio.Semaphore(1))
    monkeypatch.setattr(
        report_service,
        "get_report_job",
        lambda report_id: {"report_id": report_id, "status": "queued"},
    )
    monkeypatch.setattr(report_service, "_update_status", lambda *a, **k: False)
    monkeypatch.setattr(
        report_service,
        "_generate_report_pdf",
        lambda *a, **k: pytest.fail("CAS 失败后不得继续生成 PDF"),
    )
    await report_service._run_report_job("report_1")
