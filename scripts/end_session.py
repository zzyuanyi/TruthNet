#!/usr/bin/env python
"""开发会话结束脚本.

本地交互模式:
- 显示 git status
- 显示 diff stat
- 运行 git_safety_check.py
- 询问是否运行测试
- 询问是否生成提交建议
- 不自动 commit
- 不自动 push
- 输出推荐 commit message

CI 模式:
    python scripts/end_session.py --ci
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


def detect_change_type(status_lines: list[str]) -> str:
    """根据文件变更推测 commit 类型."""
    files = [l[3:].strip() for l in status_lines]

    has_feat = False
    has_fix = False
    has_docs = False
    has_test = False

    for f in files:
        p = Path(f)
        if p.suffix == ".py" and "test" in p.stem.lower():
            has_test = True
        elif p.suffix == ".py":
            has_feat = True
        elif p.suffix in (".md",):
            has_docs = True
        elif "fix" in str(p).lower():
            has_fix = True

    if has_test and not has_feat and not has_fix:
        return "test"
    if has_docs and not has_feat and not has_fix:
        return "docs"
    if has_feat:
        return "feat"
    if has_fix:
        return "fix"
    return "chore"


def main():
    parser = argparse.ArgumentParser(description="开发会话结束脚本")
    parser.add_argument("--ci", action="store_true", help="CI 模式：只检查，不询问")
    args = parser.parse_args()
    ci_mode: bool = args.ci or is_ci()

    print("=" * 60)
    print("  TruthNet — 开发会话结束 (end_session.py)")
    if ci_mode:
        print("  [CI 模式：只检查，不交互]")
    print("=" * 60)

    # 1. 当前分支
    code, branch, _ = run_git(["branch", "--show-current"])
    if code != 0:
        print("  [FAIL] 无法获取当前分支")
        return 1

    print(f"\n  当前分支: {branch}")

    # 2. git status
    print("\n--- Git Status ---")
    code, status_out, _ = run_git(["status", "--short"])
    if code != 0:
        print("  [FAIL] 无法获取 git status")
        return 1

    if not status_out:
        print("  工作区干净，无未提交文件。")
        print("\n  无需进一步操作。")
        return 0

    status_lines = status_out.strip().split("\n")
    print(f"  共 {len(status_lines)} 个文件有变更:")
    for line in status_lines:
        print(f"    {line}")

    # 3. diff stat
    print("\n--- Diff Stat ---")
    code, diff_out, _ = run_git(["diff", "--stat"])
    if code == 0 and diff_out:
        print(diff_out)
    else:
        print("  (无法获取 diff 或暂存区无变更)")

    # 4. 运行 git_safety_check
    print("\n--- Git 安全检查 ---")
    safety_script = REPO_ROOT / "scripts" / "git_safety_check.py"
    if safety_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(safety_script), "--ci" if ci_mode else ""],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO_ROOT),
            )
            # 只打印关键行
            for line in result.stdout.splitlines():
                if any(tag in line for tag in ["[PASS]", "[WARN]", "[FAIL]", "✅", "⚠️", "❌"]):
                    print(f"  {line.strip()}")
        except Exception:
            print("  [WARN] 无法运行 git_safety_check.py")
    else:
        print("  [WARN] git_safety_check.py 不存在")

    # CI 模式到此为止
    if ci_mode:
        print(f"\n  [CI] 检查完成。")
        return 0

    # ============================================================
    # 交互模式
    # ============================================================
    print("\n" + "-" * 40)

    # 5. 询问是否运行测试
    if ask_yes_no("  是否运行后端测试？", default=True):
        print("  正在运行 python -m pytest backend/tests -v ...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "backend/tests", "-v"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(REPO_ROOT),
            )
            print(result.stdout[-2000:])  # 最后2000字符
            if result.returncode != 0:
                print("\n  ⚠️  测试未全部通过，请检查后再提交。")
        except subprocess.TimeoutExpired:
            print("  [WARN] 测试超时")
        except Exception as e:
            print(f"  [WARN] 无法运行测试: {e}")

    # 6. 询问是否运行 doctor
    if ask_yes_no("  是否运行环境检测 (doctor.py)？", default=True):
        print("  正在运行 python scripts/doctor.py ...")
        try:
            result = subprocess.run(
                [sys.executable, "scripts/doctor.py"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO_ROOT),
            )
            print(result.stdout[-2000:])
        except Exception as e:
            print(f"  [WARN] 无法运行 doctor.py: {e}")

    # 7. 生成提交建议
    print("\n--- 提交建议 ---")
    change_type = detect_change_type(status_lines)

    # 推测 scope
    all_files = [l[3:].strip() for l in status_lines]
    scopes = set()
    for f in all_files:
        parts = Path(f).parts
        if parts[0] in ("backend", "frontend", "docs", "scripts", ".github", ".claude"):
            scopes.add(parts[0])
        else:
            scopes.add("project")

    scope = ",".join(sorted(scopes)) if len(scopes) <= 2 else "multi"

    print(f"  推荐 commit 类型: {change_type}")
    print(f"  推荐 scope: {scope}")
    print(f"  推荐 commit message:")
    print(f'    {change_type}({scope}): <描述你的改动>')
    print()
    print("  示例:")
    if change_type == "feat":
        print(f'    {change_type}({scope}): 添加 WebSocket 最小 mock 端点')
    elif change_type == "docs":
        print(f'    {change_type}({scope}): 更新编码规范与 Git 协作流程文档')
    elif change_type == "test":
        print(f'    {change_type}({scope}): 添加 WebSocket smoke 测试')
    else:
        print(f'    {change_type}({scope}): 更新项目配置与工具脚本')

    # 8. 询问下一步操作
    print("\n--- 下一步操作 ---")
    print("  请选择:")
    print("    1. 仅保存文件，不提交")
    print("    2. 创建本地 checkpoint commit（不 push）")
    print("    3. 提交到当前分支并 push 到远程")
    print("    4. 暂不操作，我手动处理")

    try:
        choice = input("\n  请输入选项 (1-4) [1]: ").strip()
    except EOFError:
        choice = "1"

    if not choice:
        choice = "1"

    if choice == "2":
        print("\n  💡 如需创建本地 commit，请手动执行:")
        print("    git add <file1> <file2> ...")
        print('    git commit -m "..."')
        print("\n  ⚠️  Claude Code 不会自动执行 commit。")
    elif choice == "3":
        print("\n  💡 如需提交并推送，请手动执行:")
        print("    git add <file1> <file2> ...")
        print('    git commit -m "..."')
        print(f"    git push origin {branch}")
        print("\n  ⚠️  Claude Code 不会自动执行 commit/push。")
    elif choice == "4":
        print("\n  [OK] 已了解，请手动处理。")
    else:
        print("\n  [OK] 文件已保存到本地。")

    print("\n  结束编辑前检查清单:")
    print("  ✅ 确认不需要提交 .env、密钥、数据库、模型文件")
    print("  ✅ 确认所有路径使用 pathlib.Path")
    print("  ✅ 确认所有文本文件使用 UTF-8 + LF")
    print("  ✅ 确认未硬编码盘符、用户名、绝对路径")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
