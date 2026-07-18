"""Neo4j 真实连接集成测试.

需要设置 TRUTHNET_RUN_EXTERNAL_TESTS=1 才运行。
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


@pytest.fixture
def neo4j_config():
    """加载 Neo4j 配置."""
    from app.core.config import Settings

    s = Settings()
    if not s.NEO4J_PASSWORD:
        pytest.skip("NEO4J_PASSWORD not configured")
    return s


def test_neo4j_driver_import():
    """Neo4j driver 可 import."""
    from neo4j import GraphDatabase

    assert GraphDatabase is not None


def test_neo4j_connectivity(neo4j_config):
    """Neo4j 连接验证."""
    from neo4j import GraphDatabase

    s = neo4j_config
    driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
    finally:
        driver.close()


def test_neo4j_return_1(neo4j_config):
    """Neo4j RETURN 1."""
    from neo4j import GraphDatabase

    s = neo4j_config
    driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            r = session.run("RETURN 1 AS ok").single()
            assert r is not None
            assert r["ok"] == 1
    finally:
        driver.close()


def test_neo4j_write_smoke(neo4j_config):
    """Neo4j 写入 smoke 测试."""
    from neo4j import GraphDatabase

    s = neo4j_config
    driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run(
                "MERGE (n:TruthNetSmokeTest {smoke_key: 'v12_integration_test'}) "
                "SET n.smoke_value = 'ok', n.updated_at = datetime()"
            )
            r = session.run(
                "MATCH (n:TruthNetSmokeTest {smoke_key: 'v12_integration_test'}) "
                "RETURN n.smoke_value AS val"
            ).single()
            assert r is not None
            assert r["val"] == "ok"
            # Cleanup
            session.run(
                "MATCH (n:TruthNetSmokeTest {smoke_key: 'v12_integration_test'}) DELETE n"
            )
    finally:
        driver.close()
