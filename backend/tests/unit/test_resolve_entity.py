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
