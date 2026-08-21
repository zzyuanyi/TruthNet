"""规则计算公共工具函数 — RULES_SPEC §1.2."""


def fmt_period(period: str | None) -> str:
    """YYYYMMDD → YYYY-MM-DD；非 8 位原样返回（用户可读期次）。"""
    p = str(period or "")
    if len(p) == 8 and p.isdigit():
        return f"{p[:4]}-{p[4:6]}-{p[6:]}"
    return p


def fmt_pct(value: float | None, digits: int = 1) -> str:
    """百分比格式化（无 None 保护：调用方保证非 None）。"""
    return f"{float(value):.{digits}f}%"


def fmt_gap_pct(value: float | None, digits: int = 1) -> str:
    """增速差格式化：按演示口径用百分号表达（不再输出 pp）。"""
    return f"{float(value):.{digits}f}%"


def fmt_yi(value: float | None, digits: int = 1) -> str:
    """元 → 亿元。"""
    return f"{float(value or 0) / 1e8:.{digits}f}"


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


def previous_quarter_period(period: str | None) -> str | None:
    """返回同一财年的上一季度报告期；Q1 没有上一季度累计可减。"""
    p = str(period or "")
    if len(p) != 8 or not p.isdigit():
        return None
    year = p[:4]
    mmdd = p[4:]
    previous = {
        "0630": "0331",
        "0930": "0630",
        "1231": "0930",
    }.get(mmdd)
    return f"{year}{previous}" if previous else None


def single_quarter_by_period(cumulative_values: list, periods: list) -> list:
    """按报告期还原单季度值，缺相邻季度时返回 None。

    与 single_quarter(list) 的兼容实现不同，这里不会把数组里的上一条记录
    当成上一季度，避免缺期或错期时盲目相减。
    """
    value_by_period = {
        str(p): v for p, v in zip(periods, cumulative_values, strict=False)
    }
    result: list = []
    for period, current in zip(periods, cumulative_values, strict=False):
        p = str(period or "")
        if current is None:
            result.append(None)
            continue
        if p.endswith("0331"):
            result.append(current)
            continue
        previous_period = previous_quarter_period(p)
        previous = value_by_period.get(previous_period) if previous_period else None
        result.append(current - previous if previous is not None else None)
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
