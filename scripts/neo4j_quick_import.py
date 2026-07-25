#!/usr/bin/env python
"""Quick Neo4j import from shareholders Excel — compact version."""

import sys
import asyncio
import hashlib
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pandas as pd
from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph
from app.infrastructure.graph.normalizer import (
    normalize_wind_code,
    make_listed_company_entity_id,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

GRAPH_VER = "equity-2026Q2"
BATCH = 2000


async def main():
    g = Neo4jEquityGraph()
    if not await g.check_connection():
        log.error("Neo4j not connected!")
        return 1

    await g.ensure_constraints()
    log.info("Constraints ready")

    fp = Path("data/raw/2/clean.xlsx")
    df = pd.read_excel(fp)
    log.info("Read %d shareholders", len(df))

    entities = {}
    rels = []
    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        if idx % 50000 == 0:
            log.info("Processing: %d/%d", idx, total)

        wc = str(row.get("s_info_windcode", ""))
        try:
            normalized = normalize_wind_code(wc)
        except ValueError:
            continue

        eid = make_listed_company_entity_id(normalized)
        if eid not in entities:
            entities[eid] = {
                "entity_id": eid,
                "canonical_name": normalized,
                "display_name": normalized,
                "entity_type": "ListedCompany",
                "wind_code": normalized,
                "aliases": [],
                "match_confidence": 1.0,
                "source_id": eid,
            }

        holder = str(row.get("s_holder_aname") or row.get("s_holder_name", ""))
        if not holder or pd.isna(row.get("s_holder_name")):
            continue

        hcat = int(row.get("s_holder_holdercategory", 0) or 0)
        hid = (
            f"p_{hashlib.sha256(holder.encode()).hexdigest()[:12]}"
            if hcat == 1
            else f"c_{hashlib.sha256(holder.encode()).hexdigest()[:12]}"
        )
        etype = "Person" if hcat == 1 else "Company"
        # Fix known misclassifications
        for kw in ["国资委", "财政局", "人民政府", "国有资产"]:
            if kw in holder:
                etype = "Government"
                break

        if hid not in entities:
            entities[hid] = {
                "entity_id": hid,
                "canonical_name": holder,
                "display_name": holder,
                "entity_type": etype,
                "wind_code": "",
                "aliases": [],
                "match_confidence": 0.9,
                "source_id": hid,
            }

        pct = float(row.get("s_holder_pct", 0) or 0)
        rels.append(
            {
                "source_entity_id": hid,
                "target_entity_id": eid,
                "relation_type": "OWNS",
                "ownership_pct": pct,
                "quantity": float(row.get("s_holder_quantity", 0) or 0),
                "report_period": str(
                    row.get("report_period", row.get("s_holder_enddate", ""))
                ),
                "ann_dt": str(row.get("ann_dt", "")),
                "source_record_id": f"{hid}_{eid}_{idx}",
                "is_latest": True,
            }
        )

    log.info("Built %d entities, %d relationships", len(entities), len(rels))

    # Import entities in batches
    ent_list = list(entities.values())
    for i in range(0, len(ent_list), BATCH):
        batch = ent_list[i : i + BATCH]
        await g.import_entities_batch(batch, graph_version=GRAPH_VER)
        log.info("Entities: %d/%d", min(i + BATCH, len(ent_list)), len(ent_list))

    # Import relationships in batches
    for i in range(0, len(rels), BATCH):
        batch = rels[i : i + BATCH]
        await g.import_relationships_batch(batch, graph_version=GRAPH_VER)
        log.info("Relationships: %d/%d", min(i + BATCH, len(rels)), len(rels))

    log.info(
        "Done! Entities: %d, Relationships: %d",
        await g.count_entities(GRAPH_VER),
        await g.count_relationships(GRAPH_VER),
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
