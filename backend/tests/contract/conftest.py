"""contract 测试目录 conftest — WS 测试会话按信封归属清理."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests._ws_cleanup import ws_envelope_sids


@pytest.fixture
def ws_session_tracker():
    """记录测试内 WS 信封产生的 session_id，teardown 只删这些（并发安全）."""
    client = TestClient(app)
    created: list[str] = []

    def track(events: list[dict]) -> None:
        for sid in ws_envelope_sids(events):
            if sid not in created:
                created.append(sid)

    yield track
    for sid in created:
        resp = client.delete(f"/api/v1/sessions/{sid}")
        if resp.status_code not in (200, 404):
            print(f"WS test session cleanup failed: {sid} -> {resp.status_code}")
