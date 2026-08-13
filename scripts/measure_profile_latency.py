"""画像页性能基线（⑦，v3.1 + v3.4 + v3.5 加固）— 全量测试库 truthnet_test.

阶段 1a（HTTP 黑盒）：五端点并发（profile/finance/equity/events/risk）
  冷样本 3 次（每次重启服务，报告 median/max 并标注 n=3 样本量有限）+
  热批次总墙钟 P50/P95（nearest-rank）+ 单端点耗时 + 错误率。
阶段 1b（受控埋点）：独立子进程 TestClient + 节点包装计数——/risk 单次
  请求内 finance/equity/events/risk 节点实际调用次数与耗时。

约束（v3.4 + v3.5）：
- 数据源为全量 truthnet_test；端点按真实语义运行（含 provenance 写入）；
- v3.5：instrument 阶段在**独立子进程**运行并注入测试库环境（父进程不
  import app——避免把演示库配置读进本进程）；子进程启动后 SELECT
  DATABASE() 确认 == MYSQL_TEST_DATABASE；
- 2xx 响应必须含 meta.trace_id；缺失记入 missing_trace_samples，
  --cleanup 模式下存在缺失 → 拒绝清理（无法精确收集 trace）；
- 清理为 **trace 定向**（顺序：claim_evidence_links → claims → 无引用
  新 Evidence → analysis_runs）；HTTP 与 instrument 两阶段都收集
  trace/Evidence 基线并参与清理；清理后回查本次 trace 的 claims、
  runs 均为零（links 经删除 rowcount 验证、claims 清零后无来源）；
- v3.5：uvicorn 日志写 data/test-artifacts（不再 DEVNULL）；
- 自启服务模式默认；连已有服务必须 --confirm-target-db；
- ready 超时直接失败退出（不再继续采样）；
- --audit-truthnet：只读审计演示库是否残留此前 instrument 产物，
  只报告不删除（未经单独确认不清理）。

用法：
    python scripts/measure_profile_latency.py [--code 603180.SH]
        [--warmup 3] [--samples 10] [--phase http|instrument|all]
        [--cleanup] [--audit-truthnet]
"""
# ruff: noqa: E402

import argparse
import concurrent.futures
import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

ENDPOINTS = ["profile", "finance", "equity", "events", "risk"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _test_env() -> dict:
    """注入测试库凭据的环境（子进程/服务共用；不触碰演示库）。"""
    env = dict(os.environ)
    for key in ("MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
        env[key] = env.get(f"MYSQL_TEST_{key[6:]}", "")
    env["SQL_BACKEND"] = "mysql"
    return env


def _start_server(port: int) -> subprocess.Popen:
    """注入测试库凭据启动独立 uvicorn；日志写 data/test-artifacts（v3.5）。"""
    env = _test_env()
    log_dir = _REPO_ROOT / "data" / "test-artifacts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"measure_profile_{int(time.time())}.log"
    log_file = open(log_path, "w", encoding="utf-8", newline="\n")
    return subprocess.Popen(
        [
            sys.executable,
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


def _url(base: str, code: str, ep: str) -> str:
    if ep == "profile":
        return f"{base}/api/v1/companies/{code}"
    return f"{base}/api/v1/companies/{code}/{ep}"


def _request(base: str, code: str, ep: str) -> tuple[float, int, str]:
    """请求单端点；返回 (耗时秒, status, trace_id)。"""
    t0 = time.monotonic()
    trace_id = ""
    try:
        with urllib.request.urlopen(_url(base, code, ep), timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                trace_id = str(json.loads(body).get("meta", {}).get("trace_id", ""))
            except Exception:  # noqa: BLE001 — trace 解析失败不影响测量
                pass
            return time.monotonic() - t0, resp.status, trace_id
    except Exception as exc:  # noqa: BLE001 — 错误率统计
        return time.monotonic() - t0, getattr(exc, "code", 0) or 500, trace_id


def _percentile(values: list[float], q: float) -> float | None:
    """nearest-rank P50/P95（与 C8 同算法）。"""
    if not values:
        return None
    return sorted(values)[math.ceil(q * len(values)) - 1]


def _mysql():
    import pymysql

    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_TEST_USER", ""),
        password=os.environ.get("MYSQL_TEST_PASSWORD", ""),
        database=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test"),
        charset="utf8mb4",
    )


def _evidence_baseline() -> set[str]:
    """运行前 Evidence ID 全量基线（用于判断“本次新出现”）。"""
    conn = _mysql()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT evidence_id FROM evidence_refs")
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def _cleanup_traces(trace_ids: set[str], evidence_baseline: set[str]) -> dict:
    """trace 定向清理（v3.5 顺序）：links → claims → 无引用新 Evidence → runs。

    v3.6：清理前记录目标 claim IDs 与新 Evidence IDs，供清理后全维度回查
    （links 无 trace 列——按记录的目标 claim IDs 回查）。
    """
    if not trace_ids:
        return {
            "links": 0,
            "claims": 0,
            "evidence_deleted": 0,
            "runs": 0,
            "claim_ids": [],
            "new_evidence_ids": [],
        }
    stats = {
        "links": 0,
        "claims": 0,
        "evidence_deleted": 0,
        "runs": 0,
        "claim_ids": [],
        "new_evidence_ids": [],
    }
    conn = _mysql()
    try:
        with conn.cursor() as cur:
            ph = ", ".join(["%s"] * len(trace_ids))
            # 0. 清理前记录目标 claim IDs（回查 links 用）
            cur.execute(
                f"SELECT claim_id FROM claims WHERE trace_id IN ({ph})",
                tuple(trace_ids),
            )
            stats["claim_ids"] = [r[0] for r in cur.fetchall()]
            # 1. links（按本次 trace 的 claims）
            cur.execute(
                f"DELETE FROM claim_evidence_links WHERE claim_id IN "
                f"(SELECT claim_id FROM claims WHERE trace_id IN ({ph}))",
                tuple(trace_ids),
            )
            stats["links"] = cur.rowcount
            # 2. claims
            cur.execute(
                f"DELETE FROM claims WHERE trace_id IN ({ph})", tuple(trace_ids)
            )
            stats["claims"] = cur.rowcount
            # 3. 无引用且本次新出现的 Evidence
            cur.execute(
                f"SELECT evidence_id FROM evidence_refs WHERE trace_id IN ({ph})",
                tuple(trace_ids),
            )
            new_ids = [r[0] for r in cur.fetchall() if r[0] not in evidence_baseline]
            stats["new_evidence_ids"] = new_ids
            if new_ids:
                ph2 = ", ".join(["%s"] * len(new_ids))
                cur.execute(
                    f"DELETE FROM evidence_refs WHERE evidence_id IN ({ph2}) "
                    "AND NOT EXISTS (SELECT 1 FROM claim_evidence_links l "
                    "  WHERE l.evidence_id = evidence_refs.evidence_id) "
                    "AND NOT EXISTS (SELECT 1 FROM rating_changes r "
                    "  WHERE r.evidence_id = evidence_refs.evidence_id) "
                    "AND NOT EXISTS (SELECT 1 FROM event_cluster_sources s "
                    "  WHERE s.evidence_id = evidence_refs.evidence_id)",
                    tuple(new_ids),
                )
                stats["evidence_deleted"] = cur.rowcount
            # 4. analysis_runs
            cur.execute(
                f"DELETE FROM analysis_runs WHERE trace_id IN ({ph})",
                tuple(trace_ids),
            )
            stats["runs"] = cur.rowcount
            conn.commit()
        print(
            f"[measure] trace 定向清理完成: links={stats['links']} "
            f"claims={stats['claims']} evidence={stats['evidence_deleted']} "
            f"runs={stats['runs']}（trace={len(trace_ids)}）"
        )
    finally:
        conn.close()
    return stats


def _verify_cleanup(
    trace_ids: set[str],
    claim_ids: list[str] | None = None,
    new_evidence_ids: list[str] | None = None,
) -> dict:
    """清理后回查（v3.6）：claims、runs、links（按清理前记录的 claim IDs）、
    本次新 Evidence 必须全部为零。
    """
    if not trace_ids:
        return {"claims_left": 0, "runs_left": 0, "links_left": 0, "evidence_left": 0}
    conn = _mysql()
    try:
        with conn.cursor() as cur:
            ph = ", ".join(["%s"] * len(trace_ids))
            cur.execute(
                f"SELECT COUNT(*) FROM claims WHERE trace_id IN ({ph})",
                tuple(trace_ids),
            )
            claims_left = cur.fetchone()[0]
            cur.execute(
                f"SELECT COUNT(*) FROM analysis_runs WHERE trace_id IN ({ph})",
                tuple(trace_ids),
            )
            runs_left = cur.fetchone()[0]
            links_left = 0
            if claim_ids:
                ph2 = ", ".join(["%s"] * len(claim_ids))
                cur.execute(
                    f"SELECT COUNT(*) FROM claim_evidence_links "
                    f"WHERE claim_id IN ({ph2})",
                    tuple(claim_ids),
                )
                links_left = cur.fetchone()[0]
            evidence_left = 0
            if new_evidence_ids:
                ph3 = ", ".join(["%s"] * len(new_evidence_ids))
                cur.execute(
                    f"SELECT COUNT(*) FROM evidence_refs "
                    f"WHERE evidence_id IN ({ph3})",
                    tuple(new_evidence_ids),
                )
                evidence_left = cur.fetchone()[0]
    finally:
        conn.close()
    return {
        "claims_left": claims_left,
        "runs_left": runs_left,
        "links_left": links_left,
        "evidence_left": evidence_left,
    }


def _wait_ready(base_url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/v1/readyz", timeout=3) as resp:
                if (
                    json.loads(resp.read().decode()).get("data", {}).get("status")
                    == "ready"
                ):
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return False


def _boot_server() -> tuple[str, subprocess.Popen]:
    port = _free_port()
    proc = _start_server(port)
    base = f"http://127.0.0.1:{port}"
    if not _wait_ready(base, 90):
        proc.terminate()
        raise SystemExit(
            "[measure] ❌ /readyz 超时未就绪（服务启动失败或依赖服务不可达）"
        )
    return base, proc


def phase_http(code: str, warmup: int, samples: int, base_url: str = "") -> dict:
    """阶段 1a：HTTP 黑盒基线（冷 n=3 + 热 P50/P95）。

    v3.5：2xx 缺 meta.trace_id 记入 missing_trace_samples（样本失败）；
    v3.6：不再自行采集 Evidence 基线——由 main 在所有阶段前采一次
    initial_evidence_baseline，HTTP/instrument 统一用它清理（两阶段不做并集）。
    """
    trace_ids: set[str] = set()
    missing_trace = 0

    cold_walls: list[float] = []
    cold_by_ep: dict[str, list[float]] = {ep: [] for ep in ENDPOINTS}
    proc: subprocess.Popen | None = None

    try:
        # ── 冷样本：服务重启 3 次，各采 1 批次（n=3，报告标注样本量有限）──
        for _ in range(3):
            if base_url:
                break  # 已有服务模式：冷样本仅 1 次（无法重启）
            base, proc = _boot_server()
            try:
                t0 = time.monotonic()
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                    results = list(
                        pool.map(lambda ep: _request(base, code, ep), ENDPOINTS)
                    )
                cold_walls.append(time.monotonic() - t0)
                for ep, (dt, status, tr) in zip(ENDPOINTS, results):
                    cold_by_ep[ep].append(dt)
                    if status == 200:
                        if tr:
                            trace_ids.add(tr)
                        else:
                            missing_trace += 1
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                proc = None

        # 热采样（自启一次服务 / 已有服务）
        if base_url:
            base = base_url.rstrip("/")
        else:
            base, proc = _boot_server()

        # 预热
        for _ in range(warmup):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                for dt, status, tr in pool.map(
                    lambda ep: _request(base, code, ep), ENDPOINTS
                ):
                    if status == 200 and tr:
                        trace_ids.add(tr)

        batch_walls: list[float] = []
        per_ep: dict[str, list[float]] = {ep: [] for ep in ENDPOINTS}
        errors = 0
        total = 0
        for _ in range(samples):
            t0 = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(lambda ep: _request(base, code, ep), ENDPOINTS))
            batch_walls.append(time.monotonic() - t0)
            for ep, (dt, status, tr) in zip(ENDPOINTS, results):
                per_ep[ep].append(dt)
                total += 1
                if status != 200:
                    errors += 1
                elif tr:
                    trace_ids.add(tr)
                else:
                    missing_trace += 1

        report = {
            "cold_n": len(cold_walls),
            "cold_batch_wall_median": (
                round(_percentile(sorted(cold_walls), 0.5), 3) if cold_walls else None
            ),
            "cold_batch_wall_max": (round(max(cold_walls), 3) if cold_walls else None),
            "cold_events_p50": {
                ep: round(_percentile(sorted(v), 0.5), 3)
                for ep, v in cold_by_ep.items()
            },
            "hot_batch_wall_p50": round(_percentile(batch_walls, 0.5), 3),
            "hot_batch_wall_p95": round(_percentile(batch_walls, 0.95), 3),
            "per_endpoint_p50": {
                ep: round(_percentile(v, 0.5), 3) for ep, v in per_ep.items()
            },
            "per_endpoint_p95": {
                ep: round(_percentile(v, 0.95), 3) for ep, v in per_ep.items()
            },
            "error_rate": round(errors / total, 4) if total else 0.0,
            "missing_trace_samples": missing_trace,
            "samples": samples,
            "note": (
                "冷样本 n=3（服务重启 3 次），P95 未计算（n 过小）；"
                if cold_walls
                else "冷样本 n=1（已有服务模式无法重启）"
            ),
        }
        print("\n===== 阶段 1a HTTP 基线 =====")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        report["trace_ids"] = sorted(trace_ids)
        return report
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def _instrument_worker(code: str) -> int:
    """阶段 1b 子进程入口（v3.5）：SELECT DATABASE() 校验 + TestClient 埋点。

    在**独立子进程**运行并注入测试库环境——父进程不 import app，
    避免演示库配置进入测量进程。结果 JSON 输出到 stdout（末行）。
    """
    import time as _time

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    expected_db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    url = URL.create(
        "mysql+pymysql",
        username=os.environ.get("MYSQL_TEST_USER", ""),
        password=os.environ.get("MYSQL_TEST_PASSWORD", ""),
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=expected_db,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(url, echo=False)

    def _fail(msg: str) -> int:
        print(json.dumps({"error": msg}, ensure_ascii=False))
        return 1

    # 子进程 SELECT DATABASE() 确认测试库（v3.5）
    try:
        with engine.connect() as conn:
            cur_db = conn.execute(text("SELECT DATABASE()")).scalar()
    except Exception as exc:  # noqa: BLE001
        return _fail(f"worker 连接测试库失败: {exc}")
    if cur_db != expected_db:
        return _fail(
            f"worker 目标库不符: SELECT DATABASE()={cur_db!r} != {expected_db!r}"
        )
    # v3.6：worker 不再采集 Evidence 基线——统一由 main 在所有阶段前采
    # initial_evidence_baseline（HTTP 阶段新证据必须出现在同一基线）

    # TestClient + 节点包装计数（import app 在子进程内完成）
    from fastapi.testclient import TestClient

    counts: dict[str, int] = {}
    durations: dict[str, float] = {}
    originals = {}

    import app.agents.nodes.equity as eq_mod
    import app.agents.nodes.events as ev_mod
    import app.agents.nodes.finance as fin_mod
    import app.agents.nodes.risk as risk_mod

    def _wrap(name: str, mod, fn_name: str):
        orig = getattr(mod, fn_name)

        def wrapped(state):  # 节点均为同步 def（见 risk_scoring_service.run_nodes）
            counts[name] = counts.get(name, 0) + 1
            t0 = _time.monotonic()
            try:
                return orig(state)
            finally:
                durations[name] = durations.get(name, 0.0) + (_time.monotonic() - t0)

        setattr(mod, fn_name, wrapped)
        originals[(name, mod, fn_name)] = orig

    _wrap("finance", fin_mod, "finance_node")
    _wrap("equity", eq_mod, "equity_node")
    _wrap("events", ev_mod, "events_node")
    _wrap("risk", risk_mod, "risk_node")

    try:
        from app.main import app

        client = TestClient(app)
        resp = client.get(f"/api/v1/companies/{code}/risk")
        body = resp.json()
        trace_id = str((body.get("meta") or {}).get("trace_id", ""))
        # 2xx 必须含 meta.trace_id（v3.5：缺失 → 样本失败）
        if resp.status_code == 200 and not trace_id:
            return _fail("2xx 响应缺 meta.trace_id（样本失败）")
        report = {
            "module_call_counts": counts,
            "module_total_seconds": {k: round(v, 3) for k, v in durations.items()},
            "http_status": resp.status_code,
            "trace_ids": [trace_id] if trace_id else [],
            # v3.6：不再输出 evidence_baseline——基线由 main 在所有阶段前
            # 采一次 initial_evidence_baseline，两阶段不做并集
        }
        # 父进程按 stdout 末行解析：报告必须单行紧凑 JSON（v3.5）
        print(json.dumps(report, ensure_ascii=False))
        return 0
    finally:
        for name, mod, fn_name in originals:
            setattr(mod, fn_name, originals[(name, mod, fn_name)])


def phase_instrument(code: str) -> tuple[dict, set[str]]:
    """阶段 1b 父进程入口：子进程隔离执行，返回 (报告, trace_ids)。

    v3.6：不再返回 evidence_baseline（统一用 main 的 initial 基线）。
    """
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--phase",
        "instrument",
        "--code",
        code,
        "--worker",
        "1",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        env=_test_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    out_lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    payload = out_lines[-1] if out_lines else ""
    try:
        report = json.loads(payload)
    except Exception:  # noqa: BLE001
        raise SystemExit(
            f"[measure] ❌ instrument worker 输出异常: {payload[:300]}\n"
            f"stderr: {proc.stderr[-500:]}"
        ) from None
    if proc.returncode != 0 or "error" in report:
        raise SystemExit(f"[measure] ❌ instrument worker 失败: {report}")
    print("\n===== 阶段 1b 受控埋点（/risk 单请求，子进程隔离）=====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report, set(report.get("trace_ids", []))


def _audit_truthnet_artifacts() -> int:
    """只读审计：演示库（truthnet）是否存在此前 instrument 遗留产物。

    特征：analysis_runs 中 endpoint 含 '/risk' 的近期记录（instrument 阶段
    用 TestClient 调 /risk 且此前无 trace 定向清理）。只报告不删除——
    未经单独确认不执行任何清理。
    """
    import pymysql

    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", ""),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "truthnet"),
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM analysis_runs")
            total_runs = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM analysis_runs "
                "WHERE endpoint LIKE '%/risk%' AND created_at >= "
                "DATE_SUB(NOW(), INTERVAL 7 DAY)"
            )
            risk_runs_7d = cur.fetchone()[0]
            cur.execute(
                "SELECT endpoint, COUNT(*) FROM analysis_runs "
                "WHERE endpoint LIKE '%/risk%' "
                "GROUP BY endpoint ORDER BY COUNT(*) DESC LIMIT 5"
            )
            top = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM evidence_refs")
            total_evidence = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM evidence_refs "
                "WHERE module='finance' OR module='events' OR module='equity'"
            )
            module_evidence = cur.fetchone()[0]
    finally:
        conn.close()
    print("===== 只读审计：演示库 instrument 产物痕迹 =====")
    print(f"  analysis_runs 总数: {total_runs}；近 7 天含 /risk 的: {risk_runs_7d}")
    for ep, n in top:
        print(f"    endpoint={ep}: {n} 条")
    print(f"  evidence_refs 总数: {total_evidence}（module 标注: {module_evidence}）")
    print(
        "  ⚠️ 只读审计完成，未执行任何删除。如需清理演示库测试产物，"
        "请人工确认后单独执行。"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", default="603180.SH", help="画像公司（默认金牌家居）")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--phase", choices=["http", "instrument", "all"], default="all")
    parser.add_argument(
        "--base-url", default="", help="连已有服务（须配合 --confirm-target-db）"
    )
    parser.add_argument(
        "--confirm-target-db", action="store_true", help="确认目标服务连接的是测试库"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="trace 定向清理测试产物（默认关闭：保留产物并提示）",
    )
    parser.add_argument(
        "--audit-truthnet",
        action="store_true",
        help="只读审计演示库 instrument 残留（不删除）",
    )
    parser.add_argument("--worker", default="", help="内部参数：子进程 worker 模式")
    args = parser.parse_args()

    if args.audit_truthnet:
        return _audit_truthnet_artifacts()

    if args.worker:
        if args.phase != "instrument":
            print("❌ --worker 仅支持 instrument 阶段")
            return 1
        return _instrument_worker(args.code)

    if not os.environ.get("MYSQL_TEST_DATABASE"):
        print("❌ 缺少 MYSQL_TEST_DATABASE（性能基线必须使用全量测试库）")
        return 1
    import seed_test_db

    seed_test_db.ensure_seed_complete()
    if args.base_url and not args.confirm_target_db:
        print(
            "❌ 连已有服务必须显式 --confirm-target-db（并人工确认该服务连接的是测试库）"
        )
        return 1

    # v3.6：所有阶段开始前只采集一次 initial_evidence_baseline——
    # HTTP/instrument 不再各自采集/做并集，清理统一用最初基线
    # （HTTP 阶段新出现的 Evidence 必须被 instrument 后的清理覆盖）。
    all_trace: set[str] = set()
    initial_baseline = _evidence_baseline()
    missing_trace_total = 0
    if args.phase in ("http", "all"):
        http_report = phase_http(args.code, args.warmup, args.samples, args.base_url)
        all_trace |= set(http_report["trace_ids"])
        missing_trace_total += http_report["missing_trace_samples"]
    if args.phase in ("instrument", "all"):
        instr_report, tr_ids = phase_instrument(args.code)
        all_trace |= tr_ids

    # 统一清理 + 全维度回查（v3.6）
    if args.cleanup:
        if missing_trace_total > 0:
            print(
                f"❌ --cleanup 未完成：{missing_trace_total} 个 2xx 样本缺 "
                f"meta.trace_id，无法精确收集 trace，拒绝清理"
            )
            return 1
        cleanup_stats = _cleanup_traces(all_trace, initial_baseline)
        verify = _verify_cleanup(
            all_trace,
            claim_ids=cleanup_stats["claim_ids"],
            new_evidence_ids=cleanup_stats["new_evidence_ids"],
        )
        if (
            verify["claims_left"]
            or verify["runs_left"]
            or verify["links_left"]
            or verify["evidence_left"]
        ):
            print(
                f"❌ 清理后回查非零: claims={verify['claims_left']} "
                f"runs={verify['runs_left']} links={verify['links_left']} "
                f"evidence={verify['evidence_left']}"
            )
            return 1
        print("✅ 清理完成且回查零残留（claims/runs/links/新 Evidence）")
    else:
        print(
            "[measure] ⚠️ --cleanup 未开启：本次运行产生的测试产物将保留"
            "（analysis_runs/evidence_refs 等）"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
