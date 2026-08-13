"""股权链路 evidence_ids 可回查验收 — Phase D #12 修复（A2）.

验收（用户核查结论）：
  未先跑 WS 问答，直接 GET /equity → 全部 evidence_ids 立即经
  GET /evidence/{id} 查询 → 全部 200（REST 幂等落库 canonical ID）。
  evidence_ids 只允许 canonical ev_eq_*（不得出现裸 relationship_id）。
"""

import os
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]
_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql", reason="需要真实 MySQL"
)


@_NEED_MYSQL
def test_rest_equity_evidence_ids_all_replayable():
    """GET /equity 返回的 evidence_ids 全部可经 GET /evidence/{id} 回查（200）。"""
    client = TestClient(app)
    code = "600518.SH"  # 康美药业（Neo4j 真实图谱数据）

    r = client.get(f"/api/v1/companies/{code}/equity")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    chains = data.get("equity_chains") or []
    if not chains:
        pytest.skip("当前图数据无控制链，跳过回查断言")
    assert chains, "equity_chains 不应为空"

    evidence_ids = [eid for c in chains for eid in (c.get("evidence_ids") or [])]
    assert evidence_ids, "链路应产出 evidence_ids"
    # 只允许 canonical ev_eq_*（A2 修复核心）
    assert all(
        eid.startswith("ev_eq_") for eid in evidence_ids
    ), f"evidence_ids 必须全部 canonical ev_eq_*：{evidence_ids}"

    # 未先跑 WS 问答：REST 幂等落库后全部可回查
    for eid in evidence_ids:
        ev = client.get(f"/api/v1/evidence/{eid}")
        assert (
            ev.status_code == 200
        ), f"证据 {eid} 应可回查，实际 {ev.status_code}: {ev.text[:120]}"
        body = ev.json()["data"]
        assert body["evidence"]["evidence_id"] == eid


@_NEED_MYSQL
def test_rest_equity_evidence_materialize_idempotent():
    """重复 GET /equity：证据落库幂等，不产生重复行。"""
    from sqlalchemy import create_engine, text

    client = TestClient(app)
    code = "600518.SH"
    r1 = client.get(f"/api/v1/companies/{code}/equity")
    assert r1.status_code == 200, r1.text
    r2 = client.get(f"/api/v1/companies/{code}/equity")
    assert r2.status_code == 200, r2.text
    chains1 = r1.json()["data"].get("equity_chains") or []
    chains2 = r2.json()["data"].get("equity_chains") or []
    if not chains1:
        pytest.skip("当前图数据无控制链，跳过幂等断言")
    eids1 = [eid for c in chains1 for eid in (c.get("evidence_ids") or [])]
    eids2 = [eid for c in chains2 for eid in (c.get("evidence_ids") or [])]
    assert set(eids1) == set(eids2), "两次 GET 应产出相同 evidence_ids"

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            for eid in set(eids1):
                n = conn.execute(
                    text("SELECT COUNT(*) FROM evidence_refs WHERE evidence_id = :e"),
                    {"e": eid},
                ).scalar()
                assert n == 1, f"证据 {eid} 应仅一行，实际 {n}"
    finally:
        engine.dispose()
