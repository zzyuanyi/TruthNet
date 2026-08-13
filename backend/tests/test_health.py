"""健康检查接口测试。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """测试 GET /health 返回正确结构和状态码。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "healthy"
    assert body["data"]["version"] == "0.2.0"
    assert body["message"] == "ok"
    assert "trace_id" in body
