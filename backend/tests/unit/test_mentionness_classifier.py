"""v3.3 批次 D / v3.3.1 §9.3 — CompanyMentionnessClassifier 测试（10.3 矩阵）.

- off/mock 零调用；
- 输出 schema 不含 wind_code（结构约束）；
- span_id 不匹配/重复/遗漏 → invalid（批量完整覆盖校验）；
- 超时/异常 → 确定性 not_found；
- 一条 query 最多一次 mentionness LLM 调用（classify_many）；
- resolver 集成：suggest 记录 verdicts、off 零记录、权威行为不变。
"""

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


def test_resolver_records_verdicts_in_suggest_authority_unchanged(monkeypatch):
    """resolver 集成：suggest 下零候选 span 记录 verdicts，但权威行为
    不变（not_found 阻断 + 不沿用历史）。"""
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
    # 权威行为不变：not_found 阻断（intent 保持确定性 single 路径）
    assert r.mentions[0].status == "not_found"
    assert not r.selected_companies
    # verdicts 仅记录（span_id 校验不匹配 → invalid 不记录）
    assert r.mentionness_verdicts == []


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
