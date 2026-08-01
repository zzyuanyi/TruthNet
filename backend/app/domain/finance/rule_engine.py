"""规则引擎主入口 — 统一调度 7 条规则."""

from app.domain.finance.models import RuleResult
from app.domain.finance.rule_r1 import evaluate_r1
from app.domain.finance.rule_r2 import evaluate_r2
from app.domain.finance.rule_r3 import evaluate_r3
from app.domain.finance.rule_r4 import evaluate_r4
from app.domain.finance.rule_r5 import evaluate_r5
from app.domain.finance.rule_r6 import evaluate_r6
from app.domain.finance.rule_r7 import evaluate_r7

_RULES = [
    ("R1", evaluate_r1),
    ("R2", evaluate_r2),
    ("R3", evaluate_r3),
    ("R4", evaluate_r4),
    ("R5", evaluate_r5),
    ("R6", evaluate_r6),
    ("R7", evaluate_r7),
]


def evaluate_all_rules(
    company_code: str, as_of: str = "20260331"
) -> dict[str, RuleResult]:
    """运行全部 7 条规则.

    Returns:
        {"R1": RuleResult, "R2": RuleResult, ...}
    """
    results: dict[str, RuleResult] = {}
    for rule_id, rule_func in _RULES:
        try:
            results[rule_id] = rule_func(company_code, as_of)
        except Exception as e:
            results[rule_id] = RuleResult(
                rule_id=rule_id,
                rule_version="1.0.0",
                status="insufficient_data",
                explanation=f"规则执行异常: {e}",
            )
    return results


def get_rule_statuses(company_code: str, as_of: str = "20260331") -> dict[str, str]:
    """获取 7 条规则的状态摘要（供 Agent 使用）."""
    results = evaluate_all_rules(company_code, as_of)
    return {rid: r.status for rid, r in results.items()}
