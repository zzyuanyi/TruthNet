"""回归：无公告 + 有评级时 events 端点不触发 UnboundLocalError.

历史 bug（外部验收发现）: _timeline_object_ids/_timeline_ann_dates 只在
`if rows:` 块内初始化，但证据持久化分支无条件引用 → 无公告公司返回
PROVENANCE_PERSIST_FAILED（cannot access local variable）。

要求: 无公告公司（如 000001.SZ）→ HTTP 200、timeline=[]、
评级正常返回、无 PROVENANCE_PERSIST_FAILED、evidence_ids=[]。
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

from app.api.v1.schemas.events import RatingChange  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    """无公告 + 有评级 + 事件簇空的端到端场景（全部 mock DB 访问）。"""
    from app.core.config import settings

    # CI 为 SQLite（SQL_BACKEND != mysql 时端点早退 DATA_SOURCE_UNAVAILABLE），
    # 测试固定按 full-profile 语义走完整分支
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")

    import app.api.v1.routers.events as ev

    # 1. 公告为空
    monkeypatch.setattr(ev, "_fetch_announcements", lambda *a, **k: [])
    # 2. 事件簇为空
    monkeypatch.setattr(ev, "_fetch_event_clusters", lambda *a, **k: [])
    # 3. 评级有 1 条 down
    monkeypatch.setattr(
        ev,
        "_fetch_rating_changes",
        lambda *a, **k: [
            RatingChange(
                date="2026-06-01",
                org_name="测试证券",
                prev_rating="买入",
                new_rating="增持",
                change="down",
                title="下调评级",
            )
        ],
    )

    # 4. 公司解析成功
    class FakeCompany:
        wind_code = "000001.SZ"
        sec_name = "测试公司"

    class FakeResolver:
        async def resolve(self, code):
            return FakeCompany()

    monkeypatch.setattr(ev, "CompanyResolver", lambda: FakeResolver())
    # 5. 持久化服务 no-op（不写库）
    monkeypatch.setattr(
        "app.application.services.provenance_service.ProvenanceService",
        lambda: type(
            "FakePS",
            (),
            {
                "create_analysis_run": lambda *a, **k: None,
                "persist_evidence": lambda *a, **k: None,
            },
        )(),
    )
    return TestClient(app)


def test_no_announcement_with_rating(client):
    r = client.get("/api/v1/companies/000001.SZ/events")
    assert r.status_code == 200
    d = r.json()["data"]
    warnings = r.json().get("warnings", [])

    # 核心回归点：无 PROVENANCE_PERSIST_FAILED
    assert not any(
        "PROVENANCE_PERSIST_FAILED" in w.get("code", "") for w in warnings
    ), warnings
    # 降级语义保持
    assert d["timeline"] == []
    assert d["announcements_available"] is False
    assert any("NO_ANNOUNCEMENT_DATA" in w.get("code", "") for w in warnings), warnings
    # 评级正常返回（有评级、无公告分支）
    rcs = d["rating_changes"]
    assert len(rcs) == 1
    assert rcs[0]["change"] == "down"
    assert rcs[0]["org_name"] == "测试证券"
    # 无公告时 timeline 证据为空
    assert d.get("evidence_ids", []) == []
