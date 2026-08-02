"""R1 · 应收–营收背离 — RULES_SPEC §2.

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


def evaluate_r1(company_code: str, as_of: str = "20260331", periods: int = 8):
    """R1: 应收增速 vs 营收增速."""
    result = RuleResult(
        rule_id="R1",
        rule_version="1.0.0",
        rule_name="应收–营收背离",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R1", "应收–营收背离", gate)

    acct_rcv_sr = fetch_series(company_code, "acct_rcv", periods, as_of)
    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    acct_rcv = acct_rcv_sr.values
    oper_rev = oper_rev_sr.values

    field_warnings = [w for w in (acct_rcv_sr.warning, oper_rev_sr.warning) if w]

    valid_ar = count_valid(acct_rcv, 4)
    valid_or = count_valid(oper_rev, 4)
    if valid_ar < 2 or valid_or < 2:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: acct_rcv有效{valid_ar}期, oper_rev有效{valid_or}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=acct_rcv_sr.coverage,
            data_completeness=round(valid_ar / 4, 2),
            missing_periods=4 - valid_ar,
        )
        result.warnings = field_warnings
        return result
    if len(acct_rcv) < 5 or len(oper_rev) < 5:
        # t-4Q 需要至少 5 期；不足则无法计算 YoY，避免越界
        result.status = "insufficient_data"
        result.explanation = (
            f"历史期数不足: acct_rcv={len(acct_rcv)}期, oper_rev={len(oper_rev)}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=acct_rcv_sr.coverage,
            data_completeness=round(valid_ar / 4, 2),
            missing_periods=4 - valid_ar,
        )
        result.warnings = field_warnings
        return result

    # ── 2. 计算 ──
    t_idx, t4_idx = -1, -5
    ar_yoy = yoy_growth(acct_rcv[t_idx], acct_rcv[t4_idx])
    or_yoy = yoy_growth(oper_rev[t_idx], oper_rev[t4_idx])
    if ar_yoy is None or or_yoy is None:
        result.status = "insufficient_data"
        result.explanation = "分母保护触发，无法计算 YoY"
        result.quality = build_parent_scope_quality(
            coverage=acct_rcv_sr.coverage,
            data_completeness=round(valid_ar / 4, 2),
            missing_periods=4 - valid_ar,
        )
        result.warnings = field_warnings
        return result

    gap = (ar_yoy - or_yoy) * 100  # 转为百分点

    # ── 3. 上一期 gap（用于连续背离判断）──
    # 需至少 6 期数据（prev_t=-2, prev_t4=-6）；不足时 prev_gap=None，不越界。
    prev_gap = None
    if len(acct_rcv) >= 6 and len(oper_rev) >= 6:
        prev_ar_yoy = yoy_growth(acct_rcv[-2], acct_rcv[-6])
        prev_or_yoy = yoy_growth(oper_rev[-2], oper_rev[-6])
        if prev_ar_yoy is not None and prev_or_yoy is not None:
            prev_gap = (prev_ar_yoy - prev_or_yoy) * 100

    # ── 4. 阈值判断 ──
    severity = "green"
    ar_pct = ar_yoy * 100
    or_pct = or_yoy * 100

    # red
    if gap > 50 and ar_yoy > 0 and prev_gap is not None and prev_gap > 30:
        severity = "red"
    elif gap > 30 and ar_pct > 50 and or_yoy < 0:
        severity = "red"

    # orange
    if severity == "green" and gap > 30 and ar_yoy > 0:
        severity = "orange"
    elif severity == "green" and gap > 20 and prev_gap is not None and prev_gap > 20:
        severity = "orange"

    # yellow
    if severity == "green" and gap > 20:
        severity = "yellow"

    # ── 5. 结果 ──
    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "acct_rcv_growth": {"value": round(ar_pct, 1), "unit": "percent"},
        "oper_rev_growth": {"value": round(or_pct, 1), "unit": "percent"},
        "gap": {"value": round(gap, 1), "unit": "percentage_point"},
    }
    if prev_gap is not None:
        result.history = [
            {"period": "t-1Q", "gap": round(prev_gap, 1)},
            {"period": "t", "gap": round(gap, 1)},
        ]
    result.quality = build_parent_scope_quality(
        coverage=acct_rcv_sr.coverage,
        data_completeness=round(valid_ar / 4, 2),
        missing_periods=4 - valid_ar,
        extra={"denominator_protection_applied": False},
    )
    result.warnings = field_warnings
    result.evidence_ids = [
        f"ev_bs_acct_rcv_{as_of}",
        f"ev_is_oper_rev_{as_of}",
    ]
    template = _build_explanation(severity, ar_pct, or_pct, gap)
    if template:
        result.explanation = template

    return result


def _build_explanation(sev: str, ar: float, ore: float, gap: float) -> str:
    if sev == "red":
        return (
            f"应收账款增速（{ar}%）显著高于营业收入增速（{ore}%），"
            f"差距达 {gap} 个百分点，收入质量存在明显下降风险。"
        )
    if sev == "orange":
        return (
            f"应收账款增速（{ar}%）明显高于营业收入增速（{ore}%），"
            f"差距达 {gap} 个百分点，需关注收入确认节奏。"
        )
    if sev == "yellow":
        return (
            f"应收账款增速略高于营业收入增速，差距 {gap} 个百分点，"
            f"建议持续关注后续季度变化。"
        )
    return ""
