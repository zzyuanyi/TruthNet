"""PatternMatch 节点（Phase D #11）单元测试.

覆盖：
- 复用 match_patterns：组合触发 → 匹配模式（含模式名/置信度/典型公司）
- 铁律反例：单规则触发 → 不输出模式
- 无 finance 结果 → 空匹配
- 康美/金牌家居典型组合（R1+R2+R4）→ 命中 ≥1 模式（P1/P4）
- pattern_match 接入 graph 后全链路 state 通过
"""

from app.agents.nodes.pattern_match import pattern_match_node
from app.agents.state import FinanceResult, ModuleResults


def _state(rule_statuses: dict[str, str], chains=None) -> dict:
    results = ModuleResults(
        finance=FinanceResult(rule_statuses=rule_statuses),
        equity=None,
    )
    state: dict = {
        "user_query": "测试",
        "results": results,
        "pattern_matches": [],
    }
    return state


def test_single_rule_no_pattern():
    """铁律反例：单条规则触发（仅 R1）→ 不得输出任何造假模式。"""
    out = pattern_match_node(_state({"R1": "triggered"}))
    assert out["pattern_matches"] == []


def test_combination_matches_pattern():
    """R1+R2 触发 → 匹配 P1 收入虚增型（含模式名/置信度/典型公司）。"""
    out = pattern_match_node(_state({"R1": "triggered", "R2": "triggered"}))
    matches = out["pattern_matches"]
    assert len(matches) >= 1
    p1 = next((m for m in matches if m["pattern_id"] == "P1"), None)
    assert p1 is not None, f"应匹配 P1，实际: {matches}"
    assert p1["pattern_name"] == "收入虚增型"
    assert p1["confidence"] in ("high", "medium")
    assert isinstance(p1["typical_companies"], list)


def test_kangmei_like_combination_matches():
    """康美/金牌家居典型组合（R1+R2+R4）→ 命中 ≥1 模式。"""
    out = pattern_match_node(
        _state({"R1": "triggered", "R2": "triggered", "R4": "triggered"})
    )
    assert len(out["pattern_matches"]) >= 1
    ids = {m["pattern_id"] for m in out["pattern_matches"]}
    assert "P1" in ids or "P4" in ids, f"应命中 P1/P4，实际: {ids}"


def test_no_finance_no_match():
    """无 finance 结果 → 空匹配（不抛错）。"""
    state = {"user_query": "测试", "results": ModuleResults(), "pattern_matches": []}
    out = pattern_match_node(state)
    assert out["pattern_matches"] == []


def test_required_output_fields():
    """输出字段齐全：pattern_id/名称/规则组合/置信度/典型公司。"""
    out = pattern_match_node(_state({"R1": "triggered", "R2": "triggered"}))
    for m in out["pattern_matches"]:
        for field in (
            "pattern_id",
            "pattern_name",
            "triggered_rules",
            "confidence",
            "reasoning",
            "typical_companies",
        ):
            assert field in m, f"缺少字段 {field}: {m}"


def test_pattern_match_in_graph():
    """pattern_match 接入 graph 后全链路可跑通（含 state 声明）。"""
    from langgraph.graph import END, StateGraph

    from app.agents.state import AgentState

    def _pass_through(state: dict) -> dict:
        # langgraph 0.2.x 要求节点至少更新一个 state key
        return {"user_query": state.get("user_query", "")}

    g = StateGraph(AgentState)
    g.add_node(
        "finance",
        lambda s: {
            "results": _state({"R1": "triggered", "R2": "triggered"})["results"]
        },
    )
    g.add_node("pattern_match", pattern_match_node)
    g.add_node("end", _pass_through)
    g.set_entry_point("finance")
    g.add_edge("finance", "pattern_match")
    g.add_edge("pattern_match", "end")
    g.add_edge("end", END)
    compiled = g.compile()

    result = compiled.invoke(
        {
            "user_query": "测试",
            "results": ModuleResults(),
            "pattern_matches": [],
        }
    )
    matches = result.get("pattern_matches", [])
    assert len(matches) >= 1, "graph 全链路应产出模式匹配"
    assert matches[0]["pattern_name"] in ("收入虚增型", "资产虚增型")
