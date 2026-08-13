"""三轮真机 WS E2E — 康美→茅台→它（v3.1 验收 · v3.4 安全加固）.

同一真实会话三轮指代验收，公司代码链必须为：
    600518.SH → 600519.SH → 600519.SH
（康美药业 → 贵州茅台 → "它的财务风险呢" 指代上一公司）

用法：
    python scripts/e2e_ws_three_turn.py                          # 自启隔离服务（默认）
    python scripts/e2e_ws_three_turn.py --base-url http://127.0.0.1:8000 --confirm-target-db
    # 连已有服务：必须显式指定 + 确认目标库（脚本提示核对）

安全边界（v3.1 + v3.4）：
- 默认自启服务注入测试库凭据，不写演示库；--base-url 必须 --confirm-target-db；
- 每次运行新建唯一 session；RunContext 在**所有异常/超时路径**下都持有
  session_id，finally 中定向清理（复用共享 SessionCleanupService，单事务，
  共享 Evidence 保留 turn_id=NULL，无引用才删除；清理异常令退出失败）；
- 退出码四条件：_CHECK 非空且全过 + 完成三轮 + 三轮唯一终态 + cleanup 成功；
- 服务日志写 data/test-artifacts/e2e_ws_<ts>.log（不入正式报告目录）；
- 只终止脚本自己启动的进程；整体超时默认 20 分钟，单轮默认 5 分钟。
"""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK 控制台

import websockets
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))
load_dotenv(_REPO_ROOT / ".env")

QUESTIONS = ["康美药业的财务风险", "贵州茅台的财务风险", "它的财务风险呢"]
EXPECTED_CODES = ["600518.SH", "600519.SH", "600519.SH"]
WS_PATH = "/api/v1/chat/ws"
READYZ_PATH = "/api/v1/readyz"

_CHECK: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _CHECK.append((name, ok, detail))
    print(f"  [{'✅' if ok else '❌'}] {name}" + (f" — {detail}" if detail else ""))


_ENVELOPE_KEYS = {
    "schema_version",
    "event_id",
    "event_type",
    "session_id",
    "turn_id",
    "sequence",
    "timestamp",
    "trace_id",
    "payload",
}


# ── 服务管理 ────────────────────────────────────────────


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> subprocess.Popen:
    """注入测试库凭据启动独立 uvicorn（不触碰演示库）。

    日志写入 data/test-artifacts/e2e_ws_<ts>.log（不入正式报告目录）。
    """
    env = dict(os.environ)
    for key in ("MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
        env[key] = env.get(f"MYSQL_TEST_{key[6:]}", "")
    env["SQL_BACKEND"] = "mysql"
    python = sys.executable
    log_dir = _REPO_ROOT / "data" / "test-artifacts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"e2e_ws_{int(time.time())}.log"
    log_file = open(log_path, "w", encoding="utf-8", newline="\n")
    return subprocess.Popen(
        [
            python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )


def _wait_ready(base_url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}{READYZ_PATH}", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("data", {}).get("status") == "ready":
                    return True
        except Exception:  # noqa: BLE001 — 服务未就绪重试
            pass
        time.sleep(2)
    return False


# ── 定向清理（v3.4 共享服务 + v3.5 强制测试库守卫）──


def _cleanup_engine():
    """MYSQL_TEST_* 显式构建 engine（v3.5：绝不落回 settings 的演示库）。"""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    url = URL.create(
        "mysql+pymysql",
        username=os.environ.get("MYSQL_TEST_USER", ""),
        password=os.environ.get("MYSQL_TEST_PASSWORD", ""),
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test"),
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, echo=False, pool_pre_ping=True)


def _assert_cleanup_target_db(engine, expected_db: str) -> None:
    """强制校验清理目标库：SELECT DATABASE() 必须严格等于 MYSQL_TEST_DATABASE。

    v3.5 守卫：engine 连错库（任何原因）→ 抛 RuntimeError 拒绝清理。
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        cur_db = conn.execute(text("SELECT DATABASE()")).scalar()
    if cur_db != expected_db:
        raise RuntimeError(
            f"清理目标库不符: SELECT DATABASE()={cur_db!r} != "
            f"MYSQL_TEST_DATABASE={expected_db!r}（拒绝清理）"
        )


def _cleanup_session(sid: str) -> dict:
    """删除本次唯一 session，并强制验证目标库 + 清理前后状态断言。

    v3.5 守卫（任一不满足即抛异常 → 调用方 cleanup_ok=False → 退出失败）：
      1. 清理前 SELECT DATABASE() 必须严格等于 MYSQL_TEST_DATABASE（错库拒绝）；
      2. 清理前断言 session 存在（找不到对象说明状态异常）；
      3. 清理后断言 session、turn 均不存在（级联删除完整）。
    共享 Evidence 保留语义同 SessionCleanupService（无引用才删）。
    """
    from sqlalchemy import text

    from app.application.services.session_cleanup_service import SessionCleanupService

    engine = _cleanup_engine()
    expected_db = os.environ.get("MYSQL_TEST_DATABASE", "")
    _assert_cleanup_target_db(engine, expected_db)
    stats = SessionCleanupService(engine=engine).cleanup_session(sid)
    if not stats["session_found"]:
        raise RuntimeError(f"清理前断言失败: session {sid} 不存在")
    with engine.connect() as conn:
        s_left = conn.execute(
            text("SELECT 1 FROM conversation_sessions WHERE session_id = :sid LIMIT 1"),
            {"sid": sid},
        ).scalar()
        t_left = conn.execute(
            text("SELECT 1 FROM conversation_turns WHERE session_id = :sid LIMIT 1"),
            {"sid": sid},
        ).scalar()
    if s_left or t_left:
        raise RuntimeError(f"清理后断言失败: session 残留={s_left} turn 残留={t_left}")
    return stats


def _read_turn_companies(sid: str) -> list[str]:
    import pymysql

    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_TEST_USER", ""),
        password=os.environ.get("MYSQL_TEST_PASSWORD", ""),
        database=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test"),
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT company_code FROM conversation_turns "
                "WHERE session_id=%s ORDER BY turn_index",
                (sid,),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


# ── 三轮 WS 交互 ───────────────────────────────────────


class _RunContext:
    """外部共享上下文（v3.4）：超时/异常路径也能拿到 session_id 用于清理。"""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.rounds_completed: int = 0
        self.terminal_counts: list[int] = []
        self.cleanup_ok: bool = False


async def _run_turn(
    ws, rnd: int, question: str, timeout_round: float, ctx: _RunContext
) -> list[dict]:
    await ws.send(
        json.dumps({"event_type": "chat.query", "payload": {"text": question}})
    )
    events: list[dict] = []
    deadline = time.monotonic() + timeout_round
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(
            ws.recv(), timeout=max(1.0, deadline - time.monotonic())
        )
        ev = json.loads(raw)
        events.append(ev)
        # 收到首个 WS 事件即记录 session_id（此后任何路径都可定向清理）
        if ctx.session_id is None and ev.get("session_id"):
            ctx.session_id = str(ev["session_id"])
        etype = ev.get("event_type")
        if etype in ("turn.completed", "turn.failed", "turn.cancelled"):
            if etype != "turn.completed":
                _check(
                    f"第 {rnd} 轮终态 {etype}（期望 turn.completed）",
                    False,
                    str(ev)[:120],
                )
            break
    else:
        _check(f"第 {rnd} 轮超时", False, f"> {timeout_round}s")
    return events


async def _run_rounds(
    ws, timeout_round: float, ctx: _RunContext
) -> tuple[list[str], list[dict], list[str]]:
    """三轮执行；返回 (每轮 session_id, 全部事件, 每轮终态 answer)。"""
    sids: list[str] = []
    all_events: list[dict] = []
    answers: list[str] = []
    for rnd, question in enumerate(QUESTIONS, 1):
        print(f"\n第 {rnd} 轮 | {question}")
        events = await _run_turn(ws, rnd, question, timeout_round, ctx)
        if not events:
            break
        all_events.extend(events)
        sids.append(str(events[0].get("session_id", "")))
        answers.append(str(events[-1].get("payload", {}).get("answer", "")))
        # 本轮校验：信封 / sequence / turn 唯一
        env_ok = all(
            set(ev) >= _ENVELOPE_KEYS
            and ev.get("schema_version") == "1.0"
            and ev.get("sequence", 0) > 0
            and isinstance(ev.get("payload"), dict)
            for ev in events
        )
        _check(
            f"第 {rnd} 轮信封严格（9 字段/版本/sequence）",
            env_ok,
            f"events={len(events)}",
        )
        seqs = [ev.get("sequence") for ev in events]
        _check(
            f"第 {rnd} 轮 sequence 递增无重复",
            seqs == sorted(seqs) and len(set(seqs)) == len(seqs),
        )
        tids = {ev.get("turn_id") for ev in events}
        _check(f"第 {rnd} 轮 turn_id 唯一", len(tids) == 1, f"turns={tids}")
        finals = [e for e in events if e.get("event_type") == "turn.completed"]
        ctx.terminal_counts.append(len(finals))
        _check(f"第 {rnd} 轮终态恰好一次", len(finals) == 1)
        _check(f"第 {rnd} 轮 answer 非空", bool(answers[-1]), answers[-1][:40])
        if rnd == 3:
            _check(
                "第 3 轮指代解析到贵州茅台（answer 含公司名）",
                ("茅台" in answers[-1]) or ("600519" in answers[-1]),
                answers[-1][:60],
            )
        ctx.rounds_completed = rnd
    return sids, all_events, answers


async def _main_async(
    base_url: str, timeout_round: float, timeout_total: float, ctx: _RunContext
) -> None:
    """执行三轮；session 状态写入外部 ctx（超时/异常也可清理）。"""
    ws_url = base_url.replace("http", "ws") + WS_PATH
    try:
        async with websockets.connect(ws_url, open_timeout=15) as ws:
            sids, all_events, answers = await asyncio.wait_for(
                _run_rounds(ws, timeout_round, ctx), timeout=timeout_total
            )
    except websockets.exceptions.ConnectionClosed as exc:
        _check("WS 连接保持（三轮同一连接）", False, str(exc)[:100])
        return
    if not sids or ctx.session_id is None:
        return
    _check(
        "三轮 session 相同",
        len(set(sids)) == 1 and bool(sids[0]),
        str(set(sids)),
    )

    # DB 回读权威断言：company_code 链
    codes = _read_turn_companies(ctx.session_id)
    _check(
        f"DB 回读公司链 {codes} == {EXPECTED_CODES}",
        codes == EXPECTED_CODES,
        "→".join(codes or ["(空)"]),
    )

    # 全连接 event_id 不重复
    ids = [ev.get("event_id", "") for ev in all_events]
    _check("全连接 event_id 不重复", len(set(ids)) == len(ids), f"events={len(ids)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="", help="连已有服务（须配合 --confirm-target-db）"
    )
    parser.add_argument(
        "--confirm-target-db", action="store_true", help="确认目标服务连接的是测试库"
    )
    parser.add_argument(
        "--timeout-round", type=float, default=300.0, help="单轮超时秒（默认 300）"
    )
    parser.add_argument(
        "--timeout-total",
        type=float,
        default=1200.0,
        help="整体超时秒（默认 1200=20 分钟）",
    )
    args = parser.parse_args()

    if not args.base_url:
        # 自启服务模式：测试库种子必须 complete（v3.4 守卫）
        import seed_test_db

        seed_test_db.ensure_seed_complete()

    # v3.5：正式验收只允许脚本自启隔离服务；--base-url 仅作诊断，
    # 诊断模式下清理断言/退出码不作为验收证据。
    verification_mode = not args.base_url
    ctx = _RunContext()
    proc: subprocess.Popen | None = None
    try:
        if args.base_url:
            if not args.confirm_target_db:
                print(
                    "❌ 连已有服务必须显式 --confirm-target-db（并人工确认该服务连接的是测试库）"
                )
                return 1
            base_url = args.base_url.rstrip("/")
            print(f"使用已有服务 {base_url}（已确认目标库）")
        else:
            if not os.environ.get("MYSQL_TEST_DATABASE"):
                print("❌ 缺少 MYSQL_TEST_DATABASE 配置（自启服务需要测试库凭据）")
                return 1
            port = _free_port()
            proc = _start_server(port)
            base_url = f"http://127.0.0.1:{port}"
            print(
                f"自启隔离服务 {base_url}（测试库 {os.environ.get('MYSQL_TEST_DATABASE')}）"
            )
        if not _wait_ready(base_url, 60):
            print("❌ /readyz 未就绪（服务启动失败或依赖服务不可达）")
            return 1
        print("✅ /readyz 就绪")

        try:
            asyncio.run(
                _main_async(base_url, args.timeout_round, args.timeout_total, ctx)
            )
        except asyncio.TimeoutError:
            print("❌ 整体超时")
            _check("整体超时控制", False, f"> {args.timeout_total}s")
        except Exception as exc:  # noqa: BLE001 — 任何异常路径都要清理
            print(f"❌ 执行异常: {exc}")
            _check("执行无异常", False, str(exc)[:120])
    finally:
        # 所有路径（含超时/异常）下都尝试定向清理
        if ctx.session_id:
            try:
                _cleanup_session(ctx.session_id)
                ctx.cleanup_ok = True
                print(f"已定向清理 session {ctx.session_id}")
            except Exception as exc:  # noqa: BLE001 — 清理失败令退出失败
                _check("session 清理成功", False, str(exc)[:120])
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            print("已终止自启服务进程")

    # 退出码判定（v3.5）：验收模式四条件（检查 + 三轮 + 唯一终态 + 清理守卫
    # 全过）；诊断模式（--base-url）清理不参与退出码——仅输出结果，
    # 不作为验收证据。
    checks_ok = bool(_CHECK) and all(ok for _, ok, _ in _CHECK)
    rounds_ok = ctx.rounds_completed == len(QUESTIONS)
    terminals_ok = len(ctx.terminal_counts) == len(QUESTIONS) and all(
        c == 1 for c in ctx.terminal_counts
    )
    if verification_mode:
        exit_ok = checks_ok and rounds_ok and terminals_ok and ctx.cleanup_ok
        if not exit_ok:
            print(
                f"❌ 退出码判定失败: checks={checks_ok} rounds={rounds_ok}"
                f"({ctx.rounds_completed}/{len(QUESTIONS)}) "
                f"terminals={terminals_ok}({ctx.terminal_counts}) "
                f"cleanup={ctx.cleanup_ok}"
            )
        return 0 if exit_ok else 1
    # 诊断模式：基础执行判定，清理结果仅提示（不作为验收证据）
    diag_ok = checks_ok and rounds_ok and terminals_ok
    print(
        f"[诊断模式] 不作为验收证据: checks={checks_ok} rounds={rounds_ok} "
        f"terminals={terminals_ok} cleanup={ctx.cleanup_ok}"
    )
    return 0 if diag_ok else 1


if __name__ == "__main__":
    sys.exit(main())
