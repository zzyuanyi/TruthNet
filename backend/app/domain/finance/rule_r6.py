"""R6 · 其他应收款与关联占用风险 — RULES_SPEC §7."""

from app.domain.finance._fetch import fetch_company_field, fetch_field
from app.domain.finance.models import RuleResult
from app.domain.finance.rule_utils import count_valid, yoy_growth


def evaluate_r6(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R6",
        rule_version="1.0.0",
        rule_name="其他应收款与关联占用风险",
        status="not_triggered",
    )

    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is not None and comp_type != 1:
        result.status = "not_applicable"
        result.explanation = "金融企业不适用"
        return result

    oth_rcv = fetch_field(company_code, "oth_rcv", periods)
    tot_assets = fetch_field(company_code, "tot_assets", periods)
    acct_rcv = fetch_field(company_code, "acct_rcv", periods)

    valid_oth = count_valid(oth_rcv, 2)
    valid_assets = count_valid(tot_assets, 2)
    if valid_oth < 2 or valid_assets < 2:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: oth_rcv有效{valid_oth}期, assets有效{valid_assets}期"
        )
        return result

    t_idx = -1
    oth_val = oth_rcv[t_idx] or 0
    assets_val = tot_assets[t_idx] or 0
    acct_val = acct_rcv[t_idx] if acct_rcv and acct_rcv[t_idx] is not None else None

    oth_to_assets = oth_val / assets_val * 100 if assets_val > 0 else 0
    oth_to_acct = oth_val / acct_val if acct_val and acct_val > 0 else None

    t4_idx = -5
    oth_yoy = yoy_growth(oth_rcv[t_idx], oth_rcv[t4_idx]) if len(oth_rcv) >= 5 else None
    oth_yoy_pct = oth_yoy * 100 if oth_yoy is not None else 0

    oth_large = oth_val > 50_000_000  # 5000 万

    severity = "green"
    # red
    if oth_to_assets > 10 and oth_yoy_pct > 200 and oth_large:
        severity = "red"
    elif oth_to_assets > 10 and oth_to_acct is not None and oth_to_acct > 1.0:
        severity = "red"

    # orange
    if severity == "green" and oth_to_assets > 10 and oth_yoy_pct > 100 and oth_large:
        severity = "orange"
    elif (
        severity == "green"
        and oth_to_assets > 10
        and oth_to_acct is not None
        and oth_to_acct > 0.5
    ):
        severity = "orange"

    # yellow
    if severity == "green":
        if (
            (oth_to_assets > 10 and oth_large)
            or (oth_yoy_pct > 200 and oth_large)
            or (oth_to_assets > 5 and oth_yoy_pct > 200)
        ):
            severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "oth_rcv_to_assets": {"value": round(oth_to_assets, 1), "unit": "percent"},
        "oth_rcv_yoy": {"value": round(oth_yoy_pct, 1), "unit": "percent"},
        "oth_rcv_large": {"value": oth_large, "unit": "bool"},
    }
    if oth_to_acct is not None:
        result.current["oth_rcv_to_acct_rcv"] = {
            "value": round(oth_to_acct, 2),
            "unit": "ratio",
        }
    result.quality = {
        "statement_scope": "parent_company",
        "related_party_data_available": False,
        "oth_rcv_to_acct_rcv_calculable": oth_to_acct is not None,
    }
    result.evidence_ids = [f"ev_bs_oth_rcv_{as_of}", f"ev_bs_tot_assets_{as_of}"]
    if severity == "red":
        result.explanation = (
            f"其他应收款占总资产 {oth_to_assets:.1f}%，同比增速 {oth_yoy_pct:.1f}%，"
            f"金额 {oth_val/1e8:.1f} 亿元，可能存在关联方资金占用。"
        )
    elif severity == "orange":
        result.explanation = (
            f"其他应收款占总资产 {oth_to_assets:.1f}%，同比增速 {oth_yoy_pct:.1f}%，"
            f"建议关注具体构成。"
        )
    elif severity == "yellow":
        result.explanation = f"其他应收款增速较快（{oth_yoy_pct:.1f}%），建议持续关注。"
    return result
