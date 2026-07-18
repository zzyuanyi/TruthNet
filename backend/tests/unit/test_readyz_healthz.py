"""/healthz 和 /readyz 单元测试."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_status_code():
    """healthz 返回 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_readyz_status_code():
    """readyz 返回 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_healthz_contains_profile():
    """healthz 数据中包含 profile 字段."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")
    body = response.json()
    assert "profile" in body["data"]


@pytest.mark.asyncio
async def test_readyz_lite_does_not_require_mysql():
    """readyz 在 lite profile 下不因 MySQL 缺失而失败."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] in ("ready", "degraded")
