#!/usr/bin/env python
"""TruthNet 轻量环境检查

doctor.py 的轻量版本，快速检查最关键的几项。
"""

import os
import sys
from pathlib import Path

# 修复 Windows GBK 控制台 Unicode 输出问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    ok = True

    # 检查 requirements.txt
    req = repo_root / "requirements.txt"
    if req.exists():
        print("[OK] requirements.txt 存在")
    else:
        print("[FAIL] requirements.txt 缺失")
        ok = False

    # 检查 .python-version
    pv = repo_root / ".python-version"
    if pv.exists():
        expected = pv.read_text().strip()
        actual = f"{sys.version_info.major}.{sys.version_info.minor}"
        if expected == actual:
            print(f"[OK] Python {actual}")
        else:
            print(f"[WARN] Python 版本: 期望 {expected}，当前 {actual}")
    else:
        print("[WARN] .python-version 缺失")

    # 检查虚拟环境
    in_conda = "CONDA_PREFIX" in os.environ or "CONDA_DEFAULT_ENV" in os.environ
    in_venv = "VIRTUAL_ENV" in os.environ
    if in_conda:
        print(f"[OK] Conda 环境: {os.environ.get('CONDA_DEFAULT_ENV', '?')}")
    elif in_venv:
        print("[OK] venv 环境已激活")
    else:
        print("[WARN] 未检测到虚拟环境")

    # 检查工作目录
    if (repo_root / "CLAUDE.md").exists():
        print("[OK] 工作目录正确")
    else:
        print("[FAIL] CLAUDE.md 缺失，工作目录可能错误")
        ok = False

    if not ok:
        print("\n请运行完整检测: python scripts/doctor.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
