"""R4 · 存货–营收背离 — RULES_SPEC §5.

口径: 固定母公司报表（statement_type=408006000），不读取合并报表。
公司类型: 统一走 check_company_type Gate（NULL/非法 → insufficient_data）。
所有状态均携带母公司口径 quality。
"""

from app.domain.finance._fetch import fetch_series
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
    single_quarter,
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

    # YoY 增速（t-4Q 需要至少 5 期，避免越界）
    if len(inventories) < 5 or len(oper_rev) < 5:
        result.status = "insufficient_data"
        result.explanation = (
            f"历史期数不足: inventory={len(inventories)}期, oper_rev={len(oper_rev)}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=inventories_sr.coverage,
            data_completeness=round(valid_inv / 4, 2),
            missing_periods=4 - valid_inv,
        )
        result.warnings = field_warnings
        return result

    t_idx, t4_idx = -1, -5
    inv_yoy = yoy_growth(inventories[t_idx], inventories[t4_idx])
    or_yoy = yoy_growth(oper_rev[t_idx], oper_rev[t4_idx])
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

    if turnover_ok and len(less_oper_cost) >= 5:
        sq_cost = single_quarter(less_oper_cost)
        annualized_cost = (
            sq_cost[t_idx] * 4
            if sq_cost[t_idx] is not None and sq_cost[t_idx] > 0
            else None
        )
        if annualized_cost:
            avg_inv = ((inventories[t_idx] or 0) + (inventories[-2] or 0)) / 2
            inv_turnover_days = (
                avg_inv / annualized_cost * 365 if annualized_cost > 0 else None
            )
            # 去年同期
            sq_cost_t4 = single_quarter(less_oper_cost)
            if len(sq_cost_t4) >= 5:
                ann_cost_t4 = (
                    sq_cost_t4[t4_idx] * 4
                    if sq_cost_t4[t4_idx] is not None and sq_cost_t4[t4_idx] > 0
                    else None
                )
                if ann_cost_t4 and len(inventories) >= 6:
                    avg_inv_t4 = (
                        (inventories[t4_idx] or 0) + (inventories[-6] or 0)
                    ) / 2
                    days_t4 = (
                        avg_inv_t4 / ann_cost_t4 * 365 if ann_cost_t4 > 0 else None
                    )
                    if inv_turnover_days and days_t4 and days_t4 > 0:
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
        extra={"turnover_calculable": turnover_ok},
    )
    result.warnings = field_warnings
    # 多期展示序列：最近 8 期存货/营收 YoY 与增速差（图表趋势用）
    # P2-3（核验修订）：按报告期对齐 + 去年同期计算，不再跨报表按下标拼接。
    from app.domain.finance._fetch import align_by_period, prev_year_period

    aligned = align_by_period(
        inv=inventories_sr, or_=oper_rev_sr, cost=less_oper_cost_sr
    )
    ordered = sorted(aligned.keys())
    gap_series: list[dict] = []
    for p in ordered[-8:]:
        t4 = prev_year_period(p, ordered)
        if t4 is None:
            continue
        inv_y = yoy_growth(aligned[p].get("inv"), aligned[t4].get("inv"))
        or_y = yoy_growth(aligned[p].get("or"), aligned[t4].get("or"))
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

    result.evidence_ids = [f"ev_bs_inventories_{as_of}", f"ev_is_oper_rev_{as_of}"]
    if severity == "red":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）远超营业收入增速（{or_yoy*100:.1f}%），"
            f"增速差达 {fmt_gap_pct(growth_gap)}，存货积压风险显著（数据期：{fmt_period(inventories_sr.periods[-1] if inventories_sr.periods else as_of)}，母公司报表）。"
        )
    elif severity == "orange":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）明显快于营收增速（{or_yoy*100:.1f}%），"
            f"需关注存货周转效率（数据期：{fmt_period(inventories_sr.periods[-1] if inventories_sr.periods else as_of)}，母公司报表）。"
        )
    elif severity == "yellow":
        result.explanation = f"存货增速快于营收增速（增速差 {fmt_gap_pct(growth_gap)}），建议持续关注（数据期：{fmt_period(inventories_sr.periods[-1] if inventories_sr.periods else as_of)}，母公司报表）。"
    return result
