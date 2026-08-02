"""R4 · 存货–营收背离 — RULES_SPEC §5."""

from app.domain.finance._fetch import fetch_company_field, fetch_series
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_utils import count_valid, single_quarter, yoy_growth


def evaluate_r4(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R4",
        rule_version="1.0.0",
        rule_name="存货–营收背离",
        status="not_triggered",
    )

    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is not None and comp_type != 1:
        result.status = "not_applicable"
        result.explanation = "金融企业不适用"
        return result

    inventories_sr = fetch_series(company_code, "inventories", periods, as_of)
    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    less_oper_cost_sr = fetch_series(company_code, "less_oper_cost", periods, as_of)
    inventories = inventories_sr.values
    oper_rev = oper_rev_sr.values
    less_oper_cost = less_oper_cost_sr.values

    valid_inv = count_valid(inventories, 4)
    valid_or = count_valid(oper_rev, 4)
    if valid_inv < 3 or valid_or < 3:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: inventory有效{valid_inv}期, oper_rev有效{valid_or}期"
        )
        return result

    # YoY 增速
    t_idx, t4_idx = -1, -5
    inv_yoy = yoy_growth(inventories[t_idx], inventories[t4_idx])
    or_yoy = yoy_growth(oper_rev[t_idx], oper_rev[t4_idx])
    if inv_yoy is None or or_yoy is None:
        result.status = "insufficient_data"
        result.explanation = "分母保护触发，无法计算 YoY"
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
    if growth_gap > 50 and inv_yoy * 100 > 50 and or_yoy < 0.10:
        severity = "red"
    elif (
        turnover_change is not None
        and turnover_change > 100
        and inv_turnover_days is not None
        and inv_turnover_days > 365
    ):
        severity = "red"

    # orange
    if (
        severity == "green"
        and growth_gap > 30
        and turnover_change is not None
        and turnover_change > 50
    ):
        severity = "orange"

    # yellow
    if severity == "green" and (
        growth_gap > 30 or (turnover_change is not None and turnover_change > 50)
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
    result.quality = {
        "statement_scope": inventories_sr.scope,
        "statement_type": inventories_sr.statement_type,
        "turnover_calculable": turnover_ok,
        "missing_periods": 4 - valid_inv,
        "data_coverage": inventories_sr.coverage,
    }
    for w in (inventories_sr.warning, oper_rev_sr.warning, less_oper_cost_sr.warning):
        if w:
            result.warnings.append(w)
    result.evidence_ids = [f"ev_bs_inventories_{as_of}", f"ev_is_oper_rev_{as_of}"]
    if severity == "red":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）远超营业收入增速（{or_yoy*100:.1f}%），"
            f"差距达 {growth_gap:.1f} 个百分点，存货积压风险显著。"
        )
    elif severity == "orange":
        result.explanation = (
            f"存货增速（{inv_yoy*100:.1f}%）明显快于营收增速（{or_yoy*100:.1f}%），"
            f"需关注存货周转效率。"
        )
    elif severity == "yellow":
        result.explanation = (
            f"存货增速快于营收增速（差距 {growth_gap:.1f}pp），建议持续关注。"
        )
    return result
