"""Provenance 路由的查询回归测试。"""

from sqlalchemy import create_engine, text

from app.api.v1.routers import provenance


def test_claims_for_evidence_returns_each_claim_once(monkeypatch):
    """同一声明通过不同关系关联同一证据时，详情页不应重复显示。"""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE claims (claim_id TEXT PRIMARY KEY, text TEXT NOT NULL)")
        )
        conn.execute(
            text(
                "CREATE TABLE claim_evidence_links "
                "(claim_id TEXT NOT NULL, evidence_id TEXT NOT NULL, relation_type TEXT NOT NULL, sequence_no INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claims (claim_id, text) VALUES ('clm_1', '营业收入为 42.81 亿元')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claims (claim_id, text) VALUES ('clm_2', '毛利率出现偏离')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO claim_evidence_links VALUES "
                "('clm_1', 'ev_1', 'supports', 1), "
                "('clm_1', 'ev_1', 'context', 2), "
                "('clm_2', 'ev_1', 'supports', 3)"
            )
        )

    monkeypatch.setattr(provenance, "_get_engine", lambda: engine)

    assert [claim["claim_id"] for claim in provenance._claims_for_evidence("ev_1")] == [
        "clm_1",
        "clm_2",
    ]
