"""四跳审计脚本测试（v3.6）— driver close 必须被 await.

用 -W error::RuntimeWarning 跑脚本级测试：若 AsyncDriver.close() 未被
await（async close 未调用或 sync 式 close），驱动析构告警将转为错误
导致退出码非零。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "audit_four_hop_paths.py"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _neo4j_available() -> bool:
    from dotenv import dotenv_values
    from neo4j import GraphDatabase

    values = dotenv_values(_REPO_ROOT / ".env")
    uri = os.environ.get("NEO4J_URI") or values.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER") or values.get("NEO4J_USER") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD") or values.get("NEO4J_PASSWORD")
    if not uri or not password:
        return False
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        record = driver.execute_query(
            "MATCH ()-[r:OWNS]->() "
            "WHERE r.graph_version = $graph_version AND r.is_latest = true "
            "RETURN count(r) AS relationships",
            graph_version="equity-2026Q2",
            database_="neo4j",
        ).records[0]
        return int(record["relationships"]) > 0
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()


@pytest.mark.skipif(
    not _neo4j_available(),
    reason="需含 equity-2026Q2 OWNS 关系的 Neo4j 真库",
)
def test_audit_script_runs_without_driver_warning():
    """v3.6：-W error::RuntimeWarning 下脚本须正常完成（driver.close() 已 await）。"""
    proc = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::RuntimeWarning",
            str(_SCRIPTS),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"脚本退出码 {proc.returncode}（RuntimeWarning 转错误?）\n"
        f"stderr: {proc.stderr[-800:]}"
    )
    assert "审计通过" in proc.stdout, proc.stdout[-800:]
