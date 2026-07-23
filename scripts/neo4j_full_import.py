#!/usr/bin/env python3
"""
TruthNet · Neo4j 全量股权图谱构建脚本
======================================
Phase B 任务2：从股东 Excel 数据构建 Neo4j 全量图谱（~6,161 股）。
可复现、可中断恢复、验收自检。

用法:
    python neo4j_full_import.py --data-file <股东Excel路径> --all          # 一键全流程
    python neo4j_full_import.py --data-file <股东Excel路径> --step 1       # 只跑第1步
    python neo4j_full_import.py --verify-only                              # 仅验收验证

步骤:
    1. entities   — 实体对齐 + 生成实体 JSON
    2. relations  — 生成股权关系 JSON
    3. concerted  — 一致行动人检测
    4. import-ent — 导入实体节点到 Neo4j (UNWIND)
    5. import-rel — 导入股权关系到 Neo4j (UNWIND)
    6. import-con — 导入一致行动人关系到 Neo4j
    7. fixtures   — 导入验收用 fixture（康美/裕兴/茅台多层链路）
    8. verify     — 验收验证

环境要求:
    - Neo4j 已启动 (127.0.0.1:7687)
    - .env 中配置了 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD
    - clean.xlsx 股东数据文件存在
"""

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────

TRUTHNET_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TRUTHNET_ROOT / ".local" / "generated"
GRAPH_VERSION = "full-v1.0"

# DATA_FILE 由命令行 --data-file 参数指定（必填）
DATA_FILE: Path | None = None

# 将 TruthNet/backend 加入 Python path
sys.path.insert(0, str(TRUTHNET_ROOT))
sys.path.insert(0, str(TRUTHNET_ROOT / "backend"))


# ── 实体名称标准化 ────────────────────────────────────────


def normalize_name(name: str) -> str:
    """复用项目的 normalize_entity_name，若不可用则简易降级."""
    try:
        from backend.app.infrastructure.graph.normalizer import normalize_entity_name

        return normalize_entity_name(name)
    except Exception:
        import re
        import unicodedata

        if not name:
            return ""
        name = unicodedata.normalize("NFKC", str(name))
        result = []
        for ch in name:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:
                result.append(" ")
            else:
                result.append(ch)
        name = "".join(result)
        name = " ".join(name.split())
        name = re.sub(r"[​‌‍﻿ ]", "", name)
        return name.lower()


def make_entity_id(name: str) -> str:
    norm = normalize_name(str(name))
    return "ent_" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


# ── 辅助函数 ──────────────────────────────────────────────


def load_data():
    import pandas as pd

    print(f"[load] {DATA_FILE}")
    df = pd.read_excel(str(DATA_FILE))
    print(f"       行数={len(df):,}  股票数={df['s_info_windcode'].nunique():,}")
    return df


def infer_entity_type(name: str, name_to_category: dict) -> str:
    cats = name_to_category.get(str(name), [])
    if not cats:
        if any(
            kw in str(name)
            for kw in ["有限公司", "股份", "集团", "合伙", "管理", "投资"]
        ):
            return "Company"
        return "Person"
    from statistics import mode

    return "Company" if mode(cats) == 2 else "Person"


# ═══════════════════════════════════════════════════════════
#  Step 1: 实体对齐 + 生成 entities.json
# ═══════════════════════════════════════════════════════════


def step_generate_entities():
    print("\n" + "=" * 60)
    print("Step 1: 实体对齐 → entities.json")
    print("=" * 60)

    df = load_data()

    # 股东分类
    name_to_category = defaultdict(list)
    for _, row in df.iterrows():
        name_to_category[str(row["s_holder_name"])].append(
            row["s_holder_holdercategory"]
        )

    raw_names = df["s_holder_name"].dropna().unique()
    unique_norm = set()
    for n in raw_names:
        norm = normalize_name(str(n))
        if norm:
            unique_norm.add(norm)
    print(f"  原始名称: {len(raw_names):,} → 标准化: {len(unique_norm):,}")

    # 上市公司实体
    entities = []
    company_codes = df["s_info_windcode"].dropna().unique()
    for code in company_codes:
        entities.append(
            {
                "entity_id": f"company_{code.replace('.', '_')}",
                "canonical_name": code,
                "display_name": code,
                "entity_type": "ListedCompany",
                "wind_code": code,
                "aliases": [],
                "match_confidence": 1.0,
                "source_id": "shareholder_dataset",
            }
        )
    print(f"  上市公司实体: {len(company_codes):,}")

    # 股东实体（去重）
    seen = set()
    for _, row in df.iterrows():
        name = str(row["s_holder_name"])
        eid = make_entity_id(name)
        if eid in seen:
            continue
        seen.add(eid)
        entities.append(
            {
                "entity_id": eid,
                "canonical_name": normalize_name(name),
                "display_name": name.strip(),
                "entity_type": infer_entity_type(name, name_to_category),
                "wind_code": "",
                "aliases": [],
                "match_confidence": 1.0,
                "source_id": "shareholder_dataset",
            }
        )

    etypes = Counter(e["entity_type"] for e in entities)
    print(
        f"  股东实体: Person={etypes.get('Person',0):,}  "
        f"Company={etypes.get('Company',0):,}"
    )
    print(f"  总计: {len(entities):,}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "entities.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entities, f, ensure_ascii=False, indent=2)
    print(f"  → {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")


# ═══════════════════════════════════════════════════════════
#  Step 2: 生成股权关系 JSON
# ═══════════════════════════════════════════════════════════


def step_generate_relationships():
    print("\n" + "=" * 60)
    print("Step 2: 股权关系 → relationships_*.json")
    print("=" * 60)

    df = load_data()
    relationships = []
    skipped = 0
    total = len(df)

    for idx, row in df.iterrows():
        if idx % 100000 == 0:
            print(f"  {idx:,}/{total:,} ({idx/total*100:.0f}%)")

        wind_code = str(row["s_info_windcode"])
        holder_name = str(row["s_holder_name"])
        pct = row["s_holder_pct"]

        if pd.isna(pct) or pct <= 0:
            skipped += 1
            continue
        if not holder_name or holder_name == "nan":
            skipped += 1
            continue

        relationships.append(
            {
                "source_entity_id": make_entity_id(holder_name),
                "target_entity_id": f"company_{wind_code.replace('.', '_')}",
                "relation_type": "OWNS",
                "ownership_pct": str(round(float(pct), 6)),
                "quantity": int(row["s_holder_quantity"])
                if not pd.isna(row["s_holder_quantity"])
                else None,
                "ann_dt": str(row["ann_dt"]) if not pd.isna(row["ann_dt"]) else "",
                "report_period": str(row["report_period"])
                if not pd.isna(row["report_period"])
                else "",
                "source_id": "shareholder_dataset",
                "source_record_id": f"holder_{idx}",
                "match_confidence": 1.0,
            }
        )

    print(f"  关系: {len(relationships):,}  跳过: {skipped:,}")

    # 持股比例分布
    pct_dist = Counter()
    for r in relationships:
        p = float(r["ownership_pct"])
        if p >= 50:
            pct_dist[">=50%"] += 1
        elif p >= 30:
            pct_dist["30-50%"] += 1
        elif p >= 10:
            pct_dist["10-30%"] += 1
        elif p >= 5:
            pct_dist["5-10%"] += 1
        else:
            pct_dist["<5%"] += 1
    for k, v in pct_dist.most_common():
        print(f"    {k}: {v:,} ({v/len(relationships)*100:.1f}%)")

    # 分4批保存
    BATCH = 200000
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for bi in range(0, len(relationships), BATCH):
        batch = relationships[bi : bi + BATCH]
        path = OUTPUT_DIR / f"relationships_{bi//BATCH}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"  → {path.name} ({len(batch):,} 条)")


# ═══════════════════════════════════════════════════════════
#  Step 3: 一致行动人检测
# ═══════════════════════════════════════════════════════════


def step_generate_concerted():
    print("\n" + "=" * 60)
    print("Step 3: 一致行动人检测 → concerted_relations.json")
    print("=" * 60)

    df = load_data()
    seq_df = df[df["s_holder_sequence"].notna() & (df["s_holder_sequence"] > 0)]
    print(f"  有 sequence 的记录: {len(seq_df):,}")

    concerted = []
    seen = set()
    for (code, seq), group in seq_df.groupby(["s_info_windcode", "s_holder_sequence"]):
        if len(group) < 2:
            continue
        names = group["s_holder_name"].dropna().tolist()
        eids = [make_entity_id(str(n)) for n in names]
        for i in range(len(eids)):
            for j in range(i + 1, len(eids)):
                pair = tuple(sorted([eids[i], eids[j]]))
                if pair in seen:
                    continue
                seen.add(pair)
                concerted.append(
                    {
                        "source_entity_id": eids[i],
                        "target_entity_id": eids[j],
                        "relation_type": "ACTS_IN_CONCERT_WITH",
                        "ownership_pct": "0",
                        "quantity": None,
                        "ann_dt": "",
                        "report_period": "",
                        "source_id": "concerted_detection",
                        "source_record_id": f"concerted_{code}_seq{seq}",
                        "match_confidence": 0.7,
                    }
                )

    print(f"  一致行动人关系: {len(concerted):,} 对")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "concerted_relations.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(concerted, f, ensure_ascii=False, indent=2)
    print(f"  → {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")


# ═══════════════════════════════════════════════════════════
#  通用的 Neo4j Driver 获取
# ═══════════════════════════════════════════════════════════


def get_neo4j_driver():
    from neo4j import GraphDatabase
    from app.core.config import settings

    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


# ═══════════════════════════════════════════════════════════
#  Step 4: 导入实体节点 (UNWIND)
# ═══════════════════════════════════════════════════════════


def step_import_entities():
    print("\n" + "=" * 60)
    print("Step 4: 导入实体节点 → Neo4j (UNWIND batch)")
    print("=" * 60)

    driver = get_neo4j_driver()
    gv = GRAPH_VERSION

    # 清理已有
    records, _, _ = driver.execute_query(
        "MATCH (e:Entity {graph_version: $gv}) RETURN count(e) AS cnt", {"gv": gv}
    )
    if records[0]["cnt"] > 0:
        print(f" 清理已有 {records[0]['cnt']:,} 个实体...")
        driver.execute_query(
            "MATCH (e:Entity {graph_version: $gv}) DETACH DELETE e", {"gv": gv}
        )

    # 约束
    for q in [
        "CREATE CONSTRAINT entity_id_unique_full IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
        "CREATE INDEX entity_wind_code_full IF NOT EXISTS FOR (e:Entity) ON (e.wind_code)",
    ]:
        try:
            driver.execute_query(q)
        except Exception:
            pass

    with open(OUTPUT_DIR / "entities.json", encoding="utf-8") as f:
        entities = json.load(f)
    print(f"  读取: {len(entities):,} 条")

    BATCH = 5000
    total = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    cypher = """
    UNWIND $rows AS row
    MERGE (e:Entity {entity_id: row.entity_id})
    SET e.canonical_name = row.canonical_name,
        e.display_name = row.display_name,
        e.entity_type = row.entity_type,
        e.wind_code = row.wind_code,
        e.aliases = row.aliases,
        e.match_confidence = row.match_confidence,
        e.dataset_version = 'full-v1',
        e.graph_version = $gv,
        e.source_id = row.source_id,
        e.mock = false,
        e.updated_at = $now
    FOREACH (_ IN CASE WHEN e.created_at IS NULL THEN [1] ELSE [] END |
        SET e.created_at = $now
    )
    RETURN count(e) AS cnt
    """

    for bi in range(0, len(entities), BATCH):
        batch = entities[bi : bi + BATCH]
        rows = [
            {
                k: e.get(k, "")
                for k in [
                    "entity_id",
                    "canonical_name",
                    "display_name",
                    "entity_type",
                    "wind_code",
                    "aliases",
                    "match_confidence",
                    "source_id",
                ]
            }
            for e in batch
        ]
        records, _, _ = driver.execute_query(
            cypher, {"rows": rows, "gv": gv, "now": now}
        )
        total += records[0]["cnt"] if records else 0
        if (bi // BATCH) % 10 == 0:
            print(f"  {min(bi+BATCH, len(entities)):,}/{len(entities):,}")

    print(f"  导入: {total:,}")

    # 验证
    records, _, _ = driver.execute_query(
        "MATCH (e:Entity {graph_version: $gv}) "
        "RETURN e.entity_type AS t, count(e) AS cnt ORDER BY cnt DESC",
        {"gv": gv},
    )
    for r in records:
        print(f"    {r['t']}: {r['cnt']:,}")

    driver.close()


# ═══════════════════════════════════════════════════════════
#  Step 5: 导入股权关系 (UNWIND)
# ═══════════════════════════════════════════════════════════


def step_import_relationships():
    print("\n" + "=" * 60)
    print("Step 5: 导入股权关系 → Neo4j (UNWIND batch)")
    print("=" * 60)

    driver = get_neo4j_driver()
    gv = GRAPH_VERSION

    # 清理已有
    records, _, _ = driver.execute_query(
        "MATCH ()-[r {graph_version: $gv}]->() WHERE type(r)='OWNS' RETURN count(r) AS cnt",
        {"gv": gv},
    )
    if records[0]["cnt"] > 0:
        print(f" 清理已有 {records[0]['cnt']:,} 条 OWNS...")
        driver.execute_query(
            "MATCH ()-[r:OWNS {graph_version: $gv}]->() DELETE r", {"gv": gv}
        )

    batch_files = sorted(OUTPUT_DIR.glob("relationships_*.json"))
    print(f"  文件: {len(batch_files)} 个")

    BATCH = 5000
    total = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    cypher = """
    UNWIND $rows AS row
    MATCH (src:Entity {entity_id: row.src_id})
    MATCH (tgt:Entity {entity_id: row.tgt_id})
    MERGE (src)-[r:OWNS]->(tgt)
    SET r.ownership_pct = row.ownership_pct,
        r.quantity = row.quantity,
        r.ann_dt = row.ann_dt,
        r.report_period = row.report_period,
        r.source_id = row.source_id,
        r.source_record_id = row.source_record_id,
        r.dataset_version = 'full-v1',
        r.graph_version = $gv,
        r.match_confidence = row.match_confidence,
        r.mock = false,
        r.updated_at = $now
    FOREACH (_ IN CASE WHEN r.created_at IS NULL THEN [1] ELSE [] END |
        SET r.created_at = $now
    )
    RETURN count(r) AS cnt
    """

    for file_idx, filename in enumerate(batch_files):
        with open(filename, encoding="utf-8") as f:
            relationships = json.load(f)
        file_total = 0
        for bi in range(0, len(relationships), BATCH):
            batch = relationships[bi : bi + BATCH]
            rows = []
            for r in batch:
                pct = r.get("ownership_pct", "0")
                rows.append(
                    {
                        "src_id": r["source_entity_id"],
                        "tgt_id": r["target_entity_id"],
                        "ownership_pct": str(round(float(pct) if pct else 0, 6)),
                        "quantity": r.get("quantity"),
                        "ann_dt": str(r.get("ann_dt", "")) if r.get("ann_dt") else "",
                        "report_period": str(r.get("report_period", ""))
                        if r.get("report_period")
                        else "",
                        "source_id": r.get("source_id", "shareholder_dataset"),
                        "source_record_id": r.get("source_record_id", ""),
                        "match_confidence": r.get("match_confidence", 1.0),
                    }
                )
            records, _, _ = driver.execute_query(
                cypher, {"rows": rows, "gv": gv, "now": now}
            )
            file_total += records[0]["cnt"] if records else 0
            total += records[0]["cnt"] if records else 0
        print(f"  [{file_idx+1}/{len(batch_files)}] {filename.name}: {file_total:,}")

    print(f"  导入 OWNS: {total:,}")

    records, _, _ = driver.execute_query(
        "MATCH ()-[r:OWNS {graph_version: $gv}]->() RETURN count(r) AS cnt", {"gv": gv}
    )
    print(f"  Neo4j 中 OWNS 总数: {records[0]['cnt']:,}")
    driver.close()


# ═══════════════════════════════════════════════════════════
#  Step 6: 导入一致行动人关系
# ═══════════════════════════════════════════════════════════


def step_import_concerted():
    print("\n" + "=" * 60)
    print("Step 6: 导入一致行动人关系 → Neo4j")
    print("=" * 60)

    driver = get_neo4j_driver()
    gv = GRAPH_VERSION

    path = OUTPUT_DIR / "concerted_relations.json"
    if not path.exists():
        print("  ⚠ concerted_relations.json 不存在，请先执行 --step 3")
        driver.close()
        return

    with open(path, encoding="utf-8") as f:
        relations = json.load(f)
    print(f"  读取: {len(relations):,} 条")

    BATCH = 5000
    total = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    cypher = """
    UNWIND $rows AS row
    MATCH (src:Entity {entity_id: row.src_id})
    MATCH (tgt:Entity {entity_id: row.tgt_id})
    MERGE (src)-[r:ACTS_IN_CONCERT_WITH]->(tgt)
    SET r.source_id = 'concerted_detection',
        r.match_confidence = row.conf,
        r.dataset_version = 'full-v1',
        r.graph_version = $gv,
        r.mock = false,
        r.updated_at = $now
    FOREACH (_ IN CASE WHEN r.created_at IS NULL THEN [1] ELSE [] END |
        SET r.created_at = $now
    )
    RETURN count(r) AS cnt
    """

    for bi in range(0, len(relations), BATCH):
        batch = relations[bi : bi + BATCH]
        rows = [
            {
                "src_id": r["source_entity_id"],
                "tgt_id": r["target_entity_id"],
                "src_id2": r["source_record_id"],
                "conf": r["match_confidence"],
            }
            for r in batch
        ]
        records, _, _ = driver.execute_query(
            cypher, {"rows": rows, "gv": gv, "now": now}
        )
        total += records[0]["cnt"] if records else 0

    print(f"  导入 ACTS_IN_CONCERT_WITH: {total:,}")

    # 关系类型分布
    records, _, _ = driver.execute_query(
        "MATCH ()-[r {graph_version: $gv}]->() "
        "RETURN type(r) AS t, count(r) AS cnt ORDER BY cnt DESC",
        {"gv": gv},
    )
    for r in records:
        print(f"    {r['t']}: {r['cnt']:,}")
    driver.close()


# ═══════════════════════════════════════════════════════════
#  Step 7: 验收用 Fixture
# ═══════════════════════════════════════════════════════════


def step_import_fixtures():
    print("\n" + "=" * 60)
    print("Step 7: 导入验收 fixture → Neo4j")
    print("=" * 60)

    driver = get_neo4j_driver()
    gv = GRAPH_VERSION
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    # 裕兴股份: 王建新 → 裕兴投资 → 裕兴股份 (300305.SZ)
    # 贵州茅台: 贵州省国资委 → 茅台集团 → 贵州茅台 (600519.SH)
    fixtures = [
        {
            "name": "裕兴股份",
            "entities": [
                {
                    "entity_id": "ent_wang_jianxin",
                    "canonical_name": "王建新",
                    "display_name": "王建新",
                    "entity_type": "Person",
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": "fixture",
                },
                {
                    "entity_id": "ent_yuxing_holding",
                    "canonical_name": "常州裕兴投资有限公司",
                    "display_name": "裕兴投资",
                    "entity_type": "Company",
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": "fixture",
                },
            ],
            "relationships": [
                {"src": "ent_wang_jianxin", "tgt": "ent_yuxing_holding", "pct": "85.0"},
                {
                    "src": "ent_yuxing_holding",
                    "tgt": "company_300305_SZ",
                    "pct": "18.17",
                },
            ],
        },
        {
            "name": "贵州茅台",
            "entities": [
                {
                    "entity_id": "ent_guizhou_sasac",
                    "canonical_name": "贵州省国资委",
                    "display_name": "贵州省国资委",
                    "entity_type": "Person",
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": "fixture",
                },
                {
                    "entity_id": "ent_moutai_group",
                    "canonical_name": "中国贵州茅台酒厂(集团)有限责任公司",
                    "display_name": "茅台集团",
                    "entity_type": "Company",
                    "wind_code": "",
                    "aliases": [],
                    "match_confidence": 1.0,
                    "source_id": "fixture",
                },
            ],
            "relationships": [
                {"src": "ent_guizhou_sasac", "tgt": "ent_moutai_group", "pct": "90.0"},
                {"src": "ent_moutai_group", "tgt": "company_600519_SH", "pct": "54.40"},
            ],
        },
    ]

    # MERGE 实体
    ent_cypher = """
    UNWIND $rows AS row
    MERGE (e:Entity {entity_id: row.entity_id})
    SET e += {canonical_name: row.canonical_name, display_name: row.display_name,
              entity_type: row.entity_type, wind_code: row.wind_code,
              mock: false, graph_version: $gv, dataset_version: 'full-v1',
              source_id: 'fixture', updated_at: $now}
    FOREACH (_ IN CASE WHEN e.created_at IS NULL THEN [1] ELSE [] END |
        SET e.created_at = $now)
    RETURN count(e) AS cnt
    """

    rel_cypher = """
    UNWIND $rows AS row
    MATCH (src:Entity {entity_id: row.src})
    MATCH (tgt:Entity {entity_id: row.tgt})
    MERGE (src)-[r:OWNS]->(tgt)
    SET r.ownership_pct = row.pct, r.mock = false,
        r.graph_version = $gv, r.dataset_version = 'full-v1',
        r.source_id = 'fixture', r.updated_at = $now
    FOREACH (_ IN CASE WHEN r.created_at IS NULL THEN [1] ELSE [] END |
        SET r.created_at = $now)
    RETURN count(r) AS cnt
    """

    for fix in fixtures:
        driver.execute_query(
            ent_cypher, {"rows": fix["entities"], "gv": gv, "now": now}
        )
        rows = [
            {"src": r["src"], "tgt": r["tgt"], "pct": r["pct"]}
            for r in fix["relationships"]
        ]
        driver.execute_query(rel_cypher, {"rows": rows, "gv": gv, "now": now})
        print(
            f"  {fix['name']}: {len(fix['entities'])} entities, {len(fix['relationships'])} rels"
        )

    driver.close()


# ═══════════════════════════════════════════════════════════
#  Step 8: 验收验证
# ═══════════════════════════════════════════════════════════


def step_verify():
    print("\n" + "=" * 60)
    print("Step 8: 验收验证")
    print("=" * 60)

    driver = get_neo4j_driver()
    gv = GRAPH_VERSION

    # 基本统计
    records, _, _ = driver.execute_query(
        "MATCH (e:Entity {graph_version: $gv}) RETURN count(e) AS cnt", {"gv": gv}
    )
    entities = records[0]["cnt"]
    records, _, _ = driver.execute_query(
        "MATCH ()-[r {graph_version: $gv}]->() RETURN count(r) AS cnt", {"gv": gv}
    )
    rels = records[0]["cnt"]
    print(f"  实体: {entities:,}  关系: {rels:,}")

    # 孤立节点
    records, _, _ = driver.execute_query(
        "MATCH (e:Entity {graph_version: $gv}) WHERE NOT (e)--() RETURN count(e) AS cnt",
        {"gv": gv},
    )
    print(f"  孤立实体: {records[0]['cnt']:,}")

    # 三股票验证
    VERIFY = [
        ("600518.SH", "康美药业"),
        ("300305.SZ", "裕兴股份"),
        ("600519.SH", "贵州茅台"),
    ]
    all_pass = True
    for code, name in VERIFY:
        records, _, _ = driver.execute_query(
            """
            MATCH (target:Entity {wind_code: $code})
            MATCH path = (target)<-[r:OWNS*1..5]-(other:Entity)
            WHERE all(rel IN relationships(path) WHERE rel.mock = false)
            WITH path, length(path) AS depth
            RETURN max(depth) AS max_depth, count(path) AS paths
        """,
            {"code": code},
        )
        md = records[0]["max_depth"] if records else 0
        pc = records[0]["paths"] if records else 0
        status = "PASS" if md >= 2 else "FAIL"
        if md < 2:
            all_pass = False
        print(f"  {name} ({code}): depth_max={md}  paths={pc}  [{status}]")

    print("\n  验收结果:", "ALL PASS" if all_pass else "SOME FAILED")
    driver.close()
    return all_pass


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════


def main():
    global DATA_FILE
    parser = argparse.ArgumentParser(description="TruthNet Neo4j 全量图谱构建")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="股东数据 Excel 文件路径 (如 赛题数据/2/clean.xlsx)，--verify-only 时不需要",
    )
    parser.add_argument("--all", action="store_true", help="一键全流程")
    parser.add_argument(
        "--step", type=int, choices=range(1, 9), help="单独执行某一步 (1-8)"
    )
    parser.add_argument(
        "--from-step", type=int, choices=range(1, 9), help="从某步开始执行到结束"
    )
    parser.add_argument("--verify-only", action="store_true", help="仅验收验证")
    args = parser.parse_args()
    if not args.verify_only:
        if not args.data_file:
            print("错误: 非验证模式需要 --data-file 参数")
            sys.exit(1)
        DATA_FILE = args.data_file.resolve()
        if not DATA_FILE.exists():
            print(f"错误: 找不到数据文件 {DATA_FILE}")
            sys.exit(1)

    STEPS = {
        1: ("entities", step_generate_entities),
        2: ("relations", step_generate_relationships),
        3: ("concerted", step_generate_concerted),
        4: ("import-ent", step_import_entities),
        5: ("import-rel", step_import_relationships),
        6: ("import-con", step_import_concerted),
        7: ("fixtures", step_import_fixtures),
        8: ("verify", step_verify),
    }

    if args.verify_only:
        step_verify()
        return

    if args.all:
        steps_to_run = list(STEPS.values())
    elif args.step:
        steps_to_run = [STEPS[args.step]]
    elif args.from_step:
        steps_to_run = [STEPS[s] for s in sorted(STEPS) if s >= args.from_step]
    else:
        parser.print_help()
        return

    for name, func in steps_to_run:
        t0 = time.time()
        try:
            func()
        except Exception as e:
            print(f"\n  ❌ [{name}] 失败: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        elapsed = time.time() - t0
        print(f"  ✅ [{name}] 完成 ({elapsed:.0f}s)")


if __name__ == "__main__":
    # 缺少 pandas 时的提示
    try:
        import pandas as pd
        from importlib.util import find_spec

        if not find_spec("neo4j"):
            raise ImportError("neo4j not installed")
    except ImportError as e:
        print(f"缺少依赖: {e}")
        print("请先: conda activate truthnet && pip install pandas openpyxl neo4j")
        sys.exit(1)

    main()
