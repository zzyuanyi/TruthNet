#!/usr/bin/env python
"""TruthNet 环境检测脚本 (跨平台兼容)

检测项目开发环境是否正确配置。
兼容 Windows / macOS / Linux。

CI 模式:
    python scripts/doctor.py --ci
    - .env 缺失只 warning
    - Node/pnpm 缺失只 warning
    - Git dirty 不报错
    - 虚拟环境检测宽松

Prompt3 新增检查:
    - stdout/stderr UTF-8 支持
    - .gitattributes 存在
    - .editorconfig 存在
    - encoding_path_audit.py --ci 通过
    - Python 3.11.x 精确版本
    - 路径非 ASCII 字符 warning
"""

import argparse
import importlib
import os
import platform
import subprocess
import sys

# 修复 Windows GBK 控制台 Unicode 输出问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """运行命令并返回 (返回码, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=True if sys.platform == "win32" else False,
        )
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        return result.returncode, stdout, stderr
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"
    except OSError:
        # Windows: some commands (e.g. pnpm.CMD) fail with CreateProcess
        return -1, "", "command not found"


def check(label: str, passed: bool, detail: str = "") -> str:
    """格式化检查结果"""
    if passed:
        return f"  [PASS] {label}"
    return f"  [WARN] {label} — {detail}"


def fail(label: str, detail: str = "") -> str:
    """格式化失败结果"""
    return f"  [FAIL] {label} — {detail}"


def main():
    parser = argparse.ArgumentParser(description="TruthNet 环境检测")
    parser.add_argument("--ci", action="store_true", help="CI 模式：放宽部分检查")
    args = parser.parse_args()
    ci_mode: bool = args.ci

    results: list[str] = []
    warnings = 0
    failures = 0

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    mode_label = " [CI 模式]" if ci_mode else ""
    print("=" * 60)
    print(f"  TruthNet — 环境检测 (doctor.py){mode_label}")
    print("=" * 60)

    # ===== 操作系统 =====
    print(f"\n  操作系统: {platform.system()} {platform.release()}")
    print(f"  架构: {platform.machine()}")
    print(f"  Python: {sys.version}")
    print(f"  工作目录: {Path.cwd()}")

    # ===== 工作目录检查 =====
    print("\n--- 工作目录 ---")
    required_files = [
        "README.md",
        "CLAUDE.md",
        "requirements.txt",
        ".python-version",
        ".gitignore",
        ".editorconfig",
        ".gitattributes",
    ]
    for f in required_files:
        exists = (repo_root / f).exists()
        r = check(f"存在 {f}", exists, "文件缺失")
        results.append(r)
        if not exists:
            failures += 1

    # ===== UTF-8 控制台支持 =====
    print("\n--- UTF-8 控制台 ---")
    stdout_ok = True
    try:
        test_str = "✓ UTF-8 测试"
        print(f"  {test_str}")
    except UnicodeEncodeError:
        stdout_ok = False

    if hasattr(sys.stdout, "reconfigure"):
        r = check("stdout 支持 reconfigure (UTF-8 可强制)", True)
    elif stdout_ok:
        r = check("stdout UTF-8 正常", True)
    else:
        r = fail("stdout 不支持 UTF-8 输出", "Windows 可能需要 chcp 65001")
        warnings += 1
    results.append(r)

    # ===== Python 版本 =====
    print("\n--- Python 版本 ---")
    version_file = repo_root / ".python-version"
    if version_file.exists():
        expected = version_file.read_text(encoding="utf-8").strip()
        actual_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        actual_full = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # 精确 3.11 检查
        is_311 = sys.version_info.major == 3 and sys.version_info.minor == 11
        if is_311:
            r = check(
                f"Python 版本: {actual_full} (期望 3.11.x)",
                True,
            )
        else:
            r = fail(
                f"Python 版本: {actual_full}",
                f"期望 3.11.x，当前为 {actual_full}",
            )
            failures += 1
        results.append(r)

        # .python-version 精确匹配
        match = actual_major_minor == expected
        if not match:
            r = check(
                f".python-version 匹配 ({expected})",
                False,
                f"文件期望 {expected}，当前 {actual_major_minor}",
            )
            warnings += 1
            results.append(r)
    else:
        r = check(".python-version", False, "文件缺失")
        results.append(r)
        warnings += 1

    # ===== 路径非 ASCII 检查 =====
    print("\n--- 路径编码 ---")
    cwd_str = str(Path.cwd())
    has_non_ascii = any(ord(c) > 127 for c in cwd_str)
    if has_non_ascii:
        r = check(
            "工作路径包含非 ASCII 字符",
            True,
            "部分工具可能不兼容，建议使用纯 ASCII 路径",
        )
        warnings += 1
    else:
        r = check("工作路径为纯 ASCII", True)
    results.append(r)

    # ===== 虚拟环境 =====
    print("\n--- 虚拟环境 ---")
    in_conda = "CONDA_PREFIX" in os.environ or "CONDA_DEFAULT_ENV" in os.environ
    in_venv = "VIRTUAL_ENV" in os.environ

    if in_conda:
        env_name = os.environ.get("CONDA_DEFAULT_ENV", "unknown")
        env_path = os.environ.get("CONDA_PREFIX", "")
        r = check(f"Conda 环境已激活: {env_name}", True, f"路径: {env_path}")
    elif in_venv:
        env_path = os.environ.get("VIRTUAL_ENV", "")
        r = check(f"venv 环境已激活: {Path(env_path).name}", True, f"路径: {env_path}")
    else:
        if ci_mode:
            r = check(
                "虚拟环境",
                True,
                "CI 使用 setup-python，无需 conda/venv",
            )
        else:
            r = check(
                "虚拟环境",
                False,
                "未检测到 conda 或 venv。建议: conda activate truthnet",
            )
            warnings += 1
    results.append(r)

    # ===== pip 可用性 =====
    print("\n--- pip ---")
    try:
        importlib.import_module("pip")
        r = check("pip 可用", True)
        results.append(r)
    except ImportError:
        r = fail("pip 不可用", "pip 未安装")
        results.append(r)
        failures += 1

    # ===== 关键包 =====
    print("\n--- 关键依赖包 ---")
    key_packages = [
        "fastapi",
        "pydantic",
        "langgraph",
        "langchain_core",
        "networkx",
        "pandas",
        "numpy",
        "sklearn",
        "pytest",
        "httpx",
        "dotenv",
    ]

    for pkg in key_packages:
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "unknown")
            r = check(f"{pkg} ({version})", True)
            results.append(r)
        except ImportError:
            r = fail(f"{pkg} 未安装", "运行: pip install -r requirements.txt")
            results.append(r)
            failures += 1
        except Exception as e:
            r = fail(f"{pkg} 导入异常", str(e)[:60])
            results.append(r)
            failures += 1

    # ===== 环境变量 =====
    print("\n--- 环境文件 ---")
    env_exists = (repo_root / ".env").exists()
    env_example_exists = (repo_root / ".env.example").exists()

    if env_exists:
        r = check(".env 存在", True, "本地环境文件未提交到 Git ✓")
    else:
        r = check(".env 不存在", True, "如需配置，复制 .env.example 为 .env")
    results.append(r)

    if env_example_exists:
        r = check(".env.example 存在", True)
    else:
        if ci_mode:
            r = check(".env.example 缺失", False, "CI 模式下跳过")
            warnings += 1
        else:
            r = fail(".env.example 缺失", "请创建环境变量模板文件")
            failures += 1
    results.append(r)

    # ===== 编码审计 =====
    print("\n--- 编码与路径审计 ---")
    audit_script = repo_root / "scripts" / "encoding_path_audit.py"
    if audit_script.exists():
        code, out, err = run_cmd([sys.executable, str(audit_script), "--ci"])
        if code == 0:
            r = check("encoding_path_audit.py --ci 通过", True)
        else:
            r = fail("encoding_path_audit.py 发现 FAIL 项", err or out[-200:])
            if ci_mode:
                warnings += 1
            else:
                failures += 1
        results.append(r)
    else:
        r = fail("encoding_path_audit.py 缺失", "该脚本应在 Prompt3 中创建")
        results.append(r)
        failures += 1

    # ===== .gitattributes =====
    print("\n--- .gitattributes ---")
    ga = repo_root / ".gitattributes"
    if ga.exists():
        content = ga.read_text(encoding="utf-8")
        if "text=auto" in content or "text = auto" in content:
            r = check(".gitattributes 存在且配置了 text=auto", True)
        else:
            r = check(".gitattributes 存在但缺少 text=auto", False)
            warnings += 1
        results.append(r)
    else:
        r = fail(".gitattributes 缺失", "请创建 .gitattributes 确保 LF 换行")
        results.append(r)
        failures += 1

    # ===== 文档 =====
    print("\n--- 项目文档 ---")
    doc_files = [
        "docs/API_CONTRACT.md",
        "docs/DATA_CONTRACT.md",
        "docs/ENVIRONMENT.md",
        "docs/GIT_WORKFLOW.md",
        "docs/SOFTWARE_ENGINEERING.md",
    ]
    for f in doc_files:
        exists = (repo_root / f).exists()
        r = check(f"存在 {f}", exists, "文件缺失")
        results.append(r)
        if not exists:
            warnings += 1

    # ===== Claude Code Skills =====
    print("\n--- Claude Code Skills ---")
    skills_dir = repo_root / ".claude" / "skills"
    if skills_dir.exists():
        skill_count = len([d for d in skills_dir.iterdir() if d.is_dir()])
        r = check(f".claude/skills/ 存在 ({skill_count} 个 skill 目录)", True)
    else:
        r = check(".claude/skills/", False, "目录缺失")
        warnings += 1
    results.append(r)

    # ===== Git =====
    print("\n--- Git ---")
    code, out, err = run_cmd(["git", "--version"])
    if code == 0:
        r = check(f"Git 已安装: {out}", True)
    else:
        r = fail("Git 未安装或不在 PATH 中", err)
        failures += 1
    results.append(r)

    # 当前分支
    git_dir = repo_root / ".git"
    if git_dir.exists():
        code, out, err = run_cmd(["git", "branch", "--show-current"])
        if code == 0 and out:
            r = check(f"当前分支: {out}", True)

            # 检查是否在 main
            if out == "main" and not ci_mode:
                r = check(
                    f"当前分支: {out}",
                    True,
                    "⚠️  不建议在 main 上直接开发，请切换到 dev 或 feature 分支",
                )
                warnings += 1
        else:
            r = check("当前分支", False, err)
        results.append(r)

        # 未提交更改
        code, out, err = run_cmd(["git", "status", "--porcelain"])
        if code == 0:
            if out:
                changed = len(out.strip().split("\n"))
                if ci_mode:
                    r = check(f"未提交更改: {changed} 个文件 (CI 模式不计为问题)", True)
                else:
                    r = check(
                        f"未提交更改: {changed} 个文件", True, "请确认是否需要提交"
                    )
            else:
                r = check("无未提交更改", True)
            results.append(r)
        else:
            r = check("git status", False, err)
            results.append(r)
    else:
        r = check("Git 仓库", False, "未找到 .git 目录")
        results.append(r)
        warnings += 1

    # ===== Git 安全检查 =====
    print("\n--- Git 安全检查 ---")
    safety_script = repo_root / "scripts" / "git_safety_check.py"
    if safety_script.exists():
        code, out, err = run_cmd([sys.executable, str(safety_script), "--ci"])
        if code == 0:
            r = check("git_safety_check.py --ci 通过", True)
        else:
            r = fail("git_safety_check.py 发现风险项", err or out[-200:])
            if ci_mode:
                warnings += 1
            else:
                failures += 1
        results.append(r)
    else:
        r = check(
            "git_safety_check.py 不存在 (Prompt3 新增)", False, "将在 Prompt3 中创建"
        )
        warnings += 1
        results.append(r)

    # ===== CI 状态脚本 =====
    print("\n--- CI 状态检查 ---")
    ci_status_script = repo_root / "scripts" / "ci_status.py"
    if ci_status_script.exists():
        r = check("scripts/ci_status.py 存在", True)
    else:
        r = fail("scripts/ci_status.py 缺失", "请创建 CI 状态检查脚本")
        failures += 1
    results.append(r)

    # gh CLI 检查
    import shutil

    gh_available = bool(shutil.which("gh"))
    if gh_available:
        r = check("GitHub CLI (gh) 已安装", True)
    else:
        r = check(
            "GitHub CLI (gh) 未安装",
            False,
            "建议安装 gh CLI 以便自动检查 CI 状态。安装: https://cli.github.com",
        )
        warnings += 1
    results.append(r)

    # ===== V12 Profile 检查 =====
    print("\n--- V12 Profile ---")
    try:
        from dotenv import load_dotenv

        load_dotenv(repo_root / ".env.example")
    except Exception:
        pass

    profile = os.environ.get("TRUTHNET_PROFILE", "lite")
    r = check(f"TRUTHNET_PROFILE = {profile}", True, "lite=默认开发/CI, full=正式演示")
    results.append(r)

    sql_backend = os.environ.get("SQL_BACKEND", "sqlite")
    r = check(f"SQL_BACKEND = {sql_backend}", True)
    results.append(r)

    graph_backend = os.environ.get("GRAPH_BACKEND", "networkx")
    r = check(f"GRAPH_BACKEND = {graph_backend}", True)
    results.append(r)

    vector_backend = os.environ.get("VECTOR_BACKEND", "chroma")
    r = check(f"VECTOR_BACKEND = {vector_backend}", True)
    results.append(r)

    llm_backend = os.environ.get("LLM_BACKEND", "mock")
    r = check(f"LLM_BACKEND = {llm_backend}", True)
    results.append(r)

    # ===== V12 新增依赖检查 =====
    print("\n--- V12 新增依赖 ---")
    v12_packages = [
        "sqlalchemy",
        "alembic",
        "pymysql",
        "neo4j",
        "structlog",
        "jsonschema",
    ]

    for pkg in v12_packages:
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "unknown")
            r = check(f"{pkg} ({version})", True)
        except ImportError:
            r = check(
                f"{pkg} 未安装",
                False,
                "V12 新增依赖，运行: pip install -r requirements.txt",
            )
            if not ci_mode:
                warnings += 1
        except Exception as e:
            r = check(f"{pkg} 导入异常", False, str(e)[:60])
            warnings += 1
        results.append(r)

    # MySQL driver import 检查（不要求服务在线）
    try:
        import pymysql  # noqa: F401 — 导入检查

        r = check("PyMySQL driver 可用", True)
    except ImportError:
        r = check("PyMySQL driver 未安装", False, "full profile 需要")
        if not ci_mode:
            warnings += 1
    results.append(r)

    # Neo4j driver import 检查（不要求服务在线）
    try:
        import neo4j

        neo4j_ver = getattr(neo4j, "__version__", "unknown")
        r = check(f"Neo4j driver ({neo4j_ver})", True)
    except ImportError:
        r = check("Neo4j driver 未安装", False, "full profile 需要")
        if not ci_mode:
            warnings += 1
    results.append(r)

    # ===== V12 契约文件检查 =====
    print("\n--- V12 契约文件 ---")
    v12_contract_files = [
        "docs/API_CONTRACT_V1.md",
        "docs/WEBSOCKET_CONTRACT_V1.md",
        "docs/FRONTEND_DESIGN.md",
    ]
    for f in v12_contract_files:
        exists = (repo_root / f).exists()
        r = check(f"存在 {f}", exists, "V12 契约文件缺失")
        results.append(r)
        if not exists:
            warnings += 1

    # ===== V12 路由检查 =====
    print("\n--- V12 路由 ---")
    try:
        main_py = repo_root / "backend" / "app" / "main.py"
        if main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            has_healthz = "/healthz" in content or "healthz" in content.lower()
            has_readyz = "/readyz" in content or "readyz" in content.lower()
            has_companies = "/companies" in content
            r = check("/healthz 路由存在", has_healthz, "V12 健康检查端点")
            results.append(r)
            if not has_healthz:
                warnings += 1
            r = check("/readyz 路由存在", has_readyz, "V12 就绪检查端点")
            results.append(r)
            if not has_readyz:
                warnings += 1
            r = check("/api/v1/companies 路由存在", has_companies, "V12 公司搜索端点")
            results.append(r)
            if not has_companies:
                warnings += 1
        else:
            r = fail("backend/app/main.py 缺失", "无法检查 V12 路由")
            results.append(r)
            failures += 1
    except Exception as e:
        r = fail("V12 路由检查异常", str(e)[:60])
        results.append(r)
        failures += 1

    # ===== 前端工具 (optional) =====
    print("\n--- 前端工具 (optional) ---")
    frontend_initialized = (repo_root / "frontend" / "package.json").exists()

    code, out, _ = run_cmd(["node", "--version"])
    if code == 0:
        r = check(f"Node.js 已安装: {out}", True)
    else:
        if frontend_initialized and not ci_mode:
            r = fail("Node.js 未安装", "前端已初始化，需要 Node.js")
            failures += 1
        else:
            r = check("Node.js 未安装", False, "前端开发需要，后端不受影响")
            if not ci_mode:
                warnings += 1
    results.append(r)

    code, out, _ = run_cmd(["pnpm", "--version"])
    if code == 0:
        r = check(f"pnpm 已安装: {out}", True)
    else:
        if frontend_initialized and not ci_mode:
            r = fail("pnpm 未安装", "前端已初始化，需要 pnpm")
            failures += 1
        else:
            r = check("pnpm 未安装", False, "前端开发需要，后端不受影响")
            if not ci_mode:
                warnings += 1
    results.append(r)

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("  检测结果汇总")
    print("=" * 60)

    total = len(results)
    passes = total - warnings - failures

    print(f"  ✅ PASS:  {passes}/{total}")
    if warnings > 0:
        print(f"  ⚠️  WARN:  {warnings}/{total}")
    if failures > 0:
        print(f"  ❌ FAIL:  {failures}/{total}")

    print("=" * 60)

    if failures > 0:
        print("\n  ⚠️  存在 FAIL 项，请在继续开发前修复。")
        print("  通常运行以下命令即可修复：")
        print("    pip install -r requirements.txt")
        print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
