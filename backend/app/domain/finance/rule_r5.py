"""R5 · 毛利率/费用率异常 — RULES_SPEC §6.

口径: 固定母公司报表（statement_type=408006000），不读取合并报表。
公司类型: 统一走 check_company_type Gate（NULL/非法 → insufficient_data）。
所有状态均携带母公司口径 quality。
"""

from app.domain.finance._fetch import align_by_period, fetch_series
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
from app.domain.finance.rule_utils import count_valid, mean_or_none


def evaluate_r5(company_code: str, as_of: str = "20260331", periods: int = 8):
    config = get_rule_config("R5")
    if not config.enabled:
        return disabled_rule_result("R5", "毛利率/费用率异常")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R5",
        rule_version=get_execution_version(),
        rule_name="毛利率/费用率异常",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R5", "毛利率/费用率异常", gate)

    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    less_oper_cost_sr = fetch_series(company_code, "less_oper_cost", periods, as_of)
    selling_exp_sr = fetch_series(company_code, "less_selling_dist_exp", periods, as_of)
    admin_exp_sr = fetch_series(company_code, "less_gerl_admin_exp", periods, as_of)
    fin_exp_sr = fetch_series(company_code, "less_fin_exp", periods, as_of)
    oper_rev = oper_rev_sr.values

    field_warnings = [
        w
        for w in (
            oper_rev_sr.warning,
            less_oper_cost_sr.warning,
            selling_exp_sr.warning,
            admin_exp_sr.warning,
            fin_exp_sr.warning,
        )
        if w
    ]

    valid_or = count_valid(oper_rev, 6)
    if valid_or < 4:
        result.status = "insufficient_data"
        result.explanation = f"数据不足: oper_rev有效{valid_or}期"
        result.quality = build_parent_scope_quality(
            coverage=oper_rev_sr.coverage,
            data_completeness=round(valid_or / 6, 2),
            missing_periods=6 - valid_or,
            extra={"history_periods_available": valid_or},
        )
        result.warnings = field_warnings
        return result

    aligned = align_by_period(
        oper_rev=oper_rev_sr,
        less_oper_cost=less_oper_cost_sr,
        selling_exp=selling_exp_sr,
        admin_exp=admin_exp_sr,
        fin_exp=fin_exp_sr,
    )
    ordered = sorted(aligned)
    current_period = next(
        (
            period
            for period in reversed(ordered)
            if aligned[period].get("oper_rev") is not None
            and aligned[period]["oper_rev"] > 0
        ),
        None,
    )
    if current_period is None:
        result.status = "insufficient_data"
        result.explanation = "当期无收入"
        result.quality = build_parent_scope_quality(
            coverage=oper_rev_sr.coverage,
            data_completeness=round(valid_or / 6, 2),
            missing_periods=6 - valid_or,
            extra={"history_periods_available": valid_or},
        )
        result.warnings = field_warnings
        return result

    # 计算最近 8 期毛利率
    gm_list = []
    er_list = []

    for period in ordered:
        row = aligned[period]
        rev = row.get("oper_rev")
        if rev is None or rev <= 0:
            gm_list.append(None)
            er_list.append(None)
            continue
        cost = row.get("less_oper_cost")
        gm_list.append((rev - cost) / rev * 100 if cost is not None else None)

        expenses = (
            row.get("selling_exp"),
            row.get("admin_exp"),
            row.get("fin_exp"),
        )
        if any(v is None for v in expenses):
            er_list.append(None)
        else:
            total_exp = sum(expenses)
            er_list.append(total_exp / rev * 100)

    current_index = ordered.index(current_period)
    gm_current = gm_list[current_index]
    gm_hist = mean_or_none(
        [g for i, g in enumerate(gm_list) if i != current_index and g is not None]
    )
    gm_deviation = (
        (gm_current - gm_hist)
        if gm_current is not None and gm_hist is not None
        else None
    )

    er_current = er_list[current_index]
    er_hist = mean_or_none(
        [e for i, e in enumerate(er_list) if i != current_index and e is not None]
    )
    er_deviation = (
        (er_current - er_hist)
        if er_current is not None and er_hist is not None
        else None
    )

    combined = (
        (abs(gm_deviation) + abs(er_deviation))
        if gm_deviation is not None and er_deviation is not None
        else None
    )

    if gm_current is None and er_current is None:
        result.status = "insufficient_data"
        result.explanation = "缺少当期成本/费用数据，无法计算毛利率或费用率"
        result.quality = build_parent_scope_quality(
            coverage=oper_rev_sr.coverage,
            data_completeness=round(valid_or / 6, 2),
            missing_periods=6 - valid_or,
            extra={"history_periods_available": valid_or},
        )
        result.warnings = field_warnings
        return result

    severity = "green"
    if (
        gm_deviation is not None
        and gm_deviation > thresholds.gross_margin_deviation_pct
    ):
        if (
            er_deviation is not None
            and er_deviation < -thresholds.red_expense_rate_drop_pct
        ):
            severity = "red"  # 毛利率提升 + 费用率大幅下降
        elif gm_deviation > thresholds.red_gross_margin_deviation_pct:
            severity = "red"  # 极端偏离

    if (
        severity == "green"
        and gm_deviation is not None
        and gm_deviation > thresholds.gross_margin_deviation_pct
    ):
        severity = "orange"
    elif (
        severity == "green"
        and er_deviation is not None
        and er_deviation < -thresholds.expense_rate_drop_pct
    ):
        severity = "orange"

    if severity == "green":
        if (
            gm_deviation is not None
            and gm_deviation > thresholds.gross_margin_deviation_pct
        ) or (
            er_deviation is not None
            and er_deviation < -thresholds.expense_rate_drop_pct
        ):
            severity = "yellow"
        elif combined is not None and combined > thresholds.combined_deviation_pct:
            severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {}
    if gm_current is not None:
        result.current["gross_margin"] = {
            "value": round(gm_current, 1),
            "unit": "percent",
        }
    if gm_deviation is not None:
        result.current["gm_deviation"] = {
            "value": round(gm_deviation, 1),
            "unit": "percentage_point",
        }
    if er_deviation is not None:
        result.current["er_deviation"] = {
            "value": round(er_deviation, 1),
            "unit": "percentage_point",
        }
    result.quality = build_parent_scope_quality(
        coverage=oper_rev_sr.coverage,
        data_completeness=round(valid_or / 6, 2),
        missing_periods=6 - valid_or,
        extra={"history_periods_available": valid_or},
    )
    result.warnings = field_warnings
    # 多期展示序列：最近 8 期毛利率（gm_list 已在计算中构建）
    gm_series: list[dict] = []
    periods_hist = ordered
    for i in range(max(0, len(gm_list) - 8), len(gm_list)):
        gm_v = gm_list[i]
        if gm_v is None:
            continue
        label = (
            str(periods_hist[i]) if i < len(periods_hist) else f"t-{len(gm_list)-1-i}Q"
        )
        gm_series.append({"period": label, "gross_margin": round(gm_v, 1)})
    if len(gm_series) >= 2:
        result.history = gm_series

    result.evidence_ids = [f"ev_is_oper_rev_{as_of}", f"ev_is_oper_cost_{as_of}"]
    if severity == "red":
        if gm_deviation is not None and er_deviation is not None:
            result.explanation = (
                f"毛利率较历史均值偏离 {gm_deviation:.1f}pp，"
                f"费用率下降 {er_deviation:.1f}pp，利润两端同时优化，异常信号叠加。"
            )
        elif gm_deviation is not None:
            result.explanation = (
                f"毛利率较历史均值偏离 {gm_deviation:.1f}pp，"
                "成本口径可计算但费用率数据不足，存在异常信号。"
            )
        elif er_deviation is not None:
            result.explanation = (
                f"费用率较历史均值下降 {er_deviation:.1f}pp，"
                "毛利率数据不足，存在异常信号。"
            )
        else:
            result.explanation = "毛利率/费用率异常信号触发，但明细数据不足。"
    elif severity == "orange":
        result.explanation = (
            f"毛利率（{gm_deviation:+.1f}pp）明显偏离历史水平，建议关注。"
        )
    elif severity == "yellow":
        result.explanation = "毛利率/费用率较历史均值有所偏离，建议持续关注。"
    return result
