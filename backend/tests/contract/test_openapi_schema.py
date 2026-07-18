"""OpenAPI Schema 生成测试."""

from app.main import app


def test_openapi_schema_generated():
    """OpenAPI schema 可生成."""
    schema = app.openapi()
    assert schema is not None
    assert "openapi" in schema


def test_openapi_info():
    """OpenAPI 包含基本信息."""
    schema = app.openapi()
    info = schema.get("info", {})
    assert info["title"] == "TruthNet API"
    assert "version" in info


def test_openapi_has_v1_routes():
    """OpenAPI 包含 /api/v1/ 路由."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    v1_paths = [p for p in paths if p.startswith("/api/v1/")]
    assert len(v1_paths) >= 3


def test_openapi_has_healthz():
    """OpenAPI 包含 /api/v1/healthz."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/healthz" in paths


def test_openapi_has_readyz():
    """OpenAPI 包含 /api/v1/readyz."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/readyz" in paths


def test_openapi_has_companies():
    """OpenAPI 包含 /api/v1/companies."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/companies" in paths
