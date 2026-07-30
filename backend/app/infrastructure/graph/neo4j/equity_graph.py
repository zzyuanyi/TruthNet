"""Neo4j EquityGraph Adapter — V12 full profile (集成版).

整合 PR #11 全量图谱查询逻辑，修复 Wind Code 规范化、历史持股
多快照保留、graph_version 稳定实体等关键问题。

实现 EquityGraphPort 协议:
- 约束和索引初始化
- 实体节点 MERGE（幂等）
- 股权关系 MERGE（按 relationship_id 保留历史快照）
- 多跳控制链查询（支持 as_of 时点）
- 权重计算（Decimal 字符串精度）

依赖: neo4j Python driver >= 5.x
"""

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.domain.equity.models import EquityEdge, EquityGraph, EquityNode, OwnershipChain

logger = logging.getLogger(__name__)

# ── 超时 ──
_CONNECTION_TIMEOUT = 10
_QUERY_TIMEOUT = 30

# ── 默认版本标记 ──
_DEFAULT_GRAPH_VERSION = "equity-mock-v12"
_DEFAULT_DATASET_VERSION = "mock-v12"


# ═══════════════════════════════════════════════════════════
# Decimal ↔ Neo4j 字符串
# ═══════════════════════════════════════════════════════════


def _pct_to_neo4j(value: Decimal | float | None) -> str | None:
    if value is None:
        return None
    d = Decimal(str(value))
    return f"{d:.6f}"


def _pct_from_neo4j(raw: str | float | int | None) -> Decimal:
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


# ═══════════════════════════════════════════════════════════
# 关系 ID 生成 — 确保历史快照不被覆盖
# ═══════════════════════════════════════════════════════════


def make_relationship_id(
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    report_period: str,
    ann_dt: str,
    source_record_id: str = "",
) -> str:
    """为每条股权关系生成确定性 relationship_id。

    由 source, target, relation_type, report_period, ann_dt,
    source_record_id 计算 SHA256 前 16 位，确保不同报告期的同一
    股东-公司关系被保留为独立快照。
    """
    raw = "|".join(
        [
            source_entity_id,
            target_entity_id,
            relation_type,
            report_period or "",
            ann_dt or "",
            source_record_id or "",
        ]
    )
    return f"rel_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# ═══════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════


class Neo4jEquityGraph:
    """Neo4j 股权图谱 — full profile adapter。

    关键设计决策：
      - 实体节点是稳定实体，graph_version 为创建版本（不覆盖）。
      - 关系节点通过 relationship_id 区分不同报告期/公告日的快照。
      - 查询默认只使用 is_latest=true 的关系；传入 as_of 返回历史时点。
      - Wind Code 统一通过 normalizer.normalize_wind_code() 处理。
    """

    def __init__(self):
        self._driver = None
        self._available = False
        self._init_driver()

    def _init_driver(self) -> None:
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

    # ── 连接管理 ──

    async def check_connection(self) -> bool:
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
        queries = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE INDEX entity_wind_code IF NOT EXISTS "
            "FOR (e:Entity) ON (e.wind_code)",
            "CREATE INDEX entity_name IF NOT EXISTS "
            "FOR (e:Entity) ON (e.canonical_name)",
            "CREATE INDEX rel_relationship_id IF NOT EXISTS "
            "FOR ()-[r:OWNS]-() ON (r.relationship_id)",
            "CREATE INDEX rel_is_latest IF NOT EXISTS "
            "FOR ()-[r:OWNS]-() ON (r.is_latest)",
        ]
        for q in queries:
            try:
                self._driver.execute_query(q)
                logger.debug("Neo4j 约束/索引: %s", q[:60])
            except Exception as e:
                logger.warning("Neo4j 约束/索引: %s", e)

    # ── Wind Code 解析 ──

    @staticmethod
    def _resolve_wind_code(code: str) -> str:
        """使用统一 normalizer 解析 Wind Code。

        Args:
            code: 任意格式（裸代码、.SH/.SZ/.BJ、.XSHG/.XSHE）

        Returns:
            规范化 Wind Code，如 "600518.SH"

        Raises:
            ValueError: 无法解析
        """
        from app.infrastructure.graph.normalizer import normalize_wind_code

        return normalize_wind_code(code)

    # ── 图查询 ──

    async def get_graph(
        self,
        company_code: str,
        depth: int = 3,
        direction: str = "upstream",
        as_of: str | None = None,
        graph_version: str | None = None,
    ) -> EquityGraph:
        """获取股权穿透图谱。

        Args:
            company_code: Wind Code（任意格式，经由 normalizer 统一）
            depth: 最大穿透深度 (1-10)
            direction: upstream=向上穿透股东 / downstream=向下穿透投资
            as_of: 可选时点查询（ISO date），不传则返回最新关系
            graph_version: 可选图版本过滤

        Returns:
            EquityGraph 域模型
        """
        if not self._available:
            await self.check_connection()
            if not self._available:
                return EquityGraph(company_id=company_code)

        try:
            resolved_code = self._resolve_wind_code(company_code)
        except ValueError:
            logger.warning("无法解析 Wind Code: %s", company_code)
            return EquityGraph(company_id=company_code)

        depth = max(1, min(10, depth))

        # 时点过滤条件（使用 rel 而非 r，因为 r 是路径中的关系列表）
        if as_of:
            time_filter = "AND rel.report_period <= $as_of"
        else:
            time_filter = "AND rel.is_latest = true"

        # 方向
        if direction == "upstream":
            rel_pattern = f"<-[r:OWNS*1..{depth}]-"
        else:
            rel_pattern = f"-[r:OWNS*1..{depth}]->"

        cypher = (
            "MATCH (target:Entity {wind_code: $code}) "
            f"MATCH path = (target){rel_pattern}(other:Entity) "
            "WHERE all(rel IN relationships(path) WHERE rel.mock = false "
            f"  {time_filter}) "
            "RETURN target, path "
            "LIMIT 200"
        )

        try:
            records, _, _ = self._driver.execute_query(
                cypher,
                {
                    "code": resolved_code,
                    "as_of": as_of,
                },
            )
        except Exception as e:
            logger.error("Neo4j 查询失败: %s", e)
            return EquityGraph(company_id=company_code)

        nodes_map: dict[str, object] = {}
        edges_map: dict[tuple[str, str], object] = {}
        paths_list: list[OwnershipChain] = []

        for record in records:
            target_data = record["target"]
            path = record["path"]

            # 收集节点
            for node in path.nodes:
                nid = node.get("entity_id", "")
                if nid and nid not in nodes_map:
                    nodes_map[nid] = EquityNode(
                        id=nid,
                        label=node.get("display_name")
                        or node.get("canonical_name", ""),
                        type=node.get("entity_type", "entity"),
                        depth=0,
                    )

            # 收集边和路径
            path_node_ids: list[str] = []
            total_fraction = Decimal("1.0")

            for rel in path.relationships:
                src_id = rel.start_node.get("entity_id", "")
                tgt_id = rel.end_node.get("entity_id", "")
                rel.get("relationship_id", "")

                if hasattr(edges_map, "get"):
                    pass  # using dict

                if src_id and tgt_id:
                    pct = _pct_from_neo4j(rel.get("ownership_pct"))
                    edge_obj = EquityEdge(
                        source=src_id,
                        target=tgt_id,
                        relation=rel.type or "OWNS",
                        stake_ratio=float(pct) / 100.0 if pct > 0 else None,
                    )
                    edges_map[(src_id, tgt_id)] = edge_obj

                path_node_ids.append(src_id)
                if pct > 0:
                    total_fraction *= pct / Decimal("100")

            tgt_nid = target_data.get("entity_id", "")
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
        self,
        company_code: str,
        max_depth: int = 5,
        as_of: str | None = None,
    ) -> list[OwnershipChain]:
        graph = await self.get_graph(company_code, depth=max_depth, as_of=as_of)
        return graph.control_chains

    # ── 数据导入 ──

    async def import_entities_batch(
        self,
        entities: list[dict[str, Any]],
        graph_version: str | None = None,
        mock: bool = False,
    ) -> int:
        """批量导入实体节点（幂等 MERGE）。

        实体节点是稳定实体——首次创建时记录 graph_version 和 created_at，
        后续 MERGE 只更新 display_name、aliases 等可变字段，
        不覆盖 graph_version（避免新导入抹除创建版本信息）。
        """
        if not self._driver:
            logger.warning("Neo4j driver 未初始化，跳过实体导入")
            return 0

        gv = graph_version or _DEFAULT_GRAPH_VERSION
        now = datetime.now(timezone.utc).isoformat()
        imported = 0

        for ent in entities:
            entity_id = ent.get("entity_id")
            if not entity_id:
                continue

            cypher = """
            MERGE (e:Entity {entity_id: $entity_id})
            SET e.canonical_name = coalesce($canonical_name, e.canonical_name),
                e.display_name = coalesce($display_name, e.display_name),
                e.entity_type = coalesce($entity_type, e.entity_type),
                e.wind_code = coalesce($wind_code, e.wind_code),
                e.aliases = coalesce($aliases, e.aliases),
                e.match_confidence = $match_confidence,
                e.dataset_version = $dataset_version,
                e.source_id = coalesce($source_id, e.source_id),
                e.mock = $mock,
                e.updated_at = $updated_at
            FOREACH (_ IN CASE WHEN e.created_at IS NULL THEN [1] ELSE [] END |
                SET e.created_at = $updated_at,
                    e.graph_version = $graph_version
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
                        "dataset_version": _DEFAULT_DATASET_VERSION,
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
        """批量导入股权关系（保留历史快照）。

        每条关系使用确定性 relationship_id：
          make_relationship_id(src, tgt, type, report_period, ann_dt, source_record_id)

        不同报告期的同一 src→tgt 关系会被保留为独立快照。
        最新快照的 is_latest 标记为 true。
        """
        if not self._driver:
            logger.warning("Neo4j driver 未初始化，跳过关系导入")
            return 0

        gv = graph_version or _DEFAULT_GRAPH_VERSION
        now = datetime.now(timezone.utc).isoformat()
        imported = 0

        for rel in relationships:
            src_id = rel.get("source_entity_id")
            tgt_id = rel.get("target_entity_id")
            rel_type = rel.get("relation_type", "OWNS")

            if not src_id or not tgt_id:
                continue

            relationship_id = make_relationship_id(
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                relation_type=rel_type,
                report_period=str(rel.get("report_period", "")),
                ann_dt=str(rel.get("ann_dt", "")),
                source_record_id=str(rel.get("source_record_id", "")),
            )

            cypher = f"""
            MATCH (src:Entity {{entity_id: $src_id}})
            MATCH (tgt:Entity {{entity_id: $tgt_id}})
            MERGE (src)-[r:{rel_type} {{relationship_id: $rel_id}}]->(tgt)
            SET r.ownership_pct = $ownership_pct,
                r.quantity = $quantity,
                r.ann_dt = $ann_dt,
                r.report_period = $report_period,
                r.source_id = $source_id,
                r.source_record_id = $source_record_id,
                r.dataset_version = $dataset_version,
                r.graph_version = $graph_version,
                r.match_confidence = $match_confidence,
                r.is_latest = $is_latest,
                r.mock = $mock,
                r.updated_at = $updated_at
            FOREACH (_ IN CASE WHEN r.created_at IS NULL THEN [1] ELSE [] END |
                SET r.created_at = $updated_at
            )
            RETURN type(r)
            """

            try:
                self._driver.execute_query(
                    cypher,
                    {
                        "rel_id": relationship_id,
                        "src_id": src_id,
                        "tgt_id": tgt_id,
                        "ownership_pct": _pct_to_neo4j(rel.get("ownership_pct")),
                        "quantity": rel.get("quantity"),
                        "ann_dt": str(rel.get("ann_dt", "")),
                        "report_period": str(rel.get("report_period", "")),
                        "source_id": str(rel.get("source_id", "")),
                        "source_record_id": str(rel.get("source_record_id", "")),
                        "dataset_version": _DEFAULT_DATASET_VERSION,
                        "graph_version": gv,
                        "match_confidence": rel.get("match_confidence", 1.0),
                        "is_latest": rel.get("is_latest", True),
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

    # ── 管理查询 ──

    async def count_entities(self, graph_version: str | None = None) -> int:
        if not self._driver:
            return 0
        gv = graph_version or _DEFAULT_GRAPH_VERSION
        records, _, _ = self._driver.execute_query(
            "MATCH (e:Entity {graph_version: $gv}) RETURN count(e) AS cnt",
            {"gv": gv},
        )
        return records[0]["cnt"] if records else 0

    async def count_relationships(self, graph_version: str | None = None) -> int:
        if not self._driver:
            return 0
        gv = graph_version or _DEFAULT_GRAPH_VERSION
        records, _, _ = self._driver.execute_query(
            "MATCH ()-[r {graph_version: $gv}]->() RETURN count(r) AS cnt",
            {"gv": gv},
        )
        return records[0]["cnt"] if records else 0

    async def cleanup_test_data(self, graph_version: str) -> dict[str, int]:
        """清理指定版本的测试数据（仅限显式版本）。"""
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
        logger.info("清理测试数据 (graph_version=%s): %s", graph_version, result)
        return result
