"""数据导入完整链路：alembic → MySQL → Neo4j → ChromaDB
============================================================
一键执行全流程数据导入。每步也可独立执行。

用法:
  python scripts/import_all.py                  # 全量导入（alembic + MySQL + Neo4j + ChromaDB）
  python scripts/import_all.py --step alembic   # 仅 alembic 迁移
  python scripts/import_all.py --step mysql     # 仅 MySQL 入库
  python scripts/import_all.py --step neo4j     # 仅 Neo4j 图谱
  python scripts/import_all.py --step chroma    # 仅 ChromaDB 向量化（约 3 小时）
  python scripts/import_all.py --skip chroma    # 全量但跳过 ChromaDB

注意事项:
  - ChromaDB 步骤需下载 BGE-small-zh-v1.5 模型（首次约 500MB），纯 CPU 约 2-3 小时
  - Neo4j 步骤需 Java 17+ 和运行中的 Neo4j 实例
  - MySQL 步骤需 MySQL 8.0+ 运行中
"""

import io
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc)

# ── 步骤定义 ──
STEPS = {
    "alembic": {
        "name": "Alembic Migration",
        "desc": "运行数据库迁移（建表/改表）",
        "cmd": [sys.executable, "-m", "alembic", "upgrade", "head"],
        "cwd": str(PROJECT_ROOT),
        "timeout_min": 2,
    },
    "mysql": {
        "name": "MySQL 全量入库",
        "desc": "导入 companies/三表/股东/公告/研报 共 7 表",
        "cmd": [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "task1_mysql_import.py"),
        ],
        "cwd": str(PROJECT_ROOT),
        "timeout_min": 30,
    },
    "neo4j": {
        "name": "Neo4j 股权图谱",
        "desc": "导入康美 fixture 至 Neo4j 图数据库",
        "cmd": [
            sys.executable,
            "-c",
            (
                "import asyncio; from app.infrastructure.graph.neo4j.importer import main_import; "
                "print(asyncio.run(main_import(source='fixture', mock=True)))"
            ),
        ],
        "cwd": str(PROJECT_ROOT / "backend"),
        "timeout_min": 5,
    },
    "chroma": {
        "name": "ChromaDB 研报向量化",
        "desc": "55K 研报 → 147K 文本块 → BGE 向量嵌入（⚠ 纯 CPU 约 2-3 小时）",
        "cmd": [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "task3_chromadb_import.py"),
        ],
        "cwd": str(PROJECT_ROOT),
        "timeout_min": 240,
    },
}

STEP_ORDER = ["alembic", "mysql", "neo4j", "chroma"]


def log(msg: str) -> None:
    print(msg, flush=True)


def _banner(title: str) -> None:
    log(f"\n{'='*60}")
    log(f"  {title}")
    log(f"{'='*60}")


def _run_step(step_key: str) -> bool:
    """执行单步，返回是否成功."""
    info = STEPS[step_key]
    _banner(f"{step_key.upper()} — {info['name']}")
    log(f"  {info['desc']}")
    log(f"  Timeout: {info['timeout_min']} min")

    t0 = time.time()
    try:
        result = subprocess.run(
            info["cmd"],
            cwd=info["cwd"],
            capture_output=False,
            timeout=info["timeout_min"] * 60,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            check=False,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            log(f"  ✓ {info['name']} — PASS ({elapsed/60:.1f} min)")
            return True
        else:
            log(
                f"  ✗ {info['name']} — FAILED (exit={result.returncode}, {elapsed/60:.1f} min)"
            )
            return False
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        log(
            f"  ✗ {info['name']} — TIMEOUT ({elapsed/60:.1f} min > {info['timeout_min']} min)"
        )
        return False
    except FileNotFoundError as e:
        log(f"  ✗ {info['name']} — COMMAND NOT FOUND: {e}")
        return False


# ====================================================================
# Prerequisites Check
# ====================================================================


def check_prereqs(requested_steps: set[str]) -> bool:
    """检查所需步骤的前置条件."""
    _banner("PRECHECK — Prerequisites")

    all_ok = True

    # Python
    log(
        f"  Python: {sys.executable} ({sys.version_info.major}.{sys.version_info.minor})"
    )

    # Data files (required for mysql step)
    if "mysql" in requested_steps:
        data_dir = PROJECT_ROOT / "data" / "raw" / "比赛数据"
        missing = []
        for sub, fname in [
            ("4", "asharebalancesheet_202605261517.csv"),
            ("4", "asharecashflow_202605261518.csv"),
            ("4", "ashareincome_202605261519.csv"),
            ("2", "clean.xlsx"),
            ("3", "clean.xlsx"),
            ("5", "rr_main_202605281537.csv"),
        ]:
            if not (data_dir / sub / fname).exists():
                missing.append(f"{sub}/{fname}")
        if missing:
            log(f"  ✗ Missing data files: {missing}")
            all_ok = False
        else:
            log(f"  ✓ Data files ({data_dir})")

    # MySQL (required for alembic + mysql + chroma)
    if {"alembic", "mysql", "chroma"} & requested_steps:
        try:
            import pymysql

            conn = pymysql.connect(
                host="localhost",
                port=3306,
                user="truthnet",
                password="truthnet123",
                database="truthnet",
                connect_timeout=5,
            )
            conn.close()
            log("  ✓ MySQL (localhost:3306)")
        except (OSError, ImportError) as e:
            log(f"  ✗ MySQL: {e}")
            all_ok = False

    # Neo4j (required for neo4j step)
    if "neo4j" in requested_steps:
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver("bolt://localhost:7687")
            driver.verify_connectivity()
            driver.close()
            log("  ✓ Neo4j (bolt://localhost:7687)")
        except (OSError, ImportError) as e:
            log(f"  ✗ Neo4j: {e}")
            all_ok = False

    return all_ok


# ====================================================================
# Main
# ====================================================================


def main():
    # 解析参数
    args = sys.argv[1:]
    step_filter: str | None = None
    skip_steps: set[str] = set()

    i = 0
    while i < len(args):
        if args[i] == "--step" and i + 1 < len(args):
            step_filter = args[i + 1]
            i += 2
        elif args[i] == "--skip" and i + 1 < len(args):
            skip_steps.add(args[i + 1])
            i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            return
        else:
            i += 1

    # 确定要执行的步骤
    if step_filter:
        if step_filter not in STEPS:
            log(f"Unknown step: {step_filter}")
            log(f"Valid steps: {', '.join(STEPS)}")
            sys.exit(1)
        steps_to_run = [step_filter]
    else:
        steps_to_run = [s for s in STEP_ORDER if s not in skip_steps]

    log(f"TruthNet Import Pipeline — {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Project: {PROJECT_ROOT}")
    log(f"Steps: {' → '.join(steps_to_run)}")

    # 前置检查
    if not check_prereqs(set(steps_to_run)):
        log("\n✗ Prerequisites check FAILED. Fix issues above and retry.")
        sys.exit(1)

    # 执行步骤
    results: dict[str, bool] = {}
    t_total = time.time()

    for step_key in steps_to_run:
        results[step_key] = _run_step(step_key)

    elapsed_total = time.time() - t_total

    # 报告
    _banner("IMPORT REPORT")
    for sk in steps_to_run:
        status = "✓ PASS" if results[sk] else "✗ FAIL"
        log(f"  {sk:10s} — {status}")
    log(f"\n  Total time: {elapsed_total/60:.1f} min")

    failed = [sk for sk, ok in results.items() if not ok]
    if failed:
        log(f"\n  Failed steps: {', '.join(failed)}")
        sys.exit(1)
    else:
        log("\n  All steps passed!")


if __name__ == "__main__":
    main()
