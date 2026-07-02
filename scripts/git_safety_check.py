#!/usr/bin/env python
"""Git 安全检查脚本.

检查当前分支安全状态，避免误在 main 开发、遗漏个人文件等。
支持 --ci 非交互模式。

功能:
- 显示当前分支
- 如果当前分支是 main，给出 FAIL
- 如果当前分支是 dev，给出 WARN
- 检查 remote 是否存在
- 检查未提交文件
- 检查疑似个人化文件
- 检查 .env、大文件、数据库、模型权重
- 输出"可提交文件"和"应保留本地文件"建议
"""

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parent.parent

# 绝对不应提交的文件模式
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (".env", "环境变量文件"),
    ("*.db", "数据库文件"),
    ("*.sqlite", "数据库文件"),
    ("*.sqlite3", "数据库文件"),
    ("*.pkl", "模型权重/Pickle 文件"),
    ("*.bin", "二进制模型文件"),
    ("*.pt", "PyTorch 模型文件"),
    ("*.pth", "PyTorch checkpoint"),
    ("*.onnx", "ONNX 模型文件"),
    ("*.safetensors", "SafeTensors 模型文件"),
    ("*.xlsx", "Excel 数据文件"),
    ("*.xls", "Excel 数据文件"),
    ("*.pdf", "PDF 文件"),
    ("*.parquet", "Parquet 数据文件"),
]


def run_git(args_list: list[str]) -> tuple[int, str, str]:
    """运行 git 命令."""
    try:
        result = subprocess.run(
            ["git"] + args_list,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "git not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"


def main():
    parser = argparse.ArgumentParser(description="Git 安全检查")
    parser.add_argument("--ci", action="store_true", help="CI 模式：不阻塞")
    args = parser.parse_args()
    ci_mode: bool = args.ci

    fails = 0
    warns = 0

    print("=" * 60)
    print("  TruthNet — Git 安全检查 (git_safety_check.py)")
    if ci_mode:
        print("  [CI 模式]")
    print("=" * 60)

    # 1. 检查 .git 目录
    print("\n--- Git 仓库检查 ---")
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists():
        print("  [FAIL] 未找到 .git 目录，当前不在 Git 仓库中")
        return 1
    print("  [PASS] .git 目录存在")

    # 2. 当前分支
    print("\n--- 分支检查 ---")
    code, branch, err = run_git(["branch", "--show-current"])
    if code != 0:
        print(f"  [FAIL] 无法获取当前分支: {err}")
        fails += 1
        branch = ""
    else:
        print(f"  当前分支: {branch}")

        if branch == "main":
            print("  [FAIL] 当前在 main 分支！不要在 main 上直接开发！")
            print("         请切换到 dev 或创建 feature 分支。")
            fails += 1
        elif branch == "dev":
            print("  [WARN] 当前在 main 分支。建议创建个人 feature 分支进行开发。")
            print("         示例: git checkout -b feature/<your-name>-<task>")
            warns += 1
        elif any(branch.startswith(p) for p in ("feature/", "fix/", "docs/", "test/")):
            print(f"  [PASS] 当前在 {branch} 分支，可以安全开发。")
        else:
            print(f"  [WARN] 未识别的分支名 '{branch}'，请确认是否为个人开发分支。")
            warns += 1

    # 3. Remote 检查
    print("\n--- Remote 检查 ---")
    code, remotes, err = run_git(["remote", "-v"])
    if code == 0 and "origin" in remotes:
        print("  [PASS] remote 'origin' 已配置")
    else:
        print("  [WARN] 未检测到 origin remote")
        warns += 1

    # 4. 未提交文件
    print("\n--- 未提交文件 ---")
    code, status_out, _ = run_git(["status", "--porcelain"])
    if code != 0:
        print("  [FAIL] 无法获取 git status")
        fails += 1
    elif status_out:
        lines = status_out.strip().split("\n")
        staged = [l for l in lines if l[0] != " " and l[1] != "?"]  # M, A, D in index
        unstaged = [l for l in lines if l[0] == " " and l[1] != "?"]  # modified but not staged
        untracked = [l for l in lines if l.startswith("??")]

        print(f"  已暂存 (staged): {len(staged)} 个文件")
        print(f"  已修改未暂存: {len(unstaged)} 个文件")
        print(f"  未跟踪 (untracked): {len(untracked)} 个文件")

        if untracked:
            print("\n  未跟踪文件列表:")
            for line in untracked:
                fpath = line[3:].strip()
                print(f"    [{fpath}]")

        # 检查是否有危险文件在未跟踪或已修改列表中
        dangerous_found = []
        for line in lines:
            fpath = line[3:].strip()
            for pattern, desc in DANGEROUS_PATTERNS:
                if Path(fpath).match(pattern) or Path(fpath).name == pattern:
                    dangerous_found.append((fpath, desc))

        if dangerous_found:
            print("\n  ⚠️  检测到疑似不应提交的文件:")
            for fpath, desc in dangerous_found:
                print(f"    - {fpath} ({desc})")
                print(f"      建议: 确保已在 .gitignore 中，或不要 git add 此文件")
            warns += len(dangerous_found)
    else:
        print("  [PASS] 工作区干净，无未提交文件")

    # 5. 可提交 vs 应保留本地的文件建议
    print("\n--- 文件分类建议 ---")
    if status_out:
        lines = status_out.strip().split("\n") if status_out.strip() else []
        committable: list[str] = []
        local_only: list[str] = []

        for line in lines:
            fpath = line[3:].strip()
            p = Path(fpath)

            # 不应提交的文件
            is_dangerous = False
            for pattern, _ in DANGEROUS_PATTERNS:
                if p.match(pattern) or p.name == pattern:
                    local_only.append(fpath)
                    is_dangerous = True
                    break

            if is_dangerous:
                continue

            # .claude/settings.local.json 是本地配置
            if ".claude/settings.local.json" in fpath:
                local_only.append(fpath)
                continue

            # .env 相关文件
            if p.name == ".env" and ".example" not in p.name:
                local_only.append(fpath)
                continue

            committable.append(fpath)

        if committable:
            print(f"  可以提交的文件 ({len(committable)} 个):")
            for f in committable[:20]:  # 最多显示20个
                print(f"    ✅ {f}")
            if len(committable) > 20:
                print(f"    ... 以及 {len(committable) - 20} 个文件")
        else:
            print("  (无新增可提交文件)")

        if local_only:
            print(f"\n  应保留本地的文件 ({len(local_only)} 个):")
            for f in local_only:
                print(f"    🏠 {f}")
            print("\n  ⚠️  以上文件不应提交到仓库！")

    # 6. 检查 .gitignore 是否存在
    print("\n--- .gitignore 检查 ---")
    if (REPO_ROOT / ".gitignore").exists():
        print("  [PASS] .gitignore 存在")
    else:
        print("  [FAIL] .gitignore 缺失")
        fails += 1

    # ============================================================
    # 汇总
    # ============================================================
    print("\n" + "=" * 60)
    print("  检查结果汇总")
    print("=" * 60)

    if fails == 0 and warns == 0:
        print("  ✅ 全部通过！当前 Git 状态安全。")
    else:
        if fails > 0:
            print(f"  ❌ FAIL: {fails} 项")
        if warns > 0:
            print(f"  ⚠️  WARN: {warns} 项")
    print("=" * 60)

    if fails > 0 and not ci_mode:
        print("\n  ⚠️  存在 FAIL 项，建议修复后再继续开发。")

    return 0 if (fails == 0 or ci_mode) else 1


if __name__ == "__main__":
    sys.exit(main())
