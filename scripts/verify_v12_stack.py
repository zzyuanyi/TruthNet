#!/usr/bin/env python
"""V12 技术栈验证脚本.

验证 V12 所有依赖可 import 并可执行最小 smoke 操作。
支持 --ci 模式和 --profile full --check-external 可选参数。
"""

import argparse
import importlib
import os
import sys

# Windows UTF-8 输出保护
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 确保可以 import backend/app 下的模块
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    """格式化并返回检查结果."""
    status = PASS if ok else FAIL
    msg = f"  {status} | {label}"
    if detail:
        msg += f"  — {detail}"
    return ok, msg


def import_pkg(name: str, pkg_name: str | None = None) -> tuple[bool, str]:
    """尝试导入包并返回结果."""
    target = pkg_name or name
    try:
        mod = importlib.import_module(target)
        version = getattr(mod, "__version__", "unknown")
        return check(f"{name} ({version})", True)
    except ImportError as e:
        return check(f"{name}", False, f"ImportError: {e}")


def check_env(ci_mode: bool = False) -> list[str]:
    """检查运行环境."""
    lines: list[str] = []

    # Python executable
    exe = sys.executable
    lines.append(f"Python executable: {exe}")

    # Python version
    py_ver = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    is_311 = sys.version_info.major == 3 and sys.version_info.minor == 11
    ok, msg = check(f"Python version ({py_ver})", is_311, "expected 3.11.x")
    lines.append(msg)

    # truthnet env check
    in_conda = "CONDA_PREFIX" in os.environ or "CONDA_DEFAULT_ENV" in os.environ
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    is_truthnet = conda_env == "truthnet"

    if in_conda:
        lines.append(f"Conda env: {conda_env}")
        if not is_truthnet and not ci_mode:
            lines.append(
                f"  {WARN} | 当前 conda 环境是 '{conda_env}'，建议: conda activate truthnet"
            )
    else:
        lines.append(f"  {WARN} | 未检测到 conda 环境，建议: conda activate truthnet")

    # .python-version
    pv_file = REPO_ROOT / ".python-version"
    if pv_file.exists():
        expected = pv_file.read_text(encoding="utf-8").strip()
        pv_ok = py_ver.startswith(expected)
        ok2, msg2 = check(
            f".python-version match ({expected})", pv_ok, f"current: {py_ver}"
        )
        lines.append(msg2)
    else:
        lines.append(f"  {FAIL} | .python-version 文件缺失")

    return lines


def check_core_deps() -> list[str]:
    """检查旧技术栈依赖."""
    lines: list[str] = []

    deps = [
        ("fastapi", None),
        ("pydantic", None),
        ("pydantic_settings", "pydantic_settings"),
        ("langgraph", None),
        ("langchain_core", "langchain_core"),
        ("networkx", None),
        ("chromadb", None),
        ("pandas", None),
        ("numpy", None),
        ("pytest", None),
        ("httpx", None),
        ("ruff", None),
        ("pre_commit", "pre_commit"),
    ]

    for name, pkg_name in deps:
        ok, msg = import_pkg(name, pkg_name)
        lines.append(msg)

    return lines


def check_v12_deps() -> list[str]:
    """检查 V12 新增依赖."""
    lines: list[str] = []

    deps = [
        ("sqlalchemy", None),
        ("alembic", None),
        ("pymysql", None),
        ("neo4j", None),
        ("structlog", None),
        ("jsonschema", None),
    ]

    for name, pkg_name in deps:
        ok, msg = import_pkg(name, pkg_name)
        lines.append(msg)

    return lines


def run_smoke_tests(profile: str = "lite") -> list[str]:
    """运行最小 smoke 测试."""
    lines: list[str] = []
    all_ok = True

    # --- SQLAlchemy smoke (SQLite in-memory) ---
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.execute(text("select 1")).scalar()
            assert result == 1
        ok, msg = check("SQLAlchemy smoke (sqlite memory SELECT 1)", True)
    except Exception as e:
        ok, msg = check("SQLAlchemy smoke (sqlite memory SELECT 1)", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- Alembic import ---
    try:
        import alembic

        assert alembic.__version__
        ok, msg = check("Alembic import", True, f"v{alembic.__version__}")
    except Exception as e:
        ok, msg = check("Alembic import", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- PyMySQL driver import ---
    try:
        import pymysql

        assert pymysql.__version__
        ok, msg = check("PyMySQL driver import", True, f"v{pymysql.__version__}")
    except Exception as e:
        ok, msg = check("PyMySQL driver import", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- Neo4j driver import ---
    try:
        from neo4j import GraphDatabase

        assert GraphDatabase is not None
        import neo4j

        ok, msg = check("Neo4j driver import", True, f"v{neo4j.__version__}")
    except Exception as e:
        ok, msg = check("Neo4j driver import", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- jsonschema smoke ---
    try:
        from jsonschema import validate

        validate({"name": "TruthNet"}, {"type": "object", "required": ["name"]})
        ok, msg = check("jsonschema validate", True)
    except Exception as e:
        ok, msg = check("jsonschema validate", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- structlog smoke ---
    try:
        import structlog

        logger = structlog.get_logger().bind(component="v12_stack")
        assert logger is not None
        ok, msg = check("structlog logger bind", True)
    except Exception as e:
        ok, msg = check("structlog logger bind", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- NetworkX smoke ---
    try:
        import networkx as nx

        g = nx.DiGraph()
        g.add_node("600519", label="贵州茅台")
        assert len(g.nodes) == 1
        ok, msg = check("NetworkX smoke (small graph)", True)
    except Exception as e:
        ok, msg = check("NetworkX smoke (small graph)", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- ChromaDB smoke ---
    try:
        import chromadb

        client = chromadb.Client(
            chromadb.config.Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=None,
                anonymized_telemetry=False,
            )
        )
        collection = client.create_collection(name="test_v12_smoke")
        collection.add(
            documents=["TruthNet V12 verification"],
            ids=["doc_1"],
        )
        results = collection.query(query_texts=["V12"], n_results=1)
        assert results is not None
        ok, msg = check("ChromaDB smoke (in-memory collection)", True)
    except Exception:
        # Windows temp file locking fallback: try EphemeralClient
        try:
            import chromadb

            client = chromadb.EphemeralClient(
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
            collection = client.create_collection(name="test_v12_smoke_eph")
            collection.add(documents=["TruthNet V12"], ids=["doc_1"])
            results = collection.query(query_texts=["V12"], n_results=1)
            assert results is not None
            ok, msg = check("ChromaDB smoke (ephemeral client)", True)
        except Exception as e2:
            ok, msg = check("ChromaDB smoke", False, str(e2)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- Pydantic V2 smoke ---
    try:
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            name: str = Field(..., description="测试")
            value: int = Field(default=42)

        m = TestModel(name="TruthNet")
        data = m.model_dump()
        assert data["name"] == "TruthNet"
        assert data["value"] == 42
        ok, msg = check("Pydantic V2 model roundtrip", True)
    except Exception as e:
        ok, msg = check("Pydantic V2 model roundtrip", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- LangGraph smoke ---
    try:
        from langgraph.graph import StateGraph

        from typing import TypedDict

        class MiniState(TypedDict):
            count: int

        _graph = StateGraph(MiniState)
        ok, msg = check("LangGraph StateGraph mini", True)
    except Exception as e:
        ok, msg = check("LangGraph StateGraph mini", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- FastAPI app import ---
    try:
        from app.main import app

        assert app.title == "TruthNet API"
        ok, msg = check("FastAPI app import", True, f"title={app.title}")
    except Exception as e:
        ok, msg = check("FastAPI app import", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    # --- V12 adapter imports ---
    try:
        from app.infrastructure.persistence.sqlite.company_repository import (
            SQLiteCompanyRepository,
        )
        from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph
        from app.infrastructure.llm.mock.provider import MockLLMProvider

        assert SQLiteCompanyRepository is not None
        assert NetworkXEquityGraph is not None
        assert MockLLMProvider is not None
        ok, msg = check("V12 lite adapter imports", True)
    except Exception as e:
        ok, msg = check("V12 lite adapter imports", False, str(e)[:80])
    lines.append(msg)
    if not ok:
        all_ok = False

    if all_ok:
        lines.append(f"\n  {PASS} | All smoke tests passed")
    else:
        lines.append(f"\n  {FAIL} | Some smoke tests failed")

    return lines


def check_external_services(profile: str = "full") -> list[str]:
    """可选的外部服务连接检测（不阻塞基础验收）."""
    lines: list[str] = []
    lines.append("\n--- Optional: External Service Connectivity ---")

    from app.core.config import settings

    # MySQL
    if settings.MYSQL_PASSWORD and profile == "full":
        try:
            from app.infrastructure.persistence.mysql.company_repository import (
                MySQLCompanyRepository,
            )

            repo = MySQLCompanyRepository()
            ok = repo.check_connection()
            status = PASS if ok else FAIL
            lines.append(f"  {status} | MySQL connection")
        except Exception as e:
            lines.append(f"  {FAIL} | MySQL connection — {e}")
    else:
        lines.append("  ℹ️ NOT_RUN | MySQL — 未配置密码或非 full profile")

    # Neo4j
    if settings.NEO4J_PASSWORD and profile == "full":
        try:
            from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

            graph = Neo4jEquityGraph()
            ok = graph.check_connection()
            status = PASS if ok else FAIL
            lines.append(f"  {status} | Neo4j connection")
        except Exception as e:
            lines.append(f"  {FAIL} | Neo4j connection — {e}")
    else:
        lines.append("  ℹ️ NOT_RUN | Neo4j — 未配置密码或非 full profile")

    return lines


def main():
    parser = argparse.ArgumentParser(description="V12 技术栈验证")
    parser.add_argument("--ci", action="store_true", help="CI 模式")
    parser.add_argument(
        "--profile", choices=["lite", "full"], default="lite", help="运行 profile"
    )
    parser.add_argument(
        "--check-external", action="store_true", help="检测外部服务连接（可选）"
    )
    parser.add_argument("--output", type=str, default=None, help="输出报告到文件")
    args = parser.parse_args()

    all_lines: list[str] = []
    all_lines.append("=" * 60)
    mode_tags = []
    if args.ci:
        mode_tags.append("CI")
    if args.profile == "full":
        mode_tags.append("FULL")
    tag = f" [{', '.join(mode_tags)}]" if mode_tags else ""
    all_lines.append(f"  TruthNet V12 Stack Verification{tag}")
    all_lines.append("=" * 60)

    fail_count = 0

    # 1. Environment check
    all_lines.append("\n--- 1. Environment ---")
    for line in check_env(args.ci):
        all_lines.append(line)
        if "FAIL" in line:
            fail_count += 1

    # 2. Core deps (old stack)
    all_lines.append("\n--- 2. Core Dependencies (Prompt1-4 baseline) ---")
    for line in check_core_deps():
        all_lines.append(line)
        if "FAIL" in line:
            fail_count += 1

    # 3. V12 new deps
    all_lines.append("\n--- 3. V12 New Dependencies ---")
    for line in check_v12_deps():
        all_lines.append(line)
        if "FAIL" in line:
            fail_count += 1

    # 4. Smoke tests
    all_lines.append("\n--- 4. Minimal Smoke Tests ---")
    for line in run_smoke_tests(args.profile):
        all_lines.append(line)
        if "FAIL" in line:
            fail_count += 1

    # 5. Optional external services
    if args.check_external:
        for line in check_external_services(args.profile):
            all_lines.append(line)

    # Summary
    all_lines.append("\n" + "=" * 60)
    if fail_count == 0:
        all_lines.append(f"  {PASS} | V12 技术栈验证通过")
    else:
        all_lines.append(f"  {FAIL} | V12 技术栈验证失败 ({fail_count} 项)")
    all_lines.append("=" * 60)

    output = "\n".join(all_lines)
    print(output)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8", newline="\n")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
