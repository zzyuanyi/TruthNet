"""Neo4j EquityGraph Adapter — V12 §8.6 full profile.

实现 EquityGraphPort 协议:
- 约束和索引初始化
- 实体节点 MERGE（幂等）
- 股权关系 MERGE（幂等）
- 多跳控制链查询
- 权重计算（Decimal）

依赖: neo4j Python driver >= 5.x
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.domain.equity.models import EquityEdge, EquityGraph, EquityNode, OwnershipChain

logger = logging.getLogger(__name__)

# ── 超时 ────────────────────────────────────────────────
_CONNECTION_TIMEOUT = 10
_QUERY_TIMEOUT = 30

# ── 图版本标记 ───────────────────────────────────────────
_GRAPH_VERSION = "equity-mock-v12"
_DATASET_VERSION = "mock-v12"

# ── Neo4j 数值表示 ───────────────────────────────────────
# Neo4j Python Driver 不原生支持 decimal.Decimal。
# 采用规范字符串方案: 写入时 Decimal → str, 读取时 str → Decimal。
# 持股比例统一以百分比 (0–100) 的规范字符串存储，精度 6 位小数。


def _pct_to_neo4j(value: Decimal | float | None) -> str | None:
    """将持股比例转换为 Neo4j 兼容的规范字符串."""
    if value is None:
        return None
    d = Decimal(str(value))
    return f"{d:.6f}"


def _pct_from_neo4j(raw: str | float | int | None) -> Decimal:
    """从 Neo4j 读取持股比例并还原为 Decimal."""
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


class Neo4jEquityGraph:
    """Neo4j 股权图谱 — full profile.

    实现 EquityGraphPort 协议。
    提供约束管理、实体/关系导入、多跳查询、控制链分析。
    """

    def __init__(self):
        self._driver = None
        self._available = False
        self._init_driver()

    def _init_driver(self) -> None:
        """初始化 Neo4j driver."""
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=_CONNECTION_TIMEOUT,
            )
            logger.info("Neo4j driver 已创建: %s", settings.NEO4J_URI)
        except Exception as e:
            logger.warning("Neo4j driver 创建失败: %s", e)
            self._driver = None

    # ── 连接管理 ──────────────────────────────────────────

    async def check_connection(self) -> bool:
        """检查 Neo4j 连接可用性."""
        if self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            self._available = True
            return True
        except Exception as e:
            logger.warning("Neo4j 连接不可用: %s", e)
            self._available = False
            return False

    async def ensure_constraints(self) -> None:
        """创建必需约束和索引（幂等）."""
        queries = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE INDEX entity_wind_code IF NOT EXISTS "
            "FOR (e:Entity) ON (e.wind_code)",
            "CREATE INDEX entity_name IF NOT EXISTS "
            "FOR (e:Entity) ON (e.canonical_name)",
            "CREATE INDEX entity_graph_version IF NOT EXISTS "
            "FOR (e:Entity) ON (e.graph_version)",
        ]
        for q in queries:
            try:
                self._driver.execute_query(q)
                logger.debug("Neo4j 约束/索引: %s", q[:60])
            except Exception as e:
                logger.warning("Neo4j 约束/索引创建失败 (%s): %s", q[:60], e)

    # ── 图查询 ────────────────────────────────────────────

    async def get_graph(
        self,
        company_code: str,
        depth: int = 3,
        direction: str = "upstream",
    ) -> EquityGraph:
        """获取股权穿透图谱.

        Args:
            company_code: 公司代码 (如 600518 或 600518.SH)
            depth: 最大穿透深度
            direction: upstream=向上穿透股东, downstream=向下穿透投资
        """
        if not self._available:
            await self.check_connection()
            if not self._available:
                return EquityGraph(company_id=company_code)

        # 规范化代码
        from app.infrastructure.graph.normalizer import extract_wind_code_suffix

        code_6, _ = extract_wind_code_suffix(company_code)
        resolved_code = code_6 if code_6 else company_code

        depth = max(1, min(10, depth))

        # 仅使用 OWNS 关系类型（CONTROLS 在一致行动人时使用，避免 unknown type warning）
        if direction == "upstream":
            rel_pattern = "<-[r:OWNS*1..%d]-" % depth
        else:
            rel_pattern = "-[r:OWNS*1..%d]->" % depth

        cypher = (
            "MATCH (target:Entity {wind_code: $code}) "
            "MATCH path = (target)" + rel_pattern + "(other:Entity) "
            "WHERE all(rel IN relationships(path) WHERE rel.mock = false) "
            "RETURN target, path "
            "LIMIT 200"
        )

        records, _, _ = self._driver.execute_query(
            cypher,
            {"code": f"{resolved_code}.SH"},
        )

        nodes_map: dict[str, EquityNode] = {}
        edges_map: dict[tuple[str, str], EquityEdge] = {}
        paths_list: list[OwnershipChain] = []

        for record in records:
            target_node = record["target"]
            path = record["path"]

            # 收集节点
            for node in path.nodes:
                nid = node.get("entity_id", "")
                if nid and nid not in nodes_map:
                    nodes_map[nid] = EquityNode(
                        id=nid,
                        label=node.get("display_name", node.get("canonical_name", "")),
                        type=node.get("entity_type", "entity"),
                        depth=0,
                    )

            # 收集边 + 构建路径
            path_node_ids: list[str] = []
            path_edge_ids: list[str] = []
            total_fraction = Decimal("1.0")

            for rel in path.relationships:
                src_id = rel.start_node.get("entity_id", "")
                tgt_id = rel.end_node.get("entity_id", "")
                rel_id = rel.get("source_record_id", str(uuid4()))
                edge_key = (src_id, tgt_id)

                if src_id and tgt_id:
                    pct = _pct_from_neo4j(rel.get("ownership_pct"))
                    if edge_key not in edges_map:
                        edges_map[edge_key] = EquityEdge(
                            source=src_id,
                            target=tgt_id,
                            relation=rel.type or "OWNS",
                            stake_ratio=float(pct) / 100.0 if pct > 0 else None,
                        )

                path_node_ids.append(src_id)
                path_edge_ids.append(rel_id)
                if pct > 0:
                    total_fraction *= pct / Decimal("100")

            # 添加最终目标节点
            tgt_nid = target_node.get("entity_id", "")
            if tgt_nid and path_node_ids:
                path_node_ids.append(tgt_nid)

            if path_node_ids:
                paths_list.append(
                    OwnershipChain(
                        path=path_node_ids,
                        total_stake=float(total_fraction),
                        depth=len(path_node_ids) - 1,
                    )
                )

        return EquityGraph(
            company_id=company_code,
            nodes=list(nodes_map.values()),
            edges=list(edges_map.values()),
            control_chains=paths_list,
        )

    async def get_control_chains(
        self, company_code: str, max_depth: int = 5
    ) -> list[OwnershipChain]:
        """获取控制链."""
        graph = await self.get_graph(company_code, depth=max_depth)
        return graph.control_chains

    # ── 数据导入 ──────────────────────────────────────────

    async def import_entities_batch(
        self,
        entities: list[dict[str, Any]],
        graph_version: str | None = None,
        mock: bool = False,
    ) -> int:
        """批量导入实体节点（幂等 MERGE）."""
        if not self._driver:
            logger.warning("Neo4j driver 未初始化，跳过导入")
            return 0

        gv = graph_version or _GRAPH_VERSION
        now = datetime.now(timezone.utc).isoformat()
        imported = 0

        for ent in entities:
            entity_id = ent.get("entity_id")
            if not entity_id:
                continue

            # 降级到纯 Cypher（不依赖 APOC）
            cypher = """
            MERGE (e:Entity {entity_id: $entity_id})
            SET e.canonical_name = $canonical_name,
                e.display_name = $display_name,
                e.entity_type = $entity_type,
                e.wind_code = $wind_code,
                e.aliases = $aliases,
                e.match_confidence = $match_confidence,
                e.dataset_version = $dataset_version,
                e.graph_version = $graph_version,
                e.source_id = $source_id,
                e.mock = $mock,
                e.updated_at = $updated_at
            FOREACH (_ IN CASE WHEN e.created_at IS NULL THEN [1] ELSE [] END |
                SET e.created_at = $updated_at
            )
            RETURN e.entity_id
            """

            try:
                self._driver.execute_query(
                    cypher,
                    {
                        "entity_id": entity_id,
                        "canonical_name": ent.get("canonical_name", ""),
                        "display_name": ent.get("display_name", ""),
                        "entity_type": ent.get("entity_type", ""),
                        "wind_code": ent.get("wind_code", ""),
                        "aliases": ent.get("aliases", []),
                        "match_confidence": ent.get("match_confidence", 1.0),
                        "dataset_version": _DATASET_VERSION,
                        "graph_version": gv,
                        "source_id": ent.get("source_id", ""),
                        "mock": mock,
                        "updated_at": now,
                    },
                )
                imported += 1
            except Exception as e:
                logger.error("导入实体 %s 失败: %s", entity_id, e)

        logger.info("导入 %d/%d 实体 (graph_version=%s)", imported, len(entities), gv)
        return imported

    async def import_relationships_batch(
        self,
        relationships: list[dict[str, Any]],
        graph_version: str | None = None,
        mock: bool = False,
    ) -> int:
        """批量导入股权关系（幂等 MERGE）."""
        if not self._driver:
            return 0

        gv = graph_version or _GRAPH_VERSION
        now = datetime.now(timezone.utc).isoformat()
        imported = 0

        for rel in relationships:
            src_id = rel.get("source_entity_id")
            tgt_id = rel.get("target_entity_id")
            rel_type = rel.get("relation_type", "OWNS")

            if not src_id or not tgt_id:
                continue

            cypher = (
                """
            MATCH (src:Entity {entity_id: $src_id})
            MATCH (tgt:Entity {entity_id: $tgt_id})
            MERGE (src)-[r:%s]->(tgt)
            SET r.ownership_pct = $ownership_pct,
                r.quantity = $quantity,
                r.ann_dt = $ann_dt,
                r.report_period = $report_period,
                r.source_id = $source_id,
                r.source_record_id = $source_record_id,
                r.dataset_version = $dataset_version,
                r.graph_version = $graph_version,
                r.match_confidence = $match_confidence,
                r.mock = $mock,
                r.updated_at = $updated_at
            FOREACH (_ IN CASE WHEN r.created_at IS NULL THEN [1] ELSE [] END |
                SET r.created_at = $updated_at
            )
            RETURN type(r)
            """
                % rel_type
            )

            try:
                self._driver.execute_query(
                    cypher,
                    {
                        "src_id": src_id,
                        "tgt_id": tgt_id,
                        "ownership_pct": _pct_to_neo4j(rel.get("ownership_pct")),
                        "quantity": rel.get("quantity"),
                        "ann_dt": rel.get("ann_dt", ""),
                        "report_period": rel.get("report_period", ""),
                        "source_id": rel.get("source_id", ""),
                        "source_record_id": rel.get("source_record_id", ""),
                        "dataset_version": _DATASET_VERSION,
                        "graph_version": gv,
                        "match_confidence": rel.get("match_confidence", 1.0),
                        "mock": mock,
                        "updated_at": now,
                    },
                )
                imported += 1
            except Exception as e:
                logger.error(
                    "导入关系 (%s)-[%s]->(%s) 失败: %s", src_id, rel_type, tgt_id, e
                )

        logger.info(
            "导入 %d/%d 关系 (graph_version=%s)", imported, len(relationships), gv
        )
        return imported

    # ── 测试数据管理 ───────────────────────────────────────

    async def count_entities(self, graph_version: str | None = None) -> int:
        """统计指定版本的实体数."""
        if not self._driver:
            return 0
        gv = graph_version or _GRAPH_VERSION
        records, _, _ = self._driver.execute_query(
            "MATCH (e:Entity {graph_version: $gv}) RETURN count(e) AS cnt",
            {"gv": gv},
        )
        return records[0]["cnt"] if records else 0

    async def count_relationships(self, graph_version: str | None = None) -> int:
        """统计指定版本的关系数."""
        if not self._driver:
            return 0
        gv = graph_version or _GRAPH_VERSION
        records, _, _ = self._driver.execute_query(
            "MATCH ()-[r {graph_version: $gv}]->() RETURN count(r) AS cnt",
            {"gv": gv},
        )
        return records[0]["cnt"] if records else 0

    async def cleanup_test_data(self, graph_version: str) -> dict[str, int]:
        """清理指定版本的测试数据."""
        if not self._driver:
            return {"nodes": 0, "relationships": 0}

        nodes_before = await self.count_entities(graph_version)
        rels_before = await self.count_relationships(graph_version)

        self._driver.execute_query(
            "MATCH (n {graph_version: $gv}) DETACH DELETE n",
            {"gv": graph_version},
        )

        nodes_after = await self.count_entities(graph_version)
        rels_after = await self.count_relationships(graph_version)

        result = {
            "nodes_before": nodes_before,
            "nodes_after": nodes_after,
            "relationships_before": rels_before,
            "relationships_after": rels_after,
        }
        logger.info("清理测试数据: %s", result)
        return result
