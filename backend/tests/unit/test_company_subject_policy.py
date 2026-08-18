"""v3.3.2 §6 批次 B：主体动作闭环与防串反例（§6.5 / §12.2）.

逐条断言 intent/reason_code/company_code：
- 回指短语 + 历史康美 -> continuation 康美（确定性闸门，零 LLM）；
- 那茅台呢 + 历史康美 -> switch 茅台（有效 mention 走现有 relation 层）；
- 回到康美 + 历史茅台 -> switch 康美；
- 防串五例 -> not_found/clarify，绝不 continuation；
- 无历史 + 毛利率正常吗 -> 不伪造主体。
"""

from sqlalchemy import create_engine, text

from app.agents.state import MemoryContext
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)

_TABLE = (
    "CREATE TABLE companies ("
    "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
    "industry_l1 TEXT, aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
    "is_latest INTEGER)"
)


def _lookup(rows: list[tuple]):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(_TABLE))
        for r in rows:
            conn.execute(
                text(
                    "INSERT INTO companies VALUES "
                    "(:eid, :code, :name, 'XSHG', NULL, :aliases, NULL, '1', 1)"
                ),
                {"eid": r[0], "code": r[1], "name": r[2], "aliases": r[3]},
            )
    repo = MySQLCompanyRepository()
    repo._engine = engine
    return repo


def _kangmei_memory() -> MemoryContext:
    return MemoryContext(
        resolved_company_code="600518.SH",
        resolved_entity_name="康美药业",
        is_anaphora=False,
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )


def _maotai_memory() -> MemoryContext:
    return MemoryContext(
        resolved_company_code="600519.SH",
        resolved_entity_name="贵州茅台",
        is_anaphora=False,
        previous_company_codes=["600519.SH"],
        previous_companies=["贵州茅台"],
    )


_REPO = [
    ("c1", "600518.SH", "康美药业", None),
    ("c2", "600519.SH", "贵州茅台", None),
]


# ── 金融追问 + 历史 → continuation（§6.5）───────────────────


def test_anaphora_phrase_continues_kangmei():
    """'总结一下这家公司'+历史康美 -> continuation 康美（无 span，
    回指短语决策）。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "总结一下这家公司", memory=_kangmei_memory()
    )
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"


# ── 显式切换（§6.5：有效 mention 走现有 relation 层）─────────


def test_na_maotai_switches_from_kangmei():
    """'那茅台呢'+历史康美 -> switch 茅台（relation 层按 prev_code
    差异判定）。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "那茅台呢", memory=_kangmei_memory()
    )
    assert r.intent == "switch"
    assert r.selected_companies[0].wind_code == "600519.SH"


def test_na_maotai_compare_keeps_maotai_subject():
    """'那茅台呢，对比一下'+历史康美 -> 跨主体对比：relation=comparison
    且当前主体切换为茅台（§12.1 第 9 轮口径）。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "那茅台呢，对比一下", memory=_kangmei_memory()
    )
    assert r.intent == "comparison"
    assert r.selected_companies[0].wind_code == "600519.SH"


# ── 最终续审 §4 A6：跨主体 comparison 不变量 ──────────────────


def test_comparison_materializes_history_peer():
    """A3：历史康美 + 那茅台呢对比一下 → 精确代码集合 {康美, 茅台}、
    茅台 primary、康美 comparison_peer（origin=history 不伪造 span）。"""
    from app.application.models.company_resolution import (
        validate_finalized_relation_roles,
    )

    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "那茅台呢，对比一下", memory=_kangmei_memory()
    )
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    by_code = {m.selected_wind_code: m for m in r.mentions}
    assert by_code["600519.SH"].role == "primary"
    assert by_code["600518.SH"].role == "comparison_peer"
    assert by_code["600518.SH"].origin == "history"
    assert by_code["600518.SH"].start is None
    assert validate_finalized_relation_roles("comparison", r.mentions) is True


def test_comparison_without_history_not_executable():
    """A3.5：无历史 + 单公司对比 → 不得生成可执行 comparison。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("茅台对比一下", memory=None)
    assert r.intent != "comparison"
    assert len(r.selected_companies) < 2


def test_comparison_same_code_not_duplicated():
    """A3.5：历史茅台 + 茅台对比 → 不得用同一代码凑两家。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "茅台对比一下", memory=_maotai_memory()
    )
    codes = [str(c.wind_code) for c in r.selected_companies]
    assert len(codes) < 2, f"不得用同一代码凑 comparison: {codes}"


def test_back_to_kangmei_switches_from_maotai():
    """'回到康美，存货周转情况如何'+历史茅台 -> switch 康美。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "回到康美，存货周转情况如何", memory=_maotai_memory()
    )
    assert r.intent == "switch"
    assert r.selected_companies[0].wind_code == "600518.SH"


# ── 防串不变量（§6.4 / §12.2）──────────────────────────────


def test_anti_leak_blocked():
    """防串五例：历史康美存在时仍阻断继承，绝不 continuation。"""
    resolver = CompanyEntityResolver(_lookup(_REPO))
    for q in [
        "茅台镇的营收",
        "康美丽的营收",
        "台泥的营收",
        "小米的营收",
        "火星科技怎么样",
    ]:
        r = resolver.resolve(q, memory=_kangmei_memory())
        assert r.intent != "continuation", f"{q} 不得继承康美"
        assert not r.selected_companies, f"{q} 不得绑定任何公司"


def test_no_history_no_fabrication():
    """无历史主体的'毛利率正常吗' -> 不伪造主体。"""
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("毛利率正常吗", memory=None)
    assert r.intent != "continuation"
    assert not r.selected_companies


# ── v3.3.4 收口复核清单 §6：比较语法 operator 边界 ────────────────


class _FakeSpan:
    def __init__(self, text: str, start: int, end: int):
        self.text = text
        self.start = start
        self.end = end


def _patch_spotter(monkeypatch, names: list[str]):
    """把精确名称 spotting 通道替换为给定名称集的朴素扫描。"""

    def fake(query, provider=None):
        spans = []
        for name in names:
            idx = (query or "").find(name)
            while idx >= 0:
                spans.append(_FakeSpan(name, idx, idx + len(name)))
                idx = (query or "").find(name, idx + 1)
        return spans

    monkeypatch.setattr(
        "app.application.services.exact_company_spotter.spot_exact_company_spans",
        fake,
    )


def test_full_prefix_comparison_drops_operator_span(monkeypatch):
    """清单 §6.2-1：「全面对比康美和茅台」→ comparison 两家，无
    not_found 残留、无 unresolved（operator 在比较语法位置被忽略）。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("全面对比康美和茅台", memory=None)
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    assert r.unresolved_mentions == []
    assert all(m.status != "not_found" for m in r.mentions)


def test_full_prefix_comparison_full_names(monkeypatch):
    """清单 §6.2-2：「全面对比康美药业和贵州茅台」→ comparison 两家。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "全面对比康美药业和贵州茅台", memory=None
    )
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    assert r.unresolved_mentions == []


def test_full_suffix_comparison_keeps_two_companies(monkeypatch):
    """清单 §6.2-3：「康美药业和贵州茅台全面对比」→ comparison 两家
    （精确名称 spotting 通道覆盖粗 span，不产生 operator 残留）。"""
    _patch_spotter(monkeypatch, ["康美药业", "贵州茅台"])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "康美药业和贵州茅台全面对比", memory=None
    )
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    assert r.unresolved_mentions == []


def test_three_company_full_comparison_not_truncated(monkeypatch):
    """清单 §6.2-4：「康美、茅台、五粮液全面对比」→ comparison 三家，
    不截断、无 not_found 残留。"""
    repo_rows = _REPO + [("c3", "000858.SZ", "五粮液", None)]
    _patch_spotter(monkeypatch, ["康美", "茅台", "五粮液"])
    r = CompanyEntityResolver(_lookup(repo_rows)).resolve(
        "康美、茅台、五粮液全面对比", memory=None
    )
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH", "000858.SZ"}
    assert r.unresolved_mentions == []


def test_legit_company_named_quanmian_not_dropped(monkeypatch):
    """清单 §6.2-5：合法公司名「全面科技」命中候选 → 不得被 operator
    规则误删。"""
    repo_rows = _REPO + [("c4", "603999.SH", "全面科技", None)]
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(repo_rows)).resolve(
        "全面科技对比茅台", memory=None
    )
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"603999.SH", "600519.SH"}


def test_comparison_operator_alone_stays_safe(monkeypatch):
    """清单 §6.3：无有效公司时「全面对比」不伪造主体 → 安全澄清。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("全面对比", memory=None)
    assert r.intent != "comparison"
    assert r.selected_companies == []


def test_nil_regression_mars_keeps_blocking(monkeypatch):
    """清单 §6.2/§9：火星科技 NIL 保持原有阻断（不被 operator 规则
    影响），unresolved 保留证据（复合 span 整体 not_found）。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "火星科技和茅台对比一下", memory=None
    )
    assert r.unresolved_mentions, "NIL 必须保留阻断证据"
    assert r.intent != "comparison"


# ── v3.3.4 收口复核审查整改：P1 NIL 阻断 + P2a 范围词一致性 ────────────


def test_p1_unknown_word_comparison_blocked(monkeypatch):
    """审查 P1：「未知词对比康美和茅台」两家已绑定但残留 NIL → 不得
    进入可执行 comparison，unresolved 保留（不静默丢弃）。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "未知词对比康美和茅台", memory=None
    )
    assert r.intent != "comparison"
    assert "未知词" in r.unresolved_mentions


def test_p1_mars_three_company_comparison_blocked(monkeypatch):
    """审查 P1：「火星科技、康美和茅台对比」→ 三家其中一家 NIL，
    同样不得执行 comparison。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "火星科技、康美和茅台对比", memory=None
    )
    assert r.intent != "comparison"
    assert r.unresolved_mentions


def test_p2a_duowei_comparison_operator_consistent(monkeypatch):
    """审查 P2a：「多维对比康美和茅台」→ 多维按比较 operator 忽略
    （与计划层 full 语义一致）→ comparison 两家，无 unresolved。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("多维对比康美和茅台", memory=None)
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    assert r.unresolved_mentions == []


def test_p2a_zhengti_comparison_operator(monkeypatch):
    """审查 P2a：「整体对比康美和茅台」→ 整体按比较 operator 忽略。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve("整体对比康美和茅台", memory=None)
    assert r.intent == "comparison"
    codes = {str(c.wind_code) for c in r.selected_companies}
    assert codes == {"600518.SH", "600519.SH"}
    assert r.unresolved_mentions == []


def test_p2a_zonghe_quanfangwei_operators(monkeypatch):
    """审查 P2a：综合（extractor 已 mask）/全方位 同样不产生 NIL 残留。"""
    _patch_spotter(monkeypatch, [])
    r = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "全方位对比康美和茅台", memory=None
    )
    assert r.intent == "comparison"
    assert r.unresolved_mentions == []
    r2 = CompanyEntityResolver(_lookup(_REPO)).resolve(
        "综合对比康美和茅台", memory=None
    )
    assert r2.intent == "comparison"
    assert r2.unresolved_mentions == []


def test_p2a_registry_single_source():
    """审查 P2a：实体层 operator 集合与计划层 full cue 的范围词部分
    必须来自同一注册表（含 多维/整体）。"""
    from app.agents.nodes.plan_modules import _FULL_COMPARISON_CUES
    from app.application.services.company_entity_resolver import (
        _COMPARISON_OPERATOR_WORDS,
    )
    from app.domain.comparison.scope_registry import (
        COMPARISON_FULL_SCOPE_WORDS,
    )

    assert _COMPARISON_OPERATOR_WORDS == frozenset(COMPARISON_FULL_SCOPE_WORDS)
    for word in COMPARISON_FULL_SCOPE_WORDS:
        assert word in _FULL_COMPARISON_CUES, f"{word} 不在计划层 full cue"
    assert "多维" in _COMPARISON_OPERATOR_WORDS
    assert "整体" in _COMPARISON_OPERATOR_WORDS


# ── v3.3.2-R1 §7：Interpreter 接线（fallback 应用 / 二次链接）────


def _mock_interpreter(monkeypatch, response, mode="fallback"):
    """构造返回固定解释的 QuerySubjectInterpreter。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode=mode)
    monkeypatch.setattr(interp, "interpret", lambda **kw: ("completed", response))
    return interp


def _prev_interp(span_ids_context=None):
    from app.application.models.company_resolution import (
        InputSpanDisposition,
        QuerySubjectInterpretation,
    )

    return QuerySubjectInterpretation(
        subject_reference="previous",
        input_span_dispositions=[
            InputSpanDisposition(mention_id=mid, kind="context")
            for mid in (span_ids_context or [])
        ],
    )


def test_interpreter_previous_continues_subject(monkeypatch):
    """fallback：Interpreter 判定 previous -> continuation（结构化
    current_company_code 驱动，不依赖词表）。"""
    interp = _mock_interpreter(monkeypatch, _prev_interp())
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("继续", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"
    assert r.subject_interpreter_status == "completed"
    assert r.subject_interpretation is not None


def test_interpreter_previous_with_unresolved_context_spans(monkeypatch):
    """fallback：'产能利用率' NIL span 被解释为 context + previous -> 延续。"""
    from app.application.models.company_resolution import (
        InputSpanDisposition,
        QuerySubjectInterpretation,
    )

    # 先解析拿到真实 mention_id（产能利用率：NIL span、非 canonical、
    # 非防串词 → 真低置信 Interpreter 场景）
    r0 = CompanyEntityResolver(_lookup(_REPO)).resolve("产能利用率如何", memory=None)
    mid = r0.mentions[0].mention_id
    response = QuerySubjectInterpretation(
        subject_reference="previous",
        input_span_dispositions=[InputSpanDisposition(mention_id=mid, kind="context")],
    )
    interp = _mock_interpreter(monkeypatch, response)
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("产能利用率如何", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_interpreter_new_spans_relinked(monkeypatch):
    """fallback：Interpreter 提出新 span -> Repository 二次链接锁定。"""
    from app.application.models.company_resolution import (
        ProposedCompanySpan,
        QuerySubjectInterpretation,
    )

    response = QuerySubjectInterpretation(
        subject_reference="new",
        additional_company_spans=[ProposedCompanySpan(text="茅台", start=1, end=3)],
        company_relation="single",
    )
    interp = _mock_interpreter(monkeypatch, response)
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("那茅台呢", memory=_kangmei_memory())
    assert r.intent == "switch"
    assert r.selected_companies[0].wind_code == "600519.SH"


def test_interpreter_shadow_does_not_change_authority(monkeypatch):
    """shadow：调用并记录审计，权威与 off 一致（批次 C 后=确定性路由+
    clarify，词表路径已删除）。"""
    interp = _mock_interpreter(monkeypatch, _prev_interp(), mode="shadow")
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("继续", memory=_kangmei_memory())
    # shadow 记录审计但不应用；「继续」无确定性信号 → 非 continuation
    # （与 off 模式一致）
    assert r.subject_interpreter_status == "shadow"
    assert r.subject_interpretation is not None
    assert r.intent != "continuation"
    assert not r.selected_companies


def test_interpreter_previous_without_current_subject_ignored(monkeypatch):
    """fallback：previous 但无 current subject -> verifier invalid ->
    fail-closed，不伪造主体。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode="fallback")
    monkeypatch.setattr(interp, "interpret", lambda **kw: ("invalid", None))
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("毛利率正常吗", memory=None)
    assert r.intent != "continuation"
    assert not r.selected_companies


# ── 中间验收批次 A2：确定性回指闸门 + fallback 失败边界（P0-2）────


def _timeout_interpreter(monkeypatch, mode="fallback"):
    """构造返回 timeout 的 QuerySubjectInterpreter。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode=mode)
    monkeypatch.setattr(interp, "interpret", lambda **kw: ("timeout", None))
    return interp


def test_explicit_anaphora_continues_without_llm(monkeypatch):
    """P0-2：明确回指短语（这家公司）+ current 主体 → 零 LLM 确定性
    continuation，Interpreter 不被调用。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode="fallback")
    calls = {"n": 0}

    def fake_interpret(**kw):
        calls["n"] += 1
        return ("completed", None)

    monkeypatch.setattr(interp, "interpret", fake_interpret)
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("总结一下这家公司的风险", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"
    assert calls["n"] == 0  # 确定性闸门短路，零 LLM


def test_interpreter_timeout_does_not_use_financial_wordlist_history(monkeypatch):
    """P0-2：fallback + timeout 后不得落入金融词表沿用历史主体。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_timeout_interpreter(monkeypatch)
    )
    r = resolver.resolve("继续", memory=_kangmei_memory())
    assert r.intent != "continuation", f"timeout 后不得沿用康美: {r.reason_code}"
    assert not r.selected_companies
    assert r.subject_interpreter_status == "timeout"


def test_interpreter_invalid_does_not_use_financial_wordlist_history(monkeypatch):
    """P0-2：fallback + invalid 后不得落入金融词表沿用历史主体。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode="fallback")
    monkeypatch.setattr(interp, "interpret", lambda **kw: ("invalid", None))
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("继续", memory=_kangmei_memory())
    assert r.intent != "continuation"
    assert not r.selected_companies
    assert r.subject_interpreter_status == "invalid"


def test_interpreter_none_does_not_use_wordlist(monkeypatch):
    """P0-2 延伸：fallback + completed(none) 尊重"无主体"裁决，
    不落词表。"""
    from app.application.models.company_resolution import (
        QuerySubjectInterpretation,
    )
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode="fallback")
    monkeypatch.setattr(
        interp,
        "interpret",
        lambda **kw: (
            "completed",
            QuerySubjectInterpretation(subject_reference="none"),
        ),
    )
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("继续", memory=_kangmei_memory())
    assert r.intent != "continuation"
    assert not r.selected_companies
    assert r.subject_interpreter_status == "completed"


def test_interpreter_timeout_with_not_found_span_blocks_history(monkeypatch):
    """P0-2：有疑似新实体 span（台泥 → NIL）时 timeout，同样不得沿用
    历史主体。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_timeout_interpreter(monkeypatch)
    )
    r = resolver.resolve("台泥的营收", memory=_kangmei_memory())
    assert r.intent != "continuation", f"疑似新实体不得被历史吞掉: {r.reason_code}"
    assert not r.selected_companies


# ── 中间验收批次 B2：relation proposal 消费（P1-2）──────────────


def _bound_mention(code, status="auto_selected", role=None):
    from app.application.models.company_resolution import EntityMention

    return EntityMention(
        mention_id=f"m_{code}",
        text=code,
        status=status,
        selected_wind_code=code,
        role=role,
    )


def test_interpreter_relation_applied_only_after_all_spans_linked():
    """P1-2：全绑定 + ≥2 不同 code → 应用 proposal；任一 NIL/歧义 →
    不应用。"""
    from app.application.services.company_entity_resolver import (
        apply_relation_proposal,
    )

    bound = [
        _bound_mention("600518.SH"),
        _bound_mention("600519.SH"),
    ]
    r, s = apply_relation_proposal(
        "ambiguous", "needs_clarification", "comparison", bound
    )
    assert (r, s) == ("comparison", "resolved")
    # reference → needs_clarification（下游 relation_clarify，P0-3）
    r2, s2 = apply_relation_proposal("single", "resolved", "reference", bound)
    assert (r2, s2) == ("reference", "needs_clarification")
    # 非 proposal 类型 → 原样
    r3, s3 = apply_relation_proposal("single", "resolved", "single", bound)
    assert (r3, s3) == ("single", "resolved")


def test_relation_proposal_rejected_when_any_span_unbound():
    """P1-2：任一 span NIL（无 selected_wind_code）→ 不应用。"""
    from app.application.services.company_entity_resolver import (
        apply_relation_proposal,
    )

    mixed = [
        _bound_mention("600518.SH"),
        _bound_mention("", status="not_found"),
    ]
    r, s = apply_relation_proposal(
        "ambiguous", "needs_clarification", "comparison", mixed
    )
    assert (r, s) == ("ambiguous", "needs_clarification")
    # needs_confirmation 同样不应用
    pending = [
        _bound_mention("600518.SH"),
        _bound_mention("", status="needs_confirmation"),
    ]
    r2, s2 = apply_relation_proposal(
        "ambiguous", "needs_clarification", "comparison", pending
    )
    assert (r2, s2) == ("ambiguous", "needs_clarification")
    # 相同 code 不构成 comparison
    dup = [_bound_mention("600518.SH"), _bound_mention("600518.SH")]
    r3, s3 = apply_relation_proposal(
        "ambiguous", "needs_clarification", "comparison", dup
    )
    assert (r3, s3) == ("ambiguous", "needs_clarification")


def test_partial_nil_does_not_form_complete_comparison(monkeypatch):
    """P1-2 resolver 级：fallback + comparison proposal 但二次链接全
    NIL → 不得形成 comparison。"""
    from app.application.models.company_resolution import (
        ProposedCompanySpan,
        QuerySubjectInterpretation,
    )

    response = QuerySubjectInterpretation(
        subject_reference="new",
        additional_company_spans=[
            ProposedCompanySpan(text="台泥", start=0, end=2),
            ProposedCompanySpan(text="小米", start=3, end=5),
        ],
        company_relation="comparison",
    )
    interp = _mock_interpreter(monkeypatch, response)
    resolver = CompanyEntityResolver(_lookup(_REPO), interpreter=interp)
    r = resolver.resolve("台泥小米", memory=None)
    assert r.intent != "comparison"
    assert not r.selected_companies


def test_reference_roles_materialized_by_text_order():
    """P1-2：reference 场景 role 由原文顺序物化（第一 primary、其余
    referenced），Interpreter 不参与 identity/role。"""
    resolver = CompanyEntityResolver(_lookup(_REPO))
    r = resolver.resolve("康美提到茅台", memory=None)
    assert r.intent == "reference"
    ordered = sorted(r.mentions, key=lambda m: m.start)
    assert ordered[0].role == "primary"
    assert ordered[1].role == "referenced"


# ── 最终续审 §5 B5：零 LLM 确定性路由（spy 证明不调用）────────


def _spy_interpreter(monkeypatch, mode="fallback"):
    """会报错的 spy：任何调用都失败，证明零 LLM 路径不依赖 Interpreter。"""
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interp = QuerySubjectInterpreter(mode=mode)

    def _boom(**kw):
        raise AssertionError("确定性路径不得调用 Interpreter")

    monkeypatch.setattr(interp, "interpret", _boom)
    return interp


def test_known_business_predicate_followup_zero_llm(monkeypatch):
    """B2：历史康美 + '毛利率正常吗'（业务谓词追问）→ 零 LLM
    continuation。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_spy_interpreter(monkeypatch)
    )
    r = resolver.resolve("毛利率正常吗", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"
    assert r.subject_interpreter_status == "not_needed"


def test_back_reference_followup_zero_llm(monkeypatch):
    """B2：历史康美 + '刚才提到的风险信号哪个最严重'（回指框架）→
    零 LLM continuation。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_spy_interpreter(monkeypatch)
    )
    r = resolver.resolve("刚才提到的风险信号哪个最严重", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_canonical_context_followup_zero_llm(monkeypatch):
    """B3：历史康美 + '有没有存贷双高的风险'（R3 canonical 术语解释）
    → 零 LLM continuation。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_spy_interpreter(monkeypatch)
    )
    r = resolver.resolve("有没有存贷双高的风险", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_canonical_continuation_priority_over_mentionness(monkeypatch):
    """8/16 语义裁决启用：suggest 下 mentionness 判「存贷双高」
    non_company_context，canonical 业务延续（历史康美）仍优先——
    不降级 no_company（canonical 先于 mentionness 应用）。"""
    import re as _re

    from app.application.models.company_resolution import (
        MentionnessDecision,
        MentionnessVerdict,
    )
    from app.application.services.company_mentionness_classifier import (
        CompanyMentionnessClassifier,
    )
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    def fake_llm(messages, schema, timeout=None):
        user = messages[-1]["content"]
        ids = _re.findall(r"span_id=([^\s'，]+)", user)
        return MentionnessDecision(
            verdicts=[
                MentionnessVerdict(span_id=sid, verdict="non_company_context")
                for sid in ids
            ]
        )

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    clf = CompanyMentionnessClassifier(mode="suggest")
    resolver = CompanyEntityResolver(
        _lookup(_REPO), mentionness=clf, interpreter=_spy_interpreter(monkeypatch)
    )
    r = resolver.resolve("有没有存贷双高的风险", memory=_kangmei_memory())
    assert r.intent == "continuation"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_known_predicates_without_history_do_not_fabricate(monkeypatch):
    """B5：无历史 + 三条已知业务追问 → 不绑定公司、不伪造。"""
    resolver = CompanyEntityResolver(
        _lookup(_REPO), interpreter=_spy_interpreter(monkeypatch)
    )
    for q in [
        "毛利率正常吗",
        "刚才提到的风险信号哪个最严重",
        "有没有存贷双高的风险",
    ]:
        r = resolver.resolve(q, memory=None)
        assert r.intent != "continuation", q
        assert not r.selected_companies, q


def test_anti_leak_five_low_confidence_allowed_but_never_inherit():
    """B5：防串五例允许低置信 Interpreter（§9.1），但绝不继承、绝不
    绑定（Interpreter 失败 fail-closed）。"""
    resolver = CompanyEntityResolver(_lookup(_REPO))
    for q in [
        "茅台镇的营收",
        "康美丽的营收",
        "台泥的营收",
        "小米的营收",
        "火星科技怎么样",
    ]:
        r = resolver.resolve(q, memory=_kangmei_memory())
        assert r.intent != "continuation", f"{q} 不得继承康美"
        assert not r.selected_companies, f"{q} 不得绑定任何公司"


def test_canonical_explanation_does_not_block_real_companies():
    """B3 防串：'有友食品有风险吗' 不被 canonical 机制误判为 context
    （残留'友/食/品'非语法字符 → 正常查库）。"""
    lookup = _lookup(_REPO + [("c3", "603697.SH", "有友食品", None)])
    r = CompanyEntityResolver(lookup).resolve("有友食品有风险吗", memory=None)
    assert any(c.wind_code == "603697.SH" for c in r.selected_companies)


def test_plan_modules_reuses_plan_hint_no_second_llm(monkeypatch):
    """§12.2：已验证 plan_hint 时 plan_modules 不再调用意图 LLM。"""
    from app.agents.state import CompanyRef
    from app.application.models.company_resolution import (
        EntityResolutionResult,
        QuerySubjectInterpretation,
    )
    from app.agents.nodes import plan_modules

    calls = {"n": 0}

    def fake_intent_llm(q):
        calls["n"] += 1
        return None

    monkeypatch.setattr(plan_modules, "_llm_intent_fallback", fake_intent_llm)
    resolution = EntityResolutionResult(
        intent="continuation",
        subject_interpreter_status="completed",
        subject_interpretation=QuerySubjectInterpretation(
            subject_reference="previous", plan_hint="summary"
        ),
    )
    state = {
        "user_query": "总结一下这家公司",
        "company": CompanyRef(
            entity_id="e1", wind_code="600518.SH", sec_name="康美药业", exchange="XSHG"
        ),
        "entity_resolution_result": resolution,
        "messages": [],
    }
    result = plan_modules.plan_modules_node(state)
    plan = result["plan"]
    assert plan.intent != "guide"
    assert calls["n"] == 0  # summary 提示命中，不调用意图 LLM


def test_plan_modules_other_hint_still_uses_llm(monkeypatch):
    """plan_hint=other 时保持现有 LLM fallback（§8：other/uncertain 不变）。"""
    from app.agents.state import CompanyRef
    from app.application.models.company_resolution import (
        EntityResolutionResult,
        QuerySubjectInterpretation,
    )
    from app.agents.nodes import plan_modules

    calls = {"n": 0}

    def fake_intent_llm(q):
        calls["n"] += 1
        return None

    monkeypatch.setattr(plan_modules, "_llm_intent_fallback", fake_intent_llm)
    resolution = EntityResolutionResult(
        intent="single",
        subject_interpreter_status="completed",
        subject_interpretation=QuerySubjectInterpretation(
            subject_reference="new", plan_hint="other"
        ),
    )
    state = {
        "user_query": "帮我看看这家",
        "company": CompanyRef(
            entity_id="e1", wind_code="600518.SH", sec_name="康美药业", exchange="XSHG"
        ),
        "entity_resolution_result": resolution,
        "messages": [],
    }
    plan_modules.plan_modules_node(state)
    assert calls["n"] == 1  # other 继续走 LLM fallback
