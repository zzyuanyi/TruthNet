"""v3.3.2-R1 §6/§12：QuerySubjectInterpreter 与 verifier 不变量测试.

覆盖：
- 14 条 verifier 不变量（§12.4：span 不符/越界/重复/未知/遗漏、
  previous 无主体、previous+company span、new 无 span、单 mention
  comparison、重叠 span）；
- off/mock 零调用（§12.1）；
- timeout/invalid fail-closed；
- 一次调用（§12.2）。
"""

from app.application.models.company_resolution import (
    InputSpanDisposition,
    ProposedCompanySpan,
    QuerySubjectInterpretation,
)
from app.application.services.query_subject_interpreter import (
    QuerySubjectInterpreter,
    verify_interpretation,
)
from app.core.config import settings


def _interp(**kw) -> QuerySubjectInterpretation:
    return QuerySubjectInterpretation(**kw)


def _span(text: str, start: int, end: int) -> ProposedCompanySpan:
    return ProposedCompanySpan(text=text, start=start, end=end)


def _um(mention_id: str, text: str, start: int, end: int):
    """便捷构造 UnresolvedMentionInput（输入 mention）。"""
    from app.application.models.company_resolution import UnresolvedMentionInput

    return UnresolvedMentionInput(
        mention_id=mention_id, text=text, start=start, end=end
    )


# ── verifier 不变量（§6.3 / §12.4）─────────────────────────


def test_span_text_must_match_query_slice():
    # span 文本与原文切片不符 -> invalid
    i2 = _interp(
        subject_reference="new",
        additional_company_spans=[_span("贵州茅台", 1, 3)],
    )
    ok2, reason2 = verify_interpretation(i2, "那茅台呢", [], False)
    assert not ok2
    assert "不符" in reason2


def test_span_out_of_bounds_invalid():
    i = _interp(
        subject_reference="new", additional_company_spans=[_span("茅台", 1, 10)]
    )
    ok, reason = verify_interpretation(i, "那茅台呢", [], False)
    assert not ok
    assert "越界" in reason


def test_unknown_and_missing_mention_ids_invalid():
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_x", kind="context")
        ],
    )
    ok, reason = verify_interpretation(
        i, "毛利率正常吗", [_um("m_1", "毛利率", 0, 3)], True
    )
    assert not ok
    assert "未知" in reason
    i2 = _interp(subject_reference="previous", input_span_dispositions=[])
    ok2, reason2 = verify_interpretation(
        i2, "毛利率正常吗", [_um("m_1", "毛利率", 0, 3)], True
    )
    assert not ok2
    assert "遗漏" in reason2


def test_duplicate_mention_id_invalid():
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context"),
            InputSpanDisposition(mention_id="m_1", kind="context"),
        ],
    )
    ok, reason = verify_interpretation(
        i, "毛利率正常吗", [_um("m_1", "毛利率", 0, 3)], True
    )
    assert not ok
    assert "重复" in reason


def test_previous_with_additional_company_span_invalid():
    """中间验收 P0-1：previous + additional_company_spans 可吞掉新主体
    （"台泥的营收" 被解释为沿用康美）。verifier 必须拒绝。"""
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context")
        ],
        additional_company_spans=[_span("台泥", 0, 2)],
        company_relation="single",
    )
    ok, reason = verify_interpretation(
        i, "台泥的营收", [_um("m_1", "台泥", 0, 2)], True
    )
    assert not ok
    assert "携带公司 span" in reason or "additional" in reason


def test_previous_relation_comparison_invalid():
    """中间验收 P0-1：previous 携带双 span + comparison 同样无效。"""
    i = _interp(
        subject_reference="previous",
        additional_company_spans=[_span("茅台", 0, 2), _span("五粮液", 2, 5)],
        company_relation="comparison",
    )
    ok, reason = verify_interpretation(i, "茅台五粮液", [], True)
    assert not ok


def test_uncertain_with_company_span_invalid():
    """中间验收 P0-1：uncertain 与 none 一样不得携带公司 span。"""
    i = _interp(
        subject_reference="uncertain", additional_company_spans=[_span("茅台", 0, 2)]
    )
    ok, reason = verify_interpretation(i, "茅台", [], False)
    assert not ok
    assert "携带公司 span" in reason


# ── 中间验收批次 B1：结构化输入 mention 不变量（P1-1）──────────


def test_input_mention_payload_must_match_query_slice():
    """输入 mention 的 text 必须等于 query 切片，否则 invalid。"""
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context")
        ],
    )
    ok, reason = verify_interpretation(
        i, "有没有存贷双高的风险", [_um("m_1", "现金流", 3, 7)], True
    )
    assert not ok
    assert "与原文不符" in reason


def test_input_mention_duplicate_invalid():
    """输入 mention_id 必须唯一。"""
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context")
        ],
    )
    ok, reason = verify_interpretation(
        i,
        "毛利率正常吗",
        [_um("m_1", "毛利率", 0, 3), _um("m_1", "毛利率", 0, 3)],
        True,
    )
    assert not ok
    assert "重复输入" in reason


def test_disposition_span_must_stay_inside_parent_mention():
    """disposition 提出的 span 必须位于其输入 mention 范围内。"""
    i = _interp(
        subject_reference="new",
        input_span_dispositions=[
            InputSpanDisposition(
                mention_id="m_1",
                kind="company",
                proposed_company_spans=[_span("茅台", 4, 6)],
            )
        ],
    )
    ok, reason = verify_interpretation(
        i, "康美提到茅台", [_um("m_1", "康美", 0, 2)], False
    )
    assert not ok
    assert "越出输入" in reason


def test_additional_span_may_be_outside_parent_but_inside_query():
    """additional_company_spans 可越出输入 mention，但必须在 query 内。"""
    i = _interp(
        subject_reference="new",
        input_span_dispositions=[
            InputSpanDisposition(
                mention_id="m_1",
                kind="company",
                proposed_company_spans=[_span("康美", 0, 2)],
            )
        ],
        additional_company_spans=[_span("茅台", 4, 6)],
        company_relation="reference",
    )
    ok, reason = verify_interpretation(
        i, "康美提到茅台", [_um("m_1", "康美", 0, 2)], False
    )
    assert ok, reason


# ── 最终续审批次 A1：include_current_subject（§4 A1）─────────


def test_include_current_subject_valid_new_comparison():
    """include_current_subject=True：新公司 span + current subject 构成
    comparison 参与者，不再强制原文两个公司 span。"""
    i = _interp(
        subject_reference="new",
        additional_company_spans=[_span("茅台", 1, 3)],
        company_relation="comparison",
        include_current_subject=True,
    )
    ok, reason = verify_interpretation(i, "那茅台呢，对比一下", [], True)
    assert ok, reason


def test_include_current_subject_requires_current_subject():
    """include_current_subject=True 但无 current subject -> invalid。"""
    i = _interp(
        subject_reference="new",
        additional_company_spans=[_span("茅台", 1, 3)],
        company_relation="comparison",
        include_current_subject=True,
    )
    ok, reason = verify_interpretation(i, "那茅台呢，对比一下", [], False)
    assert not ok
    assert "current subject" in reason


def test_include_current_subject_requires_new_reference():
    """include_current_subject=True 只允许 subject_reference=new。"""
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[],
        company_relation="comparison",
        include_current_subject=True,
    )
    ok, reason = verify_interpretation(i, "对比一下", [], True)
    assert not ok
    assert "new" in reason or "span" in reason


def test_include_current_subject_requires_comparison_relation():
    """include_current_subject=True 只允许 company_relation=comparison。"""
    i = _interp(
        subject_reference="new",
        additional_company_spans=[_span("茅台", 1, 3)],
        company_relation="single",
        include_current_subject=True,
    )
    ok, reason = verify_interpretation(i, "那茅台呢", [], True)
    assert not ok
    assert "comparison" in reason


def test_include_current_subject_requires_new_span():
    """include_current_subject=True 必须有至少一个合法新公司 span。"""
    i = _interp(
        subject_reference="new",
        company_relation="comparison",
        include_current_subject=True,
    )
    ok, reason = verify_interpretation(i, "对比一下", [], True)
    assert not ok
    assert "无公司 span" in reason


def test_previous_without_current_subject_invalid():
    i = _interp(subject_reference="previous", input_span_dispositions=[])
    ok, reason = verify_interpretation(i, "毛利率正常吗", [], False)
    assert not ok
    assert "无 current subject" in reason


def test_previous_with_company_span_invalid():
    """防串核心（§6.3 第 10 条）：previous 时 unresolved 必须是 context。"""
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(
                mention_id="m_1",
                kind="company",
                proposed_company_spans=[_span("台泥", 0, 2)],
            )
        ],
    )
    ok, reason = verify_interpretation(
        i, "台泥的营收", [_um("m_1", "台泥", 0, 2)], True
    )
    assert not ok
    assert "非 context" in reason


def test_new_without_company_span_invalid():
    i = _interp(subject_reference="new")
    ok, reason = verify_interpretation(i, "毛利率正常吗", [], False)
    assert not ok
    assert "无公司 span" in reason


def test_company_disposition_without_span_invalid():
    i = _interp(
        subject_reference="new",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="company")
        ],
    )
    ok, reason = verify_interpretation(
        i, "台泥的营收", [_um("m_1", "台泥", 0, 2)], False
    )
    assert not ok
    assert "无 span" in reason


def test_context_disposition_with_span_invalid():
    i = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(
                mention_id="m_1",
                kind="context",
                proposed_company_spans=[_span("存贷双高", 0, 4)],
            )
        ],
    )
    ok, reason = verify_interpretation(
        i, "存贷双高", [_um("m_1", "存贷双高", 0, 4)], True
    )
    assert not ok
    assert "携带 span" in reason


def test_none_with_company_span_invalid():
    i = _interp(
        subject_reference="none", additional_company_spans=[_span("茅台", 1, 3)]
    )
    ok, reason = verify_interpretation(i, "那茅台呢", [], False)
    assert not ok
    assert "携带公司 span" in reason


def test_single_mention_comparison_invalid():
    i = _interp(
        subject_reference="new",
        additional_company_spans=[_span("茅台", 0, 2)],
        company_relation="comparison",
    )
    ok, reason = verify_interpretation(i, "茅台对比", [], False)
    assert not ok
    assert "不足" in reason


def test_overlapping_spans_invalid():
    i = _interp(
        subject_reference="new",
        additional_company_spans=[_span("康美", 0, 2), _span("美药", 1, 3)],
    )
    ok, reason = verify_interpretation(i, "康美药", [], False)
    assert not ok
    assert "重叠" in reason


def test_short_span_invalid():
    i = _interp(subject_reference="new", additional_company_spans=[_span("美", 0, 1)])
    ok, reason = verify_interpretation(i, "美的", [], False)
    assert not ok
    assert "过短" in reason


def test_valid_previous_and_valid_new():
    """合法 previous / 合法 new + 双 span reference。"""
    i1 = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context")
        ],
    )
    ok1, reason1 = verify_interpretation(
        i1, "有没有存贷双高的风险", [_um("m_1", "存贷双高", 3, 7)], True
    )
    assert ok1, reason1
    i2 = _interp(
        subject_reference="new",
        additional_company_spans=[_span("茅台", 1, 3)],
        company_relation="single",
    )
    ok2, reason2 = verify_interpretation(i2, "那茅台呢", [], True)
    assert ok2, reason2
    i3 = _interp(
        subject_reference="new",
        additional_company_spans=[_span("康美", 0, 2), _span("茅台", 4, 6)],
        company_relation="reference",
    )
    ok3, reason3 = verify_interpretation(i3, "康美提到茅台", [], False)
    assert ok3, reason3


# ── 调用策略（§7 / §12.1）─────────────────────────────────


def test_off_mode_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_llm(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    interp = QuerySubjectInterpreter(mode="off")
    status, result = interp.interpret(
        query="毛利率正常吗", unresolved_mentions=[], has_current_subject=True
    )
    assert status == "disabled"
    assert result is None
    assert calls == []


def test_timeout_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", lambda *a, **kw: None)
    interp = QuerySubjectInterpreter(mode="fallback")
    status, result = interp.interpret(
        query="毛利率正常吗", unresolved_mentions=[], has_current_subject=True
    )
    assert status == "timeout"
    assert result is None
    assert interp.last_status == "timeout"


def test_invalid_interpretation_fail_closed(monkeypatch):
    """LLM 返回 verifier 不通过的输出 -> invalid，不应用。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    bad = _interp(subject_reference="previous")  # 无 current subject -> invalid
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", lambda *a, **kw: bad)
    interp = QuerySubjectInterpreter(mode="fallback")
    status, result = interp.interpret(
        query="毛利率正常吗", unresolved_mentions=[], has_current_subject=False
    )
    assert status == "invalid"
    assert result is None


def test_completed_single_call(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    good = _interp(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id="m_1", kind="context")
        ],
    )
    calls = {"n": 0}

    def fake_llm(messages, schema, timeout=None):
        calls["n"] += 1
        return good

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    interp = QuerySubjectInterpreter(mode="fallback")
    status, result = interp.interpret(
        query="有没有存贷双高的风险",
        unresolved_mentions=[_um("m_1", "存贷双高", 3, 7)],
        has_current_subject=True,
    )
    assert status == "completed"
    assert result is not None
    assert calls["n"] == 1  # 单次调用
    assert result.subject_reference == "previous"
