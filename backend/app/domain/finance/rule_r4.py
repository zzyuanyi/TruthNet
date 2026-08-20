"""R4 · 存货–营收背离 — RULES_SPEC §5.

口径: 固定母公司报表（statement_type=408006000），不读取合并报表。
公司类型: 统一走 check_company_type Gate（NULL/非法 → insufficient_data）。
所有状态均携带母公司口径 quality。
"""

from app.domain.finance._fetch import align_by_period, fetch_series, prev_year_period
from app.domain.finance.financial_rule_config import (
    get_execution_version,
    disabled_rule_result,
    get_rule_config,
)
from app.domain.finance.models import RuleResult
from app.domain.finance.parent_scope import (
    build_gate_result,
    build_parent_scope_quality,
    check_company_type,
)
from app.domain.finance.rule_utils import (
    count_valid,
    fmt_gap_pct,
    fmt_period,
    previous_quarter_period,
    single_quarter_by_period,
    yoy_growth,
)


def evaluate_r4(company_code: str, as_of: str = "20260331", periods: int = 8):
    config = get_rule_config("R4")
    if not config.enabled:
        return disabled_rule_result("R4", "存货–营收背离")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R4",
        rule_version=get_execution_version(),
        rule_name="存货–营收背离",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R4", "存货–营收背离", gate)

    inventories_sr = fetch_series(company_code, "inventories", periods, as_of)
    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    less_oper_cost_sr = fetch_series(company_code, "less_oper_cost", periods, as_of)
    inventories = inventories_sr.values
    oper_rev = oper_rev_sr.values
    less_oper_cost = less_oper_cost_sr.values

    field_warnings = [
        w
        for w in (
            inventories_sr.warning,
            oper_rev_sr.warning,
            less_oper_cost_sr.warning,
        )
        if w
    ]

    valid_inv = count_valid(inventories, 4)
    valid_or = count_valid(oper_rev, 4)
    if valid_inv < 3 or valid_or < 3:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: inventory有效{valid_inv}期, oper_rev有效{valid_or}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=inventories_sr.coverage,
            data_completeness=round(valid_inv / 4, 2),
            missing_periods=4 - valid_inv,
        )
        result.warnings = field_warnings
        return result

    aligned = align_by_period(inv=inventories_sr, or_=oper_rev_sr, cost=less_oper_cost_sr)
    ordered = sorted(aligned.keys())
    current_period = None
    prior_year_period = None
    for period in reversed(ordered):
        candidate_prior = prev_year_period(period, ordered)
        if candidate_prior is None:
            continue
        row = aligned[period]
        prior_row = aligned[candidate_prior]
        if (
            row.get("inv") is not None
            and row.get("or_") is not None
            and prior_row.get("inv") is not None
            and prior_row.get("or_") is not None
        ):
            current_period = period
            prior_year_period = candidate_prior
            break
    if current_period is None or prior_year_period is None:
        result.status = "insufficient_data"
        result.explanation = "缺少可精确对齐的当期与去年同期存货/营收数据"
        result.quality = build_parent_scope_quality(
            coverage=inventories_sr.coverage,
            data_completeness=round(valid_inv / 4, 2),
            missing_periods=4 - valid_inv,
        )
        result.warnings = field_warnings
        return result

    current_row = aligned[current_period]
    prior_year_row = aligned[prior_year_period]
    inv_yoy = yoy_growth(current_row.get("inv"), prior_year_row.get("inv"))
    or_yoy = yoy_growth(current_row.get("or_"), prior_year_row.get("or_"))
    if inv_yoy is None or or_yoy is None:
        result.status = "insufficient_data"
        result.explanation = "分母保护触发，无法计算 YoY"
        result.quality = build_parent_scope_quality(
            coverage=inventories_sr.coverage,
            data_completeness=round(valid_inv / 4, 2),
            missing_periods=4 - valid_inv,
        )
        result.warnings = field_warnings
        return result

    growth_gap = (inv_yoy - or_yoy) * 100

    # 周转天数（累计值还原单季度 → 年化）
    cost_valid = count_valid(less_oper_cost, 4)
    turnover_ok = cost_valid >= 3
    turnover_change = None
    inv_turnover_days = None

    if turnover_ok:
        cost_values = [aligned[p].get("cost") for p in ordered]
        sq_cost_by_period = dict(
            zip(ordered, single_quarter_by_period(cost_values, ordered), strict=False)
        )

        def _turnover_days_for(period: str) -> float | None:
            sq_cost = sq_cost_by_period.get(period)
            if sq_cost is None or sq_cost <= 0:
                return None
            previous_period = previous_quarter_period(period)
            if previous_period is None:
                return None
            current_inv = aligned.get(period, {}).get("inv")
            previous_inv = aligned.get(previous_period, {}).get("inv")
            if current_inv is None or previous_inv is None:
                return None
            annualized_cost = sq_cost * 4
            avg_inv = (current_inv + previous_inv) / 2
            return avg_inv / annualized_cost * 365 if annualized_cost > 0 else None

        inv_turnover_days = _turnover_days_for(current_period)
        days_t4 = _turnover_days_for(prior_year_period)
        if inv_turnover_days is not None and days_t4 is not None and days_t4 > 0:
            turnover_change = (inv_turnover_days - days_t4) / days_t4 * 100

    severity = "green"
    # red
    if (
        growth_gap > thresholds.red_growth_gap_pp
        and inv_yoy * 100 > thresholds.red_inventory_growth_pct
        and or_yoy * 100 < thresholds.red_revenue_growth_max_pct
    ):
        severity = "red"
    elif (
        turnover_change is not None
        and turnover_change > thresholds.red_turnover_change_pct
        and inv_turnover_days is not None
        and inv_turnover_days > thresholds.red_turnover_days
    ):
        severity = "red"

    # orange
    if (
        severity == "green"
        and growth_gap > thresholds.orange_growth_gap_pp
        and turnover_change is not None
        and turnover_change > thresholds.orange_turnover_change_pct
    ):
        severity = "orange"

    # yellow
    if severity == "green" and (
        growth_gap > thresholds.yellow_growth_gap_pp
        or (
            turnover_change is not None
            and turnover_change > thresholds.yellow_turnover_change_pct
        )
    ):
        severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "inventory_yoy": {"value": round(inv_yoy * 100, 1), "unit": "percent"},
        "oper_rev_yoy": {"value": round(or_yoy * 100, 1), "unit": "percent"},
        "growth_gap": {"value": round(growth_gap, 1), "unit": "percentage_point"},
    }
    if inv_turnover_days is not None:
        result.current["inventory_turnover_days"] = {
            "value": round(inv_turnover_days, 1),
            "unit": "days",
        }
    if turnover_change is not None:
        result.current["turnover_change"] = {
            "value": round(turnover_change, 1),
            "unit": "percent",
        }
    result.quality = build_parent_scope_quality(
        coverage=inventories_sr.coverage,
        data_completeness=round(valid_inv / 4, 2),
        missing_periods=4 - valid_inv,
        extra={
            "turnover_calculable": inv_turnover_days is not None,
            "turnover_change_calculable": turnover_change is not None,
        },
    )
    result.warnings = field_warnings
    # 多期展示序列：最近 8 期存货/营收 YoY 与增速差（图表趋势用）
    # P2-3（核验修订）：按报告期对齐 + 去年同期计算，不再跨报表按下标拼接。
    gap_series: list[dict] = []
    for p in ordered[-8:]:
        t4 = prev_year_period(p, ordered)
        if t4 is None:
            continue
        inv_y = yoy_growth(aligned[p].get("inv"), aligned[t4].get("inv"))
        or_y = yoy_growth(aligned[p].get("or_"), aligned[t4].get("or_"))
        if inv_y is None or or_y is None:
            continue
        gap_series.append(
            {
                "period": p,
                "inventory_yoy": round(inv_y * 100, 1),
                "oper_rev_yoy": round(or_y * 100, 1),
                "growth_gap": round((inv_y - or_y) * 100, 1),
            }
        )
    if len(gap_series) >= 2:
        result.history = gap_series

    result.evidence_ids = [
        f"ev_bs_inventories_{current_period}",
        f"ev_is_oper_rev_{current_period}",
    ]
    if severity == "red":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）远超营业收入增速（{or_yoy*100:.1f}%），"
            f"增速差达 {fmt_gap_pct(growth_gap)}，存货积压风险显著（数据期：{fmt_period(current_period)}，母公司报表）。"
        )
    elif severity == "orange":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）明显快于营收增速（{or_yoy*100:.1f}%），"
            f"需关注存货周转效率（数据期：{fmt_period(current_period)}，母公司报表）。"
        )
    elif severity == "yellow":
        result.explanation = f"存货增速快于营收增速（增速差 {fmt_gap_pct(growth_gap)}），建议持续关注（数据期：{fmt_period(current_period)}，母公司报表）。"
    return result
