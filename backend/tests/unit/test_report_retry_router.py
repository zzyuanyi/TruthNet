"""PDF 报告重试 Router 单测 — 8.11 P2（审查）：响应不得是陈旧 failed。

覆盖：幂等命中 failed 任务 → POST /reports 重试 → 响应 queued；
CAS 失败（并发请求已重置）→ 重新查询返回最新状态，不重复启动。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _patch_services(monkeypatch, *, retry_result: bool):
    """mock report_service：get_report_job 首次返回 failed，之后返回 queued。"""
    import app.api.v1.routers.reports as reports_mod

    started: list[str] = []

    def fake_create_report_job(**kwargs):
        return "report_retry_test", False  # 幂等命中（created=False）

    state = {"calls": 0}

    def fake_get_report_job(rid):
        state["calls"] += 1
        if state["calls"] == 1:
            return {
                "report_id": rid,
                "session_id": None,
                "company_code": "600518.SH",
                "status": "failed",
                "progress": 42,
                "idempotency_key": None,
                "file_path": None,
                "file_sha256": None,
                "error_code": "E",
                "error_message": "x",
                "trace_id": "t",
                "created_at": None,
                "started_at": None,
                "completed_at": None,
            }
        return {
            "report_id": rid,
            "session_id": None,
            "company_code": "600518.SH",
            "status": "queued",
            "progress": 0,
            "idempotency_key": None,
            "file_path": None,
            "file_sha256": None,
            "error_code": None,
            "error_message": None,
            "trace_id": "t",
            "created_at": None,
            "started_at": None,
            "completed_at": None,
        }

    async def fake_start(report_id):
        started.append(report_id)

    monkeypatch.setattr(
        reports_mod.report_service, "create_report_job", fake_create_report_job
    )
    monkeypatch.setattr(
        reports_mod.report_service, "get_report_job", fake_get_report_job
    )
    monkeypatch.setattr(
        reports_mod.report_service, "retry_failed_report_job", lambda rid: retry_result
    )
    monkeypatch.setattr(
        reports_mod.report_service, "start_report_generation", fake_start
    )
    return started


def test_report_retry_router_returns_fresh_queued(client, monkeypatch):
    """CAS 成功：响应必须为 queued（不是先前读取的 failed），并启动一次。"""
    started = _patch_services(monkeypatch, retry_result=True)

    resp = client.post(
        "/api/v1/reports",
        json={"company_code": "600518.SH", "idempotency_key": "retry_rt_1"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "queued", f"重试后响应应为 queued，实际 {data['status']}"
    assert started == ["report_retry_test"], "CAS 成功应启动生成一次"


def test_report_retry_router_cas_failed_returns_fresh_status(client, monkeypatch):
    """CAS 失败（并发请求已重置）：重新查询返回 queued，不重复启动。"""
    started = _patch_services(monkeypatch, retry_result=False)

    resp = client.post(
        "/api/v1/reports",
        json={"company_code": "600518.SH", "idempotency_key": "retry_rt_2"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert (
        data["status"] == "queued"
    ), f"CAS 失败时不得返回陈旧 failed，应重新查询（实际 {data['status']}）"
    assert started == [], "CAS 失败（并发已启动）时不得重复启动"
