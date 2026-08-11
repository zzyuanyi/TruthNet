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
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
    return bool(os.environ.get("NEO4J_PASSWORD"))


@pytest.mark.skipif(not _neo4j_available(), reason="需 Neo4j 真库")
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
