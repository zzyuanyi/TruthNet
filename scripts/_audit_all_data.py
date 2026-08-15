"""全库数据审计 — 对照 DATA_README/DATA_CHECKLIST 预期核查所有表（只读，不写库）。

用法: python scripts/_audit_all_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402

load_dotenv(_ROOT / ".env")

url = (
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
)
e = create_engine(url)
issues = []


def q(sql: str, **p):
    with e.connect() as c:
        return c.execute(text(sql), p).scalar()


def check(name: str, actual, expect, note: str = ""):
    ok = actual == expect
    flag = "✅" if ok else "❌"
    print(f"  {flag} {name}: {actual} (预期 {expect}){(' ' + note) if note else ''}")
    if not ok:
        issues.append(
            f"{name}: {actual} != 预期 {expect}{(' ' + note) if note else ''}"
        )


print("=== 一、主数据 ===")
check("companies 总数", q("SELECT COUNT(*) FROM companies"), 6713)
check(
    "balance_sheet 总数",
    q("SELECT COUNT(*) FROM balance_sheet"),
    39019,
    "(母公司 408006000)",
)
check(
    "income_statement 总数",
    q("SELECT COUNT(*) FROM income_statement"),
    38210,
    "(母公司 408006000)",
)
check(
    "cash_flow 总数", q("SELECT COUNT(*) FROM cash_flow"), 39985, "(母公司 408006000)"
)
three_total = sum(
    q(f"SELECT COUNT(*) FROM {t}")
    for t in ("balance_sheet", "income_statement", "cash_flow")
)
check("三表合计", three_total, 117214)
# 母公司口径行数（R1-R7 实际使用）
parent = sum(
    q(f"SELECT COUNT(*) FROM {t} WHERE statement_type = '408006000'")
    for t in ("balance_sheet", "income_statement", "cash_flow")
)
print(f"  ℹ️ 母公司口径行数: {parent}（R1-R7 使用）")
merged = q("SELECT COUNT(*) FROM balance_sheet WHERE statement_type = '408001000'")
print(f"  ℹ️ 合并口径(balance_sheet): {merged}（存储但规则不使用）")
check("research_reports 总数", q("SELECT COUNT(*) FROM research_reports"), 55214)
check(
    "research_reports 覆盖公司",
    q("SELECT COUNT(DISTINCT wind_code) FROM research_reports"),
    3438,
)
check(
    "announcements 总数",
    q("SELECT COUNT(*) FROM announcements"),
    7311,
    "(源 Sheet2 7311 行)",
)
check(
    "announcements 覆盖公司",
    q("SELECT COUNT(DISTINCT wind_code) FROM announcements"),
    2585,
)
# 股东表名探测
tables = [
    r[0]
    for r in e.connect()
    .execute(
        text(
            "SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema = :s"
        ),
        {"s": settings.MYSQL_DATABASE},
    )
    .fetchall()
]
print(f"  ℹ️ 数据库表清单: {sorted(tables)}")
e.dispose()

print()
print("=== 二、衍生数据（Phase C 8/3 导入）===")
with e.connect() as c:
    for t in (
        "industry_benchmarks",
        "rating_changes",
        "event_clusters",
        "event_cluster_sources",
    ):
        n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"  ℹ️ {t}: {n}")
        if t == "industry_benchmarks" and n != 279:
            issues.append(f"industry_benchmarks: {n} != 279")
        if t == "rating_changes" and n != 861:
            issues.append(f"rating_changes: {n} != 861")
        if t == "event_clusters" and n != 746:
            issues.append(f"event_clusters: {n} != 746")
        if t == "event_cluster_sources" and n != 1406:
            issues.append(f"event_cluster_sources: {n} != 1406")

print()
print("=== 三、证据链路 ===")
with e.connect() as c:
    ev_total = c.execute(text("SELECT COUNT(*) FROM evidence_refs")).scalar()
    by_type = dict(
        c.execute(
            text("SELECT source_type, COUNT(*) FROM evidence_refs GROUP BY source_type")
        ).fetchall()
    )
    print(f"  ℹ️ evidence_refs 总数: {ev_total}, 分布: {by_type}")
    claims = c.execute(text("SELECT COUNT(*) FROM claims")).scalar()
    links = c.execute(text("SELECT COUNT(*) FROM claim_evidence_links")).scalar()
    print(f"  ℹ️ claims: {claims}, claim_evidence_links: {links}")
    # 批处理证据无会话（turn_id NULL）
    batch_null = c.execute(
        text("SELECT COUNT(*) FROM evidence_refs WHERE turn_id IS NULL")
    ).scalar()
    print(f"  ℹ️ turn_id 为 NULL（批处理/构建产物）: {batch_null}")

print()
print("=== 四、Neo4j / Chroma（跨库）===")
try:
    from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

    g = Neo4jEquityGraph()
    stats = g.get_stats_sync() if hasattr(g, "get_stats_sync") else None
    if stats:
        check("Neo4j 节点", stats.get("nodes"), 80567)
        check("Neo4j 关系", stats.get("relationships"), 646449)
    else:
        print("  ⚠️ Neo4j get_stats 不可用，跳过")
except Exception as exc:  # noqa: BLE001
    print(f"  ⚠️ Neo4j 审计跳过: {exc}")
try:
    import chromadb

    client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    coll = client.get_collection("research_report_chunks")
    n = coll.count()
    check("Chroma research_report_chunks", n, 203058)
except Exception as exc:  # noqa: BLE001
    print(f"  ⚠️ Chroma 审计跳过: {exc}")

print()
print("=== 五、版本一致性（2026-08-15 复核 P1：统一 competition-2026）===")
expected_dv = settings.DATASET_VERSION
with e.connect() as c:
    for t in (
        "announcements",
        "companies",
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "research_reports",
        "top_shareholders",
        "event_clusters",
        "rating_changes",
        "industry_benchmarks",
    ):
        rows = c.execute(
            text(
                f"SELECT dataset_version, COUNT(*) FROM {t} " "GROUP BY dataset_version"
            )
        ).fetchall()
        ok = all(str(r[0]) == expected_dv for r in rows)
        flag = "✅" if ok else "❌"
        print(f"  {flag} {t}: {rows}")
        if not ok:
            issues.append(
                f"{t} dataset_version 不一致: {rows}（期望全部 {expected_dv}）"
            )
    # 证据链：announcement 证据版本必须与 announcements 表一致
    # （evidence ID digest 含 dataset_version，版本漂移会产生两种 ID）
    ann_ev = c.execute(
        text(
            "SELECT dataset_version, COUNT(*) FROM evidence_refs "
            "WHERE source_type='announcement' GROUP BY dataset_version"
        )
    ).fetchall()
    ok = all(str(r[0]) == expected_dv for r in ann_ev)
    flag = "✅" if ok else "❌"
    print(f"  {flag} evidence_refs(announcement): {ann_ev}")
    if not ok:
        issues.append(f"evidence_refs announcement 版本不一致: {ann_ev}")

print()
print("=" * 50)
if issues:
    print(f"❌ 发现 {len(issues)} 处与预期不一致：")
    for i in issues:
        print(f"  - {i}")
else:
    print("✅ 全部数据与预期一致")
