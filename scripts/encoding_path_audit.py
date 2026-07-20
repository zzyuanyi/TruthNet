#!/usr/bin/env python
"""编码与路径跨平台审计脚本.

扫描项目文件，检查:
1. 文本文件是否可用 UTF-8 解码
2. Python 文件中是否存在裸 `open(` 且无 encoding 参数
3. 是否存在硬编码 Windows 盘符
4. 是否存在硬编码个人路径
5. 是否存在 .env 被 track
6. 是否存在大文件风险

CI 模式:
    python scripts/encoding_path_audit.py --ci
"""

import argparse
import re
import sys

# 修复 Windows GBK 控制台 Unicode 输出问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path


# ============================================================
# 可忽略目录
# ============================================================
IGNORE_DIRS: set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".conda",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "chroma_db",
    "chroma_data",
    "htmlcov",
    "dist",
    "build",
    ".mypy_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    ".local",  # 本地环境数据目录（MySQL/Neo4j/JDK 等）
}

# 可忽略目录内的子路径前缀 (glob 风格)
IGNORE_PATH_PREFIXES: list[str] = [
    "reports/prompt",
    "reports/",  # 报告文件可能包含本机路径引用
    "data/raw/",
    "data/processed/",
    "scripts/services/",  # 本地服务启动脚本（含本机路径）
    ".claude/skills/",  # Skill 文档中的示例代码
    "docs/ENVIRONMENT_REPRODUCTION.md",  # 环境复现文档（含示例路径）
    "docs/SETUP_FULL_PROFILE_WINDOWS.md",  # Windows 部署文档（含示例路径）
    "docs/SOFTWARE_ENGINEERING.md",  # 软件工程规范文档（含反例示例）
    "backend/tests/test_encoding_path_policy.py",  # 编码策略测试（含模式定义）
]

# 大文件阈值 (字节)
LARGE_FILE_THRESHOLD: int = 500 * 1024  # 500KB

# 文本文件扩展名 (尝试 UTF-8 解码检查)
TEXT_EXTENSIONS: set[str] = {
    ".py",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".xml",
    ".csv",
    ".cfg",
    ".ini",
    ".env",
    ".env.example",
    ".sh",
    ".ps1",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
}


def should_ignore(path: Path, repo_root: Path) -> bool:
    """检查路径是否应该被忽略."""
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True

    parts = rel.parts
    if not parts:
        return False

    # 检查是否在可忽略目录内
    for part in parts:
        if part in IGNORE_DIRS:
            return True

    # 检查是否匹配可忽略路径前缀
    rel_str = str(rel).replace("\\", "/")
    for prefix in IGNORE_PATH_PREFIXES:
        if rel_str.startswith(prefix):
            return True

    return False


def iter_text_files(repo_root: Path) -> list[Path]:
    """收集所有可扫描的文本文件."""
    result: list[Path] = []
    for p in repo_root.rglob("*"):
        if p.is_file() and p.suffix in TEXT_EXTENSIONS:
            if not should_ignore(p, repo_root):
                result.append(p)
    return result


def iter_python_files(repo_root: Path) -> list[Path]:
    """收集所有可扫描的 Python 文件."""
    result: list[Path] = []
    for p in repo_root.rglob("*.py"):
        if p.is_file() and not should_ignore(p, repo_root):
            result.append(p)
    return result


# ============================================================
# 辅助判断函数
# ============================================================


def _is_doc_example(line: str) -> bool:
    """判断是否为文档中的反例示例（标记为错误示范的行）."""
    stripped = line.strip()
    # 文档中的错误示范标记
    if "❌" in stripped:
        return True
    if "错误" in stripped:
        return True
    if "禁止" in stripped:
        return True
    # 代码注释中的示例路径
    if "#" in stripped:
        comment_part = stripped.split("#", 1)[1] if "#" in stripped else ""
        if any(word in comment_part for word in ["不要", "反例"]):
            return True
    return False


def _is_pattern_definition(line: str) -> bool:
    """判断是否为搜索模式定义（非实际使用）."""
    stripped = line.strip()
    # 模式定义行：drive_patterns = [...], path_patterns = [...]
    if re.match(
        r"^(drive_patterns|path_patterns|pat\d*|.*_pattern)\s*=\s*\[", stripped
    ):
        return True
    if re.match(r"^(drive_pattern|.*_pattern)\s*=\s*re\.", stripped):
        return True
    return False


def _is_audit_self_diagnostic(line: str) -> bool:
    """判断是否为审计脚本自身的诊断消息（非实际代码问题）."""
    stripped = line.strip()
    # 诊断字符串包含 "裸 open()" 或 "硬编码盘符" 等
    if "裸 open()" in stripped or "bare_open" in stripped:
        return True
    if 'f"硬编码' in stripped or "f'硬编码" in stripped:
        return True
    return False


# ============================================================
# 检查函数
# ============================================================


def check_utf8_decodable(files: list[Path]) -> list[str]:
    """检查文本文件是否可用 UTF-8 解码."""
    issues: list[str] = []
    for fp in files:
        try:
            fp.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            issues.append(f"UTF-8 解码失败: {fp}")
    return issues


def check_bare_open(py_files: list[Path]) -> list[str]:
    """检查 Python 文件中是否存在裸 open() 无 encoding 参数."""
    issues: list[str] = []
    bare_open_pattern = re.compile(r"\bopen\s*\(\s*([^)]*)\)")

    for fp in py_files:
        # 跳过审计脚本自身
        if fp.name == "encoding_path_audit.py":
            continue

        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _is_doc_example(line):
                continue
            if _is_audit_self_diagnostic(line):
                continue
            if '"""' in line or "'''" in line:
                continue

            for match in bare_open_pattern.finditer(line):
                args = match.group(1)
                if "encoding" not in args:
                    if '"rb"' in args or "'rb'" in args:
                        continue
                    if '"wb"' in args or "'wb'" in args:
                        continue
                    if '"ab"' in args or "'ab'" in args:
                        continue
                    issues.append(
                        f"裸 open() 无 encoding: {fp}:{lineno}: {stripped[:80]}"
                    )
    return issues


def check_hardcoded_drive_letters(files: list[Path]) -> list[str]:
    """检查是否存在硬编码 Windows 盘符."""
    issues: list[str] = []
    drive_pattern = re.compile(r'["\'\`][A-Za-z]:[/\\]')

    for fp in files:
        if fp.name == "encoding_path_audit.py":
            continue

        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _is_doc_example(line):
                continue
            if _is_pattern_definition(line):
                continue
            if _is_audit_self_diagnostic(line):
                continue

            for match in drive_pattern.finditer(line):
                issues.append(f"硬编码盘符: {fp}:{lineno}: {stripped[:80]}")
    return issues


def check_hardcoded_personal_paths(files: list[Path]) -> list[str]:
    """检查是否存在硬编码个人路径."""
    issues: list[str] = []
    path_patterns = [
        re.compile(r'["\'\`]/Users/\S*["\'\`]'),
        re.compile(r'["\'\`]/home/\S*["\'\`]'),
        re.compile(r'["\'\`]C:/Users/\S*["\'\`]', re.IGNORECASE),
    ]

    for fp in files:
        if fp.name == "encoding_path_audit.py":
            continue

        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _is_doc_example(line):
                continue
            if _is_audit_self_diagnostic(line):
                continue

            for pat in path_patterns:
                if pat.search(line):
                    issues.append(f"硬编码个人路径: {fp}:{lineno}: {stripped[:80]}")
                    break
    return issues


def check_env_tracked(repo_root: Path) -> list[str]:
    """检查 .env 是否被 Git track."""
    issues: list[str] = []
    env_path = repo_root / ".env"
    if not env_path.exists():
        return issues

    import subprocess

    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=10,
        )
        if result.returncode == 0:
            issues.append(".env 已被 Git track！运行: git rm --cached .env")
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    return issues


def check_large_files(repo_root: Path) -> list[str]:
    """检查是否存在大文件 (>500KB)."""
    issues: list[str] = []
    for p in repo_root.rglob("*"):
        if p.is_file() and not should_ignore(p, repo_root):
            try:
                size = p.stat().st_size
                if size > LARGE_FILE_THRESHOLD:
                    issues.append(f"大文件: {p} ({size / 1024:.0f} KB)")
            except OSError:
                pass
    return issues


def check_crlf_files(files: list[Path]) -> list[str]:
    """检查文本文件是否包含 CRLF 换行符."""
    issues: list[str] = []
    for fp in files:
        try:
            content = fp.read_bytes()
            if b"\r\n" in content:
                issues.append(f"CRLF 换行符: {fp}")
        except Exception:
            pass
    return issues


# ============================================================
# 主逻辑
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="编码与路径跨平台审计")
    parser.add_argument("--ci", action="store_true", help="CI 模式：不阻塞")
    args = parser.parse_args()
    ci_mode: bool = args.ci

    repo_root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    print("  TruthNet — 编码与路径审计 (encoding_path_audit.py)")
    if ci_mode:
        print("  [CI 模式]")
    print("=" * 60)

    all_issues: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    # 收集文本文件
    text_files = iter_text_files(repo_root)
    py_files = iter_python_files(repo_root)
    print(f"\n扫描范围: {len(text_files)} 个文本文件, {len(py_files)} 个 Python 文件")

    # 1. UTF-8 解码检查
    print("\n--- UTF-8 解码 ---")
    issues = check_utf8_decodable(text_files)
    if issues:
        all_issues["utf8_decode"] = issues
        for i in issues:
            print(f"  [FAIL] {i}")
    else:
        print(f"  [PASS] 所有 {len(text_files)} 个文件 UTF-8 解码通过")

    # 2. 裸 open() 检查
    print("\n--- 裸 open() 检查 ---")
    issues = check_bare_open(py_files)
    if issues:
        warnings["bare_open"] = issues
        for i in issues:
            print(f"  [WARN] {i}")
    else:
        print("  [PASS] 未发现裸 open() 无 encoding 的情况")

    # 3. 硬编码盘符检查
    print("\n--- 硬编码盘符 ---")
    issues = check_hardcoded_drive_letters(text_files)
    if issues:
        all_issues["drive_letters"] = issues
        for i in issues:
            print(f"  [FAIL] {i}")
    else:
        print("  [PASS] 未发现硬编码盘符")

    # 4. 硬编码个人路径
    print("\n--- 硬编码个人路径 ---")
    issues = check_hardcoded_personal_paths(text_files)
    if issues:
        all_issues["personal_paths"] = issues
        for i in issues:
            print(f"  [FAIL] {i}")
    else:
        print("  [PASS] 未发现硬编码个人路径")

    # 5. .env track 检查
    print("\n--- .env 是否为 Git tracked ---")
    issues = check_env_tracked(repo_root)
    if issues:
        all_issues["env_tracked"] = issues
        for i in issues:
            print(f"  [FAIL] {i}")
    else:
        env_exists = (repo_root / ".env").exists()
        if env_exists:
            print("  [PASS] .env 存在但未被 Git track")
        else:
            print("  [PASS] .env 不存在（开发环境未配置，正常）")

    # 6. 大文件检查
    print("\n--- 大文件检查 ---")
    issues = check_large_files(repo_root)
    if issues:
        all_issues["large_files"] = issues
        for i in issues:
            print(f"  [FAIL] {i}")
    else:
        print(f"  [PASS] 未发现大于 {LARGE_FILE_THRESHOLD / 1024:.0f} KB 的文件")

    # 7. CRLF 检查
    print("\n--- 换行符检查 (CRLF) ---")
    issues = check_crlf_files(text_files)
    if issues:
        warnings["crlf"] = issues
        for i in issues:
            print(f"  [WARN] {i}")
    else:
        print("  [PASS] 所有文本文件使用 LF 换行符")

    # ============================================================
    # 汇总
    # ============================================================
    print("\n" + "=" * 60)
    print("  审计结果汇总")
    print("=" * 60)

    total_fails = sum(len(v) for v in all_issues.values())
    total_warns = sum(len(v) for v in warnings.values())

    if total_fails == 0 and total_warns == 0:
        print("  ✅ 全部通过！编码与路径规范符合项目标准。")
    else:
        if total_fails > 0:
            print(f"  ❌ FAIL: {total_fails} 项")
        if total_warns > 0:
            print(f"  ⚠️  WARN: {total_warns} 项")

    print("=" * 60)

    if total_fails > 0:
        if ci_mode:
            print("\n  CI 模式下 FAIL 项不会阻塞，但建议修复。")
        else:
            print("\n  ⚠️  存在 FAIL 项，请在提交前修复。")

    return 0 if (total_fails == 0 or ci_mode) else 1


if __name__ == "__main__":
    sys.exit(main())
