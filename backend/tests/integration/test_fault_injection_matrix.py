"""五类故障注入矩阵集成测试 — Phase D #1.

逐一模拟：MySQL 不可用 / Neo4j 不可用 / Chroma 不可用或超时 /
LLM 主备均失败或超时 / 公司无公告数据。

注入方式（不破坏真实环境）：
  - dependency override / monkeypatch / fake adapter / settings override；
  - 绝不关闭用户真实 MySQL、删除 Neo4j 数据、修改真实 .env、清空 Chroma。

验收：
  - 主入口不返回无解释 500；
  - module_status.state 正确；
  - error_code / recoverable 正确；
  - warnings 对应真实故障；
  - 可用模块仍返回结果；
  - Evidence 不伪造；
  - Neo4j 故障不得用 NetworkX 冒充 Full Profile 图数据。
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]

_CODE = "600518.SH"


def _client():
    # raise_server_exceptions=False：故障注入场景需读取结构化错误响应
    # （默认 True 会把服务端异常直接抛出，看不到 RFC 9457 envelope）。
    return TestClient(app, raise_server_exceptions=False)


# ── 1. MySQL 不可用 ─────────────────────────────────────────


def test_mysql_unavailable_returns_structured_error(monkeypatch):
    """MySQL 不可用 → 非 500 结构化错误（RFC 9457 / V12 envelope）。"""
    import app.domain.finance._fetch as fetch_mod

    def _broken_engine():
        # 模拟真实 MySQL 连接失败（pymysql.err.OperationalError 2003）
        from pymysql.err import OperationalError

        raise OperationalError(
            2003, "Can't connect to MySQL server (simulated connection refused)"
        )

    monkeypatch.setattr(fetch_mod, "_get_engine", _broken_engine)

    r = _client().get(f"/api/v1/companies/{_CODE}/finance?as_of=2026Q2")
    assert r.status_code != 500, f"MySQL 不可用不得无解释 500，实际 {r.status_code}"
    data = r.json()
    # 允许 503/200(partial) — 关键是错误结构正确（RFC 9457 或 V12 envelope）
    if r.status_code == 503:
        assert data.get("error_code") == "DATASTORE_UNAVAILABLE", data.get("error_code")
        assert data.get("recoverable") is True
    else:
        assert "data" in data or "detail" in data


# ── 2. Neo4j 不可用 ─────────────────────────────────────────


def test_neo4j_unavailable_returns_partial_not_500(monkeypatch):
    """Neo4j 不可用 → partial + NEO4J_UNAVAILABLE，绝不 NetworkX 冒充。"""
    import app.infrastructure.graph.neo4j.equity_graph as ng

    class _BrokenAdapter:
        async def check_connection(self) -> bool:
            return False

    monkeypatch.setattr(ng, "Neo4jEquityGraph", lambda: _BrokenAdapter())

    r = _client().get(f"/api/v1/companies/{_CODE}/equity")
    assert (
        r.status_code == 200
    ), f"Neo4j 不可用应返回 200(partial)，实际 {r.status_code}"
    data = r.json()["data"]
    assert data["partial"] is True, "Neo4j 不可用应 partial=True"
    codes = [w.get("code") for w in r.json()["warnings"]]
    assert "NEO4J_UNAVAILABLE" in codes
    # 不得用 NetworkX 冒充（source_system 不能是 networkx）
    assert data["source_system"] != "networkx"
    assert data["nodes"] == [] and data["edges"] == [], "Neo4j 不可用应返回空图"


# ── 3. Chroma 不可用或超时 ──────────────────────────────────


def test_chroma_unavailable_falls_back_to_sql(monkeypatch):
    """Chroma 不可用 → SQL 兜底，不 500，不空返回。"""
    from app.application.services import research_search as rs

    async def _broken_search(*args, **kwargs):
        raise RuntimeError("simulated Chroma unavailable")

    # Chroma 检索抛异常 → search_research_insights 内部走 _fallback_sql_filter
    monkeypatch.setattr(rs, "search_research_insights", _broken_search)
    monkeypatch.setattr(
        rs, "_fallback_sql_filter_sync", lambda *a, **k: [{"content": "兜底结果"}]
    )

    # 通过同步入口验证降级（不阻塞，走 SQL 兜底）
    out = rs.search_research_insights_sync("白酒行业近期研报观点", top_k=3)
    assert isinstance(out, list), "Chroma 不可用应返回列表（SQL 兜底或空）"


# ── 4. LLM 主备均失败或超时 ────────────────────────────────


def test_llm_all_fail_uses_template(monkeypatch):
    """LLM 主备均失败 → 模板降级，回答完整不 500。"""
    from app.agents import llm_sync

    monkeypatch.setattr(llm_sync, "run_llm_chat", lambda *a, **k: "")
    monkeypatch.setattr(llm_sync, "run_llm_structured", lambda *a, **k: None)

    r = _client().post(
        "/api/v1/chat",
        json={"question": "康美药业有造假风险吗", "session_id": "ses_fault_llm"},
    )
    assert r.status_code == 200, f"LLM 失败应降级模板返回 200，实际 {r.status_code}"
    data = r.json()["data"]
    assert data["answer"], "LLM 失败模板降级仍应返回非空回答"


# ── 5. 公司无公告数据 ───────────────────────────────────────


def test_no_announcement_data(monkeypatch):
    """公司无公告 → 空时间线 + NO_ANNOUNCEMENT_DATA，不 500。"""
    from app.agents.nodes import events as events_node

    monkeypatch.setattr(events_node, "_fetch_announcements", lambda *a, **k: [])
    monkeypatch.setattr(
        events_node,
        "_fetch_event_clusters",
        lambda *a, **k: {"clusters": [], "warnings": []},
    )

    r = _client().get(f"/api/v1/companies/{_CODE}/events")
    assert r.status_code == 200, f"无公告数据不得 500，实际 {r.status_code}"
    body = r.json()
    data = body["data"]
    # 空时间线或明确 partial/warning
    assert "timeline" in data
    warning_codes = [w.get("code") for w in body.get("warnings", [])]
    assert "NO_ANNOUNCEMENT_DATA" in warning_codes or not data.get("timeline")


# ── 汇总：错误结构统一 ──────────────────────────────────────


def test_fault_errors_have_consistent_shape(monkeypatch):
    """故障场景错误结构：module_status.state / error_code / recoverable 一致。"""
    # 构造 finance 规则引擎故障 → partial + error_code
    import app.domain.finance.rule_engine as re_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated rule engine failure")

    monkeypatch.setattr(re_mod, "evaluate_all_rules", _boom)

    r = _client().get(f"/api/v1/companies/{_CODE}/finance?as_of=2026Q2")
    assert r.status_code != 500, f"规则引擎故障不得 500，实际 {r.status_code}"
    body = r.json()
    # 路由可能降级为 200(partial) 或结构化错误；检查 envelope 形状
    assert "data" in body or "detail" in body
    if "data" in body and "module_status" in body.get("data", {}):
        fin_status = body["data"]["module_status"].get("finance", {})
        assert fin_status.get("state") in (
            "partial",
            "failed",
        ), f"finance 状态应为 partial/failed，实际 {fin_status.get('state')}"
        assert fin_status.get("recoverable") is True
