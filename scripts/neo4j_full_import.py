#!/usr/bin/env python
"""TruthNet — Neo4j 全量股权图谱构建 (Phase B Task 2, 集成版).

设计原则：
  - 默认幂等增量写入（不删除已有数据）
  - --replace-graph-version 为显式危险操作
  - 实体节点是稳定实体（graph_version 记录创建版本，不覆盖）
  - 关系节点通过 relationship_id 保留历史快照
  - 统一使用 normalizer 的 Wind Code / entity_id 方法
  - 一致行动人检测按 wind_code + report_period + sequence 分组
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.core.config import settings  # noqa: E402
from backend.app.infrastructure.graph.neo4j.equity_graph import (  # noqa: E402
    Neo4jEquityGraph,
    make_relationship_id,
)
from backend.app.infrastructure.graph.normalizer import (  # noqa: E402
    make_listed_company_entity_id,
    normalize_wind_code,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 实体对齐
# ═══════════════════════════════════════════════════════════


def normalize_entity_name(name: str) -> str:
    """标准化实体名称（NFKC + 全角→半角 + 去空白）."""
    import unicodedata

    if not name or pd.isna(name):
        return ""
    name = str(name)
    name = unicodedata.normalize("NFKC", name)
    # 全角转半角
    result = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(ch)
    return "".join(result).strip()


def build_entity_id(
    name: str,
    wind_code: str | None = None,
    holder_category: int | None = None,
) -> str:
    """为股东实体生成稳定 entity_id。

    上市公司: company_{code}_{exchange}
    个人股东: person_{name_hash}
    企业股东: corp_{name_hash}
    """
    if wind_code:
        return make_listed_company_entity_id(wind_code)

    name_hash = hashlib.sha256(name.encode()).hexdigest()[:12]
    if holder_category == 1:
        return f"person_{name_hash}"
    else:
        return f"corp_{name_hash}"


# ═══════════════════════════════════════════════════════════
# 一致行动人检测
# ═══════════════════════════════════════════════════════════


def detect_concerted_parties(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """检测一致行动人。

    按 (wind_code, report_period, sequence) 分组，
    同组多个股东的持股比例合并。

    s_holder_sequence 的语义需验证；仅在 sequence 有明确
    一致行动含义时才合并。
    """
    groups = []
    for (wind_code, period, seq), group in df.groupby(
        ["wind_code", "report_period", "s_holder_sequence"]
    ):
        if seq is None or pd.isna(seq) or len(group) <= 1:
            continue

        names = group["s_holder_aname"].fillna(group["s_holder_name"]).tolist()
        total_pct = group["s_holder_pct"].sum()

        groups.append(
            {
                "wind_code": normalize_wind_code(str(wind_code)),
                "report_period": str(period),
                "sequence": int(seq),
                "members": [normalize_entity_name(n) for n in names],
                "combined_pct": float(total_pct),
                "confidence": 0.7,  # heuristic, not confirmed
                "method": "sequence_grouping",
            }
        )

    return groups


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Neo4j 全量股权图谱构建")

    p.add_argument("--data-file", required=True, help="十大股东 Excel/CSV 路径")
    p.add_argument("--graph-version", default=settings.GRAPH_VERSION)
    p.add_argument("--dataset-version", default=settings.DATASET_VERSION)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mock", action="store_true", help="标记为 mock 数据")
    p.add_argument(
        "--replace-graph-version",
        action="store_true",
        help="⚠️ 危险：替换指定 graph_version 的全部关系（保留实体节点）",
    )
    p.add_argument(
        "--concerted-only",
        action="store_true",
        help="仅运行一致行动人检测并输出 CSV",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error("数据文件不存在: %s", data_path)
        return 1

    # 读取数据
    if data_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, low_memory=False)

    logger.info("读取 %d 条股东记录", len(df))

    # 仅一致行动人检测模式
    if args.concerted_only:
        concerted = detect_concerted_parties(df)
        out_path = data_path.parent / "concerted_parties.csv"
        pd.DataFrame(concerted).to_csv(out_path, index=False)
        logger.info("一致行动人: %d 组 → %s", len(concerted), out_path)
        return 0

    # 初始化 Neo4j adapter
    adapter = Neo4jEquityGraph()
    if not adapter._driver:
        logger.error("Neo4j 连接不可用，请检查 NEO4J_URI 配置")
        return 2

    import asyncio

    async def _run():
        await adapter.check_connection()
        await adapter.ensure_constraints()

        # 替换模式：清除指定版本的旧关系
        if args.replace_graph_version:
            logger.warning(
                "⚠️ 将替换 graph_version=%s 的全部关系！",
                args.graph_version,
            )
            await adapter.cleanup_test_data(args.graph_version)

        datetime.now(timezone.utc).isoformat()

        # Step 1: 构建实体节点
        entities: dict[str, dict] = {}
        for _, row in df.iterrows():
            wind_code = str(row.get("s_info_windcode", ""))
            try:
                normalized_code = normalize_wind_code(wind_code)
            except ValueError:
                continue

            # 上市公司实体
            listed_entity_id = make_listed_company_entity_id(normalized_code)
            if listed_entity_id not in entities:
                entities[listed_entity_id] = {
                    "entity_id": listed_entity_id,
                    "canonical_name": normalize_entity_name(wind_code),
                    "display_name": normalize_entity_name(wind_code),
                    "entity_type": "ListedCompany",
                    "wind_code": normalized_code,
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": str(uuid.uuid4()),
                }

            # 股东实体
            holder_name = str(row.get("s_holder_aname") or row.get("s_holder_name", ""))
            holder_name = normalize_entity_name(holder_name)
            if not holder_name:
                continue

            holder_category = int(row.get("s_holder_holdercategory", 0) or 0)
            holder_entity_id = build_entity_id(
                holder_name, holder_category=holder_category
            )

            if holder_entity_id not in entities:
                entity_type = "Person" if holder_category == 1 else "Company"
                # ⚠️ 特殊实体类型校正
                if any(
                    kw in holder_name
                    for kw in ["国资委", "财政局", "人民政府", "国有资产"]
                ):
                    entity_type = "Government"

                entities[holder_entity_id] = {
                    "entity_id": holder_entity_id,
                    "canonical_name": holder_name,
                    "display_name": holder_name,
                    "entity_type": entity_type,
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 0.9,
                    "source_id": str(uuid.uuid4()),
                }

        logger.info(f"去重后实体: {len(entities)}")

        # Step 2: 导入实体
        if not args.dry_run:
            n_entities = await adapter.import_entities_batch(
                list(entities.values()),
                graph_version=args.graph_version,
                mock=args.mock,
            )
            logger.info("导入实体: %d", n_entities)

        # Step 3: 构建关系
        relationships: list[dict] = []
        for _, row in df.iterrows():
            wind_code = str(row.get("s_info_windcode", ""))
            try:
                normalized_code = normalize_wind_code(wind_code)
            except ValueError:
                continue

            holder_name = normalize_entity_name(
                str(row.get("s_holder_aname") or row.get("s_holder_name", ""))
            )
            if not holder_name:
                continue

            holder_category = int(row.get("s_holder_holdercategory", 0) or 0)
            src_id = build_entity_id(holder_name, holder_category=holder_category)
            tgt_id = make_listed_company_entity_id(normalized_code)
            pct = float(row.get("s_holder_pct", 0) or 0)
            report_period = str(
                row.get("report_period", "") or row.get("s_holder_enddate", "")
            )
            ann_dt = str(row.get("ann_dt", ""))

            rel_id = make_relationship_id(
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                relation_type="OWNS",
                report_period=report_period,
                ann_dt=ann_dt,
                source_record_id=str(uuid.uuid4()),
            )

            relationships.append(
                {
                    "source_entity_id": src_id,
                    "target_entity_id": tgt_id,
                    "relation_type": "OWNS",
                    "ownership_pct": pct,
                    "quantity": float(row.get("s_holder_quantity", 0) or 0),
                    "ann_dt": ann_dt,
                    "report_period": report_period,
                    "source_id": rel_id,
                    "source_record_id": rel_id,
                    "match_confidence": 0.9,
                    "is_latest": True,
                }
            )

        logger.info(f"关系总数: {len(relationships)}")

        # Step 4: 导入关系
        if not args.dry_run:
            n_rels = await adapter.import_relationships_batch(
                relationships,
                graph_version=args.graph_version,
                mock=args.mock,
            )
            logger.info("导入关系: %d", n_rels)

        # Step 5: 验证
        n_entities_neo = await adapter.count_entities(args.graph_version)
        n_rels_neo = await adapter.count_relationships(args.graph_version)
        logger.info(
            "Neo4j 验证: 实体=%d, 关系=%d (graph_version=%s)",
            n_entities_neo,
            n_rels_neo,
            args.graph_version,
        )

        return 0

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
