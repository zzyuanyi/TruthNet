"""四跳持股路径只读审计 — 严格 >3（4..10 跳）逐条明细（v3.1）.

对真库 equity-2026Q2 的 10 条可验证四跳持股路径做逐条核验：
  - 口径复刻：与 count_multi_hop_paths 同源（版本/快照/节点互异/去重）；
  - 断言 4..10 == 10、5..10 == 0、truncated == false；
  - 节点序列分组：同一节点链的平行边作为边变体列出，不重复计数；
  - 确定性排序 + canary 路径存在性（中央汇金→南京高科→南京银行→
    江苏国信→江苏新能）；
  - 边证据三态回查（evidence_refs）：
      materialized_ok / not_materialized（不算失败） / identity_mismatch（失败）；
  - 输出 Markdown 审计报告（含签核状态列，人工签核后更新）。

用法：
    python scripts/audit_four_hop_paths.py [--graph-version equity-2026Q2]
                                          [--output audit_four_hop_paths.md]
    # --output 缺省时报告打印到 stdout；只读，不写任何库。
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402
import pymysql  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

from app.application.services.equity_shareholder_service import (  # noqa: E402
    make_equity_edge_evidence_id,
)
from app.core.config import settings  # noqa: E402

# canary 路径（2026-08-11 真库实测）：10 条四跳路径的共同中间段
# 600064(南京高科)→601009(南京银行)→002608(江苏国信)→603693(江苏新能)。
# 注：8.09 记录的起点"中央汇金"为近似表述——真库 canonical_name 无
# "中央汇金"节点，实际起点为汇金系基金/自然人（见审计报告说明）。
CANARY_CODES = ["600064.SH", "601009.SH", "002608.SZ", "603693.SH"]

_FAILURES: list[str] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'✅' if ok else '❌'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(name)


def _mysql_conn() -> pymysql.Connection:
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", ""),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "truthnet"),
        charset="utf8mb4",
    )


def _check_evidence(conn, evidence_id: str, identity: dict) -> str:
    """evidence_refs 三态回查。

    返回 "materialized_ok" / "not_materialized" / "identity_mismatch"。
    canonical 身份元组：source_type/source_record_id/field_path/period/
    dataset_version/company_code。
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_type, source_record_id, field_path, period, "
            "dataset_version, company_code FROM evidence_refs WHERE evidence_id=%s",
            (evidence_id,),
        )
        row = cur.fetchone()
        if row is None:
            # 同身份元组是否对应其他 ID（身份冲突）
            cur.execute(
                "SELECT evidence_id FROM evidence_refs "
                "WHERE source_type=%s AND source_record_id=%s AND field_path=%s "
                "AND period=%s AND dataset_version=%s AND company_code=%s",
                (
                    identity["source_type"],
                    identity["source_record_id"],
                    identity["field_path"],
                    identity["period"],
                    identity["dataset_version"],
                    identity["company_code"],
                ),
            )
            other = cur.fetchone()
            if other is not None:
                return f"identity_mismatch(同身份→{other[0]})"
            return "not_materialized"
        expected = (
            identity["source_type"],
            identity["source_record_id"],
            identity["field_path"],
            identity["period"],
            identity["dataset_version"],
            identity["company_code"],
        )
        return (
            "materialized_ok"
            if tuple(row) == expected
            else f"identity_mismatch(字段差异{row})"
        )


async def audit(gv: str, output: str = "") -> int:
    # v3.5：AsyncGraphDatabase——execute_query 可直接 await，去掉不可终止
    # 的 to_thread；外层仍保留 asyncio.wait_for 兜底。
    from neo4j import AsyncGraphDatabase, Query, RoutingControl

    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    try:
        # ── 1. 口径对照（复用生产计数）──
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        adapter = Neo4jEquityGraph()
        d4 = await adapter.count_multi_hop_paths(gv, min_depth=4, max_depth=10)
        d5 = await adapter.count_multi_hop_paths(gv, min_depth=5, max_depth=10)
        print(
            f"count(4..10)={d4['count']} truncated={d4['truncated']}; "
            f"count(5..10)={d5['count']} truncated={d5['truncated']}"
        )
        _check("4..10 == 10", d4["count"] == 10, str(d4))
        _check("4..10 未截断", not d4["truncated"])
        _check("5..10 == 0", d5["count"] == 0, str(d5))

        # ── 2. 明细查询（复刻 count 口径：版本/快照/节点互异/目标端上市）──
        cypher = """
        MATCH p = (a:Entity)-[:OWNS*4..10]->(b:Entity)
        WHERE b.wind_code <> ''
          AND a.entity_id <> b.entity_id
          AND all(r IN relationships(p) WHERE r.graph_version = $gv AND r.is_latest = true)
          AND all(n IN nodes(p) WHERE size([m IN nodes(p) WHERE m = n]) = 1)
        RETURN [n IN nodes(p) | n.entity_id] AS node_ids,
               [n IN nodes(p) | n.canonical_name] AS node_names,
               [n IN nodes(p) | n.wind_code] AS node_wcodes,
               [r IN relationships(p) | {
                   relationship_id: r.relationship_id,
                   src: startNode(r).entity_id,
                   dst: endNode(r).entity_id,
                   ownership_pct: r.ownership_pct,
                   report_period: r.report_period,
                   source_record_id: r.source_record_id,
                   ann_dt: r.ann_dt
               }] AS rels
        """
        # v3.5：双层超时——neo4j.Query 原生 timeout=120s（服务器侧终止）
        # + Python 层 asyncio.wait_for(..., 130s) 兜底；直接 await（AsyncDriver）。
        query = Query(cypher, timeout=120)
        records, _, _ = await asyncio.wait_for(
            driver.execute_query(
                query,
                gv=gv,
                routing_=RoutingControl.READ,
            ),
            130,
        )
        # 节点序列分组（去重口径：唯一节点链）；平行边变体按
        # **完整 relationship ID 元组**确定性排序（v3.5：整条边序列排序，
        # 同链多组边输出顺序稳定可复现）
        groups: dict[tuple, dict] = {}
        for rec in records:
            node_ids = tuple(rec["node_ids"])
            if node_ids not in groups:
                groups[node_ids] = {
                    "names": rec["node_names"],
                    "wcodes": rec["node_wcodes"],
                    "rel_variants": [],
                }
            rels = sorted(rec["rels"], key=lambda r: (r.get("relationship_id") or ""))
            groups[node_ids]["rel_variants"].append(rels)
        for g in groups.values():
            g["rel_variants"].sort(
                key=lambda rels: tuple(r.get("relationship_id") or "" for r in rels)
            )
        _check(
            "明细组数 == count(4..10) == 10", len(groups) == 10, f"groups={len(groups)}"
        )

        # ── 3. canary 路径存在（确定性断言：按 wind_code 连续子序列）──
        has_canary = any(
            CANARY_CODES == wcodes[i : i + len(CANARY_CODES)]
            for wcodes in (g["wcodes"] for g in groups.values())
            for i in range(len(wcodes) - len(CANARY_CODES) + 1)
        )
        _check(f"canary 中间段存在（{'→'.join(CANARY_CODES)}）", has_canary)

        # ── 4. 证据三态回查（MySQL evidence_refs，只读）──
        conn = _mysql_conn()
        try:
            conn_rows: list[
                tuple
            ] = []  # (idx, hop, src, dst, pct, period, rel_id, src_rec, ann_dt, eid, status, variant)
            for idx, (node_ids, g) in enumerate(
                sorted(
                    groups.items(),
                    key=lambda kv: (
                        kv[1]["wcodes"][-1] or "",
                        kv[1]["names"][0] or "",
                        kv[0],
                    ),
                ),
                start=1,
            ):
                wcodes = g["wcodes"]
                target_code = wcodes[-1] or ""
                # 平行边变体：同节点链多组边（第一组为主，其余标注）
                for vi, rels in enumerate(g["rel_variants"]):
                    variant_tag = "" if vi == 0 else f" [边变体{vi + 1}]"
                    for hi, rel in enumerate(rels):
                        eid = make_equity_edge_evidence_id(
                            edge=rel, company_code=target_code, graph_version=gv
                        )
                        if not eid:
                            # 边无稳定来源键：make_equity_edge_evidence_id 返回空，
                            # 视为失败（审计要求每条边可生成 canonical 证据）
                            conn_rows.append(
                                (
                                    idx,
                                    hi + 1,
                                    rel.get("src"),
                                    rel.get("dst"),
                                    rel.get("ownership_pct"),
                                    rel.get("report_period"),
                                    rel.get("relationship_id"),
                                    rel.get("source_record_id"),
                                    rel.get("ann_dt"),
                                    "",
                                    "no_stable_key",
                                    variant_tag,
                                )
                            )
                            continue
                        identity = {
                            "source_type": "neo4j_relationship",
                            "source_record_id": rel.get("relationship_id") or "",
                            "field_path": "ownership_pct",
                            "period": rel.get("report_period") or "",
                            "dataset_version": gv,
                            "company_code": target_code,
                        }
                        status = _check_evidence(conn, eid, identity)
                        conn_rows.append(
                            (
                                idx,
                                hi + 1,
                                rel.get("src"),
                                rel.get("dst"),
                                rel.get("ownership_pct"),
                                rel.get("report_period"),
                                rel.get("relationship_id"),
                                rel.get("source_record_id"),
                                rel.get("ann_dt"),
                                eid,
                                status,
                                variant_tag,
                            )
                        )
        finally:
            conn.close()
        bad = [
            r
            for r in conn_rows
            if r[10] != "not_materialized" and r[10] != "materialized_ok"
        ]
        for r in bad:
            _check(f"证据身份一致（{r[0]} 路径 {r[10]}）", False, str(r[9]))
        _check("证据身份冲突为 0", len(bad) == 0, f"bad={len(bad)}")

        # ── 5. Markdown 报告 ──
        # v3.5：报告含完整"名称（代码）→名称（代码）"节点链；内容转义
        # （| 与换行不破坏表格结构）。
        def _md_escape(v) -> str:
            return str(v or "").replace("|", "\\|").replace("\n", " ")

        chain_by_idx: dict[int, str] = {}
        for idx, (node_ids, g) in enumerate(
            sorted(
                groups.items(),
                key=lambda kv: (
                    kv[1]["wcodes"][-1] or "",
                    kv[1]["names"][0] or "",
                    kv[0],
                ),
            ),
            start=1,
        ):
            parts = [
                f"{_md_escape(n)}（{_md_escape(w)}）" if w else _md_escape(n)
                for n, w in zip(g["names"], g["wcodes"])
            ]
            chain_by_idx[idx] = "→".join(parts)

        md = [
            f"# 四跳持股路径审计报告（{gv}）",
            "",
            f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}（本地时间）",
            f"- count(4..10)={d4['count']} / count(5..10)={d5['count']} / canary 存在={has_canary}",
            f"- 明细组数：{len(groups)}（与 count 一致={len(groups) == 10}）",
            f"- 证据冲突：{len(bad)}（材料化 OK / 未材料化 / 冲突见下表）",
            "",
            "| # | 节点链（名称（代码）） | 跳 | 源 | 目标 | 持股% | 报告期 | 边来源（rel_id / src_record_id / ann_dt / gv / source） | evidence_id | 状态 | 签核 |",
            "|---|------------------------|--:|------|------|------:|--------|-------------------------------------------------|-------------|------|:--:|",
        ]
        for r in conn_rows:
            edge_src = " / ".join([_md_escape(r[i]) for i in (6, 7, 8)] + [gv, "neo4j"])
            md.append(
                f"| {r[0]} | {_md_escape(chain_by_idx.get(r[0], ''))} | {r[1]} "
                f"| {_md_escape(r[2])} | {_md_escape(r[3])} | {r[4]} | {r[5]} "
                f"| {edge_src} | {_md_escape(r[9])} | {r[10]}{r[11]} | ☐ |"
            )
        md += [
            "",
            "> 签核说明：10 条路径人工核验后，将对应行的 ☐ 改为 ☑ 并附核验日期。",
            "> 未材料化（not_materialized）不算失败：可通过对应公司的 "
            "GET /companies/{code}/equity 请求幂等补录；审计脚本不触发任何写入。",
        ]
        report = "\n".join(md)
        if output:
            Path(output).write_text(report, encoding="utf-8", newline="\n")
            print(f"报告已写入 {output}")
        else:
            print("\n===== 审计报告预览（前 20 行）=====")
            print("\n".join(md[:20]))
    finally:
        # v3.6：AsyncDriver.close() 是协程，必须 await（sync close 会告警/泄漏）
        await driver.close()
    return 0 if not _FAILURES else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-version", default="equity-2026Q2")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if not settings.NEO4J_PASSWORD:
        print("❌ 缺少 NEO4J_PASSWORD 配置")
        return 1
    code = asyncio.run(audit(args.graph_version, args.output))
    if code == 0:
        print("\n✅ 审计通过（10 条路径明细已输出）")
    else:
        print(f"\n❌ 审计失败：{len(_FAILURES)} 项")
        for f in _FAILURES:
            print(f"   - {f}")
    return code


if __name__ == "__main__":
    sys.exit(main())
