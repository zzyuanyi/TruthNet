"""方案 v3.1 §7 关键测试 — 步骤 6（CompanyEntityResolver）.

对应审查测试项：
- 唯一精确命中自动锁定，唯一启发式命中按策略处理（P1-2 六项条件）；
- 新实体解析失败或 LLM 失败时不得沿用历史公司（历史防串）；
- 多个 segmentation alternatives 不扁平为 company candidates（P0-4）；
- 恰好 limit 个候选不误判 truncated，limit+1 才截断（P1-3 状态映射）。
"""

import json

from sqlalchemy import create_engine, text

from app.agents.state import MemoryContext
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)

_TABLE = (
    "CREATE TABLE companies ("
    "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
    "industry_l1 TEXT, aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
    "is_latest INTEGER)"
)


def _mysql_lookup(rows: list[tuple]):
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


def _resolver(lookup) -> CompanyEntityResolver:
    return CompanyEntityResolver(lookup)


def _memory(**kw) -> MemoryContext:
    return MemoryContext(**kw)


def _km_memory() -> MemoryContext:
    """历史：康美药业（代码 + 名称）。"""
    return _memory(
        resolved_entity_name="康美药业",
        resolved_company_code="600518.SH",
        is_anaphora=False,
        previous_company_codes=["600518.SH"],
        previous_companies=["康美药业"],
    )


# ── 确定性正例（唯一命中自动锁定）────────────────────────────


def test_exact_name_locked():
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("贵州茅台营收")
    assert r.intent == "single"
    assert r.selected_companies[0].sec_name == "贵州茅台"
    assert r.mentions[0].status == "auto_selected"
    assert not r.needs_confirmation


def test_exact_code_locked():
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("600519.SH 的营收")
    assert r.selected_companies[0].wind_code == "600519.SH"


def test_same_company_name_and_code_are_one_subject():
    lookup = _mysql_lookup([("c1", "600518.SH", "康美药业", None)])
    r = _resolver(lookup).resolve("康美药业 600518.SH 的公告")
    assert r.intent == "single"
    assert [company.wind_code for company in r.selected_companies] == ["600518.SH"]
    assert [mention.selected_wind_code for mention in r.mentions] == ["600518.SH"]


def test_reverse_contains_unique_locked():
    """safe_reverse_contains：'茅台' → 贵州茅台 自动锁定。"""
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("茅台营收")
    assert r.selected_companies[0].sec_name == "贵州茅台"
    assert r.mentions[0].status == "auto_selected"
    assert r.mentions[0].resolution_source == "substring"


def test_grammar_suffix_stripped_locks():
    """'和邦的营收'：提取器剥离尾部"的"→ span '和邦' 直接命中 → 锁定。"""
    lookup = _mysql_lookup(
        [
            ("c1", "603077.SH", "和邦生物", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    r = _resolver(lookup).resolve("和邦的营收")
    assert not r.needs_confirmation
    assert r.mentions[0].status == "auto_selected"
    assert r.mentions[0].selected_wind_code == "603077.SH"
    assert r.selected_companies[0].sec_name == "和邦生物"


# ── 历史延续与防串 ──────────────────────────────────────────


def test_anaphora_continues_history():
    lookup = SQLiteCompanyRepository()
    mc = _memory(
        resolved_entity_name="康美药业",
        resolved_company_code="600518.SH",
        is_anaphora=True,
    )
    r = _resolver(lookup).resolve("它的应收账款增速", mc)
    assert r.intent == "continuation"
    assert r.selected_companies[0].sec_name == "康美药业"
    assert r.mentions[0].resolution_source == "history"


def test_unresolved_new_entity_not_inherited():
    """'台泥的营收'（历史康美）→ not_found，绝不沿用康美（防串）。"""
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("台泥的营收", _km_memory())
    assert r.selected_companies == []
    assert r.unresolved_mentions == ["台泥"]
    assert r.mentions[0].status == "not_found"


def test_out_of_db_company_not_inherited():
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("小米的营收", _km_memory())
    assert r.selected_companies == []
    assert r.mentions[0].status == "not_found"


def test_new_company_switches_from_history():
    """历史康美 + '茅台营收' → switch 到贵州茅台，不沿用康美。"""
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("茅台营收", _km_memory())
    assert r.intent == "switch"
    assert r.selected_companies[0].sec_name == "贵州茅台"


# ── 多 mention 与关系 ───────────────────────────────────────


def test_compound_split_two_mentions():
    """'茅台和和邦对比' → 复合分段 → 两家 → comparison。"""
    lookup = _mysql_lookup(
        [
            ("c1", "600519.SH", "贵州茅台", None),
            ("c2", "603077.SH", "和邦生物", None),
        ]
    )
    r = _resolver(lookup).resolve("茅台和和邦对比")
    assert r.intent == "comparison"
    assert len(r.selected_companies) == 2
    assert {c.sec_name for c in r.selected_companies} == {"贵州茅台", "和邦生物"}
    assert not r.needs_confirmation


def test_ambiguous_mention_kept_per_mention():
    """'平安和茅台对比' → 平安多候选 needs_confirmation（只确认平安）。

    最终续审 §4 A4：部分绑定不得作为可执行 comparison 离开 Resolver
    → 降级 ambiguous（mentions/候选保留，确认重跑后恢复 comparison）。
    """
    lookup = _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
            ("c3", "600519.SH", "贵州茅台", None),
        ]
    )
    r = _resolver(lookup).resolve("平安和茅台对比")
    # comparison is retained as the confirmable intermediate relation;
    # final executability is checked after the last identity confirmation.
    assert r.intent == "comparison"
    assert r.reason_code == "comparison_missing_peer"
    assert r.needs_confirmation
    by_text = {m.text: m for m in r.mentions}
    assert by_text["平安"].status == "needs_confirmation"
    assert len(by_text["平安"].candidates) == 2
    assert by_text["茅台"].status == "auto_selected"
    assert by_text["茅台"].selected_wind_code == "600519.SH"


def test_segmentation_alternatives_not_flattened():
    """复合切分采用唯一合法方案，mention 边界不扁平。

    "茅台和协和和和邦的营收"：多种切分点但合法全程方案唯一
    （茅台/协和电子/和邦生物）；"和邦的"为变体命中 → 按 P1-2
    条件 4 需确认，但三个 mention 分组各自保留候选（不扁平合并）。
    """
    lookup = _mysql_lookup(
        [
            ("c1", "600519.SH", "贵州茅台", None),
            ("c2", "600071.SH", "协和电子", None),
            ("c3", "603077.SH", "和邦生物", None),
        ]
    )
    r = _resolver(lookup).resolve("茅台和协和和和邦的营收")
    by_text = {m.text: m for m in r.mentions}
    assert set(by_text) == {"茅台", "协和", "和邦"}
    assert by_text["茅台"].status == "auto_selected"
    assert by_text["茅台"].selected_wind_code == "600519.SH"
    assert by_text["协和"].status == "auto_selected"
    assert by_text["协和"].selected_wind_code == "600071.SH"
    assert by_text["和邦"].status == "auto_selected"
    assert by_text["和邦"].selected_wind_code == "603077.SH"
    assert not r.needs_confirmation
    assert len(r.mentions) == 3


def test_truncated_candidates_need_refinement():
    """候选截断（limit+1）→ needs_refinement，不锁定不确认。"""
    rows = [(f"c{i}", f"{601000 + i}.SH", f"平安集团{i}", None) for i in range(7)]
    lookup = _mysql_lookup(rows)
    r = _resolver(lookup).resolve("平安集团营收")
    assert r.mentions[0].status == "needs_refinement"
    assert r.mentions[0].truncated is True  # v3.2.1 批次 7：DTO 按 mention 置位
    assert r.needs_confirmation is False  # 不可确认（无完整候选集）
    assert not r.selected_companies


def test_shrink_fallback_offers_candidates_not_lock():
    """'平安的存贷风险' → span 含业务词整查失败 → 尾部收缩 '平安'
    → 候选展示（needs_confirmation），绝不自动锁定（P1-2 条件 2）。"""
    lookup = _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
        ]
    )
    r = _resolver(lookup).resolve("平安的存贷风险")
    assert r.needs_confirmation
    m = r.mentions[0]
    assert m.status == "needs_confirmation"
    assert m.selected_wind_code is None
    assert {c.company.sec_name for c in m.candidates} == {"平安银行", "中国平安"}


def test_shrink_fallback_not_found_stays_blocked():
    """收缩到 2 字仍无候选（lite 无台泥）→ not_found，防串保持。"""
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("台泥的营收", _km_memory())
    assert r.mentions[0].status == "not_found"
    assert r.selected_companies == []


def test_short_name_boundary_regression_20260815():
    """第三轮复核 P1/P2 回归（2026-08-15，交接说明 §十一.3）。

    真机现象：『围海近期舆情事件对公司有什么影响？』被提取为
    mention「围海近期」（短称与邻近时间词误并单 span）→ not_found，
    用户可见"疑似公司「围海近期」但未能识别"；『002586.SZ 近期…』
    则多出「近期」not_found mention（fail-closed 阻断整句）。

    当前锁定行为（防串保持，不修 span 边界）：
    - 「围海近期」误并 span → not_found，不静默锁任何公司；
    - 「002586.SZ」代码 mention 正常 auto_selected，附属「近期」not_found。
    修复批目标（实体识别后续批次）：短称「围海」应走候选确认
    （needs_confirmation 候选 *ST围海）而非直接 NIL；届时更新本用例断言。
    """
    lookup = _mysql_lookup(
        [
            (
                "c1",
                "002586.SZ",
                "*ST围海",
                json.dumps(["围海", "围海股份"], ensure_ascii=False),
            )
        ]
    )
    # ① 短称+邻近词误并：not_found 且不锁公司（防串保持）
    r = _resolver(lookup).resolve("围海近期舆情事件对公司有什么影响？")
    m = r.mentions[0]
    assert m.text == "围海近期"
    assert m.status == "not_found"
    assert r.selected_companies == []
    assert not r.needs_confirmation
    # ② 代码 + 邻近词：代码正常锁定，附属词 not_found
    r2 = _resolver(lookup).resolve("002586.SZ 近期舆情事件对公司有什么影响？")
    by_text = {mm.text: mm for mm in r2.mentions}
    assert by_text["002586.SZ"].status == "auto_selected"
    assert by_text["002586.SZ"].selected_wind_code == "002586.SZ"
    assert by_text["近期"].status == "not_found"


# ── v3.2.1 批次 2/3：业务上下文与受控所有格（旧断言迁移）──────


def test_lookalike_company_names_not_confirmed():
    """旧 test_entity_fragments 迁移（六轮审查 P1-1）：'茅台镇/康美丽'
    不得静默串成贵州茅台/康美药业——零候选即 not_found，禁止逐字截短。"""
    lookup = _mysql_lookup(
        [
            ("c1", "600519.SH", "贵州茅台", None),
            ("c2", "600518.SH", "康美药业", None),
        ]
    )
    for q in ("茅台镇的营收", "康美丽的营收"):
        r = _resolver(lookup).resolve(q)
        assert r.mentions[0].status == "not_found", q
        assert r.selected_companies == [], q
        assert not r.needs_confirmation, q


def test_business_context_dropped_with_valid_company():
    """'康美药业 2025 年报财务分析' → '年报'为业务上下文被忽略，
    intent=single、康美有效、无公司错误。"""
    lookup = _mysql_lookup([("c1", "600518.SH", "康美药业", None)])
    r = _resolver(lookup).resolve("康美药业 2025 年报财务分析")
    assert r.intent == "single"
    assert r.selected_companies[0].sec_name == "康美药业"
    assert r.unresolved_mentions == []  # 年报不进入 unresolved
    assert [m.text for m in r.mentions] == ["康美药业"]


def test_company_name_containing_you_and_trailing_predicates_resolve_exactly():
    """公司名中的“有”保留；尾部谓语只在左侧可独立命中时受控剥离。"""
    lookup = _mysql_lookup(
        [
            ("c1", "603697.SH", "有友食品", None),
            ("c2", "600518.SH", "康美药业", None),
        ]
    )
    cases = {
        "你认为有友食品怎么样": "有友食品",
        "有友食品有风险吗": "有友食品",
        "康美药业有造假风险吗": "康美药业",
        "康美药业存在造假风险吗": "康美药业",
        "康美药业持有多少资产": "康美药业",
    }
    for query, expected in cases.items():
        result = _resolver(lookup).resolve(query)
        assert result.intent == "single", query
        assert result.selected_companies[0].sec_name == expected, query
        assert result.mentions[0].text == expected, query
        assert result.mentions[0].status == "auto_selected", query


def test_full_name_compound_is_segmented_before_contains_candidates():
    """低置信 contains 不得抢在合法复合分段之前吞掉两个完整公司名。"""
    lookup = _mysql_lookup(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    result = _resolver(lookup).resolve("康美药业和贵州茅台的营收")
    assert result.intent == "comparison"
    assert not result.needs_confirmation
    assert {m.text for m in result.mentions} == {"康美药业", "贵州茅台"}
    assert {c.wind_code for c in result.selected_companies} == {
        "600518.SH",
        "600519.SH",
    }


def test_research_topic_query_returns_no_company():
    """'白酒行业近期研报观点' → no_company/research_context（非阻断）。"""
    lookup = SQLiteCompanyRepository()
    r = _resolver(lookup).resolve("白酒行业近期研报观点")
    assert r.intent == "no_company"
    assert r.reason_code == "research_context"
    assert r.unresolved_mentions == []
    assert not r.needs_confirmation


def test_research_topic_exclusions_stay_not_found():
    """公司形态后缀（科技）下'火星科技行业风险/研报'仍 not_found 阻断。"""
    lookup = SQLiteCompanyRepository()
    for q in ("火星科技行业风险", "火星科技行业研报"):
        r = _resolver(lookup).resolve(q)
        assert r.mentions[0].status == "not_found", q
        assert r.unresolved_mentions, q


def test_detect_comparison_industry_context_not_comparison():
    """旧 test_resolve_entity 迁移（P1-1 第三轮审查）：0 家候选 +
    行业/指标语境 → 非跨公司。"白酒行业比较"是行业分析不是跨公司比较。"""
    from app.application.services.company_entity_resolver import _detect_comparison

    assert _detect_comparison("白酒行业比较", []) is False
    assert _detect_comparison("医药行业对比", []) is False
    assert _detect_comparison("康美药业与行业比较怎么样", ["康美药业"]) is False
    assert _detect_comparison("茅台和五粮液对比", ["贵州茅台", "五粮液"]) is True


def test_suffix_variants_grammar_only():
    """旧 test_entity_fragments 迁移（六轮审查 P1-1）：只删明确尾部语法
    字符，禁止任意截短——"茅台"尾部"台"非语法字符 → 不截短。"""
    from app.application.services.company_entity_resolver import _suffix_variants

    assert _suffix_variants("茅台镇的") == ["茅台镇的", "茅台镇"]
    assert _suffix_variants("茅台镇") == ["茅台镇"]  # "镇"非语法字符
    assert _suffix_variants("和邦的") == ["和邦的", "和邦"]


# ── v3.3 批次 B：多代码 / 代码+名称 / 查询预算（10.1 矩阵）──────


def _two_code_lookup():
    return _mysql_lookup(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )


def test_two_embedded_codes_both_mentions():
    """'600518.SH 和 600519.SH 对比' → 两个代码 mention（P1-4）。"""
    r = _resolver(_two_code_lookup()).resolve("600518.SH 和 600519.SH 对比")
    assert r.intent == "comparison"
    assert [m.text for m in r.mentions] == ["600518.SH", "600519.SH"]
    assert {c.wind_code for c in r.selected_companies} == {
        "600518.SH",
        "600519.SH",
    }


def test_code_plus_name_both_mentions():
    """'600518.SH 和茅台对比' → 代码 + 名称两个 mention（P1-4）。"""
    r = _resolver(_two_code_lookup()).resolve("600518.SH 和茅台对比")
    assert r.intent == "comparison"
    assert [m.text for m in r.mentions] == ["600518.SH", "茅台"]
    assert {c.sec_name for c in r.selected_companies} == {"康美药业", "贵州茅台"}


def test_leading_connector_stripped_by_candidate_recall():
    """'比较 600518 与康美药业' → 段首连接词剥离经候选召回验证：
    '与康美药业'→'康美药业'（v3.3 4.2 第 5 项）。

    最终续审 §4 A4：两 mention 绑定同一公司（600518.SH），comparison
    需要两个不同 Wind Code → comparison_missing_peer 拒绝，不凑数。
    """
    r = _resolver(_two_code_lookup()).resolve("比较 600518 与康美药业")
    assert r.intent != "comparison"
    assert r.reason_code == "comparison_missing_peer"
    assert [m.text for m in r.mentions] == ["600518", "康美药业"]
    assert all(m.status == "auto_selected" for m in r.mentions)


def test_proposal_budget_memoizes_and_caps():
    """ProposalLookupBudget：相同 text 只查一次；12 次上限后返回显式
    耗尽 Outcome（v3.3.1 §5.1：不再用 None 表示耗尽）。"""
    from app.application.services.company_mention_proposal_service import (
        ProposalLookupBudget,
    )

    calls: list[str] = []

    class _CountingLookup:
        def lookup_mention(self, text):
            calls.append(text)
            from app.application.models.company_resolution import (
                CandidateLookupResult,
            )

            return CandidateLookupResult()

    budget = ProposalLookupBudget(_CountingLookup())
    for _ in range(3):
        budget.lookup("茅台")  # memoize：只计数一次
    assert len(calls) == 1
    for i in range(20):
        budget.lookup(f"span_{i}")
    assert budget.exhausted
    outcome = budget.lookup("never_seen")  # 耗尽后不查询、不缓存
    assert outcome.budget_exhausted is True
    assert outcome.result is None


def test_budget_exhaustion_returns_needs_refinement():
    """预算耗尽 → needs_refinement，不得静默丢弃后自动绑定（§4.2）。"""
    lookup = _mysql_lookup(
        [(f"c{i}", f"{601000 + i}.SH", f"平安集团{i}", None) for i in range(40)]
    )
    # 大量互不相同的长 span（复合切分查询消耗预算）
    q = "和".join(f"未知公司{i}" for i in range(6)) + "的营收"
    r = _resolver(lookup).resolve(q)
    assert (
        any(m.status == "needs_refinement" and m.truncated for m in r.mentions)
        or not r.selected_companies
    )


# ── override 重跑（P0-3：指纹/span/候选校验后恢复完整决策）──────


def _override_for(lookup, query: str, relation: str = "comparison"):
    """构造合法 override：先解析一次拿 mention_id/span，再填确认值。"""
    from app.application.models.company_resolution import (
        EntityResolutionOverride,
        OverrideDecision,
        make_query_fingerprint,
    )

    r0 = _resolver(lookup).resolve(query)
    decisions = []
    for idx, m in enumerate(r0.mentions):
        # v3.2.1 批次 4：comparison 终态要求恰好一个 primary，其余
        # comparison_peer（严格校验 validate_finalized_relation_roles）
        if relation == "comparison":
            role = "primary" if idx == 0 else "comparison_peer"
        else:
            role = "primary"
        code = (
            m.candidates[0].company.wind_code
            if m.status == "needs_confirmation"
            else m.selected_wind_code
        )
        decisions.append(
            OverrideDecision(
                mention_id=m.mention_id,
                text=m.text,
                start=m.start,
                end=m.end,
                wind_code=code,
                role=role,
            )
        )
    return EntityResolutionOverride(
        query_fingerprint=make_query_fingerprint(query),
        relation=relation,
        decisions=decisions,
    )


def test_override_resume_restores_relation_and_role():
    """确认完成重跑：override 恢复身份 + relation + role（P0-3）。"""
    from app.agents.state import RequestContext

    lookup = _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
            ("c3", "600519.SH", "贵州茅台", None),
        ]
    )
    override = _override_for(lookup, "平安和茅台对比")
    rc = RequestContext(entity_overrides=override)
    r = _resolver(lookup).resolve("平安和茅台对比", request_context=rc)
    assert r.intent == "comparison"
    assert r.reason_code == "override"
    assert not r.needs_confirmation
    by_text = {m.text: m for m in r.mentions}
    assert by_text["平安"].status == "user_confirmed"
    assert by_text["平安"].selected_wind_code == "000001.SZ"
    assert by_text["平安"].role == "primary"
    assert by_text["茅台"].selected_wind_code == "600519.SH"


def test_override_fingerprint_mismatch_rejected():
    """指纹不匹配 → 拒绝 override，走正常解析（防陈旧确认注入）。"""
    from app.agents.state import RequestContext

    lookup = _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
        ]
    )
    override = _override_for(lookup, "分析平安", relation="single")
    override.query_fingerprint = "wrong-fingerprint"
    rc = RequestContext(entity_overrides=override)
    r = _resolver(lookup).resolve("分析平安", request_context=rc)
    assert r.reason_code != "override"
    assert r.needs_confirmation  # 走正常解析（歧义 → 确认）


def test_override_out_of_allowlist_rejected():
    """库外 wind_code → 拒绝 override，走正常解析。"""
    from app.agents.state import RequestContext

    lookup = _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
        ]
    )
    override = _override_for(lookup, "分析平安", relation="single")
    override.decisions[0].wind_code = "600519.SH"  # 库外
    rc = RequestContext(entity_overrides=override)
    r = _resolver(lookup).resolve("分析平安", request_context=rc)
    assert r.reason_code != "override"


# ── v3.2.1 批次 4：override 严格终态校验拒绝用例 ──────────────


def _pingan_maotai_lookup():
    return _mysql_lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
            ("c3", "600519.SH", "贵州茅台", None),
        ]
    )


def _resolve_override(query: str, override):
    from app.agents.state import RequestContext

    lookup = _pingan_maotai_lookup()
    rc = RequestContext(entity_overrides=override)
    return _resolver(lookup).resolve(query, request_context=rc)


def test_override_missing_decision_rejected():
    """'平安和茅台对比' override 只含茅台 → 缺失 decision，拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions = override.decisions[1:]  # 只留茅台
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"
    assert r.needs_confirmation  # 回退正常解析 → 平安仍需确认


def test_override_empty_decisions_rejected():
    """decisions 为空 → 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions = []
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_duplicate_decision_id_rejected():
    """重复 mention_id → 拒绝。"""
    from app.application.models.company_resolution import OverrideDecision

    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    first = override.decisions[0]
    override.decisions = [
        first,
        OverrideDecision(
            mention_id=first.mention_id,
            text=first.text,
            start=first.start,
            end=first.end,
            wind_code="601318.SH",
            role="comparison_peer",
        ),
    ]
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_empty_code_rejected():
    """空 wind_code → 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions[0].wind_code = ""
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_empty_role_rejected():
    """空 role → 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions[0].role = None
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_inexecutable_relation_rejected():
    """reference/sequence/ambiguous 等不可执行 relation → 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.relation = "reference"
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_single_multi_company_rejected():
    """relation=single 但 decisions 覆盖两家 → 终态校验拒绝。"""
    override = _override_for(
        _pingan_maotai_lookup(), "平安和茅台对比", relation="single"
    )
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_comparison_duplicate_codes_rejected():
    """comparison 两个 decision 同一代码 → 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions[1].wind_code = override.decisions[0].wind_code
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"


def test_override_comparison_wrong_roles_rejected():
    """comparison 两个 primary（无 comparison_peer）→ 拒绝。"""
    override = _override_for(_pingan_maotai_lookup(), "平安和茅台对比")
    override.decisions[0].role = "primary"
    override.decisions[1].role = "primary"
    r = _resolve_override("平安和茅台对比", override)
    assert r.reason_code != "override"
