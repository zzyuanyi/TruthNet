"""R5 · 毛利率/费用率异常 — RULES_SPEC §6."""

from app.domain.finance._fetch import fetch_company_field, fetch_series
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_utils import count_valid, mean_or_none


def evaluate_r5(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R5",
        rule_version="1.0.0",
        rule_name="毛利率/费用率异常",
        status="not_triggered",
    )

    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is not None and comp_type != 1:
        result.status = "not_applicable"
        result.explanation = "金融企业不适用"
        return result

    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    less_oper_cost_sr = fetch_series(company_code, "less_oper_cost", periods, as_of)
    selling_exp_sr = fetch_series(company_code, "less_selling_dist_exp", periods, as_of)
    admin_exp_sr = fetch_series(company_code, "less_gerl_admin_exp", periods, as_of)
    fin_exp_sr = fetch_series(company_code, "less_fin_exp", periods, as_of)
    oper_rev = oper_rev_sr.values
    less_oper_cost = less_oper_cost_sr.values
    selling_exp = selling_exp_sr.values
    admin_exp = admin_exp_sr.values
    fin_exp = fin_exp_sr.values

    valid_or = count_valid(oper_rev, 6)
    if valid_or < 4:
        result.status = "insufficient_data"
        result.explanation = f"数据不足: oper_rev有效{valid_or}期"
        return result

    if oper_rev[-1] is None or oper_rev[-1] <= 0:
        result.status = "insufficient_data"
        result.explanation = "当期无收入"
        return result

    # 计算最近 8 期毛利率
    gm_list = []
    er_list = []
    for i in range(len(oper_rev)):
        rev = oper_rev[i] or 0
        if rev <= 0:
            gm_list.append(None)
            er_list.append(None)
            continue
        cost = less_oper_cost[i] or 0 if i < len(less_oper_cost) else 0
        gm = (rev - cost) / rev * 100
        gm_list.append(gm)
        sell = selling_exp[i] or 0 if i < len(selling_exp) else 0
        adm = admin_exp[i] or 0 if i < len(admin_exp) else 0
        fin = fin_exp[i] or 0 if i < len(fin_exp) else 0
        total_exp = sell + adm + fin
        er = total_exp / rev * 100
        er_list.append(er)

    gm_current = gm_list[-1] if gm_list[-1] is not None else None
    gm_hist = mean_or_none([g for g in gm_list[:-1] if g is not None])
    gm_deviation = (
        (gm_current - gm_hist)
        if gm_current is not None and gm_hist is not None
        else None
    )

    er_current = er_list[-1] if er_list[-1] is not None else None
    er_hist = mean_or_none([e for e in er_list[:-1] if e is not None])
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

    severity = "green"
    if gm_deviation is not None and gm_deviation > 10:
        if er_deviation is not None and er_deviation < -10:
            severity = "red"  # 毛利率提升 + 费用率大幅下降
        elif gm_deviation > 15:
            severity = "red"  # 极端偏离

    if severity == "green" and gm_deviation is not None and gm_deviation > 10:
        severity = "orange"
    elif severity == "green" and er_deviation is not None and er_deviation < -5:
        severity = "orange"

    if severity == "green":
        if (gm_deviation is not None and gm_deviation > 10) or (
            er_deviation is not None and er_deviation < -5
        ):
            severity = "yellow"
        elif combined is not None and combined > 15:
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
    result.quality = {
        "statement_scope": oper_rev_sr.scope,
        "statement_type": oper_rev_sr.statement_type,
        "history_periods_available": valid_or,
        "data_coverage": oper_rev_sr.coverage,
    }
    for w in (
        oper_rev_sr.warning,
        less_oper_cost_sr.warning,
        selling_exp_sr.warning,
        admin_exp_sr.warning,
        fin_exp_sr.warning,
    ):
        if w:
            result.warnings.append(w)
    result.evidence_ids = [f"ev_is_oper_rev_{as_of}", f"ev_is_oper_cost_{as_of}"]
    if severity == "red":
        result.explanation = (
            f"毛利率较历史均值偏离 {gm_deviation:.1f}pp，费用率下降 {er_deviation:.1f}pp，"
            f"利润两端同时优化，异常信号叠加。"
        )
    elif severity == "orange":
        result.explanation = (
            f"毛利率（{gm_deviation:+.1f}pp）明显偏离历史水平，建议关注。"
        )
    elif severity == "yellow":
        result.explanation = "毛利率/费用率较历史均值有所偏离，建议持续关注。"
    return result
