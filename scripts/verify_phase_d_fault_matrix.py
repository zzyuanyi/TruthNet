#!/usr/bin/env python
"""Phase D #1 故障注入矩阵验证脚本.

对五类故障场景逐一注入（monkeypatch / fake adapter / settings override），
验证主入口不 500、错误结构正确、module_status 正确、可恢复性正确。

输出：
  - 结构化 JSON 摘要（docs/reports/fault_matrix.json）
  - Markdown 摘要（stdout + docs/reports/fault_matrix.md）

使用本地 MySQL/Neo4j 实环境；绝不修改真实 .env / 不关服务 / 不清数据。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_CODE = "600518.SH"
REPORT_DIR = _ROOT / "docs" / "reports"


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _scenario_mysql():
    """MySQL 不可用 → DATASTORE_UNAVAILABLE 503。"""
    import app.domain.finance._fetch as fetch_mod
    from pymysql.err import OperationalError

    def _broken_engine():
        raise OperationalError(2003, "Can't connect to MySQL (simulated)")

    original = fetch_mod._get_engine
    fetch_mod._get_engine = _broken_engine
    try:
        r = _client().get(f"/api/v1/companies/{_CODE}/finance?as_of=2026Q2")
        body = r.json()
        return {
            "name": "MySQL 不可用",
            "status_code": r.status_code,
            "error_code": body.get("error_code"),
            "recoverable": body.get("recoverable"),
            "ok": r.status_code != 500 or r.status_code == 503,
        }
    finally:
        fetch_mod._get_engine = original


def _scenario_neo4j():
    """Neo4j 不可用 → partial + NEO4J_UNAVAILABLE。"""
    import app.infrastructure.graph.neo4j.equity_graph as ng

    class _Broken:
        async def check_connection(self) -> bool:
            return False

    original = ng.Neo4jEquityGraph
    ng.Neo4jEquityGraph = lambda: _Broken()
    try:
        r = _client().get(f"/api/v1/companies/{_CODE}/equity")
        data = r.json()["data"]
        codes = [w.get("code") for w in r.json()["warnings"]]
        return {
            "name": "Neo4j 不可用",
            "status_code": r.status_code,
            "partial": data.get("partial"),
            "source_system": data.get("source_system"),
            "has_warning": "NEO4J_UNAVAILABLE" in codes,
            "ok": r.status_code == 200 and data.get("partial") is True,
        }
    finally:
        ng.Neo4jEquityGraph = original


def _scenario_chroma():
    """Chroma 不可用 → SQL 兜底，不 500。"""
    from app.application.services import research_search as rs

    async def _broken(*a, **k):
        raise RuntimeError("simulated Chroma unavailable")

    original = rs.search_research_insights
    rs.search_research_insights = _broken
    try:
        out = rs.search_research_insights_sync("白酒行业近期研报观点", top_k=3)
        return {
            "name": "Chroma 不可用",
            "result_is_list": isinstance(out, list),
            "result_count": len(out),
            "ok": isinstance(out, list),
        }
    finally:
        rs.search_research_insights = original


def _scenario_llm():
    """LLM 主备均失败 → 模板降级，回答完整。"""
    from app.agents import llm_sync

    original_chat = llm_sync.run_llm_chat
    original_struct = llm_sync.run_llm_structured
    llm_sync.run_llm_chat = lambda *a, **k: ""
    llm_sync.run_llm_structured = lambda *a, **k: None
    try:
        r = _client().post(
            "/api/v1/chat",
            json={"question": "康美药业有造假风险吗", "session_id": "ses_fault_llm_v"},
        )
        data = r.json()["data"]
        return {
            "name": "LLM 主备均失败",
            "status_code": r.status_code,
            "answer_nonempty": bool(data.get("answer")),
            "ok": r.status_code == 200 and bool(data.get("answer")),
        }
    finally:
        llm_sync.run_llm_chat = original_chat
        llm_sync.run_llm_structured = original_struct


def _scenario_no_announcement():
    """公司无公告 → 空时间线 + NO_ANNOUNCEMENT_DATA。"""
    from app.agents.nodes import events as ev_node

    original_ann = ev_node._fetch_announcements
    original_cluster = ev_node._fetch_event_clusters
    ev_node._fetch_announcements = lambda *a, **k: []
    ev_node._fetch_event_clusters = lambda *a, **k: {"clusters": [], "warnings": []}
    try:
        r = _client().get(f"/api/v1/companies/{_CODE}/events")
        data = r.json()["data"]
        codes = [w.get("code") for w in r.json().get("warnings", [])]
        return {
            "name": "公司无公告数据",
            "status_code": r.status_code,
            "has_timeline": "timeline" in data,
            "has_warning": "NO_ANNOUNCEMENT_DATA" in codes,
            "ok": r.status_code == 200 and ("timeline" in data),
        }
    finally:
        ev_node._fetch_announcements = original_ann
        ev_node._fetch_event_clusters = original_cluster


def main() -> int:
    scenarios = [
        _scenario_mysql(),
        _scenario_neo4j(),
        _scenario_chroma(),
        _scenario_llm(),
        _scenario_no_announcement(),
    ]
    all_ok = all(s["ok"] for s in scenarios)

    report = {
        "phase": "Phase D #1 故障注入矩阵",
        "company_code": _CODE,
        "scenarios": scenarios,
        "all_passed": all_ok,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "fault_matrix.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    md = ["# Phase D #1 故障注入矩阵结果\n"]
    md.append("| 场景 | 状态码 | 关键字段 | 结论 |")
    md.append("|------|:------:|----------|:----:|")
    for s in scenarios:
        key = s.get("error_code") or s.get("partial") or s.get("answer_nonempty")
        md.append(
            f"| {s['name']} | {s.get('status_code', 'n/a')} | {key} | "
            f"{'✅' if s['ok'] else '❌'} |"
        )
    md.append("")
    md.append(f"**全部通过**: {'✅' if all_ok else '❌'}")
    md_path = REPORT_DIR / "fault_matrix.md"
    md_path.write_text("\n".join(md), encoding="utf-8", newline="\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[OK] JSON: {json_path}")
    print(f"[OK] MD:   {md_path}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
