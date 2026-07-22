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
        """初始化 mock 股权数据（含康美验收 fixture）."""
        # 贵州茅台
        self._graph.add_node("600519", label="贵州茅台", type="company", depth=0)
        self._graph.add_node("mt_group", label="茅台集团", type="controller", depth=1)
        self._graph.add_node("gzw_gz", label="贵州省国资委", type="controller", depth=2)
        self._graph.add_edge("mt_group", "600519", relation="54%控股", stake_ratio=0.54)
        self._graph.add_edge("gzw_gz", "mt_group", relation="100%控股", stake_ratio=1.0)

        # 康美药业 (Task 6 验收 fixture)
        self._graph.add_node("600518", label="康美药业", type="listed_company", depth=0)
        self._graph.add_node(
            "ent_kangmei_industrial", label="康美实业", type="company", depth=1
        )
        self._graph.add_node("ent_ma_xingtian", label="马兴田", type="person", depth=2)
        self._graph.add_edge(
            "ent_kangmei_industrial",
            "600518",
            relation="30.1%控股",
            stake_ratio=0.301,
        )
        self._graph.add_edge(
            "ent_ma_xingtian",
            "ent_kangmei_industrial",
            relation="99.7%控股",
            stake_ratio=0.997,
        )

    async def get_graph(
        self, company_code: str, depth: int = 3, direction: str = "upstream"
    ) -> EquityGraph:
        """获取股权穿透图谱 — 向上游穿透股东."""
        nodes = []
        edges = []

        if company_code not in self._graph:
            return EquityGraph(company_id=company_code)

        # 使用 reverse_view 向上游（入边方向）遍历
        reversed_graph = nx.reverse_view(self._graph)
        nodes_seen: set[str] = set()

        # BFS 从目标公司向上游
        bfs_nodes = list(nx.bfs_tree(reversed_graph, company_code, depth_limit=depth))
        for node in bfs_nodes:
            if node not in nodes_seen:
                attrs = self._graph.nodes[node]
                nodes_seen.add(node)
                nodes.append(
                    EquityNode(
                        id=node,
                        label=attrs.get("label", node),
                        type=attrs.get("type", "company"),
                        depth=attrs.get("depth", 0),
                    )
                )

        # 收集子图内所有边（入边方向 = 股东 → 公司，去重）
        edges_seen: set[tuple[str, str]] = set()
        for node in bfs_nodes:
            for u, v, data in self._graph.in_edges(node, data=True):
                edge_key = (u, v)
                if u in nodes_seen and edge_key not in edges_seen:
                    edges_seen.add(edge_key)
                    edges.append(
                        EquityEdge(
                            source=u,
                            target=v,
                            relation=data.get("relation", "holds"),
                            stake_ratio=data.get("stake_ratio"),
                        )
                    )

        # 控制链
        chains: list[OwnershipChain] = []
        for node in bfs_nodes:
            if node == company_code:
                continue
            try:
                simple_paths = list(
                    nx.all_simple_paths(
                        reversed_graph, company_code, node, cutoff=depth
                    )
                )
                for path in simple_paths:
                    total = 1.0
                    for i in range(len(path) - 1):
                        ed = self._graph.get_edge_data(path[i + 1], path[i])
                        if ed:
                            total *= ed.get("stake_ratio", 0) or 0
                    chains.append(
                        OwnershipChain(
                            path=path,
                            total_stake=total,
                            depth=len(path) - 1,
                        )
                    )
            except (nx.NodeNotFound, nx.NetworkXNoPath):
                pass

        return EquityGraph(
            company_id=company_code,
            nodes=nodes,
            edges=edges,
            control_chains=chains,
        )

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取控制链."""
        graph = await self.get_graph(company_code, depth=max_depth)
        return graph.control_chains

    async def check_connection(self) -> bool:
        """NetworkX 始终可用（内存模式）."""
        return True
