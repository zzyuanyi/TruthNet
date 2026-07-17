"""Neo4j EquityGraph Adapter — full profile (骨架).

实现 EquityGraphPort 协议。
当前为空实现，不要求真实 Neo4j 连接。
"""

import logging

from app.core.config import settings
from app.domain.equity.models import EquityGraph, OwnershipChain

logger = logging.getLogger(__name__)


class Neo4jEquityGraph:
    """Neo4j 股权图谱 — full profile 骨架.

    TODO: 接入 neo4j Python driver 实现真实图查询。
    """

    def __init__(self):
        self._available = False
        logger.info("Neo4jEquityGraph: 骨架已加载，连接未激活")

    async def check_connection(self) -> bool:
        """检查 Neo4j 连接可用性."""
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            driver.verify_connectivity()
            driver.close()
            self._available = True
            return True
        except Exception as e:
            logger.warning(f"Neo4j 连接不可用: {e}")
            self._available = False
            return False

    async def get_graph(
        self, company_code: str, depth: int = 3, direction: str = "upstream"
    ) -> EquityGraph:
        """获取股权穿透图谱 (空实现)."""
        return EquityGraph(company_id=company_code)

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取控制链 (空实现)."""
        return []
