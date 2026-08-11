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


def test_neo4j_write_smoke_rolls_back(neo4j_config):
    """Neo4j 写入 smoke：显式事务内写入→读取→回滚，事务外断言节点不存在.

    主图零写入验收（v3.1，2026-08-11）：所有图写测试必须在显式事务中
    回滚，不得向共享图提交写入。smoke_key 按进程唯一，避免与历史残留
    节点互相干扰。若今后存在必须提交图写入的测试，需独立 Neo4j 实例
    （Community 单库下 graph_version + cleanup 仅是逻辑隔离）。
    """
    from neo4j import GraphDatabase

    s = neo4j_config
    smoke_key = f"v12_integration_test_pid{os.getpid()}"
    driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            with session.begin_transaction() as tx:
                tx.run(
                    "MERGE (n:TruthNetSmokeTest {smoke_key: $key}) "
                    "SET n.smoke_value = 'ok', n.updated_at = datetime()",
                    key=smoke_key,
                )
                r = tx.run(
                    "MATCH (n:TruthNetSmokeTest {smoke_key: $key}) "
                    "RETURN n.smoke_value AS val",
                    key=smoke_key,
                ).single()
                assert r is not None, "事务内应能读到刚写入的节点"
                assert r["val"] == "ok"
                tx.rollback()  # 显式回滚：不向主图提交任何写入
            # 事务外：节点必须不存在（回滚生效验证）
            c = session.run(
                "MATCH (n:TruthNetSmokeTest {smoke_key: $key}) RETURN count(n) AS c",
                key=smoke_key,
            ).single()
            assert c["c"] == 0, "回滚后 smoke 节点不得残留（主图零写入）"
    finally:
        driver.close()
