#!/usr/bin/env python
"""开发会话开始脚本.

本地交互模式:
- 显示当前分支和 git status
- 询问是否 fetch 远程
- 询问是否切换/创建个人 feature 分支
- 询问是否基于 origin/main 对齐
- 只在用户输入 yes 后执行 git 操作

CI 模式:
    python scripts/start_session.py --ci
    - 只检查，不询问
"""

import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parent.parent


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


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """询问用户 yes/no."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        answer = input(prompt + suffix).strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def is_ci() -> bool:
    """检测是否在 CI 环境."""
    return bool(os.environ.get("CI"))


def main():
    parser = argparse.ArgumentParser(description="开发会话开始脚本")
    parser.add_argument("--ci", action="store_true", help="CI 模式：只检查，不询问")
    args = parser.parse_args()
    ci_mode: bool = args.ci or is_ci()

    print("=" * 60)
    print("  TruthNet — 开发会话开始 (start_session.py)")
    if ci_mode:
        print("  [CI 模式：只检查，不交互]")
    print("=" * 60)

    # 1. 显示当前分支
    print("\n--- 当前 Git 状态 ---")
    code, branch, _ = run_git(["branch", "--show-current"])
    if code == 0:
        print(f"  当前分支: {branch}")
    else:
        print("  [FAIL] 无法获取当前分支")
        return 1

    # 2. 显示 git status
    code, status_out, _ = run_git(["status", "--short"])
    if code == 0:
        if status_out:
            print(f"  未提交更改:\n{status_out}")
        else:
            print("  工作区干净")
    else:
        print("  [WARN] 无法获取 git status")

    # 3. 显示 remote
    print("\n--- Remote ---")
    code, remote_out, _ = run_git(["remote", "-v"])
    if code == 0 and remote_out:
        print(f"  {remote_out}")
    else:
        print("  [WARN] 无 remote 配置")

    # CI 模式：到此为止
    if ci_mode:
        print("\n  [CI] 检查完成，跳过交互式询问。")

        # 但仍检查是否在 main 分支
        if branch == "main":
            print("  ⚠️  当前在 main 分支！CI 不应在 main 上运行开发任务。")
            return 1
        return 0

    # ============================================================
    # 交互模式
    # ============================================================
    print("\n" + "-" * 40)

    # 4. 检查是否在安全分支
    if branch == "main":
        print("\n  ⚠️  你当前在 main 分支！")
        print("  main 是稳定版本分支，不应直接开发。")
        print("  main 是稳定分支，不直接开发。")
        print("  请创建个人 feature 分支进行开发。")

    if branch == "main":
        print("\n  💡 你当前在 main 分支。")
        if ask_yes_no("  是否创建新的 feature 分支？", default=True):
            user_name = input("  请输入你的 GitHub 用户名: ").strip()
            task_name = input("  请输入任务名称 (如 backend-websocket): ").strip()
            if user_name and task_name:
                new_branch = f"feature/{user_name}-{task_name}"
                if ask_yes_no(f"  创建分支 '{new_branch}' 并切换？", default=True):
                    code, _, err = run_git(["checkout", "-b", new_branch])
                    if code != 0:
                        print(f"  [FAIL] 创建分支失败: {err}")
                    else:
                        print(f"  [OK] 已切换到 {new_branch}")
                        branch = new_branch
            else:
                print("  已跳过（用户名或任务名称为空）")

    # 5. 询问是否 fetch 远程
    print(f"\n  当前分支: {branch}")
    if ask_yes_no("  是否需要从远程拉取最新 main/dev 对齐？", default=True):
        print("  正在 fetch origin...")
        code, _, err = run_git(["fetch", "origin"])
        if code == 0:
            print("  [OK] fetch 完成")
            print(f"\n  远程 dev 最新状态: origin/main")
            print(f"  本地分支: {branch}")
            if ask_yes_no("  是否需要将 origin/main 合并到当前分支？", default=False):
                code, _, err = run_git(["merge", "origin/main"])
                if code == 0:
                    print("  [OK] 已合并 origin/main")
                else:
                    print(f"  [WARN] 合并可能有问题: {err}")
                    print("  如有冲突，请手动解决。")
        else:
            print(f"  [WARN] fetch 失败: {err}")

    # 6. 最终摘要
    print("\n" + "=" * 60)
    print("  会话准备完成")
    print(f"  当前分支: {branch}")
    print("=" * 60)
    print()
    print("  开发前提醒:")
    print("  - 使用 pathlib.Path 处理路径")
    print("  - 文本文件使用 UTF-8 + LF")
    print("  - 不要硬编码盘符、用户名、绝对路径")
    print("  - 编辑完成后运行 python scripts/end_session.py")
    print("  - Claude Code 不会自动 commit/push/merge")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
