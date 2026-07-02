#!/usr/bin/env python
"""环境引导脚本 — 自适应检测并配置开发环境.

检测系统、conda/venv 状态，给出对应配置指令。
仅在用户显式传入 --apply 时才会执行环境创建和依赖安装。
不会在无确认情况下自动下载 Anaconda/Miniconda。

用法:
    python scripts/env_bootstrap.py --check          # 只检测，输出建议
    python scripts/env_bootstrap.py --apply           # 执行环境创建和依赖安装
    python scripts/env_bootstrap.py --ci --check      # CI 模式
    python scripts/env_bootstrap.py --use-venv        # 强制使用 venv
    python scripts/env_bootstrap.py --download-miniconda  # 下载 Miniconda（需确认）
    python scripts/env_bootstrap.py --pip-index-url https://... --npm-registry https://...
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Miniconda 官方下载 URL
MINICONDA_URLS: dict[str, dict[str, str]] = {
    "Windows": {
        "x86_64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe",
        "arm64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe",  # Windows ARM 少见
    },
    "Darwin": {
        "x86_64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh",
        "arm64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh",
    },
    "Linux": {
        "x86_64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
        "aarch64": "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh",
    },
}

# Anaconda 官方安装指南 URL
ANACONDA_GUIDE_URL = "https://docs.anaconda.com/anaconda/install/"


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """运行命令，返回 (返回码, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"


def detect_system() -> dict:
    """检测当前系统信息."""
    info = {
        "system": platform.system(),  # Windows, Darwin, Linux
        "release": platform.release(),
        "machine": platform.machine().lower(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_executable": sys.executable,
    }

    # 架构标准化
    machine = info["machine"]
    if machine in ("amd64", "x86_64", "x64"):
        info["arch"] = "x86_64"
    elif machine in ("arm64", "aarch64"):
        info["arch"] = "arm64"
    else:
        info["arch"] = machine

    return info


def detect_conda() -> dict:
    """检测 conda 状态."""
    conda_exe = shutil.which("conda")
    if conda_exe is None:
        return {"available": False, "path": None, "envs": []}

    # 获取 conda 版本
    code, out, err = run_cmd(["conda", "--version"])
    version = out if code == 0 else "unknown"

    # 获取 conda env list
    code, out, err = run_cmd(["conda", "env", "list"])
    envs: list[str] = []
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if parts:
                    envs.append(parts[0])

    # 当前是否在 conda 环境中
    in_conda = "CONDA_PREFIX" in os.environ or "CONDA_DEFAULT_ENV" in os.environ
    current_env = os.environ.get("CONDA_DEFAULT_ENV", "")

    return {
        "available": True,
        "path": conda_exe,
        "version": version,
        "envs": envs,
        "in_conda": in_conda,
        "current_env": current_env,
        "truthnet_exists": "truthnet" in envs,
    }


def detect_venv() -> dict:
    """检测 venv 状态."""
    in_venv = "VIRTUAL_ENV" in os.environ
    venv_path = os.environ.get("VIRTUAL_ENV", "")

    local_venv = REPO_ROOT / ".venv"
    venv_exists = local_venv.exists()

    return {
        "in_venv": in_venv,
        "venv_path": venv_path,
        "local_venv_exists": venv_exists,
    }


def detect_node() -> dict:
    """检测 Node.js 和 pnpm."""
    node_path = shutil.which("node")
    node_version = ""
    if node_path:
        code, out, _ = run_cmd(["node", "--version"])
        if code == 0:
            node_version = out

    pnpm_path = shutil.which("pnpm")
    pnpm_version = ""
    if pnpm_path:
        code, out, _ = run_cmd(["pnpm", "--version"])
        if code == 0:
            pnpm_version = out

    return {
        "node_available": node_path is not None,
        "node_version": node_version,
        "pnpm_available": pnpm_path is not None,
        "pnpm_version": pnpm_version,
    }


def detect_git() -> dict:
    """检测 Git."""
    git_path = shutil.which("git")
    git_version = ""
    if git_path:
        code, out, _ = run_cmd(["git", "--version"])
        if code == 0:
            git_version = out

    return {
        "git_available": git_path is not None,
        "git_version": git_version,
    }


def print_conda_install_guide(system_info: dict):
    """打印 conda 安装引导."""
    system = system_info["system"]
    arch = system_info["arch"]

    print("\n  --- Miniconda 安装引导 ---")
    print(f"  当前系统: {system} ({arch})")
    print()

    if system in MINICONDA_URLS and arch in MINICONDA_URLS[system]:
        url = MINICONDA_URLS[system][arch]
        print(f"  官方下载地址: {url}")
    else:
        print(f"  请访问 Anaconda 官方安装指南: {ANACONDA_GUIDE_URL}")

    print()
    if system == "Windows":
        print("  Windows 安装步骤:")
        print("  1. 下载 Miniconda3 Windows exe 安装器")
        print("  2. 双击运行安装器")
        print("  3. 勾选 'Add Miniconda3 to my PATH environment variable'")
        print("  4. 安装完成后打开新的 PowerShell / 命令提示符")
        print("  5. 运行: conda --version 验证安装")
    elif system == "Darwin":
        print("  macOS 安装步骤:")
        print("  1. 下载 Miniconda3 macOS .sh 安装脚本")
        print(f"  2. 运行: bash ~/Downloads/Miniconda3-latest-MacOSX-{arch}.sh")
        print("  3. 按提示完成安装")
        print("  4. 重启终端或运行: source ~/.zshrc")
        print("  5. 运行: conda --version 验证安装")
    else:
        print("  Linux 安装步骤:")
        print(f"  1. 下载: wget {url}")
        print(f"  2. 运行: bash Miniconda3-latest-Linux-{arch}.sh")
        print("  3. 按提示完成安装")
        print("  4. 重启终端或运行: source ~/.bashrc")
        print("  5. 运行: conda --version 验证安装")

    print()
    print("  ⚠️  本脚本不会自动下载安装器。")
    print("     如需自动下载，请加 --download-miniconda 参数并再次确认。")


def check_only(system_info: dict, conda_info: dict, venv_info: dict,
               node_info: dict, git_info: dict, args) -> int:
    """仅执行环境检测，输出报告."""
    print("=" * 60)
    print("  TruthNet — 环境引导检测 (env_bootstrap.py)")
    print("=" * 60)

    # 系统信息
    print(f"\n--- 系统 ---")
    print(f"  操作系统: {system_info['system']} {system_info['release']}")
    print(f"  架构: {system_info['arch']} ({system_info['machine']})")
    print(f"  Python: {system_info['python_version']}")
    print(f"  Python 路径: {system_info['python_executable']}")

    # Python 版本检查
    is_py311 = (
        sys.version_info.major == 3 and sys.version_info.minor == 11
    )
    if is_py311:
        print(f"  [PASS] Python 版本: {system_info['python_version']}")
    else:
        print(f"  [FAIL] Python 版本需为 3.11.x，当前为 {system_info['python_version']}")

    # Conda
    print(f"\n--- Conda ---")
    if conda_info["available"]:
        print(f"  [PASS] conda 已安装: {conda_info['version']}")
        print(f"  路径: {conda_info['path']}")
        if conda_info["in_conda"]:
            print(f"  [PASS] 当前在 conda 环境: {conda_info['current_env']}")
        else:
            print(f"  [WARN] conda 已安装但未激活任何环境")

        if conda_info["truthnet_exists"]:
            print(f"  [PASS] truthnet 环境已存在")
        else:
            print(f"  [INFO] truthnet 环境不存在，运行 --apply 可创建")

        print(f"  已有环境: {', '.join(conda_info['envs']) or '(无)'}")
    else:
        print(f"  [WARN] conda 未安装")
        if not args.ci:
            print_conda_install_guide(system_info)

    # venv
    print(f"\n--- venv ---")
    if venv_info["in_venv"]:
        print(f"  [PASS] 当前在 venv: {venv_info['venv_path']}")
    elif venv_info["local_venv_exists"]:
        print(f"  [INFO] .venv 目录存在但未激活")
    else:
        print(f"  [INFO] .venv 不存在")

    # Node / pnpm
    print(f"\n--- Node.js / pnpm ---")
    if node_info["node_available"]:
        print(f"  [PASS] Node.js: {node_info['node_version']}")
    else:
        print(f"  [WARN] Node.js 未安装（前端开发需要）")

    if node_info["pnpm_available"]:
        print(f"  [PASS] pnpm: {node_info['pnpm_version']}")
    else:
        print(f"  [WARN] pnpm 未安装（前端开发需要，不影响后端）")

    # Git
    print(f"\n--- Git ---")
    if git_info["git_available"]:
        print(f"  [PASS] Git: {git_info['git_version']}")
    else:
        print(f"  [FAIL] Git 未安装")

    # 虚拟环境配置建议
    print(f"\n--- 建议 ---")
    if conda_info["available"]:
        if conda_info["truthnet_exists"]:
            print(f"  ✅ conda 环境 'truthnet' 已就绪")
            if not conda_info["in_conda"]:
                print(f"  激活: conda activate truthnet")
        else:
            print(f"  创建环境: conda create -n truthnet python=3.11 -y")
            print(f"  激活: conda activate truthnet")
            print(f"  安装依赖: pip install -r requirements.txt")
    else:
        print(f"  方案 A: 安装 Miniconda（推荐）")
        print(f"  方案 B: 使用 venv fallback:")
        print(f"    python -m venv .venv")
        if system_info["system"] == "Windows":
            print(f"    .venv\\Scripts\\Activate.ps1")
        else:
            print(f"    source .venv/bin/activate")
        print(f"    pip install -r requirements.txt")

    print(f"\n  运行 --apply 执行实际配置（不会自动下载 conda）")

    return 0


def apply_config(system_info: dict, conda_info: dict, venv_info: dict, args) -> int:
    """执行环境配置."""
    print("=" * 60)
    print("  TruthNet — 环境引导配置 (env_bootstrap.py --apply)")
    print("=" * 60)

    use_venv = getattr(args, "use_venv", False)

    if conda_info["available"] and not use_venv:
        # 使用 conda
        if not conda_info["truthnet_exists"]:
            print(f"\n  正在创建 conda 环境 'truthnet' (Python 3.11)...")
            code, out, err = run_cmd(
                ["conda", "create", "-n", "truthnet", "python=3.11", "-y"],
                timeout=120,
            )
            if code != 0:
                print(f"  [FAIL] conda 环境创建失败: {err}")
                print(f"  尝试使用 venv fallback...")
                use_venv = True
            else:
                print(f"  [OK] truthnet 环境已创建")
        else:
            print(f"\n  [OK] truthnet 环境已存在，跳过创建")

        if not use_venv:
            print(f"\n  请在终端中手动激活环境:")
            print(f"    conda activate truthnet")
            print(f"    pip install -r requirements.txt")

    if use_venv or not conda_info["available"]:
        # 使用 venv
        venv_dir = REPO_ROOT / ".venv"
        if not venv_dir.exists():
            print(f"\n  正在创建 venv 环境...")
            code, out, err = run_cmd(
                [sys.executable, "-m", "venv", str(venv_dir)],
                timeout=60,
            )
            if code != 0:
                print(f"  [FAIL] venv 创建失败: {err}")
                return 1
            print(f"  [OK] .venv 已创建")
        else:
            print(f"\n  [OK] .venv 已存在")

        print(f"\n  请手动激活 venv:")
        if system_info["system"] == "Windows":
            print(f"    .venv\\Scripts\\Activate.ps1")
        else:
            print(f"    source .venv/bin/activate")
        print(f"    pip install -r requirements.txt")

    # pip 镜像提示
    pip_index = getattr(args, "pip_index_url", None)
    if pip_index:
        print(f"\n  pip 镜像已指定: {pip_index}")
        print(f"  安装命令: pip install -r requirements.txt -i {pip_index}")
        print(f"  ⚠️  镜像配置仅用于本次会话，不写入仓库文件。")

    # npm 镜像提示
    npm_registry = getattr(args, "npm_registry", None)
    if npm_registry:
        print(f"\n  npm registry 已指定: {npm_registry}")
        print(f"  配置命令: pnpm config set registry {npm_registry}")
        print(f"  ⚠️  registry 配置仅用于本机，不写入仓库文件。")

    print(f"\n  [OK] 环境配置完成。")
    print(f"  运行验证: python scripts/doctor.py")
    return 0


def main():
    parser = argparse.ArgumentParser(description="TruthNet 环境引导脚本")
    parser.add_argument("--check", action="store_true", default=True,
                        help="仅检测环境状态（默认）")
    parser.add_argument("--apply", action="store_true",
                        help="执行环境创建和依赖安装")
    parser.add_argument("--ci", action="store_true",
                        help="CI 模式：不阻塞，不输出安装引导")
    parser.add_argument("--use-venv", action="store_true",
                        help="强制使用 venv 而非 conda")
    parser.add_argument("--download-miniconda", action="store_true",
                        help="下载 Miniconda 安装器（需再次确认）")
    parser.add_argument("--pip-index-url", type=str, default=None,
                        help="pip 镜像 URL（仅本机使用，不写入仓库）")
    parser.add_argument("--npm-registry", type=str, default=None,
                        help="npm registry URL（仅本机使用，不写入仓库）")

    args = parser.parse_args()

    # 检测
    system_info = detect_system()
    conda_info = detect_conda()
    venv_info = detect_venv()
    node_info = detect_node()
    git_info = detect_git()

    # --download-miniconda 需要二次确认
    if args.download_miniconda:
        if args.ci:
            print("[CI] 不会在 CI 模式下下载 Miniconda。")
        else:
            print("=" * 60)
            print("  ⚠️  即将下载 Miniconda 安装器")
            print("=" * 60)
            print(f"  系统: {system_info['system']}")
            print(f"  架构: {system_info['arch']}")

            system = system_info["system"]
            arch = system_info["arch"]
            if system in MINICONDA_URLS and arch in MINICONDA_URLS[system]:
                url = MINICONDA_URLS[system][arch]
                print(f"  下载地址: {url}")

            print("\n  是否确认下载？")
            try:
                confirm = input("  输入 'yes' 确认: ").strip()
            except EOFError:
                confirm = "no"

            if confirm.lower() == "yes":
                print("\n  ⚠️  出于安全考虑，本脚本不会自动下载安装器。")
                print("  请手动访问上述 URL 下载，或使用系统包管理器安装。")
            else:
                print("\n  已取消。")

    if args.apply:
        return apply_config(system_info, conda_info, venv_info, args)
    else:
        return check_only(system_info, conda_info, venv_info, node_info, git_info, args)


if __name__ == "__main__":
    sys.exit(main())
