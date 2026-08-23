"""财务规则的结构化可复算血缘工具。"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.finance.field_mapping import get_table
from app.domain.finance.models import CalculationInput, CalculationTrace, RuleResult


def calculation_input(
    field_path: str,
    period: str,
    value: float | str | None,
    *,
    role: str,
    unit: str = "元",
) -> CalculationInput | None:
    """从规则已读取的数据构建输入；缺失值不伪造成零。"""
    if value is None:
        return None
    return CalculationInput(
        source_table=get_table(field_path),
        field_path=field_path,
        period=str(period),
        value=value,
        unit=unit,
        role=role,
    )


def attach_calculation_trace(
    result: RuleResult,
    *,
    formula: str,
    inputs: Iterable[CalculationInput | None],
) -> None:
    """把计算时的原值挂回 RuleResult，禁止完成计算后再次查询数据库。"""
    result.calculation_trace = CalculationTrace(
        formula_id=result.rule_id,
        formula=formula,
        calculation_version=result.rule_version,
        inputs=[item for item in inputs if item is not None],
    )


def inputs_from_aligned(
    aligned: dict[str, dict[str, float | None]],
    field_map: dict[str, str],
    *,
    periods: Iterable[str] | None = None,
) -> list[CalculationInput]:
    """把规则使用的对齐矩阵转换为逐字段、逐期原始输入。"""
    selected = list(periods) if periods is not None else sorted(aligned)
    inputs: list[CalculationInput] = []
    for period in selected:
        row = aligned.get(period, {})
        for alias, field_path in field_map.items():
            item = calculation_input(
                field_path,
                period,
                row.get(alias),
                role=f"{alias}@{period}",
            )
            if item is not None:
                inputs.append(item)
    return inputs
