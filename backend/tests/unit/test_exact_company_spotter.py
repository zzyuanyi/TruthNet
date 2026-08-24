"""exact_company_spotter 与 resolver 合并单元测试 — v3.3.3 收口批次 C/B。

覆盖（方案 §3.3/§3.5/§5.2）：
  - 官方三题第二家公司补召回（伊利/双汇、茅台/五粮液、中石化/中石油）；
  - 最长优先、区间不重叠；
  - anti-leak：茅台镇/康美丽不命中（必须完整 sec_name）；
  - provider 注入静态名称集：不触碰真实数据库、不创建 Engine；
  - 缓存按 provider.profile_key 隔离（backend/测试库切换不互用）；
  - SQLite provider 返回 fixture 名称并完成 spotting；aliases 语义；
  - extractor 吞词 span 被精确 span 替换；与既有 span 一致时去重。
"""

import pytest

from app.application.models.company_resolution import (
    CandidateLookupResult,
    EntityMention,
)
from app.application.services.company_entity_resolver import _merge_exact_spots
from app.application.services.exact_company_spotter import (
    ExactNameSpan,
    spot_exact_company_spans,
)

_NAMES = frozenset(
    {
        "伊利股份",
        "双汇发展",
        "贵州茅台",
        "五粮液",
        "中国石化",
        "中国石油",
        "康美药业",
    }
)


class _StaticProvider:
    """静态名称集 provider（不触碰数据库；记录加载次数）。"""

    def __init__(self, names, profile_key="static-test"):
        self._names = frozenset(names)
        self.profile_key = profile_key
        self.calls = 0

    def list_company_names(self):
        self.calls += 1
        return self._names


class _ExplodingProvider:
    """一调用就抛异常——空查询短路/异常兜底不得触发。"""

    profile_key = "exploding"

    def list_company_names(self):
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.application.services import exact_company_spotter as m

    m.invalidate_cache()
    yield
    m.invalidate_cache()


def test_spot_official_two_company_questions():
    """官方三题：两家公司名称均被召回（provider 注入，无数据库）。"""
    provider = _StaticProvider(_NAMES)
    spans = spot_exact_company_spans(
        "伊利股份的存货周转天数比双汇发展低多少？", provider
    )
    assert [s.text for s in spans] == ["伊利股份", "双汇发展"]

    spans = spot_exact_company_spans(
        "贵州茅台最新季度毛利率与五粮液相比高多少", provider
    )
    assert [s.text for s in spans] == ["贵州茅台", "五粮液"]

    spans = spot_exact_company_spans("中国石化的上市日期比中国石油早几年？", provider)
    assert [s.text for s in spans] == ["中国石化", "中国石油"]


def test_spot_longest_priority_non_overlapping():
    provider = _StaticProvider(_NAMES)
    spans = spot_exact_company_spans("伊利股份和双汇发展", provider)
    assert [s.text for s in spans] == ["伊利股份", "双汇发展"]
    # 区间不重叠且按原文顺序
    for prev, cur in zip(spans, spans[1:]):
        assert prev.end <= cur.start


def test_spot_anti_leak_requires_full_name():
    """茅台镇/康美丽：无完整 sec_name → 不命中（NIL 不回归）。"""
    provider = _StaticProvider(_NAMES)
    assert spot_exact_company_spans("茅台镇的营收怎么样", provider) == []
    assert spot_exact_company_spans("康美丽的营收怎么样", provider) == []


def test_spot_empty_query_short_circuits_before_provider():
    """空查询在访问 provider 前短路（provider 失败也不影响）。"""
    assert spot_exact_company_spans("", _ExplodingProvider()) == []
    assert spot_exact_company_spans(None, _ExplodingProvider()) == []


def test_provider_failure_returns_empty():
    """provider 加载失败 → 空 spotting，不阻断实体主流程。"""
    assert spot_exact_company_spans("伊利股份的存货", _ExplodingProvider()) == []


def test_sqlite_provider_returns_fixture_names():
    """SQLite provider：返回与 lite fixture 一致的全部 sec_name。"""
    from app.infrastructure.persistence.sqlite.company_name_provider import (
        SQLiteCompanyNameIndexProvider,
    )

    provider = SQLiteCompanyNameIndexProvider()
    names = provider.list_company_names()
    assert {"贵州茅台", "五粮液", "康美药业", "宁德时代"} <= names
    assert provider.profile_key == "sqlite:data/truthnet.db"
    spans = spot_exact_company_spans("贵州茅台的毛利率比五粮液高多少", provider)
    assert [s.text for s in spans] == ["贵州茅台", "五粮液"]


def test_cache_isolated_by_profile_key():
    """不同 profile_key 缓存互用不得发生（测试库/演示库隔离）。"""
    pa = _StaticProvider({"甲公司"}, profile_key="mysql:demo")
    pb = _StaticProvider({"乙公司"}, profile_key="mysql:test")
    assert spot_exact_company_spans("甲公司", pa) != []
    assert spot_exact_company_spans("乙公司", pb) != []
    # pb 的缓存里不得有 pa 的名称（profile 隔离）
    assert spot_exact_company_spans("甲公司", pb) == []
    assert spot_exact_company_spans("乙公司", pa) == []


def test_cache_reused_within_ttl():
    """同 profile 在 TTL 内复用缓存（不重复查询 provider）。"""
    provider = _StaticProvider(_NAMES, profile_key="ttl-test")
    spot_exact_company_spans("伊利股份", provider)
    spot_exact_company_spans("双汇发展", provider)
    assert provider.calls == 1


def test_aliases_spotted_when_present():
    """provider 提供有效别名 → 可 spotting（aliases 由 adapter 解析）。"""
    provider = _StaticProvider({"伊利股份", "双汇发展"}, profile_key="alias-test")
    spans = spot_exact_company_spans("双汇发展的存货", provider)
    assert [s.text for s in spans] == ["双汇发展"]
    # 名称集里没有的文本不命中（空 aliases 不改变结果）
    assert spot_exact_company_spans("不存在的公司名", provider) == []


# ── resolver 合并（_merge_exact_spots）────────────────────────


def test_merge_adds_missing_second_company(monkeypatch):
    """extractor 漏提第二家 → merge 补召回（官方反例形态）。"""
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [ExactNameSpan("双汇发展", 12, 16)],
    )
    mentions = [EntityMention(mention_id="m_0_4", text="伊利股份", start=0, end=4)]
    merged = _merge_exact_spots("伊利股份的存货周转天数比双汇发展低多少？", mentions)
    assert [m.text for m in merged] == ["伊利股份", "双汇发展"]


def test_merge_prefers_exact_over_swallowed_span(monkeypatch):
    """extractor 吞词 span「贵州茅台最新季度」被精确 span 替换。"""
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [
            ExactNameSpan("贵州茅台", 0, 4),
            ExactNameSpan("五粮液", 12, 15),
        ],
    )
    mentions = [
        EntityMention(mention_id="m_0_8", text="贵州茅台最新季度", start=0, end=8)
    ]
    merged = _merge_exact_spots("贵州茅台最新季度毛利率与五粮液相比高多少", mentions)
    assert [m.text for m in merged] == ["贵州茅台", "五粮液"]


def test_merge_identical_span_deduped(monkeypatch):
    """既有 span 与精确 span 完全一致 → 去重（不重复 mention）。"""
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [ExactNameSpan("伊利股份", 0, 4)],
    )
    mentions = [EntityMention(mention_id="m_0_4", text="伊利股份", start=0, end=4)]
    merged = _merge_exact_spots("伊利股份的存货", mentions)
    assert len(merged) == 1
    assert merged[0].text == "伊利股份"


def test_merge_no_spots_returns_original(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [],
    )
    mentions = [EntityMention(mention_id="m_0_4", text="伊利股份", start=0, end=4)]
    assert _merge_exact_spots("任意文本", mentions) == mentions


def test_merge_preserves_explicit_market_alias_over_shorter_exact_spot(monkeypatch):
    """完整市场别名不得被其内部的另一证券短名覆盖。"""
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [ExactNameSpan("太平洋", 0, 3)],
    )
    mentions = [EntityMention(mention_id="m_0_5", text="太平洋保险", start=0, end=5)]
    merged = _merge_exact_spots("太平洋保险最新净利润", mentions)
    assert [(m.text, m.start, m.end) for m in merged] == [("太平洋保险", 0, 5)]


def test_merge_rejects_spot_absent_from_injected_candidate_source(monkeypatch):
    """全局名称索引不得把当前注入候选仓库不认识的名称带入 Resolver。"""
    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        lambda q: [ExactNameSpan("金百泽", 5, 8)],
    )
    mentions = [
        EntityMention(mention_id="m_0_8", text="证券机构对金百泽", start=0, end=8)
    ]

    class _EmptyOutcome:
        budget_exhausted = False
        result = CandidateLookupResult()

    merged = _merge_exact_spots(
        "证券机构对金百泽的评价如何",
        mentions,
        candidate_lookup=lambda _text: _EmptyOutcome(),
    )
    assert [(m.text, m.start, m.end) for m in merged] == [("证券机构对金百泽", 0, 8)]
