"""ResolveEntity 节点测试 — 主语省略延续与指代消解接入."""

from app.agents.nodes.resolve_entity import resolve_entity_node
from app.agents.state import AgentState, MemoryContext, RuntimeState


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
