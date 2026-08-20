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
    extract_executive_compensation_excerpt,
    extract_ipo_price_from_hits,
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


def test_extract_from_title():
    assert (
        extract_listing_date_from_hits([_hit(title="康美药业 2001.3.19 上市")])
        == "2001-03-19"
    )


def test_published_at_is_never_used_as_listing_date():
    """8/19 审查：网页发布日期 ≠ 公司上市日期，published_at 绝不作为上市日期。"""
    hits = [_hit(published_at="2001-03-19T00:00:00Z")]
    assert extract_listing_date_from_hits(hits) is None
    # 即使 published_at 有值、snippet/title 无上市语义 → 仍为 None
    hits = [_hit(snippet="康美药业股份有限公司", published_at="2001-03-19T00:00:00Z")]
    assert extract_listing_date_from_hits(hits) is None


def test_extract_chinese_date_format():
    hits = [_hit(snippet="于2001年3月19日在上海证券交易所上市")]
    assert extract_listing_date_from_hits(hits) == "2001-03-19"


def test_extract_no_date_returns_none():
    assert (
        extract_listing_date_from_hits([_hit(snippet="康美药业股份有限公司")]) is None
    )
    assert extract_listing_date_from_hits([]) is None


def test_extract_ipo_price_from_hits():
    hits = [_hit(snippet="波长光电首次公开发行价格为18.20元/股")]
    assert extract_ipo_price_from_hits(hits) == "18.20元/股"


def test_extract_executive_compensation_excerpt_requires_salary_context():
    assert extract_executive_compensation_excerpt(
        [_hit(snippet="公司2024年度高管薪酬披露摘要")]
    ) == "公司2024年度高管薪酬披露摘要"
    assert extract_executive_compensation_excerpt(
        [_hit(snippet="公司2024年度营业收入增长")]
    ) is None


# ── 8/19 审查：上市语义负例（非上市日期不得误填）─────────────


def test_article_publish_date_not_listing():
    hits = [_hit(snippet="文章发布于 2026-08-18，康美药业…")]
    assert extract_listing_date_from_hits(hits) is None


def test_company_founded_date_not_listing():
    hits = [_hit(snippet="公司成立于 1997-01-01，主营业务…")]
    assert extract_listing_date_from_hits(hits) is None
    hits = [_hit(snippet="成立日期 1997-01-01，注册资本 5 亿元")]
    assert extract_listing_date_from_hits(hits) is None


def test_announcement_update_disclosure_dates_not_listing():
    for snippet in (
        "公告日期 2024-03-10，关于回购的公告",
        "更新时间 2025-06-01",
        "年报披露日期 2024-04-30",
    ):
        assert extract_listing_date_from_hits([_hit(snippet=snippet)]) is None


def test_founded_and_listed_dates_pick_listing_only():
    """同文本含成立日期+上市日期 → 只取上市日期（上下文窗口消歧）。"""
    hits = [_hit(snippet="成立日期 1997-01-01，上市日期 2001-03-19")]
    assert extract_listing_date_from_hits(hits) == "2001-03-19"


def test_conflicting_dates_fail_closed():
    """多结果上市日期互异 → 无法裁决 → None（不猜）。"""
    hits = [
        _hit(snippet="上市日期 2001-03-19"),
        _hit(snippet="于 2002-05-01 上市"),
    ]
    assert extract_listing_date_from_hits(hits) is None


def test_same_date_across_hits_ok():
    hits = [
        _hit(snippet="上市日期 2001-03-19"),
        _hit(snippet="于2001年3月19日在上海证券交易所上市"),
    ]
    assert extract_listing_date_from_hits(hits) == "2001-03-19"


def test_exchange_listing_sentences():
    for snippet in (
        "于 2001-03-19 在深圳证券交易所上市",
        "2001-03-19 在北京证券交易所挂牌",
        "2001-03-19 上市，发行价…",
    ):
        assert extract_listing_date_from_hits([_hit(snippet=snippet)]) == "2001-03-19"


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


def test_web_hit_fills_ipo_price(monkeypatch):
    hits = [_hit(snippet="波长光电首次公开发行价格为18.20元/股")]
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: hits)
    state = _fact_state()
    state["company"] = CompanyRef(
        entity_id="company_301421_SZ",
        wind_code="301421.SZ",
        sec_name="波长光电",
        exchange="XSHE",
    )
    out = generate_answer._answer_company_fact(state, "ipo_price")
    assert "18.20元/股" in out["final_response"].answer
    assert out["evidence"][0].source_type == "web_search"


def test_ipo_price_falls_back_to_general_query_when_vertical_empty(monkeypatch):
    calls: list[str] = []

    def _fake_search(query, *args, **kwargs):
        calls.append(query)
        if len(calls) == 1:
            return []
        return [_hit(snippet="波长光电首次公开发行价格为18.20元/股")]

    monkeypatch.setattr(web_search_service, "web_search", _fake_search)
    state = _fact_state()
    state["company"] = CompanyRef(
        entity_id="company_301421_SZ",
        wind_code="301421.SZ",
        sec_name="波长光电",
        exchange="XSHE",
    )
    out = generate_answer._answer_company_fact(state, "ipo_price")
    assert "18.20元/股" in out["final_response"].answer
    assert len(calls) == 2
    assert "301421.SZ" in calls[0]
    assert "301421.SZ" not in calls[1]
    assert "公告" in calls[1]


def test_web_hit_fills_executive_compensation_excerpt(monkeypatch):
    hits = [_hit(snippet="中国平安2024年度高管薪酬披露摘要")]
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: hits)
    state = _fact_state()
    state["company"] = CompanyRef(
        entity_id="company_601318_SH",
        wind_code="601318.SH",
        sec_name="中国平安",
        exchange="XSHG",
    )
    out = generate_answer._answer_company_fact(state, "executive_compensation")
    assert "高管薪酬相关公告摘要" in out["final_response"].answer
    assert out["evidence"][0].source_type == "web_search"
    assert len(out["evidence"][0].value or "") <= 256


def test_in_db_listing_date_does_not_trigger_web_search(monkeypatch):
    """8/19 审查：库内已有 listing_date → 不联网（0 次 web_search 调用）。"""
    calls = {"n": 0}

    def _spy(*a, **k):
        calls["n"] += 1
        return [_hit(snippet="上市日期 1999-01-01")]

    monkeypatch.setattr(web_search_service, "web_search", _spy)
    state = _fact_state()
    state["company"] = CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
        listing_date="2001-03-19",
    )
    out = generate_answer._answer_company_fact(state, "listing_date")
    assert "2001-03-19" in out["final_response"].answer
    assert calls["n"] == 0, "库内已有 listing_date → Web Search 零调用"
