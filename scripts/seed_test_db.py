"""MySQL 测试库种子导入 — v3.1 + v3.4 + v3.5 安全边界.

从演示库 truthnet 复制表结构（全表）+ 数据（子集或全量）到测试库
truthnet_test。幂等：每次运行先按管辖范围定向清理再插入。

用法：
    python scripts/seed_test_db.py --confirm truthnet_test                 # 子集（康美+茅台）
    python scripts/seed_test_db.py --confirm truthnet_test --full          # 全量（性能基线）

安全边界（v3.4 + v3.5）：
- --confirm <目标库名> 必需（批量写命令需显式确认）；
- 删除/复制阶段分开：删除子→父、插入父→子（按 information_schema
  FK 依赖拓扑排序，不使用 FOREIGN_KEY_CHECKS=0 简化）；STRUCTURE_ONLY
  表同样按 FK 拓扑顺序清理（v3.5：不再单独无序遍历）；
- copy_table() 不再隐式 DELETE（v3.5：删除职责归删除阶段）；
- 内部错误统一 SeedError，确保失败时状态写入 failed（v3.5）；
- 测试库与演示库比较大小写不敏感（v3.5）；两侧连接均执行
  SELECT DATABASE() 二次确认实际库名（v3.5）；
- 分批 fetchmany(5000) + 分表提交；中途失败将测试库标记为 incomplete
  （test_db_seed_status 表），E2E/性能脚本拒绝在 incomplete 状态下运行；
- 动态 ID（event_cluster_sources.fcode）参数绑定，不拼接数据库内容；
- 完成后逐表行数校验（与源库同过滤条件对比）。
"""

import argparse
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

_SAFE_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_FORBIDDEN_DB_NAMES = {
    "truthnet",
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
}

# 目标公司（风控/勾稽/舆情联调子集）
COMPANY_CODES = ("600518.SH", "600519.SH")

# 按 wind_code 过滤的数据表 → 列名
BY_WIND_CODE = [
    "companies",
    "balance_sheet",
    "income_statement",
    "cash_flow",
    "announcements",
    "top_shareholders",
    "rating_changes",
    "research_reports",
    "event_clusters",
    "rule_evaluations",
    "risk_assessments",
]

# 仅复制结构（运行时表：会话/证据/任务等，测试自行生成）
STRUCTURE_ONLY = [
    "analysis_runs",
    "claim_evidence_links",
    "claims",
    "conversation_sessions",
    "conversation_turns",
    "report_jobs",
    "truthnet_smoke_test",
]

# 运行时表部分数据：research_report 类型证据（研报证据回查回归测试依赖）
EVIDENCE_SUBSET = ("evidence_refs", "WHERE source_type='research_report'")

# 全量小表（主数据/基准/规则/迁移版本——alembic_version 保留迁移状态）
FULL_TABLES = ["industry_benchmarks", "rule_definitions", "alembic_version"]

_BATCH = 5000


class SeedError(Exception):
    """种子导入内部错误（v3.5）：统一捕获并标记测试库 state=failed。"""


def validate_db_name(db: str, kind: str) -> None:
    """测试库名校验（拒绝名单/安全命名）；演示库只需安全命名。"""
    if kind == "测试" and db.lower() in {n.lower() for n in _FORBIDDEN_DB_NAMES}:
        raise SystemExit(f"[seed-test-db] {kind} 库名 {db!r} 在拒绝名单中")
    if not _SAFE_DB_NAME_RE.match(db):
        raise SystemExit(f"[seed-test-db] {kind} 库名 {db!r} 含不安全字符")


def connect(db: str, use_test_creds: bool = False) -> pymysql.Connection:
    """演示库用 MYSQL_USER 读；测试库用 MYSQL_TEST_USER（隔离凭据）写。"""
    if use_test_creds:
        user = os.environ.get("MYSQL_TEST_USER", "")
        password = os.environ.get("MYSQL_TEST_PASSWORD", "")
    else:
        user = os.environ.get("MYSQL_USER", "")
        password = os.environ.get("MYSQL_PASSWORD", "")
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        connect_timeout=10,
    )


def assert_connected_db(conn, expected: str, kind: str) -> None:
    """v3.5：连接后 SELECT DATABASE() 二次确认实际库名（大小写不敏感）。"""
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        actual = cur.fetchone()[0]
    if (actual or "").lower() != expected.lower():
        raise SeedError(
            f"{kind}库连接不符: SELECT DATABASE()={actual!r} != 期望 {expected!r}"
        )


def fk_topological_order(
    conn, schema: str, tables: list[str]
) -> tuple[list[str], list[str]]:
    """按 FK 依赖计算顺序：返回 (插入序[父先], 删除序[子先])。

    读取 information_schema.key_column_usage 的引用关系做拓扑排序；
    无依赖循环（循环 FK 极少见，遇环按原顺序兜底）。
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, referenced_table_name FROM information_schema."
            "key_column_usage WHERE table_schema=%s AND referenced_table_name IS NOT NULL",
            (schema,),
        )
        deps: dict[str, set[str]] = {}
        for t, ref in cur.fetchall():
            if t in tables and ref in tables and t != ref:
                deps.setdefault(t, set()).add(ref)  # t 依赖 ref（ref 为父）

    def topo() -> list[str]:
        remaining = list(tables)
        ordered: list[str] = []
        while remaining:
            progressed = False
            for t in list(remaining):
                if not (deps.get(t, set()) & set(remaining)):
                    ordered.append(t)
                    remaining.remove(t)
                    progressed = True
            if not progressed:  # 循环依赖兜底
                ordered.extend(remaining)
                break
        return ordered

    insert_order = topo()  # 父表在前
    delete_order = list(reversed(insert_order))  # 子表在前
    return insert_order, delete_order


def copy_table(
    dc,
    tc,
    demo_db: str,
    test_db: str,
    table: str,
    where_sql: str = "",
    where_params: tuple = (),
) -> int:
    """Python 中转分批复制：演示库 SELECT 读回 → 测试库分批 INSERT.

    跨库 INSERT ... SELECT 会被 MySQL 按执行连接校验两侧权限（测试账号
    无演示库权限，正是隔离要求），故需经 Python 中转。分批 fetchmany +
    executemany，避免大表全载内存/超大事务。

    v3.5：不再隐式 DELETE（删除职责归删除阶段，调用方负责先清目标表）。
    """
    dc.execute(
        f"SELECT * FROM `{demo_db}`.`{table}` {where_sql}".rstrip(), where_params
    )
    cols = [d[0] for d in dc.description]
    col_sql = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = (
        f"INSERT INTO `{test_db}`.`{table}` ({col_sql}) VALUES ({placeholders})"
    )
    total = 0
    while True:
        rows = dc.fetchmany(_BATCH)
        if not rows:
            break
        tc.executemany(insert_sql, rows)
        tc.connection.commit()  # 分表分批提交（中途失败可定位）
        total += len(rows)
    return total


def verify_row_counts(
    dc,
    tc,
    demo_db: str,
    test_db: str,
    table: str,
    where_sql: str = "",
    where_params: tuple = (),
) -> bool:
    """行数校验：源库与测试库同过滤条件对比。"""
    dc.execute(
        f"SELECT COUNT(*) FROM `{demo_db}`.`{table}` {where_sql}".rstrip(),
        where_params,
    )
    n_demo = dc.fetchone()[0]
    tc.execute(
        f"SELECT COUNT(*) FROM `{test_db}`.`{table}` {where_sql}".rstrip(),
        where_params,
    )
    n_test = tc.fetchone()[0]
    ok = n_demo == n_test
    if not ok:
        print(f"  [✗] {table}: 源 {n_demo} != 测试 {n_test}")
    return ok


def seed_status_mark(conn, state: str) -> None:
    """测试库种子状态标记（v3.4）：in_progress → complete / failed。"""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS test_db_seed_status "
            "(state VARCHAR(16) NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        cur.execute("DELETE FROM test_db_seed_status")
        cur.execute("INSERT INTO test_db_seed_status (state) VALUES (%s)", (state,))
    conn.commit()


def ensure_seed_complete(test_db: str = "") -> None:
    """E2E/性能脚本守卫（v3.4）：测试库种子不完整（in_progress/failed/无状态）
    时拒绝运行，防止在不完整数据上产生误导性结果。

    状态表不存在（手动建库未跑过 seed）同样拒绝，提示先执行 seed。
    v3.5：修复 information_schema 存在性查询（SELECT 1 而非不存在列的
    SELECT state）。
    """
    db = test_db or os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = connect(db, use_test_creds=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name='test_db_seed_status'",
                (db,),
            )
            if cur.fetchone() is None:
                raise SystemExit(
                    f"[seed-guard] 测试库 {db} 无种子状态记录，请先执行 "
                    f"python scripts/seed_test_db.py --confirm {db}"
                )
            cur.execute(
                "SELECT state FROM test_db_seed_status ORDER BY updated_at DESC LIMIT 1"
            )
            state = cur.fetchone()[0]
    finally:
        conn.close()
    if state != "complete":
        raise SystemExit(
            f"[seed-guard] 测试库 {db} 种子状态={state}（非 complete），拒绝运行；"
            f"请重新执行 python scripts/seed_test_db.py --confirm {db}"
        )


def _run_seed(
    demo,
    test,
    demo_db: str,
    test_db: str,
    full: bool,
) -> dict:
    """种子主体（v3.5）：结构 → 删除阶段（子→父，含 STRUCTURE_ONLY）
    → 复制阶段（父→子）→ 行数校验。内部失败抛 SeedError。"""
    in_list = ", ".join(["%s"] * len(COMPANY_CODES))
    stats: dict[str, int] = {}
    with demo.cursor() as dc, test.cursor() as tc:
        # 1. 结构：SHOW CREATE TABLE 取 DDL 文本 → 测试连接执行（幂等）
        #    CREATE TABLE ... LIKE 会读源表元数据，测试账号无演示库权限，
        #    故经 DDL 文本中转；外键依赖（1824）未就绪的表留到下一轮。
        dc.execute("SHOW TABLES FROM `%s`" % demo_db)
        all_tables = [r[0] for r in dc.fetchall()]
        pending = list(all_tables)
        while pending:
            progressed = False
            for t in list(pending):
                tc.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema=%s AND table_name=%s",
                    (test_db, t),
                )
                if tc.fetchone()[0] > 0:
                    pending.remove(t)
                    progressed = True
                    continue
                dc.execute(f"SHOW CREATE TABLE `{demo_db}`.`{t}`")
                ddl = dc.fetchone()[1].replace(f"`{demo_db}`.", f"`{test_db}`.")
                try:
                    tc.execute(ddl)
                except pymysql.err.OperationalError as exc:
                    if exc.args[0] == 1824:  # 外键引用的表未就绪
                        continue
                    raise
                pending.remove(t)
                progressed = True
            if not progressed:
                raise SeedError(f"无法创建表（外键依赖未满足）: {pending}")
        test.commit()

        insert_order, delete_order = fk_topological_order(demo, demo_db, all_tables)

        # 2. 删除阶段（子→父；STRUCTURE_ONLY 同样按 FK 拓扑序清理，v3.5）
        for t in delete_order:
            if t in STRUCTURE_ONLY:
                tc.execute(f"DELETE FROM `{test_db}`.`{t}`")
            elif full:
                tc.execute(f"DELETE FROM `{test_db}`.`{t}`")
            elif t in BY_WIND_CODE:
                tc.execute(
                    f"DELETE FROM `{test_db}`.`{t}` WHERE wind_code IN ({in_list})",
                    COMPANY_CODES,
                )
        if not full:
            for t in FULL_TABLES:
                tc.execute(f"DELETE FROM `{test_db}`.`{t}`")
            tc.execute("DELETE FROM `%s`.`event_cluster_sources`" % test_db)
            tc.execute(
                "DELETE FROM `%s`.`evidence_refs` WHERE source_type='research_report'"
                % test_db
            )
        test.commit()

        # 3. 复制阶段（父→子）
        data_tables = [t for t in insert_order if t not in STRUCTURE_ONLY]
        if full:
            for t in data_tables:
                stats[t] = copy_table(dc, tc, demo_db, test_db, t)
        else:
            for t in BY_WIND_CODE:
                stats[t] = copy_table(
                    dc,
                    tc,
                    demo_db,
                    test_db,
                    t,
                    f"WHERE wind_code IN ({in_list})",
                    COMPANY_CODES,
                )
            for t in FULL_TABLES:
                stats[t] = copy_table(dc, tc, demo_db, test_db, t)
            # 关联表：事件簇来源（fcode 参数绑定）
            dc.execute(
                f"SELECT n_info_fcode FROM `{demo_db}`.`announcements` "
                f"WHERE wind_code IN ({in_list})",
                COMPANY_CODES,
            )
            fcodes = [r[0] for r in dc.fetchall()]
            if fcodes:
                fc_ph = ", ".join(["%s"] * len(fcodes))
                stats["event_cluster_sources"] = copy_table(
                    dc,
                    tc,
                    demo_db,
                    test_db,
                    "event_cluster_sources",
                    f"WHERE fcode IN ({fc_ph})",
                    tuple(fcodes),
                )
            # 运行时表部分数据（research_report 证据）
            t, where = EVIDENCE_SUBSET
            stats[t] = copy_table(dc, tc, demo_db, test_db, t, where)

        # 4. 行数校验（同过滤条件）
        print("[seed-test-db] 行数校验:")
        verify_ok = True
        if full:
            for t in data_tables:
                ok = verify_row_counts(dc, tc, demo_db, test_db, t)
                verify_ok = verify_ok and ok
        else:
            for t in BY_WIND_CODE:
                ok = verify_row_counts(
                    dc,
                    tc,
                    demo_db,
                    test_db,
                    t,
                    f"WHERE wind_code IN ({in_list})",
                    COMPANY_CODES,
                )
                verify_ok = verify_ok and ok
            for t in FULL_TABLES:
                ok = verify_row_counts(dc, tc, demo_db, test_db, t)
                verify_ok = verify_ok and ok
        if not verify_ok:
            raise SeedError("行数校验失败（测试库不完整）")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test-db", default=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    )
    parser.add_argument(
        "--demo-db", default=os.environ.get("MYSQL_DATABASE", "truthnet")
    )
    parser.add_argument("--full", action="store_true", help="全量复制所有数据表")
    parser.add_argument(
        "--confirm",
        default="",
        help="必须显式输入目标测试库名（如 --confirm truthnet_test），防误操作",
    )
    args = parser.parse_args()
    test_db, demo_db = args.test_db, args.demo_db

    validate_db_name(test_db, "测试")
    validate_db_name(demo_db, "演示")
    # v3.5：大小写不敏感比较
    if test_db.lower() == demo_db.lower():
        raise SystemExit(
            f"[seed-test-db] 测试库 {test_db!r} 不得等于演示库 {demo_db!r}"
        )
    if not args.confirm or args.confirm != test_db:
        raise SystemExit(f"[seed-test-db] 必须显式 --confirm {test_db}（批量写需确认）")

    demo = connect(demo_db, use_test_creds=False)
    test = connect(test_db, use_test_creds=True)
    try:
        # v3.5：两侧 SELECT DATABASE() 二次确认
        assert_connected_db(demo, demo_db, "演示")
        assert_connected_db(test, test_db, "测试")
        seed_status_mark(test, "in_progress")
        stats = _run_seed(demo, test, demo_db, test_db, args.full)
        seed_status_mark(test, "complete")
    except Exception as exc:
        try:
            seed_status_mark(test, "failed")
        except Exception:  # noqa: BLE001 — 标记失败不掩盖原始错误
            pass
        if isinstance(exc, SeedError):
            print(f"[seed-test-db] ✗ {exc}")
            return 1
        raise
    finally:
        demo.close()
        test.close()

    print("[seed-test-db] 导入完成:")
    for t, n in sorted(stats.items()):
        print(f"  {t}: {n}")
    print(f"  结构表 {len(STRUCTURE_ONLY)} 张已清空（仅结构）；状态=complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
