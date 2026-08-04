"""Provenance 追溯端点契约测试 — Phase C 任务 16.

GET /api/v1/evidence/{id}
GET /api/v1/claims/{id}
GET /api/v1/companies/{code}/events

验证 V12 envelope、404 Problem Details、非法 ID 422。
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_evidence_lookup_v12_envelope_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/evidence/nonexistent_evidence_xyz")
    assert response.status_code == 404
    body = response.json()
    # Problem Details 由 not_found_handler 扁平化到顶层
    assert body.get("error_code") == "EVIDENCE_NOT_FOUND"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_claim_lookup_v12_envelope_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/claims/nonexistent_claim_xyz")
    assert response.status_code == 404
    body = response.json()
    assert body.get("error_code") == "CLAIM_NOT_FOUND"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_evidence_invalid_id_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/evidence/illegal id!@@")
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_claim_invalid_id_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/claims/illegal id!@@")
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_events_v12_envelope():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/companies/600518.SH/events")
    # full profile 返回数据；lite profile 返回 DATA_SOURCE_UNAVAILABLE 但仍为 V12 envelope
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "warnings" in body
    assert body["meta"]["schema_version"] == "1.0"
    assert "event_clusters" in body["data"]


@pytest.mark.asyncio
async def test_events_company_not_found_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/companies/999999.XSHG/events")
    assert response.status_code == 404
    assert response.json().get("error_code") == "COMPANY_NOT_COVERED"
