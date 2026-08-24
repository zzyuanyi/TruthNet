"""R2 · 现金流–利润背离 — RULES_SPEC §3.

口径: 固定母公司报表（statement_type=408006000），不读取合并报表。
公司类型: 统一走 check_company_type Gate（NULL/非法 → insufficient_data）。
所有状态均携带母公司口径 quality。
"""

from app.domain.finance._fetch import fetch_series
from app.domain.finance.calculation_trace import (
    attach_calculation_trace,
    inputs_from_aligned,
)
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
from app.domain.finance.period import next_quarter  # noqa: E402 — 与 R2 共用公共季度函数（8.11）
from app.domain.finance.rule_utils import (
    fmt_period,
    mean_or_none,
    safe_div,
    yoy_growth,
)


def evaluate_r2(company_code: str, as_of: str = "20260331", periods: int = 8):
    config = get_rule_config("R2")
    if not config.enabled:
        return disabled_rule_result("R2", "现金流–利润背离")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R2",
        rule_version=get_execution_version(),
        rule_name="现金流–利润背离",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R2", "现金流–利润背离", gate)

    net_profit_sr = fetch_series(
        company_code, "net_profit_excl_min_int_inc", periods, as_of
    )
    oper_cf_sr = fetch_series(company_code, "net_cash_flows_oper_act", periods, as_of)

    field_warnings = [w for w in (net_profit_sr.warning, oper_cf_sr.warning) if w]

    # P1-1（第三轮审查修订）：全部判定消费同一份 align_by_period() 结果，
    # 且按**共同有效期**分析——先找 np/cf 同时有效的最新共同期作为 current，
    # 分析窗口截止于该共同期（不包含后续单边数据）；数据完整性按成对有效
    # 期数计算；缺失期打断连续负现金流。
    from app.domain.finance._fetch import align_by_period, prev_year_period

    aligned = align_by_period(np=net_profit_sr, cf=oper_cf_sr)
    ordered = sorted(aligned.keys())
    if not ordered:
        result.status = "insufficient_data"
        result.explanation = "无可对齐的报告期"
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=0.0,
            missing_periods=4,
        )
        result.warnings = field_warnings
        return result

    cur_period = next(
        (
            p
            for p in reversed(ordered)
            if aligned[p].get("np") is not None and aligned[p].get("cf") is not None
        ),
        None,
    )
    if cur_period is None:
        result.status = "insufficient_data"
        result.explanation = "无净利润与现金流同时有效的报告期"
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=0.0,
            missing_periods=4,
        )
        result.warnings = field_warnings
        return result

    # 分析窗口：截止于共同期（含）的最后 4 期
    cur_idx = ordered.index(cur_period)
    recent_periods = ordered[max(0, cur_idx - 3) : cur_idx + 1]
    recent_np = [aligned[p].get("np") for p in recent_periods]
    recent_cf = [aligned[p].get("cf") for p in recent_periods]

    # 数据完整性：成对有效期数（np/cf 同时非 None）≥ 3
    valid_pairs = sum(
        1 for np, cf in zip(recent_np, recent_cf) if np is not None and cf is not None
    )
    if valid_pairs < 3:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: 共同有效期仅 {valid_pairs} 期（需 ≥3 期成对数据）"
        )
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=round(valid_pairs / 4, 2),
            missing_periods=4 - valid_pairs,
        )
        result.warnings = field_warnings
        return result

    # 检查是否全部为 profit<=0 且 cf<=0（窗口内成对期）
    pairs = [
        (np, cf)
        for np, cf in zip(recent_np, recent_cf)
        if np is not None and cf is not None
    ]
    if pairs and all(np <= 0 for np, _ in pairs) and all(cf <= 0 for _, cf in pairs):
        result.status = "not_applicable"
        result.explanation = "公司持续亏损且现金流出，非粉饰信号"
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=round(valid_pairs / 4, 2),
            missing_periods=4 - valid_pairs,
        )
        result.warnings = field_warnings
        return result

    # 计算每期 cf/profit ratio（缺失期打断连续负现金流，不跨期累计；
    # 第四轮审查修订：整季缺失（两表均无该期）时并集窗口不出现该期，
    # 相邻校验保证只有相邻季度才累计连续值）
    ratios = []
    consec_neg = 0
    max_consec_neg = 0
    prev_period = None
    for p, np, cf in zip(recent_periods, recent_np, recent_cf):
        if prev_period is not None and next_quarter(prev_period) != p:
            consec_neg = 0  # 非相邻季度（整季缺失）→ 重置连续计数
        prev_period = p
        if np is None or cf is None:
            consec_neg = 0  # 第三轮审查修订：缺失期打断连续负现金流
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
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=round(valid_pairs / 4, 2),
            missing_periods=4 - valid_pairs,
        )
        result.warnings = field_warnings
        return result

    # 判断严重程度（current 基于共同期，而非并集最后一期）
    has_neg_cf_this = recent_cf[-1] is not None and recent_cf[-1] < 0
    has_pos_profit_this = recent_np[-1] is not None and recent_np[-1] > 0

    severity = "green"
    if (
        has_pos_profit_this
        and has_neg_cf_this
        and max_consec_neg >= thresholds.red_consecutive_negative_cashflow_periods
    ):
        severity = "red"
    elif (
        has_pos_profit_this
        and avg_ratio < 0
        and max_consec_neg >= thresholds.red_growth_consecutive_periods
    ):
        # 利润增长但现金越来越差（同比：精确去年同期，缺失则不比——
        # 第二轮审查修订：不得用下标 -5 推断）
        np_yoy = None
        t4 = prev_year_period(recent_periods[-1], ordered)
        if t4 is not None:
            np_yoy = yoy_growth(recent_np[-1], aligned[t4].get("np"))
        if np_yoy is not None and np_yoy * 100 > thresholds.red_profit_yoy_pct:
            severity = "red"

    if (
        severity == "green"
        and has_pos_profit_this
        and has_neg_cf_this
        and max_consec_neg >= thresholds.orange_consecutive_negative_cashflow_periods
    ):
        severity = "orange"
    elif (
        severity == "green"
        and has_pos_profit_this
        and 0 <= avg_ratio < thresholds.orange_cashflow_profit_ratio
    ):
        severity = "orange"

    if severity == "green" and has_pos_profit_this and has_neg_cf_this:
        severity = "yellow"
    elif (
        severity == "green"
        and has_pos_profit_this
        and thresholds.orange_cashflow_profit_ratio
        <= avg_ratio
        < thresholds.yellow_cashflow_profit_ratio
    ):
        severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "cf_to_profit_ratio": {"value": round(avg_ratio, 3), "unit": "ratio"},
        "consec_neg_cf": {"value": max_consec_neg, "unit": "quarters"},
    }
    ratio_extreme = abs(avg_ratio) > 100
    result.quality = build_parent_scope_quality(
        coverage=net_profit_sr.coverage,
        data_completeness=round(valid_pairs / 4, 2),
        missing_periods=4 - valid_pairs,
        extra={
            "profit_sign": "positive" if has_pos_profit_this else "negative",
            "cashflow_profit_ratio_extreme": ratio_extreme,
        },
    )
    # 多期展示序列：最近 8 期现金流/利润比（图表趋势用）。
    # P2-3（核验修订）：复用同一份对齐结果，不再跨报表按数组下标拼接。
    cf_series: list[dict] = []
    for p in ordered[-8:]:
        np_v = aligned[p].get("np")
        cf_v = aligned[p].get("cf")
        if np_v is None or cf_v is None or np_v == 0:
            continue
        cf_series.append(
            {"period": p, "cf_to_profit_ratio": round(cf_v / abs(np_v), 3)}
        )
    if cf_series:
        result.history = cf_series

    result.warnings = field_warnings
    if ratio_extreme:
        result.warnings.append(
            "现金流/利润比绝对值超过 100，用户文案不直接展示极端比率；请核对原始利润与现金流金额"
        )
    result.evidence_ids = [
        f"ev_is_net_profit_{as_of}",
        f"ev_cf_oper_{as_of}",
    ]
    trace_periods = list(recent_periods)
    t4 = prev_year_period(cur_period, ordered)
    if t4 is not None and t4 not in trace_periods:
        trace_periods.append(t4)
    attach_calculation_trace(
        result,
        formula=(
            "mean(net_cash_flows_oper_act/abs(net_profit_excl_min_int_inc)); "
            "count consecutive periods where profit>0 and operating_cashflow<0"
        ),
        inputs=inputs_from_aligned(
            aligned,
            {
                "np": "net_profit_excl_min_int_inc",
                "cf": "net_cash_flows_oper_act",
            },
            periods=trace_periods,
        ),
    )

    if severity == "red":
        ratio_text = (
            "现金流/利润比呈极端值，具体以原始利润和现金流金额为准"
            if ratio_extreme
            else f"平均现金流/利润比仅 {avg_ratio:.2f}，盈利缺乏现金支撑"
        )
        result.explanation = (
            f"最近 {max_consec_neg} 个季度净利润为正但经营现金流为负，"
            f"{ratio_text}（数据期：{fmt_period(cur_period)}，母公司报表）。"
        )
    elif severity == "orange":
        if max_consec_neg > 0:
            result.explanation = (
                f"净利润为正但经营现金流近 {max_consec_neg} 个季度为负，"
                f"现金流/利润比（{avg_ratio:.2f}）低于健康水平"
                f"（数据期：{fmt_period(cur_period)}，母公司报表）。"
            )
        else:
            result.explanation = (
                f"经营现金流对利润的平均覆盖偏弱，现金流/利润比仅 {avg_ratio:.2f}，"
                f"低于健康水平（数据期：{fmt_period(cur_period)}，母公司报表）。"
            )
    elif severity == "yellow":
        result.explanation = f"本期经营现金流为负，与正利润背离，建议关注（数据期：{fmt_period(cur_period)}，母公司报表）。"
    return result
