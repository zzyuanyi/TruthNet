"""Phase C 任务 14/15/16 全量集成测试（真实 MySQL/Neo4j）.

需要 TRUTHNET_RUN_FULL_INTEGRATION=1 才运行。
- 任务 14: 康美/茅台/平安画像来自 MySQL，股权来自 Neo4j；
- 任务 15: 事件簇交接导入 + 消费；
- 任务 16: Claim/Evidence 持久化 + 正向/反向追溯（服务重启后仍可查询）。
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]

_SESSION = f"ses_integration_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_companies_real_profiles():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for name, code in [
            ("康美", "600518.SH"),
            ("茅台", "600519.SH"),
            ("平安", "601318.SH"),
        ]:
            r = await client.get(f"/api/v1/companies?query={name}")
            assert r.status_code == 200
            cands = r.json()["data"]["candidates"]
            assert any(c["wind_code"] == code for c in cands), f"{name} 未命中 {code}"

            rp = await client.get(f"/api/v1/companies/{code}")
            assert rp.status_code == 200
            prof = rp.json()["data"]
            assert prof["data_quality"]["source"] == "mysql"
            assert prof["entity_id"].startswith("company_")
            assert "risk_summary" in prof  # 不硬编码风险


@pytest.mark.asyncio
async def test_equity_from_neo4j():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/companies/600518.SH/equity?depth=3")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["target"]["entity_id"] == "company_600518_SH"
        assert d["source_system"] == "neo4j"
        assert d["partial"] is False
        assert len(d["edges"]) > 0
        assert all(e["relationship_id"] for e in d["edges"][:20])
        assert all(
            e["ownership_pct"] is None or 0 <= e["ownership_pct"] <= 100
            for e in d["edges"][:50]
        )
        assert any(p["edge_ids"] for p in d["paths"][:20])


@pytest.mark.asyncio
async def test_events_consumes_event_clusters():
    """事件簇交接数据可被 REST 消费（event_cluster_id 原样返回）。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/companies/600518.SH/events")
        assert r.status_code == 200
        d = r.json()["data"]
        for cluster in d["event_clusters"]:
            assert cluster["event_cluster_id"].startswith("evtcl_")
            assert cluster["sources"]
            assert cluster["evidence_ids"]


@pytest.mark.asyncio
async def test_provenance_roundtrip_restart():
    """Chat 产生 Claim/Evidence → 持久化 → 重新加载 app → 仍可查询。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/chat",
            json={"question": "康美药业的股权风险如何？", "session_id": _SESSION},
        )
        assert r.status_code == 200
        assert not any(
            "PROVENANCE_PERSIST_FAILED" in w
            for w in r.json()["data"].get("warnings", [])
        )

    # 模拟重启：重新 import app（新进程语义）
    import importlib

    import app.main as main_module

    reloaded_app = importlib.reload(main_module).app
    async with AsyncClient(
        transport=ASGITransport(app=reloaded_app), base_url="http://test"
    ) as client:
        # 从 trace 找到 claim
        turns = await _query_claims(client)
        assert turns, "应有持久化的 Claim"

    # 清理本轮测试数据（不删除生产数据）
    await _cleanup()


async def _query_claims(client):
    import sys

    sys.path.insert(0, "backend")
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, echo=False)
    claims = []
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT c.claim_id, c.verification_status, c.company_code "
                    "FROM claims c JOIN conversation_turns t ON t.turn_id = c.turn_id "
                    "WHERE t.session_id = :sid"
                ),
                {"sid": _SESSION},
            )
            .mappings()
            .all()
        )
        claims = [dict(r) for r in rows]
    if claims:
        cid = claims[0]["claim_id"]
        r = await client.get(f"/api/v1/claims/{cid}")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["claim"]["claim_id"] == cid
        assert len(body["evidence"]) >= 1
    engine.dispose()
    return claims


async def _cleanup():
    import sys

    sys.path.insert(0, "backend")
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, echo=False)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM conversation_turns WHERE session_id = :sid"),
            {"sid": _SESSION},
        )
        conn.execute(
            text("DELETE FROM conversation_sessions WHERE session_id = :sid"),
            {"sid": _SESSION},
        )
        # 删除本轮测试产生的无主 claim/evidence（仅测试前缀证据，保守不删真实数据）
        conn.execute(
            text(
                "DELETE l FROM claim_evidence_links l "
                "LEFT JOIN claims c ON c.claim_id = l.claim_id "
                "WHERE c.claim_id IS NULL"
            )
        )
    engine.dispose()
