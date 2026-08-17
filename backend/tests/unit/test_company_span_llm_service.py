"""8/17 LLM-NER 子实体提取 — company_span_llm_service 测试.

覆盖：
- off/mock 零调用；
- LLM 提取成功：批量返回子实体，校验原文切片；
- 校验失败（输出数不匹配 / 子串非原文切片）→ 整体 fail-closed；
- Resolver 集成：长 not_found span 提取子实体 → 二次链接
  （命中 → 用子实体识别；不命中 → 报子实体疑似替代整句）；
- 短 span（<5 字）不触发提取。
"""

from app.application.models.company_resolution import (
    EntityMention,
    make_mention_id,
)
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.application.services.company_span_llm_service import (
    CompanySpanLLMExtractor,
    SpanExtractionBatch,
    SpanExtractionOutput,
)
from app.core.config import settings
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


def _mention(text: str, start: int, end: int) -> EntityMention:
    return EntityMention(
        mention_id=make_mention_id(start, end, text),
        text=text,
        start=start,
        end=end,
        status="not_found",
    )


def test_off_mode_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "off")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    ext = CompanySpanLLMExtractor(mode="off")
    result = ext.extract_many(
        user_query="证券机构对金百泽的评价",
        mentions=[_mention("证券机构对金百泽", 0, 8)],
    )
    assert result == {}
    assert calls == []


def test_mock_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    ext = CompanySpanLLMExtractor(mode="suggest")
    result = ext.extract_many(
        user_query="证券机构对金百泽的评价",
        mentions=[_mention("证券机构对金百泽", 0, 8)],
    )
    assert result == {}
    assert calls == []


def test_extract_success_validates_original_slice(monkeypatch):
    """提取成功：子串必须位于输入 span 的原文范围内。"""
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    batch = SpanExtractionBatch(
        results=[SpanExtractionOutput(has_company=True, company_span="金百泽")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: batch
    )
    ext = CompanySpanLLMExtractor(mode="suggest")
    result = ext.extract_many(
        user_query="证券机构对金百泽的评价",
        mentions=[_mention("证券机构对金百泽", 0, 8)],
    )
    assert ext.last_status == "completed"
    mid = make_mention_id(0, 8, "证券机构对金百泽")
    assert result.get(mid) == "金百泽"


def test_extract_non_slice_fail_closed(monkeypatch):
    """子串非原文切片（LLM 编造）→ 整体 fail-closed。"""
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    batch = SpanExtractionBatch(
        results=[SpanExtractionOutput(has_company=True, company_span="编造公司")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: batch
    )
    ext = CompanySpanLLMExtractor(mode="suggest")
    result = ext.extract_many(
        user_query="证券机构对金百泽的评价",
        mentions=[_mention("证券机构对金百泽", 0, 8)],
    )
    assert result == {}
    assert ext.last_status == "invalid"


def test_extract_count_mismatch_fail_closed(monkeypatch):
    """输出数与输入不匹配 → fail-closed。"""
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    batch = SpanExtractionBatch(results=[])
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: batch
    )
    ext = CompanySpanLLMExtractor(mode="suggest")
    result = ext.extract_many(
        user_query="证券机构对金百泽的评价",
        mentions=[_mention("证券机构对金百泽", 0, 8)],
    )
    assert result == {}


def test_short_span_not_extracted():
    """短 span（<触发长度）不触发提取（守卫）。"""
    ext = CompanySpanLLMExtractor(mode="suggest")
    result = ext.extract_many(
        user_query="融资融券的风险",
        mentions=[_mention("融资融券", 0, 4)],
    )
    assert result == {}
    assert ext.last_status == "disabled"


def test_resolver_relinks_to_sub_entity_not_found(monkeypatch):
    """Resolver 集成：长 not_found span 提取子实体 → 报子实体疑似
    （"证券机构对金百泽" → "金百泽"，不再整句当公司）。"""
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    batch = SpanExtractionBatch(
        results=[SpanExtractionOutput(has_company=True, company_span="金百泽")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: batch
    )
    ext = CompanySpanLLMExtractor(mode="suggest")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), span_extractor=ext)
    r = resolver.resolve("证券机构对金百泽的评价如何")
    nf = [m for m in r.mentions if m.status == "not_found"]
    assert nf, "应保留 not_found mention（子实体不在库）"
    assert nf[0].text == "金百泽", f"应报子实体而非整句，实际 {nf[0].text!r}"
    assert "证券机构对" not in nf[0].text


def test_resolver_relink_hits_real_company(monkeypatch):
    """Resolver 集成：子实体命中库内公司 → 直接识别（治本：库内公司
    被施事/介词句式吞掉的场景）。"""
    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    batch = SpanExtractionBatch(
        results=[SpanExtractionOutput(has_company=True, company_span="康美药业")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: batch
    )
    ext = CompanySpanLLMExtractor(mode="suggest")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), span_extractor=ext)
    r = resolver.resolve("研究员点评康美药业的风险")
    assert r.selected_companies, "子实体应命中库内公司"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_resolver_no_extractor_keeps_whole_span():
    """无 span_extractor（off 环境）→ 保持整句 not_found（原逻辑）。"""
    resolver = CompanyEntityResolver(SQLiteCompanyRepository())
    r = resolver.resolve("证券机构对金百泽的评价如何")
    nf = [m for m in r.mentions if m.status == "not_found"]
    assert nf
    assert nf[0].text == "证券机构对金百泽"
