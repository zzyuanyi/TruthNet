"""v3.3.1 §5 批次 A：查询预算崩溃修复与顶层原始 span 公平召回.

反例（§5.4 / §12.2）：
- 第 13 次查询不抛异常（P0：'NoneType' object has no attribute 'matches'）；
- 四个复杂片段后追加"茅台营收"，茅台原始 span 仍获查询机会；
- 顶层 span 数超过预算上限 → 整体 needs_refinement、零自动绑定；
- 相同 normalized text 只查一次；
- Repository 总调用次数不超过 limit；
- 预算耗尽后不得继续递归查询。
"""

from app.application.models.company_resolution import (
    CandidateLookupResult,
    EntityMention,
    make_mention_id,
)
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.application.services.company_mention_proposal_service import (
    ProposalLookupBudget,
)


class _CountingLookup:
    """零候选 stub：记录每次查询文本。"""

    def __init__(self):
        self.calls: list[str] = []

    def lookup_mention(self, text: str) -> CandidateLookupResult:
        self.calls.append(text)
        return CandidateLookupResult()


def _span(text: str, start: int, end: int) -> EntityMention:
    return EntityMention(
        mention_id=make_mention_id(start, end, text),
        text=text,
        start=start,
        end=end,
    )


def _monkeypatch_spans(monkeypatch, spans: list[EntityMention]) -> None:
    # 最终续审 §5 B1：resolver 消费 extract_company_mention_result，
    # patch 目标同步为结构化结果
    from app.application.models.company_resolution import (
        MentionExtractionResult,
    )

    monkeypatch.setattr(
        "app.application.services.company_entity_resolver.extract_company_mention_result",
        lambda q: MentionExtractionResult(mentions=spans),
    )


# ── 预算类：显式 Outcome 语义（§5.1）─────────────────────────


def test_budget_outcome_explicit_not_none():
    """耗尽返回 budget_exhausted=True/result=None，缓存命中返回结果对象；
    零候选与耗尽不再共用 None 语义。"""
    lookup = _CountingLookup()
    budget = ProposalLookupBudget(lookup, limit=3)
    for _ in range(3):
        budget.lookup("茅台")  # memoize：只计数一次
    assert len(lookup.calls) == 1
    for i in range(2):
        budget.lookup(f"span_{i}")
    assert budget.exhausted
    outcome = budget.lookup("never_seen")
    assert outcome.budget_exhausted is True
    assert outcome.result is None
    cached = budget.lookup("茅台")
    assert cached.budget_exhausted is False
    assert cached.result is not None
    assert len(lookup.calls) == 3  # 耗尽后不查询、不缓存


# ── P0 反例：预算耗尽不崩溃（§5.1 / §12.2）──────────────────


def test_exhaustion_does_not_crash_marks_refinement(monkeypatch):
    """P0 反例：预算耗尽不再以 AttributeError 崩溃，而是
    needs_refinement + proposal_budget_exceeded issue；耗尽后零查询。"""
    lookup = _CountingLookup()
    spans = [
        _span("甲公司营收的增速", 0, 7),
        _span("乙公司营收的增速", 8, 15),
        _span("丙公司营收的增速", 16, 23),
    ]
    _monkeypatch_spans(monkeypatch, spans)
    resolver = CompanyEntityResolver(lookup, lookup_limit=4)
    r = resolver.resolve("甲公司营收的增速乙公司营收的增速丙公司营收的增速")
    assert "proposal_budget_exceeded" in [i.code for i in r.resolution_issues]
    assert any(m.status == "needs_refinement" for m in r.mentions)
    assert not r.selected_companies
    assert len(lookup.calls) == 4  # 耗尽后不再继续递归查询


# ── 公平召回：顶层原始 span 预留（§5.2 / §12.2）───────────────


def test_trailing_precise_span_gets_original_query_chance(monkeypatch):
    """四个复杂片段后追加"茅台营收"：茅台原始 span 必须在 prime 阶段
    获得查询机会（首个查询批含全部顶层原始文本），且不重复查询。"""
    lookup = _CountingLookup()
    spans = [
        _span("甲公司营收的增速", 0, 7),
        _span("乙公司营收的增速", 8, 15),
        _span("丙公司营收的增速", 16, 23),
        _span("丁公司营收的增速", 24, 31),
        _span("茅台营收", 32, 36),
    ]
    _monkeypatch_spans(monkeypatch, spans)
    resolver = CompanyEntityResolver(lookup)
    resolver.resolve(
        "甲公司营收的增速乙公司营收的增速丙公司营收的增速丁公司营收的增速茅台营收"
    )
    assert set(lookup.calls[:5]) == {
        "甲公司营收的增速",
        "乙公司营收的增速",
        "丙公司营收的增速",
        "丁公司营收的增速",
        "茅台营收",
    }
    assert lookup.calls.count("茅台营收") == 1
    assert len(lookup.calls) <= 12


def test_too_many_top_spans_fail_closed(monkeypatch):
    """顶层唯一 span 数超过预算上限 → 整体 needs_refinement、
    too_many_entity_mentions issue、零自动绑定、零 Repository 调用。"""
    lookup = _CountingLookup()
    spans = [_span(f"未知公司{i}", i * 4, i * 4 + 4) for i in range(5)]
    _monkeypatch_spans(monkeypatch, spans)
    resolver = CompanyEntityResolver(lookup, lookup_limit=4)
    r = resolver.resolve(" ".join(m.text for m in spans))
    assert all(m.status == "needs_refinement" for m in r.mentions)
    assert [i.code for i in r.resolution_issues] == ["too_many_entity_mentions"]
    assert not r.selected_companies
    assert not r.needs_confirmation
    assert lookup.calls == []


def test_identical_text_memoized_single_repository_call(monkeypatch):
    """相同 normalized text 只访问 Repository 一次（prime 去重 +
    memoize 双保险）。"""
    lookup = _CountingLookup()
    spans = [_span("康美药业", 0, 4), _span("康美药业", 5, 9)]
    _monkeypatch_spans(monkeypatch, spans)
    resolver = CompanyEntityResolver(lookup)
    resolver.resolve("康美药业 康美药业")
    assert lookup.calls.count("康美药业") == 1
