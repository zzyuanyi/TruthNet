"""API v1 完整契约测试."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_returns_v12_envelope():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "warnings" in body
    assert body["meta"]["schema_version"] == "1.0"
    assert body["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readyz_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    assert response.status_code == 200
    body = response.json()
    # 2️⃣ 预热门控：TestClient 未跑 lifespan 预热 → 允许 "starting"
    assert body["data"]["status"] in ("ready", "degraded", "not_ready", "starting")
    assert body["data"]["profile"] in ("lite", "full")
    assert isinstance(body["data"]["checks"], dict)
    assert "meta" in body
    assert body["meta"]["schema_version"] == "1.0"


@pytest.mark.asyncio
async def test_companies_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/companies?query=康美")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert len(body["data"]["candidates"]) >= 1


@pytest.mark.asyncio
async def test_chat_v1_contract(ws_session_tracker):
    """REST chat 契约（归属化清理，对齐审计 P1-4）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post("/api/v1/sessions", json={"title": "chat-test"})
        sid = create.json()["data"]["session_id"]
        response = await client.post(
            "/api/v1/chat",
            json={"question": "康美药业有造假风险吗", "session_id": sid},
        )
    assert response.status_code == 200
    body = response.json()
    # V12 envelope
    assert "meta" in body
    assert body["meta"]["schema_version"] == "1.0"
    assert "answer" in body["data"]

    ws_session_tracker([{"session_id": sid}])


@pytest.mark.asyncio
async def test_legacy_health_still_works():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "healthy"
