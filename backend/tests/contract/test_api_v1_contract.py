"""API v1 契约测试 — V12 baseline.

验证 V12 端点返回正确的 response envelope。
"""

import json

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
    assert "candidates" in data  # V12: companies → candidates
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
async def test_legacy_chat_still_works(ws_session_tracker):
    """POST /api/v1/chat 返回 V12 格式（旧格式已移除）.

    REST chat 会持久化会话（归属化清理：先建会话并显式传 session_id，
    测试结束删除——对齐审计 P1-4 并发安全）。
    """
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
    # V12 格式
    assert "data" in body
    assert "meta" in body
    assert "answer" in body["data"]

    # 归属清理（tracker 走 TestClient DELETE，级联 + 证据保护）
    ws_session_tracker([{"session_id": sid}])


# ── 错误信封契约（RFC 9457 ProblemDetail 顶层结构） ────────


@pytest.mark.asyncio
async def test_empty_chat_request_returns_422_problem_detail():
    """空 chat 请求 → 422 SCHEMA_VALIDATION_FAILED（顶层 ProblemDetail）.

    回归：之前 RequestValidationError 未注册 handler，422 返回 FastAPI 默认
    {"detail": [...]}，与 V12 错误码体系断档。
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={})

    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["error_code"] == "SCHEMA_VALIDATION_FAILED"
    assert body["status"] == 422
    assert "errors" in body["extra"]
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_blank_question_returns_422():
    """question 为空字符串（min_length=1 违反）→ 422 SCHEMA_VALIDATION_FAILED."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"question": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SCHEMA_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_datastore_down_returns_503(monkeypatch):
    """数据库不可用 → 503 DATASTORE_UNAVAILABLE（顶层 ProblemDetail）.

    回归：之前 sessions 抛 500 + 嵌套 {"detail": {...}} 结构。
    """
    from app.api.v1.routers import sessions as sessions_router
    from app.core.config import settings

    def _boom():
        raise RuntimeError("mysql down")

    # 必须强制 mysql 分支：sessions 仅在 SQL_BACKEND=mysql 时走 DB 查询路径，
    # 否则（仓库默认 sqlite）直接返回 200 空列表，测试在 CI 上假失败
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(sessions_router, "_get_engine", _boom)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/sessions")

    assert response.status_code == 503
    assert "application/problem+json" in response.headers["content-type"]
    body = response.json()
    assert body["error_code"] == "DATASTORE_UNAVAILABLE"
    assert body["status"] == 503
    assert body["recoverable"] is True


@pytest.mark.asyncio
async def test_http_exception_handler_preserves_router_type():
    """路由层指定的 type（如 invalid-period）不得被 handler 覆盖为 about:blank.

    回归：http_exception_handler 曾固定输出 about:blank，丢失路由语义。
    """
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.api.v1.exception_handlers import http_exception_handler
    from starlette.requests import Request

    exc = StarletteHTTPException(
        status_code=422,
        detail={
            "type": "https://truthnet.dev/errors/invalid-period",
            "title": "Invalid Period",
            "status": 422,
            "detail": "无法解析期间: 2026XQ",
            "error_code": "INVALID_PERIOD",
            "trace_id": "t1",
            "recoverable": True,
            "extra": {"period": "2026XQ"},
        },
        headers={"X-Custom": "v1"},
    )
    request = Request({"type": "http", "method": "GET", "path": "/test", "headers": []})
    response = await http_exception_handler(request, exc)

    assert response.status_code == 422
    assert "application/problem+json" in response.headers["content-type"]
    body = json.loads(response.body)
    assert body["type"] == "https://truthnet.dev/errors/invalid-period"
    assert body["error_code"] == "INVALID_PERIOD"
    assert body["extra"] == {"period": "2026XQ"}
    assert response.headers.get("x-custom") == "v1"
