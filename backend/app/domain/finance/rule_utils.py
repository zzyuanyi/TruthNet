"""规则计算公共工具函数 — RULES_SPEC §1.2."""


def yoy_growth(current: float | None, base: float | None) -> float | None:
    """同比增长率 — RULES_SPEC §1.2.

    yoy_growth(t) = (value(t) - value(t-4Q)) / |value(t-4Q)|

    若分母为 0/NULL 或绝对值 < 1 万元 → 返回 None（标记 insufficient_data）。
    """
    if current is None or base is None:
        return None
    if abs(base) < 10_000:  # 1 万元分母保护
        return None
    return (current - base) / abs(base)


def single_quarter(cumulative_values: list) -> list:
    """将累计值还原为单季度值.

    利润表/现金流量表科目为累计值（Q1=1-3月, Q2=1-6月, Q3=1-9月, Q4=1-12月）。
    还原逻辑: single_quarter(t) = cumulative(t) - cumulative(t-1Q)，Q1 直接取。
    """
    if len(cumulative_values) < 2:
        return [v for v in cumulative_values]
    result = [cumulative_values[0]]
    for i in range(1, len(cumulative_values)):
        if cumulative_values[i] is not None and cumulative_values[i - 1] is not None:
            result.append(cumulative_values[i] - cumulative_values[i - 1])
        else:
            result.append(None)
    return result


def safe_div(a: float | None, b: float | None) -> float | None:
    """安全除法."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def count_valid(values: list, lookback: int = 4) -> int:
    """统计最近 lookback 期内非 None 的期数."""
    return sum(1 for v in values[-lookback:] if v is not None)


def mean_or_none(values: list) -> float | None:
    """计算均值，全部为 None 则返回 None."""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None
