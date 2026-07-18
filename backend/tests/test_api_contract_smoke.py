"""API 契约 smoke 验证 — 确认 FastAPI 端点返回与文档一致的响应格式。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_contract():
    """GET /health 返回正确的统一响应格式。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()

    # 统一响应结构
    assert "code" in body
    assert body["code"] == 0
    assert "data" in body
    assert "message" in body
    assert body["message"] == "ok"
    assert "trace_id" in body
    assert isinstance(body["trace_id"], str)
    assert len(body["trace_id"]) > 0

    # data 内容
    assert body["data"]["status"] == "healthy"
    assert body["data"]["version"] == "0.2.0"


@pytest.mark.asyncio
async def test_chat_mock_contract():
    """POST /api/v1/chat mock 返回正确的响应结构。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={})

    assert response.status_code == 200
    body = response.json()

    # 统一响应结构
    assert body["code"] == 0
    assert body["message"] == "ok"

    # data 核心字段 (与 API_CONTRACT.md 一致)
    data = body["data"]
    required_fields = [
        "answer",
        "evidence",
        "graph",
        "timeline",
        "risk_score",
        "warnings",
        "missing_modules",
        "trace_id",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # 字段类型
    assert isinstance(data["answer"], str)
    assert isinstance(data["evidence"], list)
    assert isinstance(data["graph"], dict)
    assert isinstance(data["timeline"], list)
    # Prompt4: risk_score 冻结为 RiskScore 对象
    assert isinstance(data["risk_score"], dict)
    assert "overall" in data["risk_score"]
    assert "financial" in data["risk_score"]
    assert "ownership" in data["risk_score"]
    assert "sentiment" in data["risk_score"]
    assert isinstance(data["warnings"], list)
    assert isinstance(data["missing_modules"], list)
    assert isinstance(data["trace_id"], str)

    # risk_score 各维度在 0-1 范围内
    for key in ("overall", "financial", "ownership", "sentiment"):
        assert 0.0 <= data["risk_score"][key] <= 1.0, f"risk_score.{key} out of range"
