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
import threading
import uuid
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


# Neo4j 持股比例存储合同：百分数（0-100），字符串类型。
# 对外 API 统一 ownership_pct = 0-100，禁止重复乘 100。
OWNERSHIP_PCT_SCALE = 100


def _clean_period(value: str | None) -> str | None:
    """清洗报告期/公告日期（去掉 '.0' 尾巴，空串转 None）。"""
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s or None


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

    # 类级共享 driver：进程内所有实例复用同一连接，避免每次实例化
    # 新建 GraphDatabase.driver（GET /evidence 逐证据回查会高频实例化，
    # 每实例一个 driver 且从不 close → 连接泄漏 + 回查耗时放大）。
    # 锁在类定义时创建（单线程安全）——惰性初始化本身有冷启动竞态：
    # 两线程并发看到 None 各建一把锁，双重检查失效，driver 可能创建两次。
    _shared_driver = None
    _driver_lock = threading.Lock()

    def __init__(self):
        cls = type(self)
        if cls._shared_driver is None:
            with cls._driver_lock:
                if cls._shared_driver is None:
                    self._init_driver()
                    cls._shared_driver = self._driver
        self._driver = cls._shared_driver
        self._available = self._driver is not None

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

    @classmethod
    def close_shared_driver(cls) -> None:
        """显式关闭共享 driver 并清空引用（lifespan 退出时调用；幂等）。

        关闭后再次实例化会重建 driver（测试/重连场景安全）。
        """
        with cls._driver_lock:
            driver, cls._shared_driver = cls._shared_driver, None
        if driver is not None:
            try:
                driver.close()
                logger.info("Neo4j 共享 driver 已关闭")
            except Exception as e:  # noqa: BLE001 — 关闭失败不阻断退出
                logger.warning("Neo4j driver 关闭失败: %s", e)

    # ── 连接管理 ──

    def _check_connection_sync(self) -> bool:
        """同步连接检查（Agent 同步节点使用）。"""
        if self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            self._available = True
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("Neo4j 连接不可用: %s", e)
            self._available = False
            return False

    async def check_connection(self) -> bool:
        return self._check_connection_sync()

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
        """获取股权穿透图谱（真实 Neo4j 查询）— 异步入口."""
        return self._get_graph_sync(
            company_code,
            depth=depth,
            direction=direction,
            as_of=as_of,
            graph_version=graph_version,
        )

    def _get_graph_sync(
        self,
        company_code: str,
        depth: int = 3,
        direction: str = "upstream",
        as_of: str | None = None,
        graph_version: str | None = None,
    ) -> EquityGraph:
        """获取股权穿透图谱（真实 Neo4j 查询）— 同步核心.

        Phase C 契约：
          - ownership_pct 为 0-100 百分数（Neo4j 存储合同为百分数字符串）。
          - 每条边绑定稳定 relationship_id；路径携带 edge_ids。
          - Neo4j 不可用时返回空图（不降级 NetworkX 冒充），由 Router 标记 partial。
        """
        if not self._available:
            self._check_connection_sync()
            if not self._available:
                logger.warning("Neo4j 不可用: %s — 返回空图", company_code)
                return EquityGraph(company_id=company_code, source_system="neo4j")

        try:
            resolved_code = self._resolve_wind_code(company_code)
        except ValueError:
            logger.warning("无法解析 Wind Code: %s", company_code)
            return EquityGraph(company_id=company_code, source_system="neo4j")

        depth = max(1, min(10, depth))
        active_graph_version = graph_version or settings.GRAPH_VERSION

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
            "  AND rel.graph_version = $graph_version "
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
                    "graph_version": active_graph_version,
                },
            )
        except Exception as e:
            logger.error("Neo4j 查询失败: %s", e)
            return EquityGraph(company_id=company_code, source_system="neo4j")

        nodes_map: dict[str, EquityNode] = {}
        edges_map: dict[str, EquityEdge] = {}
        paths_list: list[OwnershipChain] = []

        for record in records:
            target_data = record["target"]
            path = record["path"]

            # 收集节点（entity_id 与 MySQL 对齐）
            for node in path.nodes:
                nid = node.get("entity_id", "") or node.element_id
                if nid and nid not in nodes_map:
                    nodes_map[nid] = EquityNode(
                        id=nid,
                        label=node.get("display_name")
                        or node.get("canonical_name")
                        or nid,
                        type=node.get("entity_type", "entity"),
                        depth=0,
                        entity_id=nid,
                        wind_code=node.get("wind_code") or None,
                        source_system="neo4j",
                        mock=bool(node.get("mock", False)),
                    )

            # 收集边和路径
            path_node_ids: list[str] = []
            path_edge_ids: list[str] = []
            total_fraction = Decimal("1.0")

            for rel in path.relationships:
                src_id = rel.start_node.get("entity_id", "")
                tgt_id = rel.end_node.get("entity_id", "")
                rel_id = rel.get("relationship_id") or ""
                pct = _pct_from_neo4j(rel.get("ownership_pct"))
                pct_100 = float(pct)

                if src_id and tgt_id:
                    if rel_id and rel_id not in edges_map:
                        edges_map[rel_id] = EquityEdge(
                            source=src_id,
                            target=tgt_id,
                            relation=rel.type or "OWNS",
                            stake_ratio=(pct_100 / 100.0) if pct > 0 else None,
                            ownership_pct=pct_100,
                            relationship_id=rel_id,
                            source_record_id=(rel.get("source_record_id") or rel_id),
                            report_period=_clean_period(rel.get("report_period")),
                            ann_dt=_clean_period(rel.get("ann_dt")),
                            is_latest=bool(rel.get("is_latest", True)),
                            source_system="neo4j",
                            mock=bool(rel.get("mock", False)),
                        )
                    if rel_id:
                        path_edge_ids.append(rel_id)

                if src_id:
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
                        edge_ids=path_edge_ids,
                        final_control_pct=round(float(total_fraction) * 100, 4),
                        path_type="control",
                        source_system="neo4j",
                    )
                )

        return EquityGraph(
            company_id=company_code,
            nodes=list(nodes_map.values()),
            edges=list(edges_map.values()),
            control_chains=paths_list,
            graph_version=active_graph_version,
            dataset_version=settings.DATASET_VERSION,
            source_system="neo4j",
        )

    async def get_control_chains(
        self,
        company_code: str,
        max_depth: int = 5,
        as_of: str | None = None,
        graph_version: str | None = None,
    ) -> list[OwnershipChain]:
        graph = await self.get_graph(
            company_code,
            depth=max_depth,
            as_of=as_of,
            graph_version=graph_version,
        )
        return graph.control_chains

    async def get_relationship_by_id(self, relationship_id: str) -> dict | None:
        """按 relationship_id 查找原关系（Evidence 来源定位用）— 异步入口."""
        return self.get_relationship_by_id_sync(relationship_id)

    def get_relationship_by_id_sync(self, relationship_id: str) -> dict | None:
        """按 relationship_id 查找原关系（Evidence 来源定位用）.

        返回关系属性 + 两端节点信息；找不到返回 None。
        """
        if not self._available:
            self._check_connection_sync()
            if not self._available:
                return None
        try:
            records, _, _ = self._driver.execute_query(
                "MATCH (s:Entity)-[r:OWNS {relationship_id: $rid}]->(t:Entity) "
                "RETURN s.entity_id AS source_entity_id, "
                "       s.canonical_name AS source_name, "
                "       t.entity_id AS target_entity_id, "
                "       t.canonical_name AS target_name, "
                "       t.wind_code AS target_wind_code, "
                "       properties(r) AS rel",
                {"rid": relationship_id},
            )
            if not records:
                return None
            rec = records[0]
            rel = dict(rec["rel"])
            rel["source_entity_id"] = rec["source_entity_id"]
            rel["source_name"] = rec["source_name"]
            rel["target_entity_id"] = rec["target_entity_id"]
            rel["target_name"] = rec["target_name"]
            rel["target_wind_code"] = rec["target_wind_code"]
            rel["relationship_id"] = relationship_id
            return rel
        except Exception as e:  # noqa: BLE001
            logger.error("Neo4j relationship 查询失败: %s", e)
            return None

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
        import_run_id: str | None = None,
    ) -> dict:
        """导入股权关系（P0-2 防误删保护）。

        注意：非完整事务回滚——历史关系属性可能被本次 MERGE 覆盖，无法恢复。

            标记语义：
              - created_run_id：关系**首次创建**时的 run（MERGE 命中旧关系不改写）
              - seen_run_id：本次运行**见到/更新**过的 run（每次覆盖为本次）

            失败时调用方只删 created_run_id=本次（真正新建的），
            已有关系不受影响；全部成功验收后删 seen_run_id<>本次（旧图）。
            批次失败立即抛异常（不记录后继续）。

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
        run_id = import_run_id or uuid.uuid4().hex[:12]
        imported = 0

        # UNWIND 批量导入（每批 _REL_BATCH_SIZE 条）——逐条 execute_query 在
        # 64 万条量级需 40 分钟+，批处理压缩到几分钟，且避免单事务内存膨胀。
        batch_size = getattr(self, "_REL_BATCH_SIZE", 1000)
        for start in range(0, len(relationships), batch_size):
            batch = relationships[start : start + batch_size]
            rows: list[dict] = []
            for rel in batch:
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
                rows.append(
                    {
                        "rel_id": relationship_id,
                        "src_id": src_id,
                        "tgt_id": tgt_id,
                        "rel_type": rel_type,
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
                    }
                )
            if not rows:
                continue

            rel_type = rows[0]["rel_type"]
            # P0-1（核验修订）：created_run_id 必须只在真正新建时写入（ON CREATE）。
            # 历史关系没有该字段，若用"字段为空→本次创建"推断，首次升级导入的
            # 旧关系会被误标为本次创建，失败清理（delete_relationships_by_run）
            # 会误删旧图。seen_run_id 对所有见到的关系都打标（stale 删除依据）。
            cypher = f"""
            UNWIND $rels AS rel
            MATCH (src:Entity {{entity_id: rel.src_id}})
            MATCH (tgt:Entity {{entity_id: rel.tgt_id}})
            MERGE (src)-[r:{rel_type} {{relationship_id: rel.rel_id}}]->(tgt)
            ON CREATE SET r.created_run_id = $run_id,
                          r.created_at = rel.updated_at
            SET r.ownership_pct = rel.ownership_pct,
                r.quantity = rel.quantity,
                r.ann_dt = rel.ann_dt,
                r.report_period = rel.report_period,
                r.source_id = rel.source_id,
                r.source_record_id = rel.source_record_id,
                r.dataset_version = rel.dataset_version,
                r.graph_version = rel.graph_version,
                r.match_confidence = rel.match_confidence,
                r.is_latest = rel.is_latest,
                r.mock = rel.mock,
                r.seen_run_id = $run_id,
                r.updated_at = rel.updated_at
            RETURN count(r) AS merged
            """

            try:
                records, _, _ = self._driver.execute_query(
                    cypher, {"rels": rows, "run_id": run_id}
                )
                merged = records[0]["merged"] if records else 0
                if merged < len(rows):
                    raise RuntimeError(
                        f"批次 {start}: 实际写入 {merged}/{len(rows)} 条，"
                        "存在缺失端点（MATCH 未命中）"
                    )
                imported += merged
            except Exception as e:  # noqa: BLE001 — 批次失败立即上抛（P0-2）
                raise RuntimeError(
                    f"关系导入批次失败 ({len(rows)} 条, 起点 {start}): {e}"
                ) from e

        logger.info(
            "导入 %d/%d 关系 (graph_version=%s, import_run_id=%s)",
            imported,
            len(relationships),
            gv,
            run_id,
        )
        return {"imported": imported, "total": len(relationships), "run_id": run_id}

    # ── P0-2 防误删保护（非完整事务回滚）──
    # 核验修订：双标记只保证"失败时不误删旧图"，被 MERGE 原地覆盖的历史
    # 关系属性不会恢复（真实回滚需版本隔离/蓝绿导入）。

    async def delete_relationships_by_run(self, import_run_id: str) -> dict[str, int]:
        """失败清理（防误删保护）：仅删除本次运行真正新建的关系
        （created_run_id=本次），并清除已有关系上的 seen_run_id 标记。
        注意：历史关系的属性可能已被本次 MERGE 覆盖，无法回滚。"""
        if not self._driver:
            return {"deleted": 0}
        records, _, _ = self._driver.execute_query(
            "MATCH ()-[r {created_run_id: $run_id}]->() "
            "DETACH DELETE r "
            "RETURN count(r) AS cnt",
            {"run_id": import_run_id},
        )
        deleted = records[0]["cnt"] if records else 0
        # 清除本次打上的 seen 标记（防误删保护：旧关系属性不回滚）
        self._driver.execute_query(
            "MATCH ()-[r {seen_run_id: $run_id}]->() " "REMOVE r.seen_run_id",
            {"run_id": import_run_id},
        )
        logger.info(
            "失败清理 import_run_id=%s: 删除新建 %d, 清除 seen 标记",
            import_run_id,
            deleted,
        )
        return {"deleted": deleted}

    async def delete_stale_relationships(
        self, graph_version: str, import_run_id: str
    ) -> dict[str, int]:
        """验收成功后删除旧关系：目标版本中本次未见过的关系
        （seen_run_id <> 本次）。分批删除防内存爆。"""
        if not self._driver:
            return {"deleted": 0}
        total = 0
        while True:
            records, _, _ = self._driver.execute_query(
                "MATCH ()-[r {graph_version: $gv}]->() "
                "WHERE r.seen_run_id IS NULL OR r.seen_run_id <> $run_id "
                "WITH r LIMIT 20000 "
                "DETACH DELETE r "
                "RETURN count(r) AS cnt",
                {"gv": graph_version, "run_id": import_run_id},
            )
            deleted = records[0]["cnt"] if records else 0
            total += deleted
            if not deleted:
                break
        # 清理临时标记
        self._driver.execute_query(
            "MATCH ()-[r {graph_version: $gv}]->() " "REMOVE r.seen_run_id",
            {"gv": graph_version},
        )
        logger.info("删除旧关系 %d 条 (graph_version=%s)", total, graph_version)
        return {"deleted": total}

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

    async def count_multi_hop_paths(
        self,
        graph_version: str | None = None,
        min_depth: int = 3,
        import_run_id: str | None = None,
        all_versions: bool = False,
    ) -> int:
        """统计上市公司间 min_depth 跳以上路径数（P0-2 验收辅助）。

        受限范围：全部节点限定上市公司（wind_code 非空、非自环），
        避免全图（含 64 万 person/产品边）变长路径指数爆炸。
        返回计数封顶 10000（仅验收判定用，非精确计数）。
        import_run_id 非空时限定 r.seen_run_id=本次（核验修订：中间验收
        不得混合旧图关系）。
        """
        if not self._driver:
            return 0
        gv = graph_version or settings.GRAPH_VERSION
        # 起点/终点必须是公司；中间节点不限制（真实穿透链路常经股东身份）。
        # P0-1：仅统计 is_latest=true 的关系 + 路径节点互异（防循环路径）。
        records, _, _ = self._driver.execute_query(
            f"""
            MATCH p = (a:Entity)-[:OWNS*{int(min_depth)}..4]->(b:Entity)
            WHERE a.wind_code <> '' AND b.wind_code <> ''
              AND a.wind_code <> b.wind_code
              AND all(r IN relationships(p)
                      WHERE ($all_versions OR r.graph_version = $gv)
                        AND r.is_latest = true
                        AND ($run_id IS NULL OR r.seen_run_id = $run_id))
              AND all(n IN nodes(p)
                      WHERE size([m IN nodes(p) WHERE m = n]) = 1)
            RETURN count(p) AS cnt
            """,
            {
                "gv": gv,
                "run_id": import_run_id,
                "all_versions": all_versions,
            },
        )
        return min(records[0]["cnt"], 10000) if records else 0

    async def clear_run_markers(self, import_run_id: str) -> int:
        """幂等增量导入后清除本次打上的 seen_run_id 标记（不删任何关系）。"""
        if not self._driver:
            return 0
        records, _, _ = self._driver.execute_query(
            "MATCH ()-[r {seen_run_id: $run_id}]->() "
            "REMOVE r.seen_run_id "
            "RETURN count(r) AS cnt",
            {"run_id": import_run_id},
        )
        n = records[0]["cnt"] if records else 0
        logger.info("清除 seen 标记 %d 条 (run_id=%s)", n, import_run_id)
        return n

    async def cleanup_relationships(self, graph_version: str) -> dict[str, int]:
        """R5：仅删除指定版本的关系，不动任何节点。

        与 cleanup_test_data 的 DETACH DELETE 不同——后者会删除节点及
        其连接的其他版本关系；重建图时必须用本函数（维护窗口内执行）。
        """
        if not self._driver:
            return {"relationships_before": 0, "relationships_after": 0}
        rels_before = await self.count_relationships(graph_version)
        # 分批删除：单条 DELETE 删除数十万关系会在单事务内爆内存
        # （Neo4j 事务内存上限，如 2.8 GiB）
        while True:
            records, _, _ = self._driver.execute_query(
                "MATCH ()-[r {graph_version: $gv}]->() "
                "WITH r LIMIT 20000 "
                "DETACH DELETE r "
                "RETURN count(r) AS cnt",
                {"gv": graph_version},
            )
            deleted = records[0]["cnt"] if records else 0
            if not deleted:
                break
        rels_after = await self.count_relationships(graph_version)
        result = {
            "relationships_before": rels_before,
            "relationships_after": rels_after,
        }
        logger.info("清理关系 (graph_version=%s): %s", graph_version, result)
        return result

    async def cleanup_orphan_corporate_nodes(self) -> dict[str, int]:
        """R5：删除无任何关系的孤立 corp_* 节点（股东身份节点残留）。

        仅在维护窗口内、且确认无关系后执行；稳定实体（company_*/person_*）
        不受影响。
        """
        if not self._driver:
            return {"nodes_deleted": 0}
        records, _, _ = self._driver.execute_query(
            "MATCH (n:Entity) "
            "WHERE n.entity_id STARTS WITH 'corp_' "
            "AND NOT EXISTS { MATCH (n)-[r]-() } "
            "DETACH DELETE n "
            "RETURN count(n) AS cnt"
        )
        cnt = records[0]["cnt"] if records else 0
        logger.info("清理孤立 corp_* 节点: %d", cnt)
        return {"nodes_deleted": cnt}
