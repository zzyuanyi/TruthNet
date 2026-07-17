"""NetworkX EquityGraph Adapter — lite profile.

实现 EquityGraphPort 协议。
内存图分析，无需外部服务。
"""

import networkx as nx

from app.domain.equity.models import EquityEdge, EquityGraph, EquityNode, OwnershipChain


class NetworkXEquityGraph:
    """NetworkX 股权图谱 — lite profile.

    内存图分析，基于 NetworkX DiGraph。
    """

    def __init__(self):
        self._graph = nx.DiGraph()
        self._init_mock_data()

    def _init_mock_data(self):
        """初始化 mock 股权数据."""
        self._graph.add_node("600519", label="贵州茅台", type="company", depth=0)
        self._graph.add_node("mt_group", label="茅台集团", type="controller", depth=1)
        self._graph.add_node("gzw_gz", label="贵州省国资委", type="controller", depth=2)
        self._graph.add_edge("mt_group", "600519", relation="54%控股", stake_ratio=0.54)
        self._graph.add_edge("gzw_gz", "mt_group", relation="100%控股", stake_ratio=1.0)

    async def get_graph(
        self, company_code: str, depth: int = 3, direction: str = "upstream"
    ) -> EquityGraph:
        """获取股权穿透图谱."""
        nodes = []
        edges = []

        if company_code in self._graph:
            # BFS 获取子图
            for node in nx.bfs_tree(self._graph, company_code, depth_limit=depth):
                attrs = self._graph.nodes[node]
                nodes.append(
                    EquityNode(
                        id=node,
                        label=attrs.get("label", node),
                        type=attrs.get("type", "company"),
                        depth=attrs.get("depth", 0),
                    )
                )
            for u, v, data in self._graph.in_edges(company_code, data=True):
                edges.append(
                    EquityEdge(
                        source=u,
                        target=v,
                        relation=data.get("relation", "holds"),
                        stake_ratio=data.get("stake_ratio"),
                    )
                )

        return EquityGraph(
            company_id=company_code, nodes=nodes, edges=edges, control_chains=[]
        )

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取控制链."""
        chains = []
        try:
            paths = list(
                nx.all_simple_paths(
                    self._graph, "gzw_gz", company_code, cutoff=max_depth
                )
            )
            for path in paths:
                chains.append(
                    OwnershipChain(
                        path=path,
                        total_stake=0.54,
                        depth=len(path) - 1,
                    )
                )
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            pass
        return chains

    async def check_connection(self) -> bool:
        """NetworkX 始终可用（内存模式）."""
        return True
