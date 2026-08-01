"""R3 · 存贷双高 — RULES_SPEC §4."""

from app.domain.finance._fetch import fetch_company_field, fetch_field
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_utils import count_valid, mean_or_none, safe_div


def evaluate_r3(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R3", rule_version="1.0.0",
        rule_name="存贷双高", status="not_triggered",
    )

    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is not None and comp_type != 1:
        result.status = "not_applicable"
        result.explanation = "金融企业不适用"
        return result

    monetary_cap = fetch_field(company_code, "monetary_cap", periods)
    st_borrow = fetch_field(company_code, "st_borrow", periods)
    lt_borrow = fetch_field(company_code, "lt_borrow", periods)
    # bonds_payable / non_cur_liab_due_within_1y 在当前数据集中不存在，仅用 st_borrow + lt_borrow
    tot_assets = fetch_field(company_code, "tot_assets", periods)
    fin_exp = fetch_field(company_code, "less_fin_exp", periods)

    valid_cash = count_valid(monetary_cap, 2)
    valid_assets = count_valid(tot_assets, 2)
    if valid_cash < 2 or valid_assets < 2:
        result.status = "insufficient_data"
        result.explanation = f"数据不足: cash有效{valid_cash}期, assets有效{valid_assets}期"
        return result

    t_idx = -1

    # 有息负债总额（当前数据集仅含 st_borrow + lt_borrow）
    debt_parts = []
    for vals in [st_borrow, lt_borrow]:
        if vals and vals[t_idx] is not None:
            debt_parts.append(vals[t_idx])
    total_debt = sum(debt_parts) if debt_parts else 0

    cash_val = monetary_cap[t_idx] or 0
    assets_val = tot_assets[t_idx] or 1

    cash_to_assets = cash_val / assets_val * 100 if assets_val > 0 else 0
    debt_to_assets = total_debt / assets_val * 100 if assets_val > 0 else 0

    # 隐含利率
    avg_debt = mean_or_none([total_debt])
    implied_rate = None
    if fin_exp and fin_exp[t_idx] is not None and avg_debt and avg_debt > 0:
        implied_rate = abs(fin_exp[t_idx]) / avg_debt * 100

    dual_high = cash_to_assets > 15 and debt_to_assets > 20

    severity = "green"
    if cash_to_assets > 25 and debt_to_assets > 25 and implied_rate is not None and implied_rate > 5:
        severity = "red"
    elif cash_to_assets > 15 and debt_to_assets > 20:
        # 检查是否持续扩大
        t4_idx = -5
        prev_cash = (monetary_cap[t4_idx] or 0) / (tot_assets[t4_idx] or 1) * 100 if len(tot_assets) >= 5 and tot_assets[t4_idx] else 0
        prev_debt = sum(v[t4_idx] for v in [st_borrow, lt_borrow] if v and len(v) >= 5 and v[t4_idx] is not None) / (tot_assets[t4_idx] or 1) * 100 if len(tot_assets) >= 5 and tot_assets[t4_idx] else 0
        if cash_to_assets > prev_cash and debt_to_assets > prev_debt:
            severity = "red"

    if severity == "green" and dual_high:
        severity = "orange"
    if severity == "green" and cash_to_assets > 20 and total_debt > 0:
        severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "cash_to_assets": {"value": round(cash_to_assets, 1), "unit": "percent"},
        "debt_to_assets": {"value": round(debt_to_assets, 1), "unit": "percent"},
    }
    if implied_rate is not None:
        result.current["implied_interest_rate"] = {"value": round(implied_rate, 2), "unit": "percent"}
    result.quality = {
        "statement_scope": "parent_company",
        "bonds_payable_included": False,  # 当前数据集无此字段
        "implied_rate_calculable": implied_rate is not None,
    }
    result.evidence_ids = [f"ev_bs_monetary_cap_{as_of}", f"ev_bs_borrow_{as_of}"]
    if severity == "red":
        result.explanation = (
            f"货币资金占总资产 {cash_to_assets:.1f}%，有息负债占 {debt_to_assets:.1f}%，"
            f"'存贷双高'特征明显，不符合商业逻辑。"
        )
    elif severity == "orange":
        result.explanation = (
            f"货币资金（{cash_to_assets:.1f}%）和有息负债（{debt_to_assets:.1f}%）"
            f"占总资产比例均偏高，'存贷双高'需要关注。"
        )
    elif severity == "yellow":
        result.explanation = f"货币资金和有息负债占总资产比例偏高，建议结合业务判断合理性。"
    return result
