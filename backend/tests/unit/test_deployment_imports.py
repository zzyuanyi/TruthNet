"""部署工作目录下的导入路径回归测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_industry_fill_imports_from_backend_workdir():
    """Docker/启动脚本仅暴露 backend 时，industry_fill 仍可正常导入。"""
    backend_dir = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app.application.services.industry_fill"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
