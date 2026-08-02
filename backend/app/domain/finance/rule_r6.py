"""R6 · 其他应收款与关联占用风险 — RULES_SPEC §7.

口径: 固定母公司报表（statement_type=408006000），不读取合并报表。
公司类型: 统一走 check_company_type Gate（NULL/非法 → insufficient_data）。
所有状态均携带母公司口径 quality。
"""

from app.domain.finance._fetch import fetch_series
from app.domain.finance.models import RuleResult
from app.domain.finance.parent_scope import (
    build_gate_result,
    build_parent_scope_quality,
    check_company_type,
)
from app.domain.finance.rule_utils import count_valid, yoy_growth


def evaluate_r6(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R6",
        rule_version="1.0.0",
        rule_name="其他应收款与关联占用风险",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R6", "其他应收款与关联占用风险", gate)

    oth_rcv_sr = fetch_series(company_code, "oth_rcv", periods, as_of)
    tot_assets_sr = fetch_series(company_code, "tot_assets", periods, as_of)
    acct_rcv_sr = fetch_series(company_code, "acct_rcv", periods, as_of)
    oth_rcv = oth_rcv_sr.values
    tot_assets = tot_assets_sr.values
    acct_rcv = acct_rcv_sr.values

    field_warnings = [
        w for w in (oth_rcv_sr.warning, tot_assets_sr.warning, acct_rcv_sr.warning) if w
    ]

    valid_oth = count_valid(oth_rcv, 2)
    valid_assets = count_valid(tot_assets, 2)
    if valid_oth < 2 or valid_assets < 2:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: oth_rcv有效{valid_oth}期, assets有效{valid_assets}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=oth_rcv_sr.coverage,
            data_completeness=round(valid_oth / 2, 2),
            missing_periods=2 - valid_oth,
        )
        result.warnings = field_warnings
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
    result.quality = build_parent_scope_quality(
        coverage=oth_rcv_sr.coverage,
        data_completeness=round(valid_oth / 2, 2),
        missing_periods=2 - valid_oth,
        extra={
            "related_party_data_available": False,
            "oth_rcv_to_acct_rcv_calculable": oth_to_acct is not None,
        },
    )
    result.warnings = field_warnings
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
