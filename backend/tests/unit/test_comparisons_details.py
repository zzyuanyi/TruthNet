"""comparisons ⑥ 契约测试 — 触发规则详情（2026-08-11）.

覆盖：
- _build_rule_details 纯函数：多指标 current 展开、D2 元数据（label/
  risk_direction）、规则级 evidence（与 /finance 同源 drafts）；
- 共享函数一致性：comparisons 与 finance 同参数生成同 ID；
- API 真库验收（mysql 模式）：triggered_rule_details 结构 + evidence 可回查。
"""

import pytest

from app.domain.finance.models import RuleResult

_RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


def _triggered_rule(rid: str, status="triggered") -> RuleResult:
    return RuleResult(
        rule_id=rid,
        rule_version="1.1.0",
        rule_name=f"rule-{rid}",
        status=status,
        severity="orange",
        current={
            "gap": {"value": 45.0, "unit": "percentage_point"},
            "acct_rcv_growth": {"value": True, "unit": ""},
        },
        evidence_ids=["ev_bs_gap_20260331", "ev_bs_acct_rcv_growth_20260331"],
        explanation=f"{rid} 触发说明",
    )


def test_build_rule_details_structure():
    from app.api.v1.routers.comparisons import _build_rule_details
    from app.application.services.finance_evidence import (
        build_finance_rule_evidence_drafts,
    )

    results = {rid: _triggered_rule(rid) for rid in _RULE_IDS}
    results["R3"] = _triggered_rule("R3", status="not_triggered")  # 未触发应排除
    built = build_finance_rule_evidence_drafts(
        rules=results, wind_code="600518.SH", as_of="20260331"
    )
    # v3.4：唯一 drafts（跨规则共用 legacy 只落库一次）+ 规则映射（含共享）
    assert len(built["unique_drafts"]) == 2  # gap + acct_rcv_growth 被 6 规则共用
    for rid in ("R1", "R2", "R4", "R5", "R6", "R7"):
        assert len(built["rule_evidence_map"][rid]) == 2  # 每条规则引用同一对证据
    details = _build_rule_details(results, built["rule_evidence_map"], "20260331")

    assert len(details) == 6  # R3 未触发排除
    r1 = next(d for d in details if d.rule_id == "R1")
    assert r1.status == "triggered"
    assert r1.severity == "orange"
    assert r1.as_of == "20260331"
    assert r1.label  # D2 元数据名称非空
    # 多指标展开（不压缩为单一值）
    keys = {m.key for m in r1.metrics}
    assert "gap" in keys and "acct_rcv_growth" in keys
    gap = next(m for m in r1.metrics if m.key == "gap")
    assert gap.value == 45.0
    assert gap.unit == "percentage_point"
    assert gap.risk_direction == "higher_is_riskier"  # D2 元数据方向
    # 布尔值指标不丢类型
    growth = next(m for m in r1.metrics if m.key == "acct_rcv_growth")
    assert growth.value is True
    # 规则级证据（drafts 同源 ID）
    assert r1.evidence_ids
    assert all(eid.startswith("ev_fin_") for eid in r1.evidence_ids)


def test_build_financial_indicators_keeps_period_difference_and_missing_value(
    monkeypatch,
):
    from types import SimpleNamespace

    from app.api.v1.routers.comparisons import _build_financial_indicators
    from app.application.services.indicator_query_service import IndicatorQueryResult

    refs = {
        "A": SimpleNamespace(wind_code="A", sec_name="甲公司"),
        "B": SimpleNamespace(wind_code="B", sec_name="乙公司"),
    }

    def fake_query(code, metric_id, **_kwargs):
        value = 10_000_000_000 if code == "A" else None
        return IndicatorQueryResult(
            status="ok" if value is not None else "insufficient_data",
            indicator=metric_id,
            label=metric_id,
            period="20260630" if value is not None else "",
            value=value,
            unit="CNY",
            observations=[],
            available_periods=["20260630"] if value is not None else [],
        )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_metric", fake_query
    )
    rows = _build_financial_indicators(refs, "20260630")

    assert len(rows) == 5
    assert rows[0].companies[0].value == 10_000_000_000
    assert rows[0].companies[1].value is None
    assert rows[0].difference is None
    assert rows[0].companies[0].period == "20260630"


def test_shared_id_consistency_with_finance():
    """共享纯函数：comparisons 与 finance 的 _normalize_evidence_id 同参数同 ID。"""
    from app.api.v1.routers.finance import _normalize_evidence_id
    from app.application.services.finance_evidence import normalize_rule_evidence_id

    legacy = "ev_bs_gap_20260331"
    assert _normalize_evidence_id(
        legacy, "600518.SH", "20260331"
    ) == normalize_rule_evidence_id(legacy, "600518.SH", "20260331")


def test_normalize_period_param_contract():
    """8/23 双轨 ID 统一契约：period 显式（实际报告期）与默认（请求期）
    在请求期=实际期时同 ID；实际期不同则 ID 不同（证据指向真实披露期）。"""
    from app.application.services.finance_evidence import normalize_rule_evidence_id

    legacy = "ev_bs_acct_rcv_growth_20260331"
    same = normalize_rule_evidence_id(legacy, "600518.SH", "20260331")
    assert (
        normalize_rule_evidence_id(legacy, "600518.SH", "20260331", period="20260331")
        == same
    )
    assert (
        normalize_rule_evidence_id(legacy, "600518.SH", "20260331", period="20251231")
        != same
    )


def test_agent_finance_node_evidence_id_matches_normalize(monkeypatch):
    """8/23 双轨 ID 统一契约：agent 节点（/risk 链路）生成的 ev_fin_* 与
    /finance 路由 normalize 同参同 ID——画像页证据引用可回查，不再 404。

    回归锁定：agent 侧不再使用三段式 source_record_id + rule_id 段生成 ID。
    """
    from datetime import date

    from app.agents.nodes import finance as finance_node_mod
    from app.agents.state import CompanyRef, ExecutionPlan, RuntimeState
    from app.application.services.finance_evidence import normalize_rule_evidence_id

    class _R:
        rule_id = "R1"
        rule_name = "应收–营收背离"
        status = "triggered"
        severity = "red"
        explanation = "应收增速与营收增速背离"
        current = {}
        warnings: list = []
        claim_ids: list = []
        quality = {}
        evidence_ids = ["ev_bs_gap_20260331"]

    monkeypatch.setattr(
        "app.domain.finance.rule_engine.evaluate_all_rules",
        lambda code, as_of: {
            "R1": _R(),
            "R2": None,
            "R3": None,
            "R4": None,
            "R5": None,
            "R6": None,
            "R7": None,
        },
    )
    monkeypatch.setattr(
        finance_node_mod, "_resolve_record", lambda cache, table, src: ({}, None)
    )
    state = {
        "company": CompanyRef(
            entity_id="600518.SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="SH",
        ),
        "plan": ExecutionPlan(
            intent="diagnose", requested_modules=["finance"], as_of=date(2026, 3, 31)
        ),
        "runtime": RuntimeState(trace_id="trace_1", turn_id="turn_1"),
    }
    out = finance_node_mod.finance_node(state)
    evidence = (out.get("results") or {}).finance.evidence
    assert evidence, "finance 节点应产出证据"
    expect = normalize_rule_evidence_id(
        "ev_bs_gap_20260331", "600518.SH", "20260331", period="20260331"
    )
    assert evidence[0].evidence_id == expect
    assert evidence[0].source_record_id == "600518.SH|20260331"


@pytest.mark.skipif(
    __import__("app.core.config", fromlist=["settings"]).settings.SQL_BACKEND
    != "mysql",
    reason="需 mysql 模式真库数据（康美+茅台财务）",
)
def test_api_comparisons_details_mysql():
    """真库 API 验收：triggered_rule_details + evidence 可回查（mysql 模式）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/comparisons",
        json={
            "company_codes": ["600518.SH", "600519.SH"],
            "period": "2026Q2",
            "indicators": ["R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    for summary in body["data"]["companies"]:
        assert "triggered_rule_details" in summary
        for detail in summary["triggered_rule_details"]:
            assert detail["rule_id"].startswith("R")
            assert detail["label"]
            assert detail["as_of"]
            assert isinstance(detail["metrics"], list)
            # 证据规则级且可回查（落库成功时）
            for eid in detail["evidence_ids"]:
                ev_resp = client.get(f"/api/v1/evidence/{eid}")
                assert (
                    ev_resp.status_code == 200
                ), f"evidence {eid} 应可回查，实际 {ev_resp.status_code}"


# ── v3.5：analysis_run 生命周期（completed / partial / failed） ──


def _fake_results():
    """最小 RuleResult 集合（not_triggered，无证据 → persist 不触发）。"""
    from app.domain.finance.models import RuleResult

    return {
        rid: RuleResult(
            rule_id=rid,
            rule_version="1.0.0",
            rule_name=f"rule-{rid}",
            status="not_triggered",
            severity="green",
            current={},
            evidence_ids=[],
            explanation="",
        )
        for rid in _RULE_IDS
    }


def _latest_run_status(client, trace_id: str) -> str:
    from app.core.config import settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        status = conn.execute(
            text(
                "SELECT status FROM analysis_runs "
                "WHERE trace_id = :t ORDER BY created_at DESC LIMIT 1"
            ),
            {"t": trace_id},
        ).scalar()
    return status


@pytest.mark.skipif(
    __import__("app.core.config", fromlist=["settings"]).settings.SQL_BACKEND
    != "mysql",
    reason="需 mysql 模式真库（analysis_runs 表）",
)
def test_analysis_run_lifecycle_completed(monkeypatch):
    """v3.5：全部成功 → analysis_run 标记 completed。"""
    from fastapi.testclient import TestClient

    from app.domain.finance import rule_engine as re_mod
    from app.main import app

    monkeypatch.setattr(
        re_mod, "evaluate_all_rules", lambda code, asof: _fake_results()
    )
    client = TestClient(app)
    resp = client.post(
        "/api/v1/comparisons",
        json={
            "company_codes": ["600518.SH", "600519.SH"],
            "period": "2026Q2",
            "indicators": ["R1"],
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    trace_id = resp.json()["meta"]["trace_id"]
    assert _latest_run_status(client, trace_id) == "completed"


@pytest.mark.skipif(
    __import__("app.core.config", fromlist=["settings"]).settings.SQL_BACKEND
    != "mysql",
    reason="需 mysql 模式真库（analysis_runs 表）",
)
def test_analysis_run_lifecycle_partial(monkeypatch):
    """v3.5：单家公司失败 → analysis_run 标记 partial（不标 completed）。"""
    from fastapi.testclient import TestClient

    from app.domain.finance import rule_engine as re_mod
    from app.main import app

    def _flaky(code, asof):
        if code == "600519.SH":
            raise RuntimeError("simulated failure")
        return _fake_results()

    monkeypatch.setattr(re_mod, "evaluate_all_rules", _flaky)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/comparisons",
        json={
            "company_codes": ["600518.SH", "600519.SH"],
            "period": "2026Q2",
            "indicators": ["R1"],
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    trace_id = resp.json()["meta"]["trace_id"]
    assert _latest_run_status(client, trace_id) == "partial"


@pytest.mark.skipif(
    __import__("app.core.config", fromlist=["settings"]).settings.SQL_BACKEND
    != "mysql",
    reason="需 mysql 模式真库（analysis_runs 表）",
)
def test_analysis_run_lifecycle_failed(monkeypatch):
    """v3.5：全公司失败 → analysis_run 标记 failed。"""
    from fastapi.testclient import TestClient

    from app.domain.finance import rule_engine as re_mod
    from app.main import app

    def _boom(code, asof):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(re_mod, "evaluate_all_rules", _boom)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/comparisons",
        json={
            "company_codes": ["600518.SH", "600519.SH"],
            "period": "2026Q2",
            "indicators": ["R1"],
        },
    )
    assert resp.status_code == 200, resp.text[:300]
    trace_id = resp.json()["meta"]["trace_id"]
    assert _latest_run_status(client, trace_id) == "failed"
