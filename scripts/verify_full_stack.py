#!/usr/bin/env python
"""V12 Full Stack 验证脚本.

验证 full profile 真实外部服务连接能力。
支持 --profile lite|full, --check-external, --write-smoke, --cleanup, --ci, --json.
"""

import argparse
import json as json_mod
import socket
import sys

# Windows UTF-8 输出保护
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"
NOT_RUN = "[NOT_RUN]"


class CheckResult:
    def __init__(self):
        self.checks: list[dict] = []

    def add(self, label: str, status: str, detail: str = "") -> None:
        self.checks.append({"label": label, "status": status, "detail": detail})

    def pass_(self, label: str, detail: str = "") -> None:
        self.add(label, "passed", detail)

    def fail(self, label: str, detail: str = "") -> None:
        self.add(label, "failed", detail)

    def not_run(self, label: str, detail: str = "") -> None:
        self.add(label, "not_run", detail)

    def warn(self, label: str, detail: str = "") -> None:
        self.add(label, "warning", detail)

    def summary(self) -> dict:
        counts = {"passed": 0, "failed": 0, "not_run": 0, "warning": 0}
        for c in self.checks:
            counts[c["status"]] = counts.get(c["status"], 0) + 1
        return counts

    def all_passed(self) -> bool:
        return self.summary()["failed"] == 0


def tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    """检测 TCP 端口是否可达."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_lite_profile(result: CheckResult) -> None:
    """验证 lite profile（不要求外部服务）."""
    # SQLite adapter
    try:
        from app.infrastructure.persistence.sqlite.company_repository import (
            SQLiteCompanyRepository,
        )

        _repo = SQLiteCompanyRepository()  # noqa: F841
        result.pass_("SQLite CompanyRepository", "lite adapter loaded")
    except Exception as e:
        result.fail("SQLite CompanyRepository", str(e)[:80])

    # NetworkX adapter
    try:
        from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph

        graph = NetworkXEquityGraph()
        ok = graph.check_connection()
        if ok:
            result.pass_("NetworkX EquityGraph", "lite adapter loaded")
        else:
            result.fail("NetworkX EquityGraph", "check_connection failed")
    except Exception as e:
        result.fail("NetworkX EquityGraph", str(e)[:80])

    # Mock LLM
    try:
        from app.infrastructure.llm.mock.provider import MockLLMProvider

        llm = MockLLMProvider()
        ok = llm.check_connection()
        if ok:
            result.pass_("Mock LLM Provider", "lite adapter loaded")
        else:
            result.fail("Mock LLM Provider", "check_connection failed")
    except Exception as e:
        result.fail("Mock LLM Provider", str(e)[:80])

    # FastAPI
    try:
        from app.main import app

        result.pass_("FastAPI app import", f"title={app.title}")
    except Exception as e:
        result.fail("FastAPI app import", str(e)[:80])


def check_mysql(
    result: CheckResult, write_smoke: bool = False, cleanup: bool = False
) -> None:
    """验证 MySQL 连接."""
    from app.core.config import Settings

    settings = Settings()

    # Driver import
    try:
        import pymysql

        result.pass_("PyMySQL driver import", f"v{pymysql.__version__}")
    except ImportError as e:
        result.fail("PyMySQL driver import", str(e))
        return

    # SQLAlchemy import
    try:
        from sqlalchemy import create_engine, text

        result.pass_("SQLAlchemy import", "OK")
    except ImportError as e:
        result.fail("SQLAlchemy import", str(e))
        return

    host = settings.MYSQL_HOST
    port = settings.MYSQL_PORT
    password = settings.MYSQL_PASSWORD
    user = settings.MYSQL_USER
    database = settings.MYSQL_DATABASE

    if not password:
        result.not_run("MySQL auth", "MYSQL_PASSWORD not configured")
        return

    # TCP reachability
    reachable = tcp_reachable(host, port)
    if not reachable:
        result.not_run(
            "MySQL TCP",
            f"{host}:{port} not reachable — service not running or not installed",
        )
        return

    result.pass_("MySQL TCP reachable", f"{host}:{port}")

    # SQLAlchemy connection
    _sanitized_url = (
        f"mysql+pymysql://{user}:***@{host}:{port}/{database}?charset=utf8mb4"
    )
    url_real = (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    )

    try:
        engine = create_engine(url_real, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            # SELECT 1
            r = conn.execute(text("SELECT 1")).scalar()
            if r == 1:
                result.pass_("MySQL SELECT 1", "OK")
            else:
                result.fail("MySQL SELECT 1", f"expected 1, got {r}")
                return

            # SELECT DATABASE()
            db = conn.execute(text("SELECT DATABASE()")).scalar()
            result.pass_("MySQL current database", str(db))

            # Write smoke (optional)
            if write_smoke:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS truthnet_smoke_test ("
                        "  id INT PRIMARY KEY AUTO_INCREMENT,"
                        "  smoke_key VARCHAR(64) NOT NULL,"
                        "  smoke_value VARCHAR(255) NOT NULL,"
                        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                        ")"
                    )
                )
                conn.commit()
                conn.execute(
                    text(
                        "INSERT INTO truthnet_smoke_test (smoke_key, smoke_value) "
                        "VALUES ('v12_full_stack', 'ok')"
                    )
                )
                conn.commit()
                row = conn.execute(
                    text(
                        "SELECT smoke_key, smoke_value FROM truthnet_smoke_test "
                        "WHERE smoke_key='v12_full_stack'"
                    )
                ).fetchone()
                if row and row[1] == "ok":
                    result.pass_("MySQL write smoke", "insert+read OK")
                else:
                    result.fail("MySQL write smoke", "read back failed")

                if cleanup:
                    conn.execute(
                        text(
                            "DELETE FROM truthnet_smoke_test WHERE smoke_key='v12_full_stack'"
                        )
                    )
                    conn.commit()
                    result.pass_("MySQL cleanup", "smoke data deleted")

        engine.dispose()
    except Exception as e:
        result.fail("MySQL connection", str(e)[:120])


def check_neo4j(
    result: CheckResult, write_smoke: bool = False, cleanup: bool = False
) -> None:
    """验证 Neo4j 连接."""
    from app.core.config import Settings

    settings = Settings()

    # Driver import
    try:
        import neo4j
        from neo4j import GraphDatabase

        result.pass_("Neo4j driver import", f"v{neo4j.__version__}")
    except ImportError as e:
        result.fail("Neo4j driver import", str(e))
        return

    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    password = settings.NEO4J_PASSWORD

    if not password:
        result.not_run("Neo4j auth", "NEO4J_PASSWORD not configured")
        return

    # 解析 host:port from URI
    host = "localhost"
    port = 7687
    if "bolt://" in uri:
        netloc = uri.replace("bolt://", "").split("@")[-1]
        if ":" in netloc:
            host, port_str = netloc.split(":")
            port = int(port_str)
        else:
            host = netloc

    # TCP reachability
    reachable = tcp_reachable(host, port)
    if not reachable:
        result.not_run(
            "Neo4j TCP",
            f"{host}:{port} not reachable — service not running or not installed",
        )
        return

    result.pass_("Neo4j TCP reachable", f"{host}:{port}")

    # Connection + RETURN 1
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        result.pass_("Neo4j verify_connectivity", "OK")

        with driver.session() as session:
            r = session.run("RETURN 1 AS ok").single()
            if r and r["ok"] == 1:
                result.pass_("Neo4j RETURN 1", "OK")
            else:
                result.fail("Neo4j RETURN 1", "unexpected result")

            if write_smoke:
                session.run(
                    "MERGE (n:TruthNetSmokeTest {smoke_key: 'v12_full_stack'}) "
                    "SET n.smoke_value = 'ok', n.updated_at = datetime()"
                )
                result.pass_("Neo4j write smoke", "node created")

                if cleanup:
                    session.run(
                        "MATCH (n:TruthNetSmokeTest {smoke_key: 'v12_full_stack'}) DELETE n"
                    )
                    result.pass_("Neo4j cleanup", "smoke node deleted")

        driver.close()
    except Exception as e:
        result.fail("Neo4j connection", str(e)[:120])


def check_chroma_persistent(result: CheckResult, cleanup: bool = False) -> None:
    """验证 ChromaDB persistent 模式."""
    from app.core.config import Settings

    settings = Settings()

    persist_dir = settings.CHROMA_PERSIST_DIR
    if not persist_dir:
        result.fail("ChromaDB", "CHROMA_PERSIST_DIR not configured")
        return

    # Ensure directory exists
    dir_path = REPO_ROOT / persist_dir
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        result.pass_("ChromaDB persist dir writable", str(dir_path))
    except Exception as e:
        result.fail("ChromaDB persist dir", str(e)[:80])
        return

    collection_name = "truthnet_v12_smoke"

    try:
        import chromadb

        # Write
        client = chromadb.PersistentClient(
            path=str(dir_path),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )

        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = client.create_collection(name=collection_name)
        collection.add(
            documents=["TruthNet V12 full stack verification"],
            metadatas=[{"source": "verify_full_stack"}],
            ids=["doc_v12_smoke"],
        )
        result.pass_("ChromaDB write", f"collection={collection_name}")

        # Query
        results = collection.query(query_texts=["V12 full stack"], n_results=1)
        if results and results.get("ids") and results["ids"]:
            result.pass_("ChromaDB query", "read back OK")
        else:
            result.fail("ChromaDB query", "no results")

        # Reopen
        del client
        client2 = chromadb.PersistentClient(
            path=str(dir_path),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        collection2 = client2.get_collection(name=collection_name)
        results2 = collection2.query(query_texts=["V12"], n_results=1)
        if results2 and results2.get("ids") and results2["ids"]:
            result.pass_("ChromaDB reopen+read", "persistence OK")
        else:
            result.fail("ChromaDB reopen+read", "data lost after reopen")

        # Cleanup
        if cleanup:
            client2.delete_collection(name=collection_name)
            result.pass_("ChromaDB cleanup", f"collection {collection_name} deleted")

        del client2
    except Exception as e:
        result.fail("ChromaDB persistent", str(e)[:120])


def check_readyz_endpoints(result: CheckResult, profile: str) -> None:
    """验证 /healthz 和 /readyz."""
    import httpx
    from httpx import ASGITransport

    from app.main import app

    transport = ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # /healthz
            r = await client.get("/api/v1/healthz")
            if r.status_code == 200:
                data = r.json()
                result.pass_(
                    "/healthz",
                    f"status={data.get('data', {}).get('status', 'unknown')}, "
                    f"profile={data.get('data', {}).get('profile', 'unknown')}",
                )
            else:
                result.fail("/healthz", f"HTTP {r.status_code}")

            # /readyz
            r2 = await client.get("/api/v1/readyz")
            if r2.status_code == 200:
                data2 = r2.json()
                status = data2.get("data", {}).get("status", "unknown")
                profile_val = data2.get("data", {}).get("profile", "unknown")
                deps = data2.get("data", {}).get("checks", {})
                result.pass_(
                    "/readyz",
                    f"status={status}, profile={profile_val}, deps={list(deps.keys())}",
                )
            else:
                result.fail("/readyz", f"HTTP {r2.status_code}")

    import asyncio

    asyncio.run(_run())


def main():
    parser = argparse.ArgumentParser(description="V12 Full Stack 验证")
    parser.add_argument("--profile", choices=["lite", "full"], default="lite")
    parser.add_argument("--check-external", action="store_true")
    parser.add_argument("--write-smoke", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    result = CheckResult()

    print("=" * 60)
    tags = [f"profile={args.profile}"]
    if args.ci:
        tags.append("CI")
    print(f"  TruthNet V12 Full Stack Verification [{', '.join(tags)}]")
    print("=" * 60)

    # 1. Environment
    print("\n--- 1. Environment ---")
    exe = sys.executable
    py_ver = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"  Python: {py_ver}  |  exe: {exe}")
    is_311 = sys.version_info.major == 3 and sys.version_info.minor == 11
    result.pass_("Python 3.11", py_ver) if is_311 else result.fail(
        "Python 3.11", py_ver
    )

    # 2. Lite profile baseline
    print("\n--- 2. Lite Profile Baseline ---")
    check_lite_profile(result)

    # 3. ChromaDB persistent
    print("\n--- 3. ChromaDB Persistent ---")
    check_chroma_persistent(result, cleanup=args.cleanup)

    # 4. External services (full profile)
    if args.check_external or args.profile == "full":
        print("\n--- 4. MySQL (External) ---")
        write_smoke = args.write_smoke and not args.no_write
        check_mysql(result, write_smoke=write_smoke, cleanup=args.cleanup)

        print("\n--- 5. Neo4j (External) ---")
        check_neo4j(result, write_smoke=write_smoke, cleanup=args.cleanup)
    else:
        print("\n--- 4-5. External Services ---")
        result.not_run("MySQL/Neo4j", "use --check-external or --profile full")

    # 6. FastAPI endpoints
    print("\n--- 6. FastAPI /healthz /readyz ---")
    check_readyz_endpoints(result, args.profile)

    # Summary
    print("\n" + "=" * 60)
    summary = result.summary()
    total = sum(summary.values())
    print(f"  Total: {total}")
    print(f"  {PASS}: {summary['passed']}")
    print(f"  {NOT_RUN}: {summary['not_run']}")
    if summary["failed"] > 0:
        print(f"  {FAIL}: {summary['failed']}")
    if summary["warning"] > 0:
        print(f"  {WARN}: {summary['warning']}")

    if result.all_passed():
        print(f"\n  {PASS} | V12 Full Stack verification passed")
    else:
        print(f"\n  {FAIL} | V12 Full Stack verification has failures")
    print("=" * 60)

    # Detailed output
    print("\n--- Detailed Results ---")
    for c in result.checks:
        status_mark = {
            "passed": PASS,
            "failed": FAIL,
            "not_run": NOT_RUN,
            "warning": WARN,
        }.get(c["status"], INFO)
        line = f"  {status_mark} | {c['label']}"
        if c["detail"]:
            line += f"  — {c['detail']}"
        print(line)

    if args.json_output:
        print("\n--- JSON Output ---")
        print(json_mod.dumps(result.checks, indent=2, ensure_ascii=False))

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json_mod.dumps(result.checks, indent=2, ensure_ascii=False),
            encoding="utf-8",
            newline="\n",
        )

    return 1 if not result.all_passed() else 0


if __name__ == "__main__":
    sys.exit(main())
