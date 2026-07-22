"""Neo4j 股权图导入器 — V12 §8.6.

支持:
- 从 fixture / MySQL / canonical 数据源导入
- 幂等 MERGE
- batch size 控制
- dry-run 预览
- mock/test 数据隔离
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── 康美药业验收 fixture ─────────────────────────────────

KANGMEI_FIXTURE = {
    "entities": [
        {
            "entity_id": "ent_ma_xingtian",
            "canonical_name": "马兴田",
            "display_name": "马兴田",
            "entity_type": "Person",
            "wind_code": "",
            "aliases": [],
            "match_confidence": 1.0,
            "source_id": "kangmei_fixture",
        },
        {
            "entity_id": "ent_kangmei_industrial",
            "canonical_name": "康美实业投资控股有限公司",
            "display_name": "康美实业",
            "entity_type": "Company",
            "wind_code": "",
            "aliases": ["康美实业"],
            "match_confidence": 1.0,
            "source_id": "kangmei_fixture",
        },
        {
            "entity_id": "company_600518_SH",
            "canonical_name": "康美药业股份有限公司",
            "display_name": "康美药业",
            "entity_type": "ListedCompany",
            "wind_code": "600518.SH",
            "aliases": ["康美药业", "ST康美"],
            "match_confidence": 1.0,
            "source_id": "kangmei_fixture",
        },
    ],
    "relationships": [
        {
            "source_entity_id": "ent_ma_xingtian",
            "target_entity_id": "ent_kangmei_industrial",
            "relation_type": "OWNS",
            "ownership_pct": "99.700000",
            "quantity": None,
            "ann_dt": "",
            "report_period": "",
            "source_id": "kangmei_fixture",
            "source_record_id": "kangmei_rel_001",
            "match_confidence": 1.0,
        },
        {
            "source_entity_id": "ent_kangmei_industrial",
            "target_entity_id": "company_600518_SH",
            "relation_type": "OWNS",
            "ownership_pct": "30.100000",
            "quantity": None,
            "ann_dt": "",
            "report_period": "",
            "source_id": "kangmei_fixture",
            "source_record_id": "kangmei_rel_002",
            "match_confidence": 1.0,
        },
    ],
}


async def import_fixture(
    adapter,
    graph_version: str = "task456_test_fixture",
    mock: bool = True,
    dry_run: bool = False,
) -> dict:
    """导入康美验收 fixture（幂等）.

    Returns:
        {"entities": count, "relationships": count}
    """
    if dry_run:
        return {
            "entities": len(KANGMEI_FIXTURE["entities"]),
            "relationships": len(KANGMEI_FIXTURE["relationships"]),
            "dry_run": True,
        }

    await adapter.ensure_constraints()

    n_entities = await adapter.import_entities_batch(
        KANGMEI_FIXTURE["entities"],
        graph_version=graph_version,
        mock=mock,
    )
    n_rels = await adapter.import_relationships_batch(
        KANGMEI_FIXTURE["relationships"],
        graph_version=graph_version,
        mock=mock,
    )

    return {
        "entities": n_entities,
        "relationships": n_rels,
        "dry_run": False,
        "graph_version": graph_version,
    }


# ── CLI 入口 ─────────────────────────────────────────────


async def main_import(
    source: str = "fixture",
    graph_version: str | None = None,
    dataset_version: str | None = None,
    batch_size: int = 100,
    limit: int = 0,
    dry_run: bool = False,
    mock: bool = False,
):
    """CLI 导入入口.

    Args:
        source: 数据源 (fixture | mysql | canonical)
        graph_version: 图版本标记
        dataset_version: 数据集版本
        batch_size: 批量大小
        limit: 最大导入数 (0=无限制)
        dry_run: 仅预览
        mock: 标记为测试数据
    """
    from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

    adapter = Neo4jEquityGraph()
    gv = (
        graph_version
        or f"import_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )

    if source == "fixture":
        result = await import_fixture(
            adapter, graph_version=gv, mock=mock, dry_run=dry_run
        )
    else:
        logger.warning("数据源 '%s' 尚不支持，仅 fixture 可用", source)
        result = {"error": f"unsupported source: {source}"}

    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # 简易参数解析
    args = {
        "source": "fixture",
        "graph_version": None,
        "dry_run": False,
        "mock": True,
    }
    for arg in sys.argv[1:]:
        if arg.startswith("--source="):
            args["source"] = arg.split("=")[1]
        elif arg.startswith("--graph-version="):
            args["graph_version"] = arg.split("=")[1]
        elif arg == "--dry-run":
            args["dry_run"] = True
        elif arg == "--mock":
            args["mock"] = True
        elif arg.startswith("--limit="):
            args["limit"] = int(arg.split("=")[1])

    result = asyncio.run(main_import(**args))
    import json

    print(json.dumps(result, indent=2, default=str))
