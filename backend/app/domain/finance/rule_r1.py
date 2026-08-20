"""R1 · 应收–营收背离 — RULES_SPEC §2.

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
    fmt_pct,
    fmt_period,
    yoy_growth,
)


def evaluate_r1(company_code: str, as_of: str = "20260331", periods: int = 8):
    """R1: 应收增速 vs 营收增速."""
    config = get_rule_config("R1")
    if not config.enabled:
        return disabled_rule_result("R1", "应收–营收背离")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R1",
        rule_version=get_execution_version(),
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

    # ── 2. 计算：按报告期配对，禁止不同字段按数组下标错配 ──
    from app.domain.finance._fetch import align_by_period, prev_year_period

    aligned = align_by_period(ar=acct_rcv_sr, or_=oper_rev_sr)
    ordered = sorted(aligned)
    current_period = None
    prior_year_period = None
    for period in reversed(ordered):
        candidate_prior = prev_year_period(period, ordered)
        if candidate_prior is None:
            continue
        current = aligned[period]
        prior = aligned[candidate_prior]
        if (
            current.get("ar") is not None
            and current.get("or_") is not None
            and prior.get("ar") is not None
            and prior.get("or_") is not None
        ):
            current_period = period
            prior_year_period = candidate_prior
            break

    if current_period is None or prior_year_period is None:
        result.status = "insufficient_data"
        result.explanation = "缺少可精确对齐的当期与去年同期应收/营收数据"
        result.quality = build_parent_scope_quality(
            coverage=acct_rcv_sr.coverage,
            data_completeness=round(valid_ar / 4, 2),
            missing_periods=4 - valid_ar,
        )
        result.warnings = field_warnings
        return result

    ar_yoy = yoy_growth(
        aligned[current_period].get("ar"), aligned[prior_year_period].get("ar")
    )
    or_yoy = yoy_growth(
        aligned[current_period].get("or_"), aligned[prior_year_period].get("or_")
    )
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
    prior_periods = [p for p in ordered if p < current_period]
    for period in reversed(prior_periods):
        candidate_prior = prev_year_period(period, ordered)
        if candidate_prior is None:
            continue
        current = aligned[period]
        prior = aligned[candidate_prior]
        prev_ar_yoy = yoy_growth(current.get("ar"), prior.get("ar"))
        prev_or_yoy = yoy_growth(current.get("or_"), prior.get("or_"))
        if prev_ar_yoy is not None and prev_or_yoy is not None:
            prev_gap = (prev_ar_yoy - prev_or_yoy) * 100
            break

    # ── 4. 阈值判断 ──
    severity = "green"
    ar_pct = ar_yoy * 100
    or_pct = or_yoy * 100

    # red
    if (
        gap > thresholds.red_consecutive_gap_pp
        and ar_yoy > 0
        and prev_gap is not None
        and prev_gap > thresholds.red_previous_gap_pp
    ):
        severity = "red"
    elif (
        gap > thresholds.red_declining_revenue_gap_pp
        and ar_pct > thresholds.red_receivable_growth_pct
        and or_yoy < 0
    ):
        severity = "red"

    # orange
    if severity == "green" and gap > thresholds.orange_gap_pp and ar_yoy > 0:
        severity = "orange"
    elif (
        severity == "green"
        and gap > thresholds.orange_consecutive_gap_pp
        and prev_gap is not None
        and prev_gap > thresholds.orange_previous_gap_pp
    ):
        severity = "orange"

    # yellow
    if severity == "green" and gap > thresholds.yellow_gap_pp:
        severity = "yellow"

    # ── 5. 结果 ──
    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "acct_rcv_growth": {"value": round(ar_pct, 1), "unit": "percent"},
        "oper_rev_growth": {"value": round(or_pct, 1), "unit": "percent"},
        "gap": {"value": round(gap, 1), "unit": "percentage_point"},
    }
    # 多期展示序列：逐期 YoY 计算 gap（最近 8 期，图表趋势用）。
    # P2-3（核验修订）：按报告期对齐 + 去年同期（prev_year_period）计算，
    # 不再跨报表按数组下标拼接（两字段期次错位时会错配）。
    if prev_gap is not None:
        from app.domain.finance._fetch import align_by_period, prev_year_period

        aligned = align_by_period(ar=acct_rcv_sr, or_=oper_rev_sr)
        ordered = sorted(aligned.keys())
        series: list[dict] = []
        for p in ordered[-8:]:
            t4 = prev_year_period(p, ordered)
            if t4 is None:
                continue
            ar_y = yoy_growth(aligned[p].get("ar"), aligned[t4].get("ar"))
            or_y = yoy_growth(aligned[p].get("or"), aligned[t4].get("or"))
            if ar_y is None or or_y is None:
                continue
            series.append({"period": p, "gap": round((ar_y - or_y) * 100, 1)})
        if len(series) >= 2:
            result.history = series
        else:
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
    template = _build_explanation(
        severity,
        ar_pct,
        or_pct,
        gap,
        current_period or as_of,
    )
    if template:
        result.explanation = template

    return result


def _build_explanation(sev: str, ar: float, ore: float, gap: float, period: str) -> str:
    """触发解释：数值最多 1 位小数，增速差用百分号，并标明实际数据期。"""
    period_text = fmt_period(period)
    if sev == "red":
        return (
            f"应收账款增速（{fmt_pct(ar)}）显著高于营业收入增速（{fmt_pct(ore)}），"
            f"增速差达 {fmt_gap_pct(gap)}，收入质量存在明显下降风险"
            f"（数据期：{period_text}，母公司报表）。"
        )
    if sev == "orange":
        return (
            f"应收账款增速（{fmt_pct(ar)}）明显高于营业收入增速（{fmt_pct(ore)}），"
            f"增速差达 {fmt_gap_pct(gap)}，需关注收入确认节奏"
            f"（数据期：{period_text}，母公司报表）。"
        )
    if sev == "yellow":
        return (
            f"应收账款增速略高于营业收入增速，增速差 {fmt_gap_pct(gap)}，"
            f"建议持续关注后续季度变化（数据期：{period_text}，母公司报表）。"
        )
    return ""
