"""R2 · 现金流–利润背离 — RULES_SPEC §3."""

from app.domain.finance._fetch import fetch_company_field, fetch_field
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_utils import count_valid, mean_or_none, safe_div


def evaluate_r2(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R2",
        rule_version="1.0.0",
        rule_name="现金流–利润背离",
        status="not_triggered",
    )

    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is not None and comp_type != 1:
        result.status = "not_applicable"
        result.explanation = "金融企业不适用"
        return result

    net_profit = fetch_field(company_code, "net_profit_excl_min_int_inc", periods)
    oper_cf = fetch_field(company_code, "net_cash_flows_oper_act", periods)

    valid_np = count_valid(net_profit, 4)
    valid_cf = count_valid(oper_cf, 4)
    if valid_np < 3 or valid_cf < 3:
        result.status = "insufficient_data"
        result.explanation = f"数据不足: profit有效{valid_np}期, cf有效{valid_cf}期"
        return result

    # 最近 4 期
    recent_np = net_profit[-4:]
    recent_cf = oper_cf[-4:]

    # 检查是否全部为 profit<=0 且 cf<=0
    if all(np is not None and np <= 0 for np in recent_np) and all(
        cf is not None and cf <= 0 for cf in recent_cf
    ):
        result.status = "not_applicable"
        result.explanation = "公司持续亏损且现金流出，非粉饰信号"
        return result

    # 计算每期 cf/profit ratio
    ratios = []
    consec_neg = 0
    max_consec_neg = 0
    for np, cf in zip(recent_np, recent_cf):
        if np is None or cf is None:
            continue
        r = safe_div(cf, abs(np)) if np != 0 else None
        if r is not None:
            ratios.append(r)
        if np > 0 and cf < 0:
            consec_neg += 1
            max_consec_neg = max(max_consec_neg, consec_neg)
        else:
            consec_neg = 0

    avg_ratio = mean_or_none(ratios)
    if avg_ratio is None:
        result.status = "insufficient_data"
        result.explanation = "无法计算现金流利润比"
        return result

    # 判断严重程度
    has_neg_cf_this = recent_cf[-1] is not None and recent_cf[-1] < 0
    has_pos_profit_this = recent_np[-1] is not None and recent_np[-1] > 0

    severity = "green"
    if has_pos_profit_this and has_neg_cf_this and max_consec_neg >= 3:
        severity = "red"
    elif has_pos_profit_this and avg_ratio < 0 and max_consec_neg >= 2:
        # 利润增长但现金越来越差
        np_yoy = safe_div(
            recent_np[-1] - (net_profit[-5] if len(net_profit) >= 5 else 0),
            abs(net_profit[-5]) if len(net_profit) >= 5 and net_profit[-5] else 1,
        )
        if np_yoy is not None and np_yoy > 0.2:
            severity = "red"

    if (
        severity == "green"
        and has_pos_profit_this
        and has_neg_cf_this
        and max_consec_neg >= 2
    ):
        severity = "orange"
    elif severity == "green" and has_pos_profit_this and 0 <= avg_ratio < 0.3:
        severity = "orange"

    if severity == "green" and has_pos_profit_this and has_neg_cf_this:
        severity = "yellow"
    elif severity == "green" and has_pos_profit_this and 0.3 <= avg_ratio < 0.5:
        severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "cf_to_profit_ratio": {"value": round(avg_ratio, 3), "unit": "ratio"},
        "consec_neg_cf": {"value": max_consec_neg, "unit": "quarters"},
    }
    result.quality = {
        "statement_scope": "parent_company",
        "profit_sign": "positive" if has_pos_profit_this else "negative",
        "data_completeness": round(valid_np / 4, 2),
    }
    result.evidence_ids = [
        f"ev_is_net_profit_{as_of}",
        f"ev_cf_oper_{as_of}",
    ]
    if severity == "red":
        result.explanation = (
            f"最近 {max_consec_neg} 个季度净利润为正但经营现金流为负，"
            f"平均现金流/利润比仅 {avg_ratio:.2f}，盈利缺乏现金支撑。"
        )
    elif severity == "orange":
        result.explanation = (
            f"净利润为正但经营现金流近 {max_consec_neg} 个季度为负，"
            f"现金流/利润比（{avg_ratio:.2f}）低于健康水平。"
        )
    elif severity == "yellow":
        result.explanation = "本季经营现金流为负，与正利润背离，建议关注。"
    return result
