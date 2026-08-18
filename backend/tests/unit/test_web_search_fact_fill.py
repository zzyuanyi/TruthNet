"""公司事实联网回填测试 — Phase E 会5（首个示范触发点）.

覆盖：
- extract_listing_date_from_hits 纯函数（多种日期格式/无日期/空）；
- _answer_company_fact 接入：off 默认行为与现状一致；
  mock 命中 → 填充值 + 来源标注；mock 无命中 → 原「未覆盖」降级。
"""

from __future__ import annotations

from app.agents.nodes import generate_answer
from app.agents.state import CompanyRef, RuntimeState
from app.application.ports.web_search_provider import SearchResult
from app.application.services import web_search_service
from app.application.services.web_search_fact_fill import (
    extract_listing_date_from_hits,
)
from app.core.config import settings


def _fact_state() -> dict:
    """公司事实问答 state：康美药业，listing_date 库内为空。"""
    return {
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }


# ── 纯函数：extract_listing_date_from_hits ─────────────────


def _hit(snippet: str = "", title: str = "", published_at: str | None = None):
    return SearchResult(
        title=title,
        url="https://x.test/1",
        snippet=snippet,
        published_at=published_at,
        source="mock",
    )


def test_extract_from_snippet():
    hits = [_hit(snippet="康美药业上市日期 2001-03-19，1999年改制…")]
    assert extract_listing_date_from_hits(hits) == "2001-03-19"


def test_extract_from_title_and_published_at():
    assert (
        extract_listing_date_from_hits([_hit(title="康美药业 2001.3.19 上市")])
        == "2001-03-19"
    )
    assert (
        extract_listing_date_from_hits([_hit(published_at="2001-03-19T00:00:00Z")])
        == "2001-03-19"
    )


def test_extract_chinese_date_format():
    hits = [_hit(snippet="于2001年3月19日在上海证券交易所上市")]
    assert extract_listing_date_from_hits(hits) == "2001-03-19"


def test_extract_no_date_returns_none():
    assert (
        extract_listing_date_from_hits([_hit(snippet="康美药业股份有限公司")]) is None
    )
    assert extract_listing_date_from_hits([]) is None


# ── _answer_company_fact 接入 ───────────────────────────────


def test_off_default_behavior_unchanged(monkeypatch):
    """off 门：库内无值 → 原「未覆盖」降级，无 claim/evidence（与现状一致）。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    out = generate_answer._answer_company_fact(_fact_state(), "listing_date")
    assert "当前结构化数据范围未覆盖" in out["final_response"].answer
    assert out["claims"] == []
    assert out["evidence"] == []


def test_web_hit_fills_value_and_annotates_source(monkeypatch):
    """mock 命中含日期 → 填充值 + source_type=web_search 证据 + limitation。"""
    hits = [_hit(title="康美药业_百度百科", snippet="上市日期 2001-03-19")]
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: hits)
    out = generate_answer._answer_company_fact(_fact_state(), "listing_date")
    fr = out["final_response"]
    assert "2001-03-19" in fr.answer
    assert "联网检索" in fr.answer
    assert len(fr.evidence) == 1
    ev = fr.evidence[0]
    assert ev.source_type == "web_search"
    assert ev.source_uri == "https://x.test/1"
    assert ev.source_excerpt == "上市日期 2001-03-19"
    assert ev.field_path == "listing_date"
    assert fr.claims[0].evidence_ids == [ev.evidence_id]
    assert any("联网检索" in lim for lim in fr.claims[0].limitations)


def test_web_hit_without_date_falls_back(monkeypatch):
    """mock 命中但解析不出日期 → 原「未覆盖」降级，不伪造。"""
    hits = [_hit(title="康美药业", snippet="无日期内容")]
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: hits)
    out = generate_answer._answer_company_fact(_fact_state(), "listing_date")
    assert "当前结构化数据范围未覆盖" in out["final_response"].answer
    assert out["claims"] == []
    assert out["evidence"] == []
