"""片段提取器与守卫旧测试（v3.1 并行迁移期保留；步骤 12 真机验收后删除）.

提取逻辑已迁移至 company_mention_extractor（等长 mask），守卫语义由
CompanyEntityResolver 覆盖。本文件在真机验收完成前整体跳过。

v3.2.1 批次 6 旧断言 -> 新断言映射清单（删除本文件前必须全部闭环）：
- test_extract_fragments_keeps_company_names
  -> ✅ test_company_mention_extractor::test_subject_slot_truncates_at_terminator
- test_extract_fragments_clears_business_terms
  -> ✅ test_company_mention_extractor::test_residual_filler_words_cleaned
- test_extract_fragments_preserves_short_names
  -> ✅ test_company_mention_extractor::test_grammar_suffix_stripped_to_min_two
- test_extract_fragments_protected_names_removed_before_split
  -> 🔜 待迁移（保护名称处理，目标 test_company_mention_extractor）
- test_guard_blocks_unresolved_new_entity
  -> ✅ test_company_entity_resolver::test_unresolved_new_entity_not_inherited
- test_guard_not_bypassed_by_anaphora_word -> 🔜 待迁移（目标 resolver 测试）
- test_guard_passes_pure_anaphora
  -> ✅ test_company_entity_resolver::test_anaphora_continues_history
- test_guard_passes_business_residue -> 🔜 待迁移
- test_guard_blocks_two_char_new_entity -> 🔜 待迁移（两字新实体防串）
- test_guard_blocks_lookalike_company_names
  -> ✅ test_company_entity_resolver::test_lookalike_company_names_not_confirmed（v3.2.1 已迁移）
- test_guard_passes_subject_slot_empty
  -> ✅ test_company_mention_extractor::test_empty_subject_slot_no_mention
- test_prefix_regex_fixed_point
  -> ✅ test_company_mention_extractor::test_span_offsets_after_leading_pronoun
- test_subject_time_expressions_not_bypassing_guard
  -> ✅ test_company_mention_extractor::test_span_offsets_after_time_words_removed
- test_extract_fragments_dividend_alternation -> 🔜 待迁移
- test_extract_fragments_chengdu_kept -> 🔜 待迁移
- test_multi_entity_connector_per_segment
  -> ✅ test_company_entity_resolver::test_segmentation_alternatives_not_flattened
- test_suffix_variants_grammar_only
  -> ✅ test_company_entity_resolver::test_suffix_variants_grammar_only（v3.2.1 已迁移）
- test_explicit_invalid_code_returns_not_found -> 🔜 待迁移（非法代码 not_found）
- test_candidates_truncated_returns_guide
  -> ✅ test_company_entity_resolver::test_truncated_candidates_need_refinement
- test_wind_code_regex_with_chinese_prefix -> 🔜 待迁移（_WIND_CODE_RE 纯函数）
- test_continuation_cues_cover_business_terms
  -> ✅ test_subject_ellipsis_continues_history（近似）+ 🔜 词表级断言待迁移
- test_v8_query_driven_compound -> 🔜 待迁移
- test_v8_pure_functions -> ⚙️ 部分纯函数已迁移（_suffix_variants 等），删除时人工确认
- test_engine_cache_rotation -> ⚙️ 机制变化（旧引擎缓存已不存在，P1-6 共享 driver），删除时人工确认
"""

# ruff: noqa: E402 — skip 必须位于 import 之前（引用已删除的旧符号）

import pytest

pytest.skip(
    "旧提取器已删除，待真机验收（步骤 12）后移除本文件", allow_module_level=True
)

from app.agents.nodes.resolve_entity import (
    _CandidateSearchResult,
    _extract_entity_fragments,
    _resolve_entity_legacy_node as resolve_entity_node,
)
from app.agents.state import CompanyRef, MemoryContext, RequestContext, RuntimeState


def _make_state(query: str, memory: MemoryContext | None = None):
    return {
        "user_query": query,
        "memory_context": memory,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def _ref(sec_name: str, code: str = "600000.SH") -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code}",
        wind_code=code,
        sec_name=sec_name,
        exchange="XSHG",
    )


# ── 1.1 片段提取器 ──────────────────────────────────────────


def test_extract_fragments_keeps_company_names():
    assert _extract_entity_fragments("分析一下茅台") == ["茅台"]
    assert _extract_entity_fragments("看茅台") == ["茅台"]
    # 四轮审查 P1-2：单字"和"不再做分段符（"康美和茅台"整体返回，
    # 由候选路径 _fragment_variants 二次分段）
    assert _extract_entity_fragments("康美和茅台对比") == ["康美和茅台"]
    assert _extract_entity_fragments("康美药业600518.SH") == ["康美药业"]
    # 六轮审查：主语槽"台积电它的"（"它"非锚定前缀不删）由守卫按原始片段阻断
    assert _extract_entity_fragments("台积电它的营收") == ["台积电它的"]


def test_extract_fragments_clears_business_terms():
    """停用词全清理 → 空（守卫放行记忆恢复）。"""
    assert _extract_entity_fragments("现金为什么下降") == []
    assert _extract_entity_fragments("经营情况是否改善") == []
    assert _extract_entity_fragments("最近三年营收") == []
    assert _extract_entity_fragments("继续看现金流") == []
    assert _extract_entity_fragments("综合给一个风险结论") == []
    # "它"前缀删 + "的呢"纯语法词片段丢弃 → 空 → 守卫放行
    assert _extract_entity_fragments("它的应收账款呢") == []


def test_extract_fragments_preserves_short_names(monkeypatch):
    """四轮审查 P1-2：单字语法词不得破坏合法简称。"""
    # "的"（美的）/"和"（协和）是合法简称成分，提取器不再误删
    assert _extract_entity_fragments("美的营收") == ["美的"]
    assert _extract_entity_fragments("协和的营收") == ["协和的"]


def test_extract_fragments_protected_names_removed_before_split():
    """保护名在分段前移除（防"协和电子"的"和"被切开）。"""
    assert _extract_entity_fragments("协和电子的营收", ("协和电子",)) == []
    assert (
        _extract_entity_fragments("康美药业和贵州茅台的营收", ("康美药业", "贵州茅台"))
        == []
    )


# ── 1.3 新实体守卫 ──────────────────────────────────────────


def test_guard_blocks_unresolved_new_entity(monkeypatch):
    """台积电的营收（历史康美）→ company_not_found，禁止记忆恢复。"""
    from app.agents.nodes import resolve_entity as node

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        resolved_entity_name="康美药业",
        is_anaphora=True,
        previous_companies=["康美药业"],
    )
    result = resolve_entity_node(_make_state("台积电的营收", mc))
    assert result["company"] is None
    assert result["entity_resolution_error"] == "company_not_found"
    # 五轮审查 P0-1：守卫使用**原始/最长片段**（"台积电的"），不做最短剥离
    assert result["unresolved_fragments"] == ["台积电的"]


def test_guard_not_bypassed_by_anaphora_word(monkeypatch):
    """台积电它的营收：指代词不豁免（三轮审查关键反例）。"""
    from app.agents.nodes import resolve_entity as node

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(previous_companies=["康美药业"])
    result = resolve_entity_node(_make_state("台积电它的营收", mc))
    assert result["company"] is None
    assert result["entity_resolution_error"] == "company_not_found"
    # 守卫按原始/最长片段阻断（五轮审查 P0-1）
    assert result["unresolved_fragments"] == ["台积电它的"]


def test_guard_passes_pure_anaphora(monkeypatch):
    """它的营收（历史康美）→ 放行记忆恢复。"""
    from app.agents.nodes import resolve_entity as node

    company = _ref("康美药业", "600518.SH")

    def fake_find(query: str):
        return company if "康美药业" in query else None

    monkeypatch.setattr(node, "_find_company", fake_find)
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        resolved_entity_name="康美药业",
        is_anaphora=True,
        previous_companies=["康美药业"],
    )
    result = resolve_entity_node(_make_state("它的营收是多少", mc))
    assert result["company"] is not None
    assert result["company"].sec_name == "康美药业"
    assert result.get("entity_resolution_error") is None


def test_guard_passes_business_residue(monkeypatch):
    """它现在财务造假的风险还高吗 → '还高' 已入精确停用词，清理后放行延续。"""
    from app.agents.nodes import resolve_entity as node

    company = _ref("康美药业", "600518.SH")
    monkeypatch.setattr(
        node, "_find_company", lambda q: company if q == "600518.SH" else None
    )
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(resolved_company_code="600518.SH", is_anaphora=True)
    result = resolve_entity_node(_make_state("它现在财务造假的风险还高吗", mc))
    assert result["company"] is not None
    assert result["company"].sec_name == "康美药业"


def test_guard_blocks_two_char_new_entity(monkeypatch):
    """四轮审查 P1-1：两字新主体不得沿用历史公司（台泥/小米）。"""
    from app.agents.nodes import resolve_entity as node

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )
    for q, frag in [("台泥的营收", "台泥的"), ("小米的营收", "小米的")]:
        result = resolve_entity_node(_make_state(q, mc))
        assert result["company"] is None, f"{q} 不得沿用康美"
        assert result["entity_resolution_error"] == "company_not_found"
        assert result["unresolved_fragments"] == [frag]


def test_guard_blocks_lookalike_company_names(monkeypatch):
    """六轮审查 P1-1：茅台镇/康美丽不得静默串成贵州茅台/康美药业。"""
    from app.agents.nodes import resolve_entity as node

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )
    for q, frag in [("茅台镇的营收", "茅台镇的"), ("康美丽的营收", "康美丽的")]:
        result = resolve_entity_node(_make_state(q, mc))
        assert result["company"] is None, f"{q} 不得沿用历史公司"
        assert result["entity_resolution_error"] == "company_not_found"
        assert result["unresolved_fragments"] == [frag]


def test_guard_passes_subject_slot_empty(monkeypatch):
    """六轮审查 P1-2：营收高吗/利润好吗/负债多吗/现金够吗 → 延续历史主体。"""
    from app.agents.nodes import resolve_entity as node

    company = _ref("康美药业", "600518.SH")
    monkeypatch.setattr(
        node, "_find_company", lambda q: company if q == "600518.SH" else None
    )
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )
    for q in ["营收高吗", "利润好吗", "负债多吗", "现金够吗"]:
        result = resolve_entity_node(_make_state(q, mc))
        assert result["company"] is not None, f"{q} 应延续历史主体"
        assert result["company"].sec_name == "康美药业"


def test_prefix_regex_fixed_point():
    """六轮审查 P2-1：前导动作/指代词锚定正则一次性（都看茅台→茅台）。"""
    assert _extract_entity_fragments("都看茅台") == ["茅台"]


def test_subject_time_expressions_not_bypassing_guard():
    """七轮审查 P0：前置时间词不得绕过守卫——时间词是**可删表达**非终止符。

    "2024年的营收"（主语槽删时间后空）→ 延续旧主体；
    "2024年茅台营收"（删时间后"茅台"）→ 切换茅台。
    """
    assert _extract_entity_fragments("2024年茅台营收") == ["茅台"]
    assert _extract_entity_fragments("去年茅台营收") == ["茅台"]
    assert _extract_entity_fragments("最近茅台公告") == ["茅台"]
    assert _extract_entity_fragments("分析2024年茅台营收") == ["茅台"]
    assert _extract_entity_fragments("2024年的营收") == []
    # 前导请求词固定点（请/请问/帮我/分析/看/查 组合）
    assert _extract_entity_fragments("请看茅台营收") == ["茅台"]
    assert _extract_entity_fragments("请分析茅台营收") == ["茅台"]


# ── 2026-08-12 五轮审查反例 ──────────────────────────────


def test_extract_fragments_dividend_alternation():
    """五轮审查 P1-2：多字连接词 alternation 整体切分——"比亚迪"不被"比"切。"""
    assert _extract_entity_fragments("比亚迪营收") == ["比亚迪"]


def test_extract_fragments_chengdu_kept():
    """五轮审查 P0-2：全局删"都"会破坏"成都"——前缀删除规则不误伤。"""
    assert _extract_entity_fragments("成都的营收") == ["成都的"]


def test_multi_entity_connector_per_segment(monkeypatch):
    """七轮审查 P1：动作词/标点后第二家公司不丢失（内存表两层验证）。

    候选层（_find_company_candidates 两家）+ resolve 层（comparison_targets 两家）。
    内存公司表不依赖测试库是否存在协和电子。
    """
    from sqlalchemy import create_engine, text

    from app.agents.nodes import resolve_entity as node

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE companies (entity_id TEXT, wind_code TEXT, sec_name TEXT, "
                "exchange_code TEXT, industry_l1 TEXT, aliases TEXT, listing_date TEXT, "
                "comp_type_code TEXT, is_latest INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO companies VALUES "
                "('e1','600519.SH','贵州茅台','XSHG','白酒',NULL,'2024-01-01','1',1), "
                "('e2','600071.SH','协和电子','XSHG','电子',NULL,'2024-01-01','1',1)"
            )
        )
    monkeypatch.setattr(node.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(node, "_get_engine", lambda: engine)
    try:
        for q in [
            "贵州茅台和协和的营收",
            "分析贵州茅台和协和的营收",
            "请比较贵州茅台和协和的营收",
            "贵州茅台，和协和的营收",
        ]:
            # 候选层：两家
            cands = node._find_company_candidates(q).candidates
            assert {c.sec_name for c in cands} == {"贵州茅台", "协和电子"}, q
            # resolve 层：比较意图两目标
            result = resolve_entity_node(_make_state(q, MemoryContext()))
            assert result.get("comparison_requested"), q
            targets = result.get("comparison_targets", [])
            assert {t.sec_name for t in targets} == {"贵州茅台", "协和电子"}, q
    finally:
        engine.dispose()


def test_suffix_variants_grammar_only():
    """六轮审查 P1-1：只删明确尾部语法字符，禁止任意截短。"""
    from app.agents.nodes.resolve_entity import _suffix_variants

    assert _suffix_variants("美的是") == ["美的是", "美的", "美"]
    assert _suffix_variants("台泥的是") == ["台泥的是", "台泥的", "台泥"]
    # "茅台"尾部"台"非语法字符 → 不截短（不得静默识别成错误公司）
    assert _suffix_variants("茅台") == ["茅台"]
    assert _suffix_variants("茅台镇的") == ["茅台镇的", "茅台镇"]


# ── 1.4 显式代码守卫 ──────────────────────────────────────────


def test_explicit_invalid_code_returns_not_found():
    """显式非法代码 → company_not_found + 代码写入 unresolved_fragments。"""
    mc = MemoryContext(previous_companies=["康美药业"])
    state = _make_state("分析茅台", mc)
    state["request_context"] = RequestContext(company_code="999999.SH")
    result = resolve_entity_node(state)
    assert result["company"] is None
    assert result["entity_resolution_error"] == "company_not_found"
    assert result["unresolved_fragments"] == ["999999.SH"]


# ── 1.2 候选截断 ──────────────────────────────────────────


def test_candidates_truncated_returns_guide(monkeypatch):
    """全局候选超上限 → candidates_truncated=True（不静默截断展示）。"""
    from app.agents.nodes import resolve_entity as node

    cands = [_ref(f"候选公司{i:02d}", f"600{i:03d}.SH") for i in range(11)]
    monkeypatch.setattr(
        node,
        "_find_company_candidates",
        lambda q: _CandidateSearchResult(candidates=cands, truncated=True),
    )
    result = resolve_entity_node(_make_state("候选公司对比", MemoryContext()))
    assert result["company"] is None
    assert result["candidates_truncated"] is True
    assert result["company_candidates"] == cands


# ── 2026-08-12 学姐复现修订（Bug 1 / 延续线索）──────────────


def test_wind_code_regex_with_chinese_prefix():
    """Bug 1（学姐复现）：\b 对中文不成立，代码前有中文必须能匹配。"""
    import re

    pat = r"(?<!\d)(\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?)(?!\d)"
    assert (
        re.search(pat, "分析600518.SH的财务风险", re.IGNORECASE).group(1) == "600518.SH"
    )
    assert re.search(pat, "分析600518的财务风险", re.IGNORECASE).group(1) == "600518"
    assert re.search(pat, "康美600518.SH", re.IGNORECASE).group(1) == "600518.SH"
    # 前后粘连数字（长数字串）不得误配
    assert re.search(pat, "123456789012345600518", re.IGNORECASE) is None


def test_continuation_cues_cover_business_terms(monkeypatch):
    """10 轮复测修订：无指代词业务追问（现金/经营/财报/下降）也延续主体。"""
    from app.agents.nodes import resolve_entity as node

    company = _ref("康美药业", "600518.SH")
    monkeypatch.setattr(
        node, "_find_company", lambda q: company if q == "600518.SH" else None
    )
    monkeypatch.setattr(
        node, "_find_company_candidates", lambda q: _CandidateSearchResult([])
    )
    mc = MemoryContext(
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )
    for q in ["现金为什么下降", "经营情况是否改善", "财报造假的风险还高吗"]:
        result = resolve_entity_node(_make_state(q, mc))
        assert result["company"] is not None, f"{q} 未延续主体"
        assert result["company"].sec_name == "康美药业"


# ── v8 终版：查询驱动复合解析 / 纯函数 / 引擎缓存 ────────────


def _compound_engine():
    """v8 复合解析内存表（含和邦/和顺/美的/茅台/协和）。"""
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE companies (entity_id TEXT, wind_code TEXT, sec_name TEXT, "
                "exchange_code TEXT, industry_l1 TEXT, aliases TEXT, listing_date TEXT, "
                "comp_type_code TEXT, is_latest INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO companies VALUES "
                "('e1','600519.SH','贵州茅台','XSHG','白酒',NULL,'2024-01-01','1',1), "
                "('e2','600071.SH','协和电子','XSHG','电子',NULL,'2024-01-01','1',1), "
                "('e3','603077.SH','和邦生物','XSHG','化工',NULL,'2024-01-01','1',1), "
                "('e4','600208.SH','和顺石油','XSHG','石化',NULL,'2024-01-01','1',1), "
                "('e5','300741.SZ','和顺科技','XSHG','电子',NULL,'2024-01-01','1',1), "
                "('e6','000333.SZ','美的集团','XSHE','家电',NULL,'2024-01-01','1',1)"
            )
        )
    return engine


def test_v8_query_driven_compound(monkeypatch):
    """v8 终版：连接词查询驱动——段首"和"不删（和邦生物），两侧独立命中
    才算连接词（茅台和协和→两家）。"""
    from app.agents.nodes import resolve_entity as node

    engine = _compound_engine()
    monkeypatch.setattr(node.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(node, "_get_engine", lambda: engine)
    try:
        # 段首"和"是公司名成分：不删（直接匹配优先）
        r = node._find_company_candidates("和邦的营收")
        assert [c.sec_name for c in r.candidates] == ["和邦生物"]
        # 段首"和"+歧义公司：和顺石油/和顺科技
        r = node._find_company_candidates("和顺的营收")
        assert {c.sec_name for c in r.candidates} == {"和顺石油", "和顺科技"}
        # 内部连接词：左右两侧独立命中 → 两家
        for q, expect in [
            ("茅台和协和的营收", {"贵州茅台", "协和电子"}),
            ("美的和协和的营收", {"美的集团", "协和电子"}),
            ("协和和茅台的营收", {"协和电子", "贵州茅台"}),
        ]:
            r = node._find_company_candidates(q)
            assert {c.sec_name for c in r.candidates} == expect, q
            assert not r.segmentation_ambiguous, q
        # 与公司名成分"和"同段的真实连接词：茅台和和邦 → 两家
        r = node._find_company_candidates("茅台和和邦对比")
        assert {c.sec_name for c in r.candidates} == {"贵州茅台", "和邦生物"}
    finally:
        engine.dispose()


def test_v8_pure_functions():
    """v8 纯函数：请求词固定点 / 时间表达最长规则。"""
    from app.agents.nodes.resolve_entity import (
        _prepare_subject_segment,
        _strip_request_prefix,
        _strip_time_modifiers,
    )

    # 请求词固定点（最长优先 + 循环）
    assert _strip_request_prefix("麻烦看茅台") == "茅台"
    assert _strip_request_prefix("请分析一下茅台") == "茅台"
    assert _strip_request_prefix("能否帮我看看茅台") == "茅台"
    assert _strip_request_prefix("茅台") == "茅台"  # 非请求词不动
    # 时间表达最长规则（组合词整体删除，不拆散）
    assert _strip_time_modifiers("最近三年茅台") == "茅台"
    assert _strip_time_modifiers("2024年上半年茅台") == "茅台"
    assert _strip_time_modifiers("2024年的茅台") == "茅台"
    assert _strip_time_modifiers("茅台2024年上半年") == "茅台"
    assert _strip_time_modifiers("茅台") == "茅台"  # 无时间词不动
    # 组合预处理
    assert _prepare_subject_segment("麻烦看2024年茅台") == "茅台"


def test_engine_cache_rotation(monkeypatch):
    """v8 引擎缓存：特殊字符密码不破坏 URL、配置变化先 dispose 再新建。"""
    from app.agents.nodes import resolve_entity as node

    from types import SimpleNamespace

    created_urls: list = []
    disposed: list = []

    def fake_create(url, **kw):
        created_urls.append(url)
        return SimpleNamespace(dispose=lambda: disposed.append(1))

    monkeypatch.setattr(node, "create_engine", fake_create)
    node._dispose_engine()  # 清理既有缓存（并发安全）

    # 特殊字符密码（@/:）→ URL.create 正常解析
    monkeypatch.setattr(node.settings, "MYSQL_PASSWORD", "p@ss:word/1")
    e1 = node._get_engine()
    assert len(created_urls) == 1
    assert "p@ss:word/1" in created_urls[0].password

    # 配置一致 → 复用
    assert node._get_engine() is e1
    assert len(created_urls) == 1

    # 密码轮换 → 先 dispose 旧引擎再新建
    monkeypatch.setattr(node.settings, "MYSQL_PASSWORD", "new-password")
    e2 = node._get_engine()
    assert e2 is not e1
    assert len(disposed) == 1
    assert len(created_urls) == 2

    # 库切换 → 同样 dispose
    monkeypatch.setattr(node.settings, "MYSQL_DATABASE", "other_db")
    node._get_engine()
    assert len(disposed) == 2

    node._dispose_engine()  # 测试清理
