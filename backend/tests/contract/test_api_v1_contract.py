"""API v1 契约测试 — V12 baseline.

验证 V12 端点返回正确的 response envelope。
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_returns_v12_envelope():
    """GET /api/v1/healthz 返回 V12 response envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")

    assert response.status_code == 200
    body = response.json()

    # V12 envelope: data, meta, warnings
    assert "data" in body
    assert "meta" in body
    assert "warnings" in body
    assert isinstance(body["warnings"], list)

    # meta 结构
    meta = body["meta"]
    assert "request_id" in meta
    assert "trace_id" in meta
    assert "schema_version" in meta
    assert meta["schema_version"] == "1.0"
    assert "generated_at" in meta
    assert "dataset_version" in meta
    assert "rule_set_version" in meta
    assert "graph_version" in meta

    # data 内容
    assert body["data"]["status"] == "healthy"
    assert "profile" in body["data"]


@pytest.mark.asyncio
async def test_readyz_lite_profile_returns_ready():
    """GET /api/v1/readyz 在 lite profile 下返回 ready."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")

    assert response.status_code == 200
    body = response.json()

    assert body["data"]["status"] in ("ready", "degraded", "not_ready")
    assert body["data"]["profile"] in ("lite", "full")
    assert "checks" in body["data"]


@pytest.mark.asyncio
async def test_companies_search_returns_v12_envelope():
    """GET /api/v1/companies 返回 V12 response envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/companies?query=茅台")

    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert "warnings" in body

    data = body["data"]
    assert "candidates" in data
    assert "total" in data
    assert isinstance(data["candidates"], list)
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_companies_empty_query_returns_all():
    """GET /api/v1/companies 无查询参数返回所有公司."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/companies")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]["candidates"]) > 0


@pytest.mark.asyncio
async def test_legacy_health_still_works():
    """GET /health 旧端点仍可用."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    # 旧格式
    assert body["code"] == 0
    assert body["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_v12_envelope():
    """POST /api/v1/chat 返回 V12 {data, meta, warnings} 格式."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"question": "test"})

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "warnings" in body
    assert body["meta"]["schema_version"] == "1.0"
    assert "answer" in body["data"]
