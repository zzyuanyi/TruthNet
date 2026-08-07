#!/usr/bin/env python
"""Phase D #7 性能 smoke 测量脚本.

后端本地 smoke：搜索 / REST 标准题 / WS 首块 的 P50/P95。
使用真实本地 MySQL/Neo4j（不冒充数据组正式评测）。

目标参考：
  - search P95 <= 500 ms
  - REST 标准题完整 <= 8 s
  - WS 首块 <= 3 s

输出：结构化 JSON + Markdown（docs/reports/perf_smoke.json/.md）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.infrastructure.observability.timing import MetricsCollector  # noqa: E402
from app.main import app  # noqa: E402

REPORT_DIR = _ROOT / "docs" / "reports"
SAMPLE_N = 5  # 本地 smoke 样本数（正式评测由数据组负责）

TARGETS = {
    "search.p95_ms": 500,
    "rest.agent_total_ms.p95_ms": 8000,
    "ws.first_delta_ms.p95_ms": 3000,
}


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = min(len(vals) - 1, int(q * len(vals)) - 1)
    return round(vals[idx], 3)


def _measure_rest(client: TestClient, collector: MetricsCollector) -> list[float]:
    """REST 标准题完整耗时（Agent total + envelope 组装）。"""
    samples = []
    for _ in range(SAMPLE_N):
        collector.clear()
        t0 = time.perf_counter()
        r = client.post(
            "/api/v1/chat",
            json={"question": "康美药业有造假风险吗", "session_id": "ses_perf_rest"},
        )
        elapsed = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            samples.append(elapsed)
    return samples


def _measure_search() -> list[float]:
    """搜索耗时（Chroma + SQL fallback 埋点已就绪，这里直接同步测量）。"""
    from app.application.services.research_search import search_research_insights_sync

    samples = []
    for _ in range(SAMPLE_N):
        t0 = time.perf_counter()
        search_research_insights_sync("白酒行业近期研报观点", top_k=3)
        samples.append((time.perf_counter() - t0) * 1000)
    return samples


def _measure_ws_first_delta(client: TestClient) -> list[float]:
    """WS 首块耗时（turn.accepted 到第一个 answer.delta）。"""
    import uuid

    samples = []
    for _ in range(SAMPLE_N):
        sid = f"ses_perf_ws_{uuid.uuid4().hex[:8]}"
        with client.websocket_connect(f"/api/v1/chat/ws?session_id={sid}") as ws:
            ws.send_json(
                {
                    "event_type": "chat.query",
                    "payload": {"text": "康美药业有造假风险吗", "session_id": sid},
                }
            )
            t0 = time.perf_counter()
            first_delta_ms = None
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                ev = ws.receive_json()
                if ev["event_type"] == "answer.delta":
                    first_delta_ms = (time.perf_counter() - t0) * 1000
                    break
                if ev["event_type"] in ("turn.failed", "turn.completed"):
                    break
            if first_delta_ms is not None:
                samples.append(first_delta_ms)
    return samples


def main() -> int:
    collector = MetricsCollector()
    client = TestClient(app, raise_server_exceptions=False)

    search = _measure_search()
    rest = _measure_rest(client, collector)
    ws = _measure_ws_first_delta(client)

    rows = [
        {
            "metric": "search.p95_ms",
            "count": len(search),
            "p50_ms": _percentile(search, 0.5),
            "p95_ms": _percentile(search, 0.95),
            "target_ms": TARGETS["search.p95_ms"],
            "reached": _percentile(search, 0.95) <= TARGETS["search.p95_ms"],
        },
        {
            "metric": "rest.standard_full.p95_ms",
            "count": len(rest),
            "p50_ms": _percentile(rest, 0.5),
            "p95_ms": _percentile(rest, 0.95),
            "target_ms": TARGETS["rest.agent_total_ms.p95_ms"],
            "reached": _percentile(rest, 0.95) <= TARGETS["rest.agent_total_ms.p95_ms"],
        },
        {
            "metric": "ws.first_delta.p95_ms",
            "count": len(ws),
            "p50_ms": _percentile(ws, 0.5),
            "p95_ms": _percentile(ws, 0.95),
            "target_ms": TARGETS["ws.first_delta_ms.p95_ms"],
            "reached": _percentile(ws, 0.95) <= TARGETS["ws.first_delta_ms.p95_ms"],
        },
    ]
    all_ok = all(r["reached"] for r in rows)

    report = {
        "phase": "Phase D #7 性能 smoke（本地）",
        "sample_count": SAMPLE_N,
        "note": "本地工程 smoke，不冒充数据组正式评测",
        "targets": TARGETS,
        "results": rows,
        "all_reached": all_ok,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "perf_smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    md = ["# Phase D #7 性能 smoke 结果（本地）\n"]
    md.append("| 指标 | 样本 | P50 | P95 | 目标 | 达成 |")
    md.append("|------|:----:|----:|----:|-----:|:----:|")
    for r in rows:
        md.append(
            f"| {r['metric']} | {r['count']} | {r['p50_ms']}ms | {r['p95_ms']}ms | "
            f"≤{r['target_ms']}ms | {'✅' if r['reached'] else '❌'} |"
        )
    md.append("")
    md.append(f"**全部达成**: {'✅' if all_ok else '❌'}")
    (REPORT_DIR / "perf_smoke.md").write_text(
        "\n".join(md), encoding="utf-8", newline="\n"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[OK] JSON: {REPORT_DIR / 'perf_smoke.json'}")
    print(f"[OK] MD:   {REPORT_DIR / 'perf_smoke.md'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
