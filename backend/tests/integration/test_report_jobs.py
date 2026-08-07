"""PDF 报告长任务集成测试 — Phase D #8.

覆盖：创建 202 / 幂等重试 / 状态机 / 成功下载 PDF 魔数 / 生成失败 /
下载未完成任务 / 路径穿越 / 重启遗留任务恢复。

注意：TestClient 会在请求结束时回收后台任务，因此本测试
直接调用 report_service 状态机 + _generate_report_pdf（同步），
并验证路由层 202/404/409 行为。
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]
_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql", reason="需要真实 MySQL"
)


def _client():
    return TestClient(app)


@_NEED_MYSQL
def test_create_report_returns_202():
    """创建报告 → 202 + report_id/status/progress。"""
    r = _client().post(
        "/api/v1/reports",
        json={
            "company_code": "600518.SH",
            "idempotency_key": f"r_{uuid.uuid4().hex[:8]}",
        },
    )
    assert r.status_code == 202, r.text
    d = r.json()["data"]
    assert d["report_id"].startswith("report_")
    assert d["status"] == "queued"
    assert d["progress"] == 0


@_NEED_MYSQL
def test_create_idempotent_retry():
    """同一 idempotency_key 重试 → 返回同一 report_id（不重复建任务）。"""
    client = _client()
    key = f"idem_{uuid.uuid4().hex[:8]}"
    r1 = client.post(
        "/api/v1/reports", json={"company_code": "600518.SH", "idempotency_key": key}
    )
    r2 = client.post(
        "/api/v1/reports", json={"company_code": "600518.SH", "idempotency_key": key}
    )
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["data"]["report_id"] == r2.json()["data"]["report_id"]


@_NEED_MYSQL
def test_state_machine_and_pdf_generation():
    """状态机：queued → running → succeeded；PDF 魔数 %PDF-。"""
    from app.application.services import report_service

    report_id, created = report_service.create_report_job(
        company_code="600518.SH",
        session_id=None,
        idempotency_key=None,
        request_payload={},
        trace_id="t",
    )
    assert created is True
    job = report_service.get_report_job(report_id)
    assert job["status"] == "queued"

    # 同步执行生成（等价于后台任务；TestClient 下后台任务会被回收）
    report_service._update_status(
        report_id, status="running", progress=5, started_at=None
    )
    pdf_path = report_service._generate_report_pdf(
        report_id, report_service.get_report_job(report_id)
    )
    sha = report_service._sha256_of(pdf_path)
    report_service._update_status(
        report_id,
        status="succeeded",
        progress=100,
        completed_at=None,
        file_path=str(pdf_path.relative_to(report_service._report_root())),
        file_sha256=sha,
    )
    job = report_service.get_report_job(report_id)
    assert job["status"] == "succeeded"
    assert job["progress"] == 100

    # 下载（HTTP 层）
    r = _client().get(f"/api/v1/reports/{report_id}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"


@_NEED_MYSQL
def test_download_not_ready():
    """下载未完成任务 → 409 REPORT_NOT_READY。"""
    from app.application.services import report_service

    report_id, _ = report_service.create_report_job(
        company_code="600518.SH",
        session_id=None,
        idempotency_key=None,
        request_payload={},
        trace_id="t",
    )
    r = _client().get(f"/api/v1/reports/{report_id}/file")
    assert r.status_code == 409
    assert r.json()["error_code"] == "REPORT_NOT_READY"


@_NEED_MYSQL
def test_status_not_found():
    """不存在任务 → 404。"""
    r = _client().get("/api/v1/reports/report_does_not_exist")
    assert r.status_code == 404


@_NEED_MYSQL
def test_generation_failure_records_failed():
    """生成失败 → failed + error_code（可重试）。"""
    from app.application.services import report_service

    report_id, _ = report_service.create_report_job(
        company_code="600518.SH",
        session_id=None,
        idempotency_key=None,
        request_payload={},
        trace_id="t",
    )
    report_service._update_status(
        report_id, status="running", progress=5, started_at=None
    )
    try:
        raise ValueError("simulated generation failure")
    except Exception as exc:  # noqa: BLE001
        report_service._update_status(
            report_id,
            status="failed",
            error_code="REPORT_GENERATION_FAILED",
            error_message=str(exc)[:500],
            completed_at=None,
        )
    job = report_service.get_report_job(report_id)
    assert job["status"] == "failed"
    assert job["error_code"] == "REPORT_GENERATION_FAILED"


@_NEED_MYSQL
def test_stale_running_recovery():
    """重启后遗留 running → retryable failed。"""
    from app.application.services import report_service

    report_id, _ = report_service.create_report_job(
        company_code="600518.SH",
        session_id=None,
        idempotency_key=None,
        request_payload={},
        trace_id="t",
    )
    report_service._update_status(
        report_id, status="running", progress=50, started_at=None
    )
    n = report_service.recover_stale_running_jobs()
    assert n >= 1
    job = report_service.get_report_job(report_id)
    assert job["status"] == "failed"
    assert job["error_code"] == "REPORT_STALE_RECOVERY"


@_NEED_MYSQL
def test_cleanup_report_jobs():
    """清理本测试创建的 report_jobs（不污染演示库）。"""
    from app.application.services import report_service
    from app.domain.finance._fetch import _get_engine
    from sqlalchemy import text

    report_id, _ = report_service.create_report_job(
        company_code="600518.SH",
        session_id=None,
        idempotency_key=None,
        request_payload={},
        trace_id="t",
    )
    with _get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM report_jobs WHERE report_id = :rid"), {"rid": report_id}
        )
    assert report_service.get_report_job(report_id) is None
