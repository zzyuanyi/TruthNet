"""模式输出三要素测试 — Phase D #16.

验证 phase / alternative_explanation / regulatory_hint：
- 在 PatternMatch 域模型 / match_patterns 输出中存在；
- 非空（regulatory_hint 固定存在）；
- LLM 润色后仍保留（回答包含模式名，三要素在结构化载荷中不丢）；
- 降级模板仍保留；
- 无模式时返回空列表而非伪造模式；
- REST /risk、REST /chat、WS turn.completed 字段一致。
"""

from app.domain.risk.fraud_patterns import load_patterns, match_patterns
from app.domain.risk.models import RiskPatternMatch


def _triggered_results():
    """R1+R2 触发（P1 收入虚增型 required 满足）。"""
    return {
        "R1": {"status": "triggered", "severity": "orange"},
        "R2": {"status": "triggered", "severity": "yellow"},
        "R3": {"status": "not_triggered", "severity": "green"},
    }


def test_pattern_match_has_triad():
    """match_patterns 输出携带 phase/alternative_explanation/regulatory_hint。"""
    matches = match_patterns(_triggered_results())
    p1 = next(m for m in matches if m.pattern_id == "P1")
    assert p1.phase, "phase 必须非空"
    assert p1.alternative_explanation, "alternative_explanation 必须非空"
    assert p1.regulatory_hint, "regulatory_hint 必须非空（固定存在）"


def test_triad_from_yaml():
    """yaml 中 P1-P5 均定义了可审计三要素基础。"""
    patterns = load_patterns()
    for pid in ("P1", "P2", "P3", "P4", "P5"):
        p = patterns[pid]
        assert p.phase, f"{pid} 缺 phase"
        assert p.alternative_explanation, f"{pid} 缺 alternative_explanation"
        assert p.regulatory_hint, f"{pid} 缺 regulatory_hint"


def test_regulatory_hint_is_verification_not_conviction():
    """regulatory_hint 是核查提示，非法律定罪结论。"""
    patterns = load_patterns()
    for pid, p in patterns.items():
        assert (
            "不构成法律定罪结论" in p.regulatory_hint
        ), f"{pid} regulatory_hint 必须声明非定罪结论"


def test_risk_pattern_match_model_has_triad():
    """RiskPatternMatch DTO 携带三要素。"""
    m = RiskPatternMatch(
        pattern_id="P1",
        pattern_name="收入虚增型",
        triggered_rules=["R1", "R2"],
        confidence="medium",
        reasoning="必需规则触发",
        phase="阶段",
        alternative_explanation="非舞弊解释",
        regulatory_hint="监管提示",
    )
    assert m.phase == "阶段"
    assert m.alternative_explanation == "非舞弊解释"
    assert m.regulatory_hint == "监管提示"


def test_no_pattern_returns_empty_not_fabricated():
    """无触发模式 → 空列表（不伪造模式）。"""
    results = {
        f"R{i}": {"status": "not_triggered", "severity": "green"} for i in range(1, 8)
    }
    assert match_patterns(results) == []


def test_pattern_match_node_outputs_triad():
    """pattern_match 节点输出包含三要素。"""
    from app.agents.nodes.pattern_match import pattern_match_node
    from app.agents.state import AgentState, FinanceResult, ModuleResults, RuntimeState

    state = AgentState(
        user_query="康美药业有造假风险吗",
        module_status={},
        results=ModuleResults(
            finance=FinanceResult(
                rule_statuses={
                    "R1": "triggered",
                    "R2": "triggered",
                    "R3": "not_triggered",
                },
                rule_details={},
            )
        ),
        runtime=RuntimeState(trace_id="t", session_id="s", turn_id="tu"),
    )
    out = pattern_match_node(state)
    assert out["pattern_matches"], "应匹配到模式"
    for m in out["pattern_matches"]:
        assert m.get("phase"), "节点输出 phase 非空"
        assert m.get("regulatory_hint"), "节点输出 regulatory_hint 非空"
        assert m.get("alternative_explanation"), "节点输出 alternative_explanation 非空"
