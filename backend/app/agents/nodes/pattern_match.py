"""PatternMatch — Phase D #11 造假模式识别运行时衔接.

复用 domain/risk/fraud_patterns.py 的 match_patterns（只读，禁止修改），
从 finance 模块的有效规则触发状态匹配手法库模式（P1-P5）。

输入：finance 的 rule_statuses（公司类型 Gate 过滤后的有效触发状态）
输出（写回 state["pattern_matches"]）：
  pattern_id / pattern_name / triggered_rules / confidence /
  reasoning / typical_companies / partial_coverage

铁律：单条规则触发不得声称造假模式——match_patterns 的模式定义
（如 P1 需 R1+R2）已保证此语义，节点不得绕过。
"""

import logging

from app.agents.state import AgentState
from app.domain.risk.fraud_patterns import load_patterns, match_patterns

logger = logging.getLogger(__name__)


def _to_match_input(rule_statuses: dict[str, str]) -> dict[str, dict]:
    """rule_statuses → match_patterns 输入格式 {rule_id: {"status": ...}}."""
    return {rid: {"status": st} for rid, st in rule_statuses.items()}


def _has_related_party_signal(state: AgentState) -> bool:
    """P2 high 判定：股权模块是否产出控制链（关联方信号）。"""
    results = state.get("results")
    if results is not None and getattr(results, "equity", None) is not None:
        return bool(getattr(results.equity, "chains", None))
    return False


def pattern_match_node(state: AgentState) -> dict:
    """造假模式匹配节点：只读复用 match_patterns，结果写回 state."""
    results = state.get("results")
    if (
        results is None
        or getattr(results, "finance", None) is None
        or not results.finance.rule_statuses
    ):
        return {"pattern_matches": []}

    match_input = _to_match_input(results.finance.rule_statuses)
    try:
        matches = match_patterns(
            match_input,
            has_related_party=_has_related_party_signal(state),
        )
    except Exception:  # noqa: BLE001 — 模式匹配失败不阻塞主流程
        logger.warning(
            "pattern_match: match_patterns 异常，跳过模式识别", exc_info=True
        )
        return {"pattern_matches": []}

    patterns = load_patterns()
    out: list[dict] = []
    for m in matches:
        out.append(
            {
                "pattern_id": m.pattern_id,
                "pattern_name": m.pattern_name,
                "triggered_rules": m.triggered_rules,
                "confidence": m.confidence,
                "reasoning": m.reasoning,
                "typical_companies": patterns.get(m.pattern_id).typical_companies
                if m.pattern_id in patterns
                else [],
                "partial_coverage": m.partial_coverage,
                # Phase D #16 模式三要素（受控透出，REST/WS/Agent 一致）
                "phase": m.phase,
                "alternative_explanation": m.alternative_explanation,
                "regulatory_hint": m.regulatory_hint,
            }
        )
    return {"pattern_matches": out}
