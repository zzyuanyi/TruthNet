#!/usr/bin/env python
"""CI 状态检查脚本.

检查当前分支的 GitHub Actions 运行状态。
优先使用 gh CLI；如果 gh 不可用，给出手动检查指引。

用法:
    python scripts/ci_status.py                  # 检查当前分支最近一次 run
    python scripts/ci_status.py --branch main     # 指定分支
    python scripts/ci_status.py --watch            # 持续监控直到完成
    python scripts/ci_status.py --failed-logs      # 显示最近失败 run 的日志
    python scripts/ci_status.py --ci               # CI 模式（不查远程）
    python scripts/ci_status.py --json             # JSON 输出
"""

import argparse
import json
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """运行命令."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"


def get_current_branch() -> str:
    """获取当前 git 分支."""
    code, out, _ = run_cmd(["git", "branch", "--show-current"])
    return out if code == 0 else "unknown"


def get_current_sha() -> str:
    """获取当前 commit SHA."""
    code, out, _ = run_cmd(["git", "rev-parse", "HEAD"])
    return out[:8] if code == 0 else "unknown"


def gh_available() -> bool:
    """检查 gh CLI 是否可用."""
    return shutil.which("gh") is not None


def get_latest_run(branch: str) -> dict | None:
    """获取分支最近一次 Actions run."""
    if not gh_available():
        return None

    code, out, _ = run_cmd(
        [
            "gh",
            "run",
            "list",
            "--branch",
            branch,
            "--limit",
            "1",
            "--json",
            "databaseId,status,conclusion,headSha,displayTitle,workflowName,url",
        ],
        timeout=30,
    )
    if code != 0 or not out:
        return None

    try:
        runs = json.loads(out)
        return runs[0] if runs else None
    except (json.JSONDecodeError, IndexError, KeyError):
        return None


def watch_run(run_id: str) -> int:
    """监控 run 直到完成，返回 exit status."""
    if not gh_available():
        print("[WARN] gh CLI 不可用，无法监控")
        return 1

    code, _, _ = run_cmd(
        ["gh", "run", "watch", run_id, "--exit-status"],
        timeout=300,
    )
    return code


def get_failed_logs(run_id: str) -> str:
    """获取失败 run 的失败步骤日志."""
    if not gh_available():
        return "gh CLI 不可用"

    code, out, err = run_cmd(
        ["gh", "run", "view", run_id, "--log-failed"],
        timeout=30,
    )
    return out if code == 0 else f"无法获取日志: {err}"


def main():
    parser = argparse.ArgumentParser(description="CI 状态检查")
    parser.add_argument("--branch", type=str, default=None, help="目标分支")
    parser.add_argument("--commit", type=str, default=None, help="目标 commit SHA")
    parser.add_argument("--watch", action="store_true", help="持续监控直到 CI 完成")
    parser.add_argument("--failed-logs", action="store_true", help="显示最近失败日志")
    parser.add_argument("--ci", action="store_true", help="CI 模式：仅本地检查")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    branch = args.branch or get_current_branch()
    sha = args.commit or get_current_sha()

    result = {
        "branch": branch,
        "commit": sha,
        "gh_available": gh_available(),
        "status": "not_run",
        "details": "",
    }

    # CI 模式：仅做存在性检查
    if args.ci:
        print("[CI] ci_status.py 存在且可用")
        print(f"  当前分支: {branch}")
        print(f"  当前 commit: {sha}")
        print(f"  gh CLI: {'可用' if gh_available() else '未安装'}")
        if branch == "main":
            print("  ⚠️  main 是受保护分支，不建议直接开发")
        return 0

    # 主逻辑
    if not args.json:
        print("=" * 60)
        print("  TruthNet — CI 状态检查 (ci_status.py)")
        print("=" * 60)
        print(f"  分支: {branch}")
        print(f"  commit: {sha}")
        print(f"  gh CLI: {'✓ 可用' if gh_available() else '✗ 未安装'}")

    # main 分支提醒
    if branch == "main":
        msg = "main 是受保护分支，不建议直接开发；应在个人分支提交 PR。"
        if not args.json:
            print(f"\n  ⚠️  {msg}")
        result["details"] = msg

    # 检查 gh
    if not gh_available():
        msg = (
            "GitHub CLI (gh) 未安装。请手动检查 Actions:\n"
            "  1. 打开 https://github.com/zzyuanyi/TruthNet/actions\n"
            "  2. 选择你的分支查看最近运行状态\n"
            "  3. 安装 gh CLI: https://cli.github.com"
        )
        if not args.json:
            print(f"\n  {msg}")
            result["status"] = "not_run"
            result["details"] = "gh CLI not available"
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # 获取最近 run
    run = get_latest_run(branch)

    if run is None:
        msg = "当前分支可能尚未 push，或 Actions 尚未触发。"
        if not args.json:
            print(f"\n  {msg}")
            print(f"  请先 push: git push origin {branch}")
        result["status"] = "not_run"
        result["details"] = msg
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    run_id = str(run.get("databaseId", ""))
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion", "unknown")
    title = run.get("displayTitle", "")
    url = run.get("url", "")

    if not args.json:
        print(f"\n  最近 run: {title}")
        print(f"  run_id: {run_id}")
        print(f"  状态: {status}")
        print(f"  结论: {conclusion}")
        if url:
            print(f"  URL: {url}")

    # --failed-logs
    if args.failed_logs:
        if conclusion in ("failure", "cancelled", "timed_out"):
            if not args.json:
                print(f"\n--- 失败日志 (run {run_id}) ---")
                print(get_failed_logs(run_id))
        else:
            if not args.json:
                print(f"\n  最近 run 结论为 '{conclusion}'，无需拉取失败日志。")

    # --watch
    if args.watch:
        if not args.json:
            print(f"\n  监控 run {run_id} ...")
        exit_code = watch_run(run_id)
        if not args.json:
            if exit_code == 0:
                print("\n  ✅ CI 通过！可以请求 PR review。")
            else:
                print(f"\n  ❌ CI 失败 (exit={exit_code})。")
                print("  拉取失败日志:")
                print(get_failed_logs(run_id))
                print("\n  修复流程:")
                print("  1. 分析失败日志，定位失败步骤")
                print("  2. 本地修复 → 运行完整检查")
                print("  3. commit → push → 再次检查 CI")
                print("  4. CI 通过后再请求 PR review")
        result["status"] = "passed" if exit_code == 0 else "failed_requires_fix"

    # 最终状态
    if conclusion == "success":
        result["status"] = "passed"
    elif conclusion == "failure":
        result["status"] = "failed_requires_fix"
    elif status in ("queued", "in_progress", "waiting"):
        result["status"] = "in_progress"

    if not args.json:
        print(f"\n  当前状态: {result['status']}")

    if args.json:
        result["run"] = run
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["status"] in ("passed", "not_run", "in_progress") else 1


if __name__ == "__main__":
    sys.exit(main())
