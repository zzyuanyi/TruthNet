"""EquityGraphPort — V12 baseline.

定义股权图谱分析接口，不依赖具体图数据库。
"""

from typing import Protocol, runtime_checkable

from app.domain.equity.models import EquityGraph, OwnershipChain


@runtime_checkable
class EquityGraphPort(Protocol):
    """股权图谱分析接口.

    lite: NetworkXAdapter
    full: Neo4jAdapter
    """

    async def get_graph(
        self, company_code: str, depth: int = 3, direction: str = "upstream"
    ) -> EquityGraph:
        """获取股权穿透图谱."""
        ...

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取控制链."""
        ...

    async def check_connection(self) -> bool:
        """检查图数据库连接."""
        ...
