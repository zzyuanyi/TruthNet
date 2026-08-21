"""Deterministic financial indicator queries for short-form answers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.domain.finance._fetch import SeriesResult, fetch_series, prev_year_period
from app.domain.finance.rule_utils import yoy_growth


@dataclass(frozen=True)
class IndicatorObservation:
    field_path: str
    source_table: str
    value: float
    # 该 observation 所属报告期（2026-08-12 双期间契约：
    # 同比查询含当前期与去年同期两条，各自携带自己的 period）
    period: str = ""


@dataclass(frozen=True)
class IndicatorQueryResult:
    status: str
    indicator: str
    label: str
    period: str = ""
    value: float | None = None
    unit: str = ""
    observations: list[IndicatorObservation] = field(default_factory=list)
    # 对比基准期（同比查询：去年同期；非同比为空）
    comparison_period: str = ""
    # v3.3.3 收口批次 A（方案 §3.1/§3.3）：该指标在 as_of 之前
    # 全部可计算期间（升序），供「最新共同期间」取交集；
    # 单字段指标 = 有值期间，多字段 = 全字段完整且公式可算的期间
    available_periods: list[str] = field(default_factory=list)
    # 非致命警告（覆盖不足/目标期不可计算等），回答层可如实展示
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _IndicatorSpec:
    label: str
    fields: tuple[str, ...]
    source_tables: tuple[str, ...]
    unit: str


_INDICATORS: dict[str, _IndicatorSpec] = {
    "debt_to_assets": _IndicatorSpec(
        "资产负债率",
        ("tot_liab", "tot_assets"),
        ("balance_sheet", "balance_sheet"),
        "percent",
    ),
    "total_assets": _IndicatorSpec(
        "总资产", ("tot_assets",), ("balance_sheet",), "CNY"
    ),
    "total_liabilities": _IndicatorSpec(
        "总负债", ("tot_liab",), ("balance_sheet",), "CNY"
    ),
    "accounts_receivable": _IndicatorSpec(
        "应收账款余额", ("acct_rcv",), ("balance_sheet",), "CNY"
    ),
    "inventories": _IndicatorSpec("存货", ("inventories",), ("balance_sheet",), "CNY"),
    "operating_revenue": _IndicatorSpec(
        "营业收入", ("oper_rev",), ("income_statement",), "CNY"
    ),
    "net_profit": _IndicatorSpec(
        "净利润",
        ("net_profit_excl_min_int_inc",),
        ("income_statement",),
        "CNY",
    ),
    "operating_cash_flow": _IndicatorSpec(
        "经营现金流",
        ("net_cash_flows_oper_act",),
        ("cash_flow",),
        "CNY",
    ),
}


def _series_values(series: SeriesResult) -> dict[str, float]:
    return {
        str(period): float(value)
        for period, value in zip(series.periods, series.values)
        if value is not None
    }


def _inconsistent_annual_revenue(
    period: str, value: float, values: dict[str, float]
) -> bool:
    """年报营收远低于同年三季报，视为源数据占位值而非真实数值。"""
    if not period.endswith("1231"):
        return False
    q3_value = values.get(f"{period[:4]}0930")
    return q3_value is not None and q3_value > 0 and value < q3_value * 0.1


def query_indicator(
    company_code: str,
    indicator: str,
    *,
    as_of: str = "",
    require_exact_period: bool = False,
) -> IndicatorQueryResult:
    """Return one indicator from parent-company statements.

    ``require_exact_period`` is used for explicit report-period questions. For a
    general as-of date, the latest common period not later than ``as_of`` is used.

    2026-08-12 三轮审查修订：后缀路由——
      xxx_mom      → 环比（当前明确不支持，带正确 label 的 unsupported，
                     不返回裸 "unsupported" 以免 generate_answer 截获后
                     丢失指标名）；
      xxx_growth   → 严格同比（_query_yoy_growth，精确去年同期）。
    先识别基础指标再判断环比/同比——"康美环比怎么样"（无指标）不会
    被误判为指标短答。
    """
    if indicator.endswith("_mom"):
        base = indicator[: -len("_mom")]
        spec = _INDICATORS.get(base)
        return IndicatorQueryResult(
            status="unsupported",
            indicator=indicator,
            label=spec.label if spec else "该指标",
        )
    if indicator.endswith("_growth"):
        return _query_yoy_growth(
            company_code,
            indicator[: -len("_growth")],
            as_of=as_of,
            require_exact_period=require_exact_period,
        )
    spec = _INDICATORS.get(indicator)
    if spec is None:
        return IndicatorQueryResult(
            status="unsupported", indicator=indicator, label="该指标"
        )

    series_by_field = {
        name: fetch_series(company_code, name, periods=40, as_of=as_of)
        for name in spec.fields
    }
    values_by_field = {
        name: _series_values(series) for name, series in series_by_field.items()
    }
    common_periods = set.intersection(
        *(set(values) for values in values_by_field.values())
    )
    available = sorted(common_periods)
    if require_exact_period:
        period = as_of if as_of in common_periods else ""
    else:
        period = max(common_periods, default="")
    if not period:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=spec.label,
            period=as_of if require_exact_period else "",
            available_periods=available,
            warnings=(
                [f"目标期 {as_of} 无数据，可计算期: {available}"]
                if require_exact_period
                else []
            ),
        )

    # 上市公司年度营业收入为 0 通常是测试库占位值或缺失映射；
    # 不把它展示成真实的“0.00 元”。
    if (
        indicator == "operating_revenue"
        and values_by_field[spec.fields[0]][period] == 0
    ):
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=spec.label,
            period=period,
            available_periods=available,
            warnings=["营业收入为零，未作为有效财务数据输出"],
        )

    if indicator == "operating_revenue" and _inconsistent_annual_revenue(
        period, values_by_field[spec.fields[0]][period], values_by_field[spec.fields[0]]
    ):
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=spec.label,
            period=period,
            available_periods=available,
            warnings=["年报营业收入与同年三季报不一致，未采用该值"],
        )

    observations = [
        IndicatorObservation(
            field_path=field_name,
            source_table=source_table,
            value=values_by_field[field_name][period],
            period=period,
        )
        for field_name, source_table in zip(spec.fields, spec.source_tables)
    ]
    if indicator == "debt_to_assets":
        liabilities, assets = (item.value for item in observations)
        if assets == 0:
            return IndicatorQueryResult(
                status="insufficient_data",
                indicator=indicator,
                label=spec.label,
                available_periods=available,
            )
        value = liabilities / assets * 100
    else:
        value = observations[0].value

    return IndicatorQueryResult(
        status="ok",
        indicator=indicator,
        label=spec.label,
        period=period,
        value=value,
        unit=spec.unit,
        observations=observations,
        available_periods=available,
    )


def _query_yoy_growth(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
    require_exact_period: bool = False,
) -> IndicatorQueryResult:
    """严格同比查询（2026-08-12 三轮审查修订）。

    利润表/现金流量表为年内累计值——增速必须精确同比：
    prev_year_period 取去年同期（YYYY-1+相同 MMDD），缺失返回 None
    （不回退两年前）；yoy_growth 分母绝对值 <1 万返回 None。
    禁用相邻期相除。

    仅单字段指标支持（营收/净利润/现金流/存货/应收/总资产/总负债）；
    双字段指标（debt_to_assets）→ unsupported。
    """
    indicator = f"{base_indicator}_growth"
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return IndicatorQueryResult(
            status="unsupported",
            indicator=indicator,
            label=spec.label if spec else "该指标",
        )

    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    values = _series_values(series)
    ordered = sorted(values)
    # v3.3.3 收口批次 A：可计算期间 = 有当前值且存在精确去年同期的期间
    available = sorted(p for p in ordered if prev_year_period(p, ordered) in values)
    if not values:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=f"{spec.label}同比增速",
        )
    if require_exact_period:
        current_period = as_of if as_of in values else ""
    else:
        current_period = max(values)
    if not current_period:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=f"{spec.label}同比增速",
            period=as_of if require_exact_period else "",
            available_periods=available,
        )

    prev_period = prev_year_period(current_period, ordered)
    if prev_period is None or values.get(prev_period) is None:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=f"{spec.label}同比增速",
            available_periods=available,
        )

    growth = yoy_growth(values[current_period], values[prev_period])
    if growth is None:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=indicator,
            label=f"{spec.label}同比增速",
            available_periods=available,
        )

    return IndicatorQueryResult(
        status="ok",
        indicator=indicator,
        label=f"{spec.label}同比增速",
        period=current_period,
        value=growth * 100,  # yoy_growth 返回小数，转百分比
        unit="percent",
        observations=[
            IndicatorObservation(
                field_path=spec.fields[0],
                source_table=spec.source_tables[0],
                value=values[current_period],
                period=current_period,
            ),
            IndicatorObservation(
                field_path=spec.fields[0],
                source_table=spec.source_tables[0],
                value=values[prev_period],
                period=prev_period,
            ),
        ],
        comparison_period=prev_period,
        available_periods=available,
    )


def query_indicator_cagr(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
    years: int = 3,
) -> IndicatorQueryResult:
    """按年度报表计算 CAGR，缺少完整起止年度时不回退到单期。"""
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return IndicatorQueryResult(
            status="unsupported", indicator=f"{base_indicator}_cagr", label="复合增长率"
        )
    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    values = _series_values(series)
    annual = {
        str(period): float(value)
        for period, value in zip(series.periods, series.values)
        if value is not None and str(period).endswith("1231")
    }
    # 年报与同年三季报相差两个数量级时，通常是源数据口径/单位异常。
    # 这种值不能继续参与 CAGR，否则会把脏数据包装成精确百分比。
    for period in list(annual):
        if _inconsistent_annual_revenue(period, annual[period], values):
            annual.pop(period)
    periods = sorted(annual)
    if len(periods) < years or years < 2:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=f"{base_indicator}_cagr",
            label=f"{spec.label}复合增长率",
            available_periods=periods,
        )
    start_period, end_period = periods[-years], periods[-1]
    start_value, end_value = annual[start_period], annual[end_period]
    if start_value <= 0 or end_value < 0:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=f"{base_indicator}_cagr",
            label=f"{spec.label}复合增长率",
            available_periods=periods,
        )
    value = ((end_value / start_value) ** (1 / (years - 1)) - 1) * 100
    return IndicatorQueryResult(
        status="ok",
        indicator=f"{base_indicator}_cagr",
        label=f"{spec.label}复合增长率",
        period=end_period,
        value=value,
        unit="percent",
        observations=[
            IndicatorObservation(
                spec.fields[0], spec.source_tables[0], start_value, start_period
            ),
            IndicatorObservation(
                spec.fields[0], spec.source_tables[0], end_value, end_period
            ),
        ],
        available_periods=periods,
    )


def query_indicator_trend(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
    periods: int = 5,
    annual_only: bool = True,
) -> list[IndicatorObservation]:
    """返回最近年度序列，供趋势/连续变化问法使用。"""
    from app.domain.benchmarks.metric_registry import REGISTRY

    if base_indicator in REGISTRY:
        return query_registry_metric_trend(
            company_code,
            base_indicator,
            as_of=as_of,
            periods=periods,
            annual_only=annual_only,
        )
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return []
    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    rows = [
        IndicatorObservation(
            spec.fields[0], spec.source_tables[0], float(value), str(period)
        )
        for period, value in zip(series.periods, series.values)
        if value is not None and (not annual_only or str(period).endswith("1231"))
    ]
    return rows[-periods:]


def query_registry_metric_trend(
    company_code: str,
    metric_id: str,
    *,
    as_of: str = "",
    periods: int = 5,
    annual_only: bool = True,
) -> list[IndicatorObservation]:
    """按报告期逐期计算注册指标的趋势序列。"""
    from app.domain.benchmarks.metric_evaluator import evaluate_metric_per_period
    from app.domain.benchmarks.metric_registry import get_metric

    try:
        metric = get_metric(metric_id)
    except KeyError:
        return []

    fetch_periods = max(40, periods + metric.periods + 4)
    sequences: dict[str, list[tuple[str, float | None]]] = {}
    for field_name in metric.fields:
        series = fetch_series(
            company_code, field_name, periods=fetch_periods, as_of=as_of
        )
        sequences[field_name] = [
            (str(period), value) for period, value in zip(series.periods, series.values)
        ]

    rows = evaluate_metric_per_period(metric, sequences)
    if annual_only:
        rows = [(period, value) for period, value in rows if period.endswith("1231")]
    return [
        IndicatorObservation(metric_id, "metric_registry", float(value), period)
        for period, value in rows[-periods:]
    ]


def query_quarter_value(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
) -> IndicatorQueryResult:
    """将年内累计基础指标还原为最近单季度值。"""
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return IndicatorQueryResult(
            status="unsupported",
            indicator=f"{base_indicator}_quarter",
            label="单季度指标",
        )
    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    values = {
        str(period): float(value)
        for period, value in zip(series.periods, series.values)
        if value is not None
    }

    def quarter_value(period: str) -> float | None:
        if len(period) != 8 or period[4:] not in ("0331", "0630", "0930", "1231"):
            return None
        if period[4:] == "0331":
            return values.get(period)
        previous = {
            "0630": "0331",
            "0930": "0630",
            "1231": "0930",
        }[period[4:]]
        current = values.get(period)
        prior = values.get(period[:4] + previous)
        return current - prior if current is not None and prior is not None else None

    candidates = sorted(p for p in values if quarter_value(p) is not None)
    target = as_of if as_of in candidates else (candidates[-1] if candidates else "")
    value = quarter_value(target) if target else None
    if value is None:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=f"{base_indicator}_quarter",
            label=f"单季度{spec.label}",
            period=target,
            available_periods=candidates,
        )
    return IndicatorQueryResult(
        status="ok",
        indicator=f"{base_indicator}_quarter",
        label=f"单季度{spec.label}",
        period=target,
        value=value,
        unit=spec.unit,
        observations=[
            IndicatorObservation(spec.fields[0], spec.source_tables[0], value, target)
        ],
        available_periods=candidates,
    )


def query_quarter_yoy(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
) -> IndicatorQueryResult:
    """将年内累计报表还原为单季度值后计算同比。"""
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return IndicatorQueryResult(
            status="unsupported",
            indicator=f"{base_indicator}_quarter_growth",
            label="单季度同比",
        )
    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    values = {
        str(p): float(v) for p, v in zip(series.periods, series.values) if v is not None
    }

    def quarter_value(period: str) -> float | None:
        if len(period) != 8 or period[4:] not in ("0331", "0630", "0930", "1231"):
            return None
        if period[4:] == "0331":
            return values.get(period)
        previous = {
            "0630": "0331",
            "0930": "0630",
            "1231": "0930",
        }[period[4:]]
        prior_period = period[:4] + previous
        current, prior = values.get(period), values.get(prior_period)
        return current - prior if current is not None and prior is not None else None

    candidates = sorted(p for p in values if quarter_value(p) is not None)
    target = as_of if as_of in candidates else (candidates[-1] if candidates else "")
    previous_year = f"{int(target[:4]) - 1}{target[4:]}" if target else ""
    current_value = quarter_value(target) if target else None
    previous_value = quarter_value(previous_year) if previous_year else None
    growth = (
        yoy_growth(current_value, previous_value)
        if current_value is not None and previous_value is not None
        else None
    )
    if growth is None:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=f"{base_indicator}_quarter_growth",
            label=f"单季度{spec.label}同比增速",
            period=target,
            available_periods=candidates,
        )
    return IndicatorQueryResult(
        status="ok",
        indicator=f"{base_indicator}_quarter_growth",
        label=f"单季度{spec.label}同比增速",
        period=target,
        value=growth * 100,
        unit="percent",
        observations=[
            IndicatorObservation(
                spec.fields[0], spec.source_tables[0], current_value, target
            ),
            IndicatorObservation(
                spec.fields[0], spec.source_tables[0], previous_value, previous_year
            ),
        ],
        comparison_period=previous_year,
        available_periods=candidates,
    )


def query_quarter_mom(
    company_code: str,
    base_indicator: str,
    *,
    as_of: str = "",
) -> IndicatorQueryResult:
    """将年内累计报表还原为单季度值后计算环比。"""
    spec = _INDICATORS.get(base_indicator)
    if spec is None or len(spec.fields) != 1:
        return IndicatorQueryResult(
            status="unsupported",
            indicator=f"{base_indicator}_quarter_mom",
            label="单季度环比增长率",
        )
    series = fetch_series(company_code, spec.fields[0], periods=40, as_of=as_of)
    values = {
        str(period): float(value)
        for period, value in zip(series.periods, series.values)
        if value is not None
    }

    def quarter_value(period: str) -> float | None:
        if len(period) != 8 or period[4:] not in ("0331", "0630", "0930", "1231"):
            return None
        if period[4:] == "0331":
            return values.get(period)
        previous = {"0630": "0331", "0930": "0630", "1231": "0930"}[period[4:]]
        current = values.get(period)
        prior = values.get(period[:4] + previous)
        return current - prior if current is not None and prior is not None else None

    def previous_quarter(period: str) -> str:
        previous = {
            "0331": (str(int(period[:4]) - 1), "1231"),
            "0630": (period[:4], "0331"),
            "0930": (period[:4], "0630"),
            "1231": (period[:4], "0930"),
        }.get(period[4:])
        return "" if previous is None else "".join(previous)

    candidates = sorted(p for p in values if quarter_value(p) is not None)
    target = as_of if as_of in candidates else (candidates[-1] if candidates else "")
    comparison_period = previous_quarter(target) if target else ""
    current_value = quarter_value(target) if target else None
    previous_value = quarter_value(comparison_period) if comparison_period else None
    growth = (
        yoy_growth(current_value, previous_value)
        if current_value is not None and previous_value is not None
        else None
    )
    if growth is None:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=f"{base_indicator}_quarter_mom",
            label=f"单季度{spec.label}环比增长率",
            period=target,
            comparison_period=comparison_period,
            available_periods=candidates,
        )
    return IndicatorQueryResult(
        status="ok",
        indicator=f"{base_indicator}_quarter_mom",
        label=f"单季度{spec.label}环比增长率",
        period=target,
        value=growth * 100,
        unit="percent",
        observations=[
            IndicatorObservation(
                spec.fields[0], spec.source_tables[0], current_value, target
            ),
            IndicatorObservation(
                spec.fields[0],
                spec.source_tables[0],
                previous_value,
                comparison_period,
            ),
        ],
        comparison_period=comparison_period,
        available_periods=candidates,
    )


def query_registry_metric(
    company_code: str,
    metric_id: str,
    *,
    as_of: str = "",
    require_exact_period: bool = False,
) -> IndicatorQueryResult:
    """按 canonical metric ID 查询 metric_registry 指标。

    v3.3.3 收口批次 A（方案 §2.1/§2.2/§3.1）重构：
      - 只调用 registry 公式（compute_from_aligned 优先，不复制公式）；
      - 经 metric_evaluator 按报告期对齐逐期计算（错期 P0 修复）；
      - require_exact_period=True 时目标期必须精确可计算，不 fallback；
      - available_periods 暴露全部可计算期间（共同期间交集用）；
      - 结果期 observations 只含目标期字段值（期间一致契约）。
    """
    from app.domain.benchmarks.metric_evaluator import evaluate_metric_per_period
    from app.domain.benchmarks.metric_registry import get_metric
    from app.domain.finance.field_mapping import get_table

    try:
        metric = get_metric(metric_id)
    except KeyError:
        return IndicatorQueryResult(
            status="unsupported", indicator=metric_id, label="该指标"
        )

    sequences: dict[str, list[tuple[str, float | None]]] = {}
    for field_name in metric.fields:
        series = fetch_series(
            company_code, field_name, periods=metric.periods + 4, as_of=as_of
        )
        sequences[field_name] = sorted(
            ((str(p), v) for p, v in zip(series.periods, series.values)),
            key=lambda item: item[0],
        )

    evaluable = evaluate_metric_per_period(metric, sequences)
    available_periods = [p for p, _ in evaluable]
    if not evaluable:
        return IndicatorQueryResult(
            status="insufficient_data",
            indicator=metric_id,
            label=metric.name,
            available_periods=[],
        )

    if require_exact_period:
        hit = next(((p, v) for p, v in evaluable if p == as_of), None)
        if hit is None:
            # 显式期不 fallback（方案 §2.2）
            return IndicatorQueryResult(
                status="insufficient_data",
                indicator=metric_id,
                label=metric.name,
                period=as_of,
                available_periods=available_periods,
                warnings=[f"目标期 {as_of} 不可计算，可计算期: {available_periods}"],
            )
        period, value = hit
    else:
        period, value = max(evaluable)

    # 单位标准化：registry ratio（小数）→ percent（百分比）
    display_value = value
    unit = metric.unit
    if metric.unit == "ratio":
        display_value = round(value * 100, 4)
        unit = "percent"

    # 结果期 observations：只列目标期字段值（方案 §2.1 期间一致契约）
    observations: list[IndicatorObservation] = []
    for field_name in metric.fields:
        field_map = {p: v for p, v in sequences[field_name]}
        obs_value = field_map.get(period)
        if obs_value is None:
            continue
        observations.append(
            IndicatorObservation(
                field_path=field_name,
                source_table=get_table(field_name),
                value=float(obs_value),
                period=period,
            )
        )

    return IndicatorQueryResult(
        status="ok",
        indicator=metric_id,
        label=metric.name,
        period=period,
        value=display_value,
        unit=unit,
        observations=observations,
        available_periods=available_periods,
    )


def supported_indicator_ids() -> frozenset[str]:
    """返回 query_metric 支持的 canonical ID 全集（v3.3.4 概览 profile 校验）。

    = metric_registry 全部注册 ID ∪ 基础指标 ID ∪ 单字段基础指标的
    `{base}_growth` 同比 ID。概览固定 profile 只允许取自该集合，
    不允许复制新公式。
    """
    from app.domain.benchmarks.metric_registry import REGISTRY

    ids = set(REGISTRY)
    for base, spec in _INDICATORS.items():
        ids.add(base)
        if len(spec.fields) == 1:
            ids.add(f"{base}_growth")
    return frozenset(ids)


def query_metric(
    company_code: str,
    indicator: str,
    *,
    as_of: str = "",
    require_exact_period: bool = False,
) -> IndicatorQueryResult:
    """v3.3.3 批次 B：指标短答统一入口。

    registry 指标（r4_turnover_days / r5_gross_margin 等）走
    query_registry_metric，其余走基础指标 query_indicator；
    返回统一 IndicatorQueryResult。
    """
    from app.domain.benchmarks.metric_registry import REGISTRY

    if indicator in REGISTRY:
        return query_registry_metric(
            company_code,
            indicator,
            as_of=as_of,
            require_exact_period=require_exact_period,
        )
    return query_indicator(
        company_code,
        indicator,
        as_of=as_of,
        require_exact_period=require_exact_period,
    )


def _company_engine():
    """8/19 全面审查：改用公共工厂（完整 profile key + 缓存 + 切库 dispose）。

    原实现每次调用新建 Engine（连接池不复用、切库后残留旧连接）。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def query_industry_benchmark(
    industry_l1: str, metric_id: str, period: str
) -> dict | None:
    """v3.3.3 收口批次 D（方案 §3.6）：查询离线行业基准行。

    返回 {sample_count, mean_value, p25, p50, p75, p95}；无匹配返回 None。
    口径：statement_scope=parent_company、dataset_version 当前配置。
    """
    from sqlalchemy import text

    if not industry_l1 or not metric_id or not period:
        return None
    try:
        with _company_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT sample_count, mean_value, p25, p50, p75, p95 "
                        "FROM industry_benchmarks "
                        "WHERE industry_l1 = :ind AND metric_id = :mid "
                        "AND period = :p "
                        "AND statement_scope = 'parent_company' "
                        "AND dataset_version = :dv LIMIT 1"
                    ),
                    {
                        "ind": industry_l1,
                        "mid": metric_id,
                        "p": period,
                        "dv": settings.DATASET_VERSION,
                    },
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return {
            k: row[k]
            for k in ("sample_count", "mean_value", "p25", "p50", "p75", "p95")
        }
    except Exception:  # noqa: BLE001 — 基准查询失败按「无基准」处理
        return None


def query_industry_benchmark_series(
    industry_l1: str, metric_id: str, *, as_of: str = ""
) -> list[dict]:
    """读取行业基准时间序列，供行业均值/变化问法使用。"""
    from sqlalchemy import text

    if not industry_l1 or not metric_id:
        return []
    clause = " AND period <= :as_of" if as_of else ""
    try:
        with _company_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT period, sample_count, mean_value, p25, p50, p75 "
                        "FROM industry_benchmarks "
                        "WHERE industry_l1 = :ind AND metric_id = :mid "
                        "AND statement_scope = 'parent_company' "
                        "AND dataset_version = :dv" + clause + " ORDER BY period"
                    ),
                    {
                        "ind": industry_l1,
                        "mid": metric_id,
                        "dv": settings.DATASET_VERSION,
                        "as_of": as_of,
                    },
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]
    except Exception:  # noqa: BLE001 — 行业基准缺失按空结果处理
        return []


def query_latest_risk_assessment(wind_code: str) -> dict | None:
    """v3.3.3 收口批次 D（方案 §3.7）：查询公司最新一条风险评估记录。

    返回 {level, overall_score, rule_version, dataset_version, assessed_at}；
    无记录返回 None。等级仅用于排序展示，不换算成差值分数。
    """
    from sqlalchemy import text

    if not wind_code:
        return None
    try:
        with _company_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT level, overall_score, rule_version, "
                        "dataset_version, assessed_at FROM risk_assessments "
                        "WHERE wind_code = :c ORDER BY assessed_at DESC LIMIT 1"
                    ),
                    {"c": wind_code},
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return {
            "level": str(row["level"] or ""),
            "overall_score": row["overall_score"],
            "rule_version": str(row["rule_version"] or ""),
            "dataset_version": str(row["dataset_version"] or ""),
            "assessed_at": str(row["assessed_at"] or ""),
        }
    except Exception:  # noqa: BLE001 — 查询失败按无记录处理（partial）
        return None
