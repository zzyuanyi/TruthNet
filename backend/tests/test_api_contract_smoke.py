"""API 契约 smoke 验证 — 确认 FastAPI 端点返回与文档一致的响应格式。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def chat_session_id():
    """Own and clean the real-DB session created by the REST smoke test."""
    session_id = f"ses_smoke_{uuid.uuid4().hex[:10]}"
    yield session_id
    response = TestClient(app).delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code in (200, 404)


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
async def test_chat_mock_contract(chat_session_id):
    """POST /api/v1/chat 返回 V12 response envelope 结构（进入 Agent graph）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "question": "康美药业有造假风险吗",
                "session_id": chat_session_id,
            },
        )

    assert response.status_code == 200
    body = response.json()

    # V12 response envelope: data, meta, warnings
    assert "data" in body
    assert "meta" in body
    assert "warnings" in body

    # data 核心字段
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
    assert isinstance(data["risk_score"], dict)
    assert isinstance(data["warnings"], list)
    assert isinstance(data["missing_modules"], list)
    assert isinstance(data["trace_id"], str)

    # risk_score 各维度在 0-1 范围内
    rs = data["risk_score"]
    if rs:  # Agent 可能返回空 dict
        for key in ("overall", "financial", "ownership", "sentiment"):
            if key in rs:
                assert 0.0 <= rs[key] <= 1.0, f"risk_score.{key} out of range"

    # meta 结构
    meta = body["meta"]
    assert "request_id" in meta
    assert "trace_id" in meta
    assert "schema_version" in meta
