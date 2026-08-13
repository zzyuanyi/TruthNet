"""ResolveEntity 节点测试 — 主语省略延续与指代消解接入."""

import json

from sqlalchemy import create_engine, text

from app.agents.nodes.resolve_entity import resolve_entity_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    MemoryContext,
    RequestContext,
    RuntimeState,
)


def _make_state(query: str, memory: MemoryContext | None) -> AgentState:
    return {
        "user_query": query,
        "memory_context": memory,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def test_anaphora_resolved_entity_appended():
    """指代轮次：resolved_entity_name 追加到搜索文本。"""
    mc = MemoryContext(
        resolved_entity_name="康美药业",
        is_anaphora=True,
        previous_companies=["康美药业"],
    )
    result = resolve_entity_node(_make_state("它的应收账款呢", mc))
    company = result["company"]
    assert company is not None
    assert company.sec_name == "康美药业"


def test_subject_ellipsis_continues_last_company():
    """主语省略：query 无公司名无指代词 → 延续最近主体。"""
    mc = MemoryContext(
        resolved_entity_name=None,
        is_anaphora=False,
        previous_companies=["康美药业", "贵州茅台"],
    )
    result = resolve_entity_node(_make_state("综合给一个风险结论", mc))
    company = result["company"]
    assert company is not None
    assert company.sec_name == "康美药业"  # 最近主体


def test_no_company_no_history_returns_none():
    """无公司名且无历史 → None。"""
    result = resolve_entity_node(_make_state("你好", MemoryContext()))
    assert result["company"] is None


def test_chitchat_does_not_inherit_previous_company(monkeypatch):
    """旧会话中的“你好/谢谢”不得继承主体并触发上一家公司的完整分析。"""
    from app.agents.nodes import resolve_entity as node

    calls: list[str] = []

    def fake_find(query: str):
        calls.append(query)
        return None

    monkeypatch.setattr(node, "_find_company", fake_find)
    mc = MemoryContext(previous_companies=["康美药业"])

    assert resolve_entity_node(_make_state("你好", mc))["company"] is None
    assert calls == [], "纯寒暄不应进入公司查询或历史主体恢复"


def test_unsupported_query_does_not_match_company_name_substring(monkeypatch):
    """“今天天气”不得因“今天国际”公司名前缀而触发完整分析。"""
    from app.agents.nodes import resolve_entity as node

    calls: list[str] = []

    def fake_find(query: str):
        calls.append(query)
        raise AssertionError("范围外问题不应进入公司实体查询")

    monkeypatch.setattr(node, "_find_company", fake_find)

    result = resolve_entity_node(_make_state("今天天气怎么样", MemoryContext()))

    assert result["company"] is None
    assert calls == []


def test_explicit_follow_up_still_inherits_previous_company(monkeypatch):
    """限制上下文继承后，明确的省略主语追问仍应延续上一家公司。"""
    from app.agents.nodes import resolve_entity as node
    from app.agents.state import CompanyRef

    company = CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )

    def fake_find(query: str):
        return company if query == "康美药业" else None

    monkeypatch.setattr(node, "_find_company", fake_find)
    mc = MemoryContext(previous_companies=["康美药业"])

    result = resolve_entity_node(_make_state("继续看现金流", mc))
    assert result["company"] == company


def test_explicit_company_context_takes_precedence(monkeypatch):
    from app.agents.nodes import resolve_entity as node

    company = CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )
    calls: list[str] = []

    def fake_find(query: str):
        calls.append(query)
        return company if query == "600518.SH" else None

    monkeypatch.setattr(node, "_find_company", fake_find)
    state = _make_state("分析贵州茅台", MemoryContext())
    state["request_context"] = RequestContext(company_code="600518.SH")
    result = resolve_entity_node(state)
    assert result["company"] == company
    assert calls == ["600518.SH"]


def test_ambiguous_company_returns_candidates(monkeypatch):
    from app.agents.nodes import resolve_entity as node

    candidates = [
        CompanyRef(
            entity_id="company_000001_SZ",
            wind_code="000001.SZ",
            sec_name="平安银行",
            exchange="XSHE",
        ),
        CompanyRef(
            entity_id="company_601318_SH",
            wind_code="601318.SH",
            sec_name="中国平安",
            exchange="XSHG",
        ),
    ]
    monkeypatch.setattr(node, "_find_company", lambda _query: None)
    monkeypatch.setattr(node, "_find_company_candidates", lambda _query: candidates)
    result = resolve_entity_node(_make_state("分析平安", MemoryContext()))
    assert result["company"] is None
    assert result["company_candidates"] == candidates


# ── 8.11：多候选歧义确认（不得沿用历史公司/静默选最长名）───


def test_ambiguous_new_company_not_inherited_from_memory(monkeypatch):
    """8.11：历史康美 + 当前问'分析国药的财务风险'（多候选）→ 返回候选，
    绝不沿用康美（新公司词解析失败不得静默恢复旧公司）。"""
    from app.agents.nodes import resolve_entity as node

    candidates = [
        _ref("国药股份", "600511.SH"),
        _ref("国药一致", "000028.SZ"),
    ]
    monkeypatch.setattr(node, "_find_company", lambda _q: None)
    monkeypatch.setattr(node, "_find_company_candidates", lambda _q: candidates)
    mc = MemoryContext(
        resolved_entity_name=None,
        previous_companies=["康美药业"],
    )
    result = resolve_entity_node(_make_state("分析国药的财务风险", mc))
    assert result["company"] is None
    assert result["company_candidates"] == candidates
    assert not result.get("comparison_requested", False)


def test_single_new_company_overrides_history(monkeypatch):
    """8.11：唯一新公司（候选唯一命中）覆盖历史公司。"""
    from app.agents.nodes import resolve_entity as node

    candidates = [_ref("国药股份", "600511.SH")]
    monkeypatch.setattr(node, "_find_company", lambda _q: None)
    monkeypatch.setattr(node, "_find_company_candidates", lambda _q: candidates)
    mc = MemoryContext(
        resolved_entity_name=None,
        previous_companies=["康美药业"],
        resolved_company_code="600518.SH",
    )
    result = resolve_entity_node(_make_state("分析国药股份", mc))
    assert result["company"] is not None
    assert result["company"].sec_name == "国药股份"


def test_candidates_computed_once(monkeypatch):
    """8.11：当前问题候选只查询一次（唯一命中路径不重复查询）。"""
    from app.agents.nodes import resolve_entity as node

    calls: list[str] = []

    def fake_candidates(query, limit=5):
        calls.append(query)
        return [_ref("国药股份", "600511.SH")]

    monkeypatch.setattr(node, "_find_company", lambda _q: None)
    monkeypatch.setattr(node, "_find_company_candidates", fake_candidates)
    result = resolve_entity_node(_make_state("分析国药股份", MemoryContext()))
    assert result["company"] is not None
    assert calls == ["分析国药股份"]


def test_alias_only_ambiguity_returns_candidates(monkeypatch):
    """共享别名命中多家公司时也必须进入候选确认，不能静默返回空。"""
    from app.agents.nodes import resolve_entity as node

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE companies ("
                "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
                "industry_l1 TEXT, aliases TEXT, is_latest INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO companies VALUES "
                "('c1', '000001.SZ', '甲银行', 'XSHE', '银行', :a1, 1), "
                "('c2', '601318.SH', '乙保险', 'XSHG', '非银金融', :a2, 1)"
            ),
            {
                "a1": json.dumps(["平安"], ensure_ascii=False),
                "a2": json.dumps(["平安"], ensure_ascii=False),
            },
        )

    monkeypatch.setattr(node.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(node, "_get_engine", lambda: engine)

    candidates = node._find_company_candidates("分析平安")
    assert {item.wind_code for item in candidates} == {"000001.SZ", "601318.SH"}
    engine.dispose()


# ── R3 优先级：request_context > 当前问题 > 记忆代码 > 记忆名称 ──


def test_resolved_company_code_recovers_entity():
    """十轮外记忆：resolved_company_code 直接按代码解析公司。"""
    mc = MemoryContext(
        resolved_entity_name=None,
        resolved_company_code="600518.SH",
        is_anaphora=True,
    )
    result = resolve_entity_node(_make_state("它现在财务造假的风险还高吗", mc))
    company = result["company"]
    assert company is not None
    assert company.sec_name == "康美药业"


def test_explicit_company_in_query_beats_memory_code():
    """当前问题明确写公司 → 覆盖记忆代码（R3 关键）。"""
    mc = MemoryContext(
        resolved_entity_name=None,
        resolved_company_code="600518.SH",  # 记忆：康美
        is_anaphora=False,
    )
    result = resolve_entity_node(_make_state("分析贵州茅台", mc))
    company = result["company"]
    assert company is not None
    assert company.sec_name == "贵州茅台"


def test_request_context_code_highest_priority(monkeypatch):
    """request_context.company_code 最高优先（跨轮上下文覆盖记忆）。

    CI 环境无 MySQL（lite profile 无 603180.SH mock），monkeypatch 隔离
    数据库依赖，仅验证优先级语义。
    """
    from app.agents.nodes import resolve_entity as node

    def fake_find(query):
        if query == "603180.SH":
            return _ref("金牌家居", "603180.SH")
        return None

    monkeypatch.setattr(node, "_find_company", fake_find)
    mc = MemoryContext(
        resolved_entity_name="贵州茅台",
        is_anaphora=False,
    )
    state = _make_state("继续分析", mc)
    state["request_context"] = RequestContext(company_code="603180.SH")
    result = resolve_entity_node(state)
    assert result["company"] is not None
    assert result["company"].sec_name == "金牌家居"


# ── P1-1（核验修订）：比较意图分级 ──────────────────────────────


def _ref(sec_name: str, code: str = "600000.SH") -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code}",
        wind_code=code,
        sec_name=sec_name,
        exchange="XSHG",
    )


def test_looks_like_comparison_grades():
    """P1-1：强比较词恒真；弱连接词需两家完整名称；vs 忽略大小写。"""
    from app.agents.nodes.resolve_entity import _looks_like_comparison

    # 强词：即使 0 家候选也判比较
    assert _looks_like_comparison("中芯国际和台积电的差距", [])
    assert _looks_like_comparison("康美药业对比贵州茅台", [])
    assert _looks_like_comparison("谁更赚钱", [])
    assert _looks_like_comparison("A vs B", [])
    assert _looks_like_comparison("A VS B", [])
    # 弱词："和"但仅一家完整名称 → 不判比较（单公司字段列举）
    assert not _looks_like_comparison("康美药业营收和现金流怎么样", [_ref("康美药业")])
    # 弱词且两家完整名称 → 判比较
    assert _looks_like_comparison(
        "康美药业和贵州茅台的营收", [_ref("康美药业"), _ref("贵州茅台")]
    )
    # 无比较词
    assert not _looks_like_comparison("康美药业属于什么行业", [])
    # P1-1（第二轮审查修订）：强词不得误伤单公司内比较——
    # 行业比较/跨期比较/指标内比较均排除
    km_ref = _ref("康美药业")
    assert not _looks_like_comparison("康美药业与行业比较怎么样", [km_ref])
    assert not _looks_like_comparison("康美药业去年与今年营收差距", [km_ref])
    assert not _looks_like_comparison("康美药业各指标对比", [km_ref])
    assert not _looks_like_comparison("康美药业营收同比变化", [km_ref])
    # 强词 + 仅一家 + 无排除信号 → 第二实体可能在库外，仍判比较
    assert _looks_like_comparison("中芯国际和台积电的差距", [_ref("中芯国际")])


def test_weak_and_single_company_not_comparison(monkeypatch):
    """P1-1：'康美药业营收和现金流怎么样' → 不判比较，正常解析单公司。"""
    from app.agents.nodes import resolve_entity as node

    def fake_find(query):
        return _ref("康美药业") if "康美药业" in query else None

    def fake_candidates(query, limit=5):
        return [_ref("康美药业")]

    monkeypatch.setattr(node, "_find_company", fake_find)
    monkeypatch.setattr(node, "_find_company_candidates", fake_candidates)
    result = resolve_entity_node(_make_state("康美药业营收和现金流怎么样", None))
    assert result["company"] is not None
    assert result["company"].sec_name == "康美药业"
    assert not result.get("comparison_requested", False)


def test_weak_and_two_companies_comparison(monkeypatch):
    """P1-1：'康美药业和贵州茅台的营收'（两家完整名称）→ 判比较。"""
    from app.agents.nodes import resolve_entity as node

    def fake_candidates(query, limit=5):
        return [_ref("康美药业"), _ref("贵州茅台")]

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(node, "_find_company_candidates", fake_candidates)
    result = resolve_entity_node(_make_state("康美药业和贵州茅台的营收", None))
    assert result["comparison_requested"] is True
    assert result["company"] is None
    assert len(result["comparison_targets"]) == 2


def test_strong_comparison_with_single_candidate(monkeypatch):
    """P1-1：强词'差距' + 仅 1 家候选 → 仍判比较（触发'需两家'文案）。"""
    from app.agents.nodes import resolve_entity as node

    def fake_candidates(query, limit=5):
        return [_ref("中芯国际")]  # 台积电不在 A 股主表

    monkeypatch.setattr(node, "_find_company", lambda q: None)
    monkeypatch.setattr(node, "_find_company_candidates", fake_candidates)
    result = resolve_entity_node(_make_state("中芯国际和台积电的差距", None))
    assert result["comparison_requested"] is True
    assert len(result["comparison_targets"]) == 1


def test_second_entity_fragment_after_connector(monkeypatch):
    """P1-1（第三轮审查修订）：连接词后是第二实体片段（库外）→ 判比较。

    "中芯国际和台积电去年营收差距"：排除词"去年"出现在第二实体之后，
    不得仅因排除词吞掉真实跨公司问题。
    """
    from app.agents.nodes.resolve_entity import _looks_like_comparison

    zxgj = _ref("中芯国际", "688981.SH")
    # 连接词"和"之后是"台积电..."（非排除词开头）→ 第二实体 → 比较
    assert _looks_like_comparison("中芯国际和台积电去年营收差距", [zxgj]) is True
    # 连接词"与"之后是"今年..."（排除词开头）→ 单公司内比较
    assert (
        _looks_like_comparison("康美药业去年与今年营收差距", [_ref("康美药业")])
        is False
    )


def test_zero_candidates_with_industry_context_not_comparison():
    """P1-1（第三轮审查修订）：0 家候选 + 行业/指标语境 → 非跨公司。

    "白酒行业比较"是行业分析不是跨公司比较，不得进跨公司引导。"""
    from app.agents.nodes.resolve_entity import _looks_like_comparison

    assert _looks_like_comparison("白酒行业比较", []) is False
    assert _looks_like_comparison("医药行业对比", []) is False
    # 无排除词的 0 候选强词 → 仍判比较（比较引导）
    assert _looks_like_comparison("A公司对比B公司", []) is True


def test_company_name_internal_connector_not_misread():
    """P1-1（第四轮审查修订）：公司名称内部的"和"不得被当作连接词。

    "协和电子"名称含"和"——各指标对比/去年与今年营收差距均为单公司内比较，
    不得误判跨公司。"""
    from app.agents.nodes.resolve_entity import _looks_like_comparison

    xh = _ref("协和电子", "600071.SH")
    assert _looks_like_comparison("协和电子各指标对比", [xh]) is False
    assert _looks_like_comparison("协和电子去年与今年营收差距", [xh]) is False
    # 名称移除后仍能识别真实第二实体
    assert (
        _looks_like_comparison("协和电子和贵州茅台谁更赚钱", [xh, _ref("贵州茅台")])
        is True
    )
