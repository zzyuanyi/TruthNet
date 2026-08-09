"""NetworkX EquityGraph Adapter — lite profile.

实现 EquityGraphPort 协议。
内存图分析，无需外部服务。
"""

import logging

import networkx as nx

from app.domain.equity.models import EquityEdge, EquityGraph, EquityNode, OwnershipChain

logger = logging.getLogger(__name__)


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
        """获取股权穿透图谱 — 异步入口（sync 核心）."""
        return self._get_graph_sync(company_code, depth=depth, direction=direction)

    def _get_graph_sync(
        self, company_code: str, depth: int = 3, direction: str = "upstream"
    ) -> EquityGraph:
        """获取股权穿透图谱 — 向上游穿透股东（同步核心）."""
        nodes = []

        # 8.09 七轮审查：适配器边界规范化 Wind Code——真实 CompanyResolver
        # 返回 "600518.SH" 而内置图键为裸码 "600518"；600518 / 600518.SH /
        # 600518.XSHG 必须解析为同一内部键，否则 Lite 路径查空图
        # （曾复现：真实 Resolver → nodes=0 / paths=0，Lite 实际不可用）。
        try:
            from app.infrastructure.graph.normalizer import parse_wind_code

            digits, _ = parse_wind_code(company_code)
        except ValueError:
            logger.warning("NetworkX: 无法解析 Wind Code: %s", company_code)
            return EquityGraph(company_id=company_code)
        company_code = digits

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
                        entity_id=node,
                        source_system="networkx",
                        mock=True,
                    )
                )

        # 收集子图内所有边（入边方向 = 股东 → 公司，去重）
        edges_seen: dict[tuple[str, str], EquityEdge] = {}
        for node in bfs_nodes:
            for u, v, data in self._graph.in_edges(node, data=True):
                edge_key = (u, v)
                if u in nodes_seen and edge_key not in edges_seen:
                    stake = data.get("stake_ratio")
                    rel_id = f"nx_{u}_{v}"
                    edges_seen[edge_key] = EquityEdge(
                        source=u,
                        target=v,
                        relation=data.get("relation", "holds"),
                        stake_ratio=stake,
                        ownership_pct=round(stake * 100, 4)
                        if stake is not None
                        else None,
                        relationship_id=rel_id,
                        source_system="networkx",
                        mock=True,
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
                    edge_ids: list[str] = []
                    for i in range(len(path) - 1):
                        ed = self._graph.get_edge_data(path[i + 1], path[i])
                        if ed:
                            total *= ed.get("stake_ratio", 0) or 0
                        edge_ids.append(f"nx_{path[i + 1]}_{path[i]}")
                    chains.append(
                        OwnershipChain(
                            path=path,
                            total_stake=total,
                            depth=len(path) - 1,
                            edge_ids=edge_ids,
                            final_control_pct=round(total * 100, 4),
                            # 8.09 五轮审查：Lite 内置图同样是持股路径（十大股东
                            # 语义），不得标记 control——与 Neo4j 主路径语义一致
                            path_type="ownership",
                            source_system="networkx",
                        )
                    )
            except (nx.NodeNotFound, nx.NetworkXNoPath):
                pass

        return EquityGraph(
            company_id=company_code,
            nodes=nodes,
            edges=list(edges_seen.values()),
            control_chains=chains,
            graph_version="networkx-lite",
            dataset_version="lite-fixture",
            source_system="networkx",
        )

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取股权路径（持股或控制关系，随 path_type 区分）."""
        graph = await self.get_graph(company_code, depth=max_depth)
        return graph.control_chains

    async def check_connection(self) -> bool:
        """NetworkX 始终可用（内存模式）."""
        return True
