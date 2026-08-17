"""v3.3 批次 D / v3.3.1 §9.3 — CompanyMentionnessClassifier 测试（10.3 矩阵）.

- off/mock 零调用；
- 输出 schema 不含 wind_code（结构约束）；
- span_id 不匹配/重复/遗漏 → invalid（批量完整覆盖校验）；
- 超时/异常 → 确定性 not_found；
- 一条 query 最多一次 mentionness LLM 调用（classify_many）；
- 8/16 语义裁决启用（suggest/auto）：non_company_context 生效——
  全判非公司 → 温和 no_company；部分判定 → 移除该 span；verdicts
  校验失败 → fail-closed 保持权威 not_found。
"""

import re

from app.application.models.company_resolution import (
    MentionnessDecision,
    MentionnessVerdict,
)
from app.application.services.company_mentionness_classifier import (
    CompanyMentionnessClassifier,
)
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.core.config import settings
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)


def _non_company_llm(messages, schema, timeout=None):
    """按消息中出现的 span_id 动态判定全部为非公司上下文。"""
    user = messages[-1]["content"]
    ids = re.findall(r"span_id=([^\s'，]+)", user)
    return MentionnessDecision(
        verdicts=[
            MentionnessVerdict(span_id=sid, verdict="non_company_context")
            for sid in ids
        ]
    )


def test_off_mode_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    clf = CompanyMentionnessClassifier(mode="off")
    status, verdict = clf.classify(
        user_query="白酒行业近期研报观点",
        span_id="s1",
        span_text="白酒行业近期研报观点",
    )
    assert status == "disabled"
    assert verdict is None
    assert calls == []


def test_verdict_schema_has_no_wind_code_field():
    """输出 schema 不含 wind_code/补全文本字段（结构上不可能编造代码）。"""
    fields = set(MentionnessVerdict.model_fields.keys())
    assert fields == {"span_id", "verdict", "evidence"}
    decision_fields = set(MentionnessDecision.model_fields.keys())
    assert decision_fields == {"verdicts"}  # 批量外壳同样无 wind_code


def _spans() -> list[dict]:
    return [
        {"span_id": "s1", "span_text": "火星科技行业风险"},
        {"span_id": "s2", "span_text": "某某集团"},
    ]


def test_span_id_mismatch_invalid(monkeypatch):
    """批量校验：输出 span 与输入不完全对应 → invalid（§9.3 反例）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    decision = MentionnessDecision(
        verdicts=[
            MentionnessVerdict(span_id="s1", verdict="abstain"),
            MentionnessVerdict(span_id="other", verdict="abstain"),  # 未知 ID
        ]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    clf = CompanyMentionnessClassifier(mode="suggest")
    status, result = clf.classify_many(user_query="火星科技", spans=_spans())
    assert status == "invalid"
    assert result is None


def test_duplicate_or_missing_verdicts_invalid(monkeypatch):
    """批量校验：重复/遗漏 span_id → invalid（§9.3 反例）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    # 重复（两个 verdict 同 span_id）
    decision = MentionnessDecision(
        verdicts=[
            MentionnessVerdict(span_id="s1", verdict="abstain"),
            MentionnessVerdict(span_id="s1", verdict="abstain"),
        ]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    clf = CompanyMentionnessClassifier(mode="suggest")
    status, _ = clf.classify_many(user_query="火星科技", spans=_spans())
    assert status == "invalid"
    # 遗漏（只覆盖一个 span）
    decision2 = MentionnessDecision(
        verdicts=[MentionnessVerdict(span_id="s1", verdict="abstain")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision2
    )
    status2, _ = clf.classify_many(user_query="火星科技", spans=_spans())
    assert status2 == "invalid"


def test_timeout_returns_timeout(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", lambda *a, **kw: None)
    clf = CompanyMentionnessClassifier(mode="suggest")
    status, result = clf.classify(
        user_query="火星科技行业风险", span_id="s1", span_text="火星科技行业风险"
    )
    assert status == "timeout"
    assert result is None


def test_completed_records_verdict(monkeypatch):
    """批量一次调用：完整覆盖 → completed，且 LLM 只被调用一次。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls = {"n": 0}

    def fake_llm(messages, schema, timeout=None):
        calls["n"] += 1
        # 按消息中出现的 span_id 动态构造（单 span 包装调用时也合法）
        user = messages[-1]["content"]
        ids = [s["span_id"] for s in _spans() if s["span_id"] in user]
        return MentionnessDecision(
            verdicts=[
                MentionnessVerdict(
                    span_id=sid,
                    verdict="company_mention" if sid == "s1" else "abstain",
                )
                for sid in ids
            ]
        )

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    clf = CompanyMentionnessClassifier(mode="suggest")
    status, decision = clf.classify_many(user_query="火星科技", spans=_spans())
    assert status == "completed"
    assert decision is not None
    assert {v.span_id for v in decision.verdicts} == {"s1", "s2"}
    assert calls["n"] == 1  # §9.3：批量一次 query 一次调用（两个 span）
    # 单 span 包装仍可用（再次调用为独立 query 级判定）
    status2, verdict = clf.classify(user_query="火星科技", span_id="s1", span_text="x")
    assert status2 == "completed"
    assert verdict is not None
    assert calls["n"] == 2


def test_resolver_suggest_applies_non_company_context(monkeypatch):
    """8/16 语义裁决启用：suggest 下 non_company_context 生效——全部
    零候选 span 判为非公司上下文 → 温和 no_company（不再报"疑似公司"，
    根治停用词穷举：评价/点评等无需逐个进词表）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", _non_company_llm)
    clf = CompanyMentionnessClassifier(mode="suggest")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), mentionness=clf)
    r = resolver.resolve("评价一下火星科技怎么样")
    assert r.intent == "no_company"
    assert r.reason_code == "non_company_context"
    assert r.unresolved_mentions == []
    assert not r.selected_companies
    assert r.mentionness_verdicts  # 审计字段仍记录判定


def test_resolver_suggest_invalid_verdicts_authority_unchanged(monkeypatch):
    """suggest 下 verdicts 校验失败（span 不匹配）→ 不生效，权威保持
    not_found 阻断（fail-closed，不猜测）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    decision = MentionnessDecision(
        verdicts=[MentionnessVerdict(span_id="__any__", verdict="non_company_context")]
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    clf = CompanyMentionnessClassifier(mode="suggest")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), mentionness=clf)
    r = resolver.resolve("火星科技行业风险")
    assert r.mentions[0].status == "not_found"
    assert not r.selected_companies
    assert r.mentionness_verdicts == []


def test_resolver_suggest_removes_partial_non_company(monkeypatch):
    """8/16：公司 span 有候选 + 零候选 span 判 non_company_context →
    非公司 span 移除，公司正常解析（"康美药业怎么样，评价一下"→康美）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    def fake_llm(messages, schema, timeout=None):
        user = messages[-1]["content"]
        ids = re.findall(r"span_id=([^\s'，]+)", user)
        return MentionnessDecision(
            verdicts=[
                MentionnessVerdict(
                    span_id=sid,
                    verdict=(
                        "non_company_context" if "评价" in sid else "company_mention"
                    ),
                )
                for sid in ids
            ]
        )

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    clf = CompanyMentionnessClassifier(mode="suggest")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), mentionness=clf)
    r = resolver.resolve("康美药业怎么样，评价一下")
    assert r.intent == "single"
    assert r.selected_companies[0].wind_code == "600518.SH"
    assert r.unresolved_mentions == []  # "评价"已被解释为非公司


def test_resolver_off_does_not_call_classifier(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    clf = CompanyMentionnessClassifier(mode="off")
    resolver = CompanyEntityResolver(SQLiteCompanyRepository(), mentionness=clf)
    r = resolver.resolve("火星科技行业风险")
    assert r.mentions[0].status == "not_found"
    assert calls == []  # off 零调用
