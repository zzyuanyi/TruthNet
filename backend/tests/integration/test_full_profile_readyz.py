"""/readyz full profile 集成测试."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_readyz_returns_200():
    """/readyz 返回 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_readyz_has_required_fields():
    """/readyz 包含必要字段."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    body = response.json()
    assert "data" in body
    assert "status" in body["data"]
    assert "profile" in body["data"]
    assert "checks" in body["data"]
    assert isinstance(body["data"]["checks"], dict)


@pytest.mark.asyncio
async def test_readyz_lite_profile_ready():
    """/readyz lite profile 返回 ready."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    body = response.json()
    assert body["data"]["status"] in ("ready", "degraded")


@pytest.mark.asyncio
async def test_readyz_full_profile_deps():
    """/readyz full profile 包含依赖状态.

    需要设置 TRUTHNET_PROFILE=full。
    """
    from app.core.config import settings

    profile = os.environ.get("TRUTHNET_PROFILE", settings.TRUTHNET_PROFILE)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readyz")
    body = response.json()

    if profile == "full":
        deps = body["data"]["checks"]
        assert "mysql" in deps
        assert "neo4j" in deps
        assert "chroma" in deps
        assert "llm" in deps
    else:
        deps = body["data"]["checks"]
        assert len(deps) >= 1
