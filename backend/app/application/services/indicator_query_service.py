"""Deterministic financial indicator queries for short-form answers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.finance._fetch import SeriesResult, fetch_series


@dataclass(frozen=True)
class IndicatorObservation:
    field_path: str
    source_table: str
    value: float


@dataclass(frozen=True)
class IndicatorQueryResult:
    status: str
    indicator: str
    label: str
    period: str = ""
    value: float | None = None
    unit: str = ""
    observations: list[IndicatorObservation] = field(default_factory=list)


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
    """
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
    if require_exact_period:
        period = as_of if as_of in common_periods else ""
    else:
        period = max(common_periods, default="")
    if not period:
        return IndicatorQueryResult(
            status="insufficient_data", indicator=indicator, label=spec.label
        )

    observations = [
        IndicatorObservation(
            field_path=field_name,
            source_table=source_table,
            value=values_by_field[field_name][period],
        )
        for field_name, source_table in zip(spec.fields, spec.source_tables)
    ]
    if indicator == "debt_to_assets":
        liabilities, assets = (item.value for item in observations)
        if assets == 0:
            return IndicatorQueryResult(
                status="insufficient_data", indicator=indicator, label=spec.label
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
    )
