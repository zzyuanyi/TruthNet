"""方案 v3.1 §7 关键测试 — 步骤 4（span extractor）.

对应审查测试项：
- 清洗时间/请求词后 start/end 仍切回原文正确片段（P1-4 等长 mask）；
- 2023/2024/2025/2026 年茅台营收均识别贵州茅台（年份通配，不硬编码）；
- 复合片段（"茅台和协和"）作为一个 span 提出（切分交给 Resolver）。
"""

from app.application.services.company_mention_extractor import (
    extract_company_mention_result,
    extract_company_mentions,
)


def _spans(query: str) -> list[tuple[str, int, int]]:
    return [(m.text, m.start, m.end) for m in extract_company_mentions(query)]


# ── 偏移保持（P1-4）：start/end 恒为原始 query 偏移 ────────────


def test_span_offsets_after_time_words_removed():
    """ "2024年的茅台营收" → '茅台' 在原文位置 (6,8)。"""
    assert _spans("2024年的茅台营收") == [("茅台", 6, 8)]


def test_span_offsets_trailing_time_words():
    """时间词在 mention 之后（"茅台2024年上半年营收"）→ '茅台' (0,2)。"""
    assert _spans("茅台2024年上半年营收") == [("茅台", 0, 2)]


def test_span_offsets_after_request_words():
    """ "麻烦看茅台营收" → '茅台' (3,5)。"""
    assert _spans("麻烦看茅台营收") == [("茅台", 3, 5)]


def test_span_offsets_after_leading_pronoun():
    """ "都看茅台营收" → '茅台' (2,4)（前导指代整组删除）。"""
    assert _spans("都看茅台营收") == [("茅台", 2, 4)]


def test_span_offsets_after_year_prefix():
    """ "去年的茅台营收" → '茅台' (3,5)。"""
    assert _spans("去年的茅台营收") == [("茅台", 3, 5)]


# ── 年份通配：2023/2024/2025/2026 均识别（不硬编码 2024）──────


def test_generic_year_matches_any_year():
    for year in ("2023", "2024", "2025", "2026"):
        q = f"{year}年茅台营收"
        spans = _spans(q)
        assert [t for t, _, _ in spans] == ["茅台"], f"{year} 年失败"


def test_span_offsets_generic_year():
    """ "2026年茅台营收" → '茅台' (5,7)（原文偏移随年份长度变化）。"""
    assert _spans("2026年茅台营收") == [("茅台", 5, 7)]


# ── 复合片段作为一个 span（切分交给 Resolver）──────────────────


def test_compound_kept_as_single_span():
    """ "茅台和协和的营收" → span '茅台和协和'（段内"和"不拆，尾部语法词剥离）。"""
    assert _spans("茅台和协和的营收") == [("茅台和协和", 0, 5)]


def test_compound_two_full_names_kept():
    """ "康美药业和贵州茅台的营收" → span '康美药业和贵州茅台'（整体提出）。"""
    assert _spans("康美药业和贵州茅台的营收") == [("康美药业和贵州茅台", 0, 9)]


def test_leading_connector_kept_for_company_name():
    """ "和邦的营收" → span '和邦'（段首"和"是公司名成分，不删；尾"的"剥离）。"""
    assert _spans("和邦的营收") == [("和邦", 0, 2)]


# ── 主语槽截断（终止符）───────────────────────────────────────


def test_subject_slot_truncates_at_terminator():
    assert _spans("康美药业财务造假风险") == [("康美药业", 0, 4)]
    assert _spans("台泥的营收") == [("台泥", 0, 2)]


def test_subject_slot_truncates_company_fact_queries():
    assert _spans("平安集团的高管薪酬") == [("平安集团", 0, 4)]
    assert _spans("波长光电的首发价格是多少") == [("波长光电", 0, 4)]


def test_empty_subject_slot_no_mention():
    """ "营收高吗"：主语槽为空 → 无 span（放行延续历史主体）。"""
    assert _spans("营收高吗") == []


def test_residual_filler_words_cleaned():
    """ "综合给一个风险结论" → 无 span（填充词+前导指代清空）。"""
    assert _spans("综合给一个风险结论") == []


def test_pure_anaphora_no_mention():
    """ "它的应收账款增速" → '它' 被前导指代删除，无显式 mention。"""
    assert _spans("它的应收账款增速") == []


def test_chitchat_proposes_span():
    """提取器不判闲聊（闲聊短路在节点层）——"你好"作为 2 字 span 提出。"""
    assert _spans("你好") == [("你好", 0, 2)]


def test_grammar_suffix_stripped_to_min_two():
    """ "美的是" → span '美的'（尾部语法词剥离，保留 ≥2 字）。"""
    assert _spans("美的是") == [("美的", 0, 2)]
    # "茅台的是" → 剥离"是"→"茅台"（尾部"的"再剥会 <2 字 → 停）
    assert _spans("茅台的是") == [("茅台", 0, 2)]


def test_mention_id_stable_from_span():
    """同一 span 恒生成同一 mention_id（重跑可关联）。"""
    a = extract_company_mentions("茅台和协和的营收")
    b = extract_company_mentions("茅台和协和的营收")
    assert a == b
    assert a[0].mention_id.startswith("m_0_5_")


def test_belong_boundary_terminates_subject():
    """v3.2.1 批次 2："属于"为公司事实问法边界——
    "小米属于什么行业"→'小米'、"康美药业属于什么行业"→'康美药业'。
    单字"的"不得入终止符（"美的营收"→'美的'不受影响）。"""
    assert _spans("小米属于什么行业") == [("小米", 0, 2)]
    assert _spans("康美药业属于什么行业") == [("康美药业", 0, 4)]
    assert _spans("美的营收") == [("美的", 0, 2)]


def test_listing_question_predicate_is_not_a_company_mention():
    assert _spans("康美药业什么时候上市的") == [("康美药业", 0, 4)]
    assert _spans("贵州茅台何时上市") == [("贵州茅台", 0, 4)]


def test_existence_predicate_is_not_part_of_company_name():
    assert _spans("浪潮信息是否存在风险") == [("浪潮信息", 0, 4)]
    assert _spans("ST尔雅存在哪些风险") == [("ST尔雅", 0, 4)]


def test_request_frame_does_not_hide_company_starting_with_you_opinion():
    """锚定请求框架应被移除，但公司名中的“有”必须完整保留。"""
    assert _spans("你认为有友食品怎么样") == [("有友食品", 3, 7)]
    assert _spans("你觉得有友食品如何") == [("有友食品", 3, 7)]


def test_you_predicate_is_not_a_global_subject_terminator():
    """“有”由 Resolver 候选驱动处理，Extractor 不得切坏有友食品。"""
    assert _spans("有友食品有风险吗") == [("有友食品有", 0, 5)]
    assert _spans("康美药业有造假风险吗") == [("康美药业有", 0, 5)]


# ── v3.3.2 §5 批次 A：多轮主体最小纠偏（§5.4 反例）────────────


def test_anaphora_phrase_no_company_span():
    """'总结一下这家公司' -> 无 '公司' span（回指短语整体 mask，
    不再残留'公司'被误召回中金/中微）。"""
    spans = extract_company_mentions("总结一下这家公司")
    assert [m.text for m in spans] == []


def test_contrast_prefix_na_maotai_keeps_offset():
    """'那茅台呢' -> '茅台'，offset 对应原文（(1,3)）。"""
    spans = extract_company_mentions("那茅台呢")
    assert [(m.text, m.start, m.end) for m in spans] == [("茅台", 1, 3)]


def test_switch_prefix_back_to_kangmei_keeps_offset():
    """'回到康美' -> '康美'，offset 对应原文（(2,4)）；'再回到/换回' 同理。"""
    spans = extract_company_mentions("回到康美")
    assert [(m.text, m.start, m.end) for m in spans] == [("康美", 2, 4)]
    spans2 = extract_company_mentions("再回到康美的分析")
    assert [(m.text, m.start, m.end) for m in spans2] == [("康美", 3, 5)]
    spans3 = extract_company_mentions("换回茅台")
    assert [(m.text, m.start, m.end) for m in spans3] == [("茅台", 2, 4)]


def test_history_reference_frame_no_mention_span():
    """'刚才提到的风险信号哪个最严重' -> 无 '提到' span（句首回指框架）。"""
    spans = extract_company_mentions("刚才提到的风险信号哪个最严重")
    assert "提到" not in [m.text for m in spans]


def test_mention_connector_compound_preserved():
    """'康美提到茅台' -> 仍保留可供复合解析的两家公司语义（'提到'
    不得全局删除）。"""
    spans = extract_company_mentions("康美提到茅台")
    assert [m.text for m in spans] == ["康美提到茅台"]


def test_existing_cases_no_regression():
    """'和邦的营收'、'协和电子'、'美的营收' 不回归。"""
    assert [m.text for m in extract_company_mentions("和邦的营收")] == ["和邦"]
    assert [m.text for m in extract_company_mentions("协和电子")] == ["协和电子"]
    assert [m.text for m in extract_company_mentions("美的营收")] == ["美的"]


def test_research_and_event_words_are_not_second_company_mentions():
    assert [m.text for m in extract_company_mentions("东吴证券的最新研报")] == [
        "东吴证券"
    ]
    assert [
        m.text for m in extract_company_mentions("双良节能最新的市场动态是什么")
    ] == ["双良节能"]


def test_continuous_loss_years_does_not_become_company_mention():
    assert [m.text for m in extract_company_mentions("通威股份连续亏损了几年")] == [
        "通威股份"
    ]


def test_market_and_research_fillers_do_not_become_company_mentions():
    assert [m.text for m in extract_company_mentions("新光制药最近的市场表现如何")] == [
        "新光制药"
    ]
    assert [m.text for m in extract_company_mentions("贵州茅台最近研报的提炼")] == [
        "贵州茅台"
    ]


def test_market_followup_fields_are_not_company_mentions():
    assert extract_company_mentions("换手率") == []
    assert extract_company_mention_result("换手率").had_subject_terminator
    assert (
        extract_company_mentions("汤姆猫是哪个板块，近期表现如何")[0].text == "汤姆猫"
    )
    assert [
        m.text for m in extract_company_mentions("今年以来，贵州茅台的最高价是多少？")
    ] == ["贵州茅台"]
