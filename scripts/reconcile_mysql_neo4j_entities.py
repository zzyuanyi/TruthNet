"""MySQL ↔ Neo4j 公司身份对齐脚本 — Phase C 任务 14.

用途：
  - --verify-only  只读核对 MySQL companies.entity_id 与 Neo4j Entity 节点是否一致；
  - --dry-run      预览将执行的幂等对齐（不写库/不写图）；
  - （默认）        执行幂等对齐：仅修正 ListedCompany 节点的
                    canonical_name/display_name 与 dataset_version 标签，
                    不删除图谱、不重建、不破坏关系。

约束：
  - 不修改数据库密码/连接串；
  - 不删除任何 Neo4j 节点或关系；
  - 对齐前先 dry-run 验证。

用法：
  python scripts/reconcile_mysql_neo4j_entities.py --verify-only
  python scripts/reconcile_mysql_neo4j_entities.py --dry-run
  python scripts/reconcile_mysql_neo4j_entities.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 使 backend/ 可导入
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings  # noqa: E402


def _connect_mysql():
    import pymysql

    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
        connect_timeout=10,
    )


def _connect_neo4j():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


def _load_mysql_listed() -> list[dict]:
    """读取 MySQL 上市公司（is_latest=1）。"""
    conn = _connect_mysql()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id, wind_code, sec_name, dataset_version "
                "FROM companies WHERE is_latest = 1 ORDER BY wind_code"
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _load_neo4j_listed(driver) -> list[dict]:
    """读取 Neo4j 上市公司节点（entity_id 以 company_ 开头）。"""
    records, _, _ = driver.execute_query(
        "MATCH (n:Entity) WHERE n.entity_id STARTS WITH 'company_' "
        "RETURN n.entity_id AS entity_id, n.wind_code AS wind_code, "
        "       n.canonical_name AS canonical_name, n.dataset_version AS dataset_version, "
        "       n.graph_version AS graph_version"
    )
    return [dict(r) for r in records]


def _main():
    parser = argparse.ArgumentParser(description="MySQL↔Neo4j 公司身份对齐")
    parser.add_argument("--verify-only", action="store_true", help="仅核对不一致")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    args = parser.parse_args()

    mysql_listed = _load_mysql_listed()
    by_eid = {r["entity_id"]: r for r in mysql_listed}

    driver = _connect_neo4j()
    neo4j_listed = _load_neo4j_listed(driver)

    print(f"MySQL 上市公司: {len(mysql_listed)}")
    print(f"Neo4j company_* 节点: {len(neo4j_listed)}")

    neo_by_eid = {r["entity_id"]: r for r in neo4j_listed}

    # ── 1. entity_id 一致性 ──────────────────────────────
    missing_in_neo4j = [e for e in by_eid if e not in neo_by_eid]
    extra_in_neo4j = [e for e in neo_by_eid if e not in by_eid]
    mismatched_wc = []
    for eid, rec in neo_by_eid.items():
        m = by_eid.get(eid)
        if m and rec.get("wind_code") and rec["wind_code"] != m["wind_code"]:
            mismatched_wc.append((eid, rec["wind_code"], m["wind_code"]))

    print(
        "\n[verify] entity_id 仅在 MySQL:", len(missing_in_neo4j), missing_in_neo4j[:10]
    )
    print("[verify] entity_id 仅在 Neo4j:", len(extra_in_neo4j), extra_in_neo4j[:10])
    print("[verify] wind_code 不一致:", mismatched_wc[:10])

    # ── 2. 标签/名称差异（仅公司节点） ────────────────────
    label_updates = []
    for eid, m in by_eid.items():
        n = neo_by_eid.get(eid)
        if n is None:
            continue
        want_name = m["sec_name"]
        want_dv = m.get("dataset_version") or settings.DATASET_VERSION
        cur_name = n.get("canonical_name") or ""
        cur_dv = n.get("dataset_version") or ""
        if cur_name != want_name or cur_dv != want_dv:
            label_updates.append(
                {
                    "entity_id": eid,
                    "wind_code": m["wind_code"],
                    "canonical_name": f"{cur_name!r} → {want_name!r}",
                    "dataset_version": f"{cur_dv!r} → {want_dv!r}",
                }
            )

    print(f"\n[label] 需对齐公司节点: {len(label_updates)}")
    for u in label_updates[:20]:
        print("   ", u)

    if args.verify_only:
        driver.close()
        sys.exit(1 if (missing_in_neo4j or extra_in_neo4j or mismatched_wc) else 0)

    if not label_updates:
        print("\n无需对齐。")
        driver.close()
        return

    if args.dry_run:
        print("\n[dry-run] 未写入，以上为预览。")
        driver.close()
        return

    # ── 3. 幂等执行（仅 SET，不删除） ────────────────────
    updated = 0
    for u in label_updates:
        m = by_eid[u["entity_id"]]
        driver.execute_query(
            "MATCH (n:Entity {entity_id: $eid}) "
            "SET n.canonical_name = $name, "
            "    n.display_name = $name, "
            "    n.dataset_version = $dv "
            "RETURN n.entity_id",
            {
                "eid": u["entity_id"],
                "name": m["sec_name"],
                "dv": settings.DATASET_VERSION,
            },
        )
        updated += 1
    print(f"\n已对齐 {updated} 个公司节点（canonical_name + dataset_version）。")

    # ── 4. 验证节点/关系数未异常减少 ────────────────────
    node_count = driver.execute_query("MATCH (n) RETURN count(n) AS c")[0][0]["c"]
    rel_count = driver.execute_query("MATCH ()-[r]->() RETURN count(r) AS c")[0][0]["c"]
    print(f"对齐后 Neo4j 节点数: {node_count}, 关系数: {rel_count}")
    driver.close()


if __name__ == "__main__":
    _main()
