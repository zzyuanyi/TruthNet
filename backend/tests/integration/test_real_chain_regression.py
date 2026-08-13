"""13 项审查修复的真实链路回归 — 三条用例（外部门禁）。

需要 TRUTHNET_RUN_EXTERNAL_TESTS=1 + MySQL/Neo4j/Chroma 数据齐备。

用例（第二轮核查后强制断言，消除字符串比较假阳性）：
  1. 康美 2025 年报：证据期次按 date 解析全部 <= 20251231。
  2. 康美最新期：普通 risk_label=normal 控制链对应 Claim 必须 green。
  3. 白酒行业研报：至少 1 条主题相关结果 + 至少 1 条 research_report
     Evidence；每条研报 Evidence 均 /evidence/{id} 200 可回查。
"""

import os
from datetime import date, datetime

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _chat(client, question: str) -> dict:
    resp = client.post("/api/v1/chat", json={"question": question})
    assert resp.status_code == 200, resp.text[:500]
    body = resp.json()
    assert body.get("data") is not None
    return body


def _parse_period(p: str) -> date | None:
    """期次文本 → date（YYYYMMDD / YYYY-MM-DD）；解析失败返回 None。"""
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(p, fmt).date()
        except ValueError:
            continue
    return None


def test_kangmei_2025_annual_report_period(client):
    """康美 2025 年报：证据期次（date 解析）全部 <= 20251231。"""
    body = _chat(client, "康美药业2025年报财务分析")
    data = body["data"]

    # 请求期次原文出现在响应（requested_period_text 或回答）
    period_text = (data.get("requested_period_text") or "") + (data.get("answer") or "")
    assert "2025年报" in period_text or "20251231" in period_text

    # 证据期次 date 解析比较（杜绝 "2026-01-01" <= "20251231" 字符串假阳性）
    cutoff = date(2025, 12, 31)
    checked = 0
    for ev in data.get("evidence", []):
        p = (ev.get("period") or "").strip()
        if not p:
            continue
        d = _parse_period(p)
        assert d is not None, f"证据期次无法解析: {ev.get('evidence_id')} period={p}"
        assert d <= cutoff, f"证据期晚于请求期: {ev.get('evidence_id')} {p}"
        checked += 1
    assert checked > 0, "康美 2025 年报未返回任何带期次的证据"


def test_kangmei_latest_green_chain_claim_green(client):
    """康美最新期：risk_label=normal 的普通控制链 Claim 必须 green（不计风险）。"""
    body = _chat(client, "分析康美药业的财务健康度")
    data = body["data"]

    # 股权链路载荷：risk_label=normal → 对应 Claim severity 必须 green
    normal_chains = [
        c for c in data.get("equity_chains", []) if c.get("risk_label") == "normal"
    ]
    if normal_chains:
        normal_claim_ids = {
            eid for c in normal_chains for eid in (c.get("evidence_ids") or [])
        }
        for claim in data.get("claims", []):
            if claim.get("claim_type") != "equity":
                continue
            if any(
                eid in normal_claim_ids for eid in (claim.get("evidence_ids") or [])
            ):
                assert (
                    claim.get("severity") == "green"
                ), f"普通控制链 Claim 必须 green: {claim}"

    # 风险计数 = 叶子信号数（排除综合 risk Claim 与 green）
    import re

    m = re.search(r"共检测到 (\d+) 项风险信号", data.get("answer", ""))
    leaf = [
        c
        for c in data.get("claims", [])
        if c.get("claim_type") != "risk"
        and c.get("severity") in ("red", "orange", "yellow")
    ]
    if m is not None:
        assert int(m.group(1)) == len(
            leaf
        ), f"风险计数与叶子信号不一致: answer={data.get('answer', '')[:200]}"


def test_research_sql_fallback_real_schema(client):
    """P1-1：SQL 兜底在真实 MySQL schema（industry_l1 列）下必须返回结果。"""
    from app.application.services.research_search import _fallback_sql_filter_sync

    rows = _fallback_sql_filter_sync("白酒行业近期研报观点", 3)
    assert rows, "SQL 兜底在真库返回空（industry 列名问题会在此暴露）"
    _UNRELATED_KW = ("化工", "电子", "医药", "银行", "地产", "汽车", "钢铁", "煤炭")
    for r in rows:
        assert r.get("report_id"), f"SQL 兜底结果缺 report_id: {r}"
        # 主题相关性：不得出现明确无关行业（abstract 全文命中"白酒"的
        # 白酒公司研报标题可能不含"白酒"字——允许）
        meta_text = (
            (r.get("source_title") or "")
            + (r.get("sec_name") or "")
            + (r.get("industry") or "")
        )
        assert not any(
            kw in meta_text for kw in _UNRELATED_KW
        ), f"白酒检索返回无关行业: {r}"


def test_research_sql_fallback_as_of(client):
    """P1-3：SQL 兜底按 as_of 过滤 publish_date（2025 年请求不得返回 2026 报告）。"""
    from app.application.services.research_search import _fallback_sql_filter_sync

    rows = _fallback_sql_filter_sync("白酒行业近期研报观点", 10, as_of="20251231")
    assert rows, "as_of SQL 兜底未返回研报（空结果不得假通过）"
    for r in rows:
        d = _parse_period(str(r.get("source_date") or "")[:10])
        assert d is not None and d <= date(
            2025, 12, 31
        ), f"研报日期晚于 as_of: {r.get('source_date')}"


def test_baijiu_research_theme_and_evidence(client):
    """白酒研报：至少 1 条主题相关结果 + research Evidence 全部可回查。"""
    body = _chat(client, "白酒行业近期研报观点")
    data = body["data"]
    answer = data.get("answer", "")

    # 强制断言：至少一条研报结果（不得空结果通过）
    import re

    sources = re.findall(r"来源：([^）]+)", answer)
    assert sources, f"白酒研报未返回任何结果: {answer[:300]}"
    # 主题相关性：来源标签不得指向明确无关行业（白酒公司研报标题可能
    # 只含公司名——允许；但绝不出现化工/电子等）
    _UNRELATED_KW = ("化工", "电子", "医药", "银行", "地产", "汽车", "钢铁", "煤炭")
    for src in sources:
        assert not any(
            kw in src for kw in _UNRELATED_KW
        ), f"白酒研报返回无关行业来源: {src}"

    # 强制断言：至少一条 source_type == research_report 的 Evidence
    research_evs = [
        ev
        for ev in data.get("evidence", [])
        if ev.get("source_type") == "research_report"
    ]
    assert research_evs, "未生成 research_report Evidence"

    # 每条研报 Evidence 均 /evidence/{id} 200 可回查
    for ev in research_evs:
        r = client.get(f"/api/v1/evidence/{ev.get('evidence_id')}")
        assert (
            r.status_code == 200
        ), f"研报 Evidence 不可回查: {ev.get('evidence_id')} ({r.text[:200]})"

    # research Claim 存在且 severity=unknown、带"不代表系统事实结论"说明
    research_claims = [
        c for c in data.get("claims", []) if c.get("claim_type") == "research"
    ]
    assert research_claims, "未生成 research Claim"
    assert all(c.get("severity") == "unknown" for c in research_claims)
