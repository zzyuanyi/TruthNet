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


_HTTP_METHODS = ("get", "post", "delete", "put")


def _http_operations(schema: dict) -> list[tuple[str, str, dict]]:
    """展开全部 HTTP 操作 → [(method, path, operation)]."""
    out = []
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() in _HTTP_METHODS:
                out.append((method.upper(), path, op))
    return out


def test_all_v1_operations_have_nonempty_200_schema():
    """对齐审计 P1-4/P2-5: 所有 /api/v1 HTTP 操作必须有非空 200 schema.

    曾 14 个业务响应为 {}——OpenAPI 无法作为前端类型来源。
    """
    schema = app.openapi()
    operations = [
        (m, p, op) for m, p, op in _http_operations(schema) if p.startswith("/api/v1/")
    ]
    assert len(operations) >= 15, f"操作数异常: {len(operations)}"
    empty = []
    for method, path, op in operations:
        content = (
            op.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
        )
        ref = content.get("schema", {}).get("$ref", "")
        if not ref:
            empty.append(f"{method} {path}")
    assert not empty, f"以下操作 200 schema 为空: {empty}"


def test_v12_response_envelope_in_schemas():
    """200 schema 引用 V12Response（含 data/meta/warnings）."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    envelope_refs = [
        ref
        for ref in components
        if ref.startswith("V12Response_") or ref.startswith("UnifiedResponse_")
    ]
    assert envelope_refs, "OpenAPI 中应存在 V12Response 泛型 schema"
    v12 = components.get("V12Response", {})
    if v12:
        props = v12.get("properties", {})
        assert "data" in props and "meta" in props and "warnings" in props


def test_sessions_schema_has_key_fields():
    """sessions 契约关键字段（审计 P2-5）."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    detail = components.get("SessionDetailDataV1", {})
    assert detail, "SessionDetailDataV1 应存在"
    props = detail.get("properties", {})
    assert "session" in props and "turns" in props
    turn = components.get("SessionTurnV1", {}).get("properties", {})
    assert "question" in turn and "answer" in turn and "evidence_ids" in turn
    lst = components.get("SessionListDataV1", {}).get("properties", {})
    assert "sessions" in lst and "total" in lst


def test_sessions_sources_structured_schema():
    """P2-1（核验修订）：sources 必须是结构化 SessionSourceV1（非裸 dict），
    OpenAPI 暴露 {id,title,source,url} 字段结构。"""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    src = components.get("SessionSourceV1", {})
    assert src, "SessionSourceV1 应存在（此前 sources 是裸 list[dict]）"
    props = src.get("properties", {})
    assert "id" in props and "title" in props and "source" in props and "url" in props
    turn = components.get("SessionTurnV1", {}).get("properties", {})
    sources_ref = turn.get("sources", {}).get("items", {}).get("$ref", "")
    assert sources_ref.endswith(
        "SessionSourceV1"
    ), f"sources 应引用 SessionSourceV1，实际: {sources_ref}"


def test_provenance_schema_has_envelope():
    """provenance 契约信封字段."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    for name in ("EvidenceLookupDataV1", "ClaimLookupDataV1", "TraceProvenanceDataV1"):
        comp = components.get(name, {})
        assert comp, f"{name} 应存在"
        assert comp.get("properties"), f"{name} 不应为空对象"


def test_health_schemas_nonempty():
    """healthz/readyz 不再为空对象."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    for name in ("HealthDataV1", "ReadyDataV1"):
        comp = components.get(name, {})
        assert comp and comp.get("properties"), f"{name} 应为非空 schema"
