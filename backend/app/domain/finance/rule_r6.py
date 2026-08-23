"""R6 · 其他应收款与关联占用风险 — RULES_SPEC §7.

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
from app.domain.finance.rule_utils import (
    count_valid,
    fmt_period,
    fmt_yi,
    yoy_growth,
)


def evaluate_r6(company_code: str, as_of: str = "20260331", periods: int = 8):
    config = get_rule_config("R6")
    if not config.enabled:
        return disabled_rule_result("R6", "其他应收款与关联占用风险")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R6",
        rule_version=get_execution_version(),
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

    # P2-3：按期次对齐（current 判定与 history 统一走对齐结果）
    from app.domain.finance._fetch import align_by_period, prev_year_period

    aligned = align_by_period(
        oth_rcv=oth_rcv_sr, assets=tot_assets_sr, acct_rcv=acct_rcv_sr
    )
    ordered_periods = sorted(aligned.keys())

    # P2-3（核验修订）：current 取核心字段（其他应收/总资产）有效的最后一期，
    # 而非对齐并集的最后一期——辅助字段（acct_rcv）多出更新一期时，
    # 并集最后一期 oth_rcv 为空会错误返回 insufficient_data。
    cur_period = next(
        (
            p
            for p in reversed(ordered_periods)
            if aligned[p].get("oth_rcv") is not None
            and aligned[p].get("assets") is not None
            and aligned[p].get("assets") > 0
        ),
        None,
    )
    if cur_period is None:
        result.status = "insufficient_data"
        result.explanation = "无核心字段（其他应收/总资产）同时有效的报告期"
        result.quality = build_parent_scope_quality(
            coverage=oth_rcv_sr.coverage,
            data_completeness=round(valid_oth / 2, 2),
            missing_periods=2 - valid_oth,
        )
        result.warnings = field_warnings
        return result
    cur = aligned[cur_period]

    oth_val = cur.get("oth_rcv")
    assets_val = cur.get("assets")
    acct_val = cur.get("acct_rcv")

    # 核心字段缺失 → 数据不足（不按零处理）
    if oth_val is None or assets_val is None or assets_val <= 0:
        result.status = "insufficient_data"
        result.explanation = "当前期其他应收或总资产缺失，无法计算占比"
        result.quality = build_parent_scope_quality(
            coverage=oth_rcv_sr.coverage,
            data_completeness=round(valid_oth / 2, 2),
            missing_periods=2 - valid_oth,
        )
        result.warnings = field_warnings
        return result

    oth_to_assets = oth_val / assets_val * 100
    oth_to_acct = oth_val / acct_val if acct_val and acct_val > 0 else None

    # YoY：当前期与去年同期（P2-3 核验修订：按 prev_year_period 取前一年
    # 同月日，不再用并集数组下标 -5 推断——错位期次会取到不同月日）。
    prev4_period = prev_year_period(cur_period, ordered_periods)
    prev4_val = aligned[prev4_period].get("oth_rcv") if prev4_period else None
    oth_yoy = yoy_growth(oth_val, prev4_val) if prev4_val is not None else None
    # P1-3（核验修订）：去年同期缺失 → 同比为 None（不是 0%），
    # 判定时显式保护，输出时省略该指标。
    oth_yoy_pct = oth_yoy * 100 if oth_yoy is not None else None

    oth_large = oth_val > thresholds.large_amount

    severity = "green"
    # red
    if (
        oth_to_assets > thresholds.red_assets_ratio_pct
        and oth_yoy_pct is not None
        and oth_yoy_pct > thresholds.red_yoy_pct
        and oth_large
    ):
        severity = "red"
    elif (
        oth_to_assets > thresholds.red_assets_ratio_pct
        and oth_to_acct is not None
        and oth_to_acct > thresholds.red_receivable_ratio
    ):
        severity = "red"

    # orange
    if (
        severity == "green"
        and oth_to_assets > thresholds.orange_assets_ratio_pct
        and oth_yoy_pct is not None
        and oth_yoy_pct > thresholds.orange_yoy_pct
        and oth_large
    ):
        severity = "orange"
    elif (
        severity == "green"
        and oth_to_assets > thresholds.orange_assets_ratio_pct
        and oth_to_acct is not None
        and oth_to_acct > thresholds.orange_receivable_ratio
    ):
        severity = "orange"

    # yellow
    if severity == "green":
        if (
            (oth_to_assets > thresholds.yellow_assets_ratio_pct and oth_large)
            or (
                oth_yoy_pct is not None
                and oth_yoy_pct > thresholds.yellow_yoy_pct
                and oth_large
            )
            or (
                oth_to_assets > thresholds.yellow_secondary_assets_ratio_pct
                and oth_yoy_pct is not None
                and oth_yoy_pct > thresholds.yellow_yoy_pct
            )
        ):
            severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "oth_rcv_to_assets": {"value": round(oth_to_assets, 1), "unit": "percent"},
        "oth_rcv_large": {"value": oth_large, "unit": "bool"},
    }
    if oth_yoy_pct is not None:
        result.current["oth_rcv_yoy"] = {
            "value": round(oth_yoy_pct, 1),
            "unit": "percent",
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
    # 多期展示序列（P2-3）：按对齐结果构建（最近 8 期，升序），
    # 分子/分母缺失跳过——不制造零值
    oth_series: list[dict] = []
    for p in ordered_periods[-8:]:
        row = aligned[p]
        o = row.get("oth_rcv")
        a = row.get("assets")
        if o is None or a is None or a <= 0:
            continue
        oth_series.append({"period": p, "oth_rcv_to_assets": round(o / a * 100, 1)})
    if len(oth_series) >= 2:
        result.history = oth_series

    result.evidence_ids = [f"ev_bs_oth_rcv_{as_of}", f"ev_bs_tot_assets_{as_of}"]
    attach_calculation_trace(
        result,
        formula=(
            "oth_rcv_to_assets=oth_rcv/tot_assets; "
            "oth_rcv_yoy=(current/prior_year)-1; "
            "oth_rcv_to_acct_rcv=oth_rcv/acct_rcv"
        ),
        inputs=inputs_from_aligned(
            aligned,
            {
                "oth_rcv": "oth_rcv",
                "assets": "tot_assets",
                "acct_rcv": "acct_rcv",
            },
        ),
    )

    # P1-3：同比缺失（去年同期无数据）时 explanation 不得格式化 None
    if oth_yoy_pct is None:
        yoy_text = "，同比数据缺失"
    elif oth_yoy_pct > 0:
        yoy_text = f"，同比增速 {oth_yoy_pct:.1f}%"
    elif oth_yoy_pct < 0:
        yoy_text = f"，同比下降 {abs(oth_yoy_pct):.1f}%"
    else:
        yoy_text = "，同比持平"
    if severity == "red":
        result.explanation = (
            f"其他应收款占总资产 {oth_to_assets:.1f}%{yoy_text}，"
            f"金额 {fmt_yi(oth_val)} 亿元，可能存在关联方资金占用（数据期：{fmt_period(cur_period)}，母公司报表）。"
        )
    elif severity == "orange":
        result.explanation = f"其他应收款占总资产 {oth_to_assets:.1f}%{yoy_text}，建议关注具体构成（数据期：{fmt_period(cur_period)}，母公司报表）。"
    elif severity == "yellow":
        assets_ratio_triggered = (
            oth_to_assets > thresholds.yellow_assets_ratio_pct and oth_large
        ) or oth_to_assets > thresholds.yellow_secondary_assets_ratio_pct
        if assets_ratio_triggered and oth_yoy_pct is not None and oth_yoy_pct < 0:
            signal_text = (
                f"其他应收款占总资产 {oth_to_assets:.1f}%（同比下降 "
                f"{abs(oth_yoy_pct):.1f}%）"
            )
        elif assets_ratio_triggered and oth_yoy_pct is not None:
            signal_text = (
                f"其他应收款占总资产 {oth_to_assets:.1f}%（同比增长 "
                f"{oth_yoy_pct:.1f}%）"
            )
        elif (
            oth_yoy_pct is not None
            and oth_yoy_pct > thresholds.yellow_yoy_pct
            and oth_large
        ):
            signal_text = f"其他应收款同比增速较快（{oth_yoy_pct:.1f}%）"
        else:
            signal_text = "其他应收款占总资产比例偏高"
        result.explanation = (
            signal_text
            + f"，建议持续关注（数据期：{fmt_period(cur_period)}，母公司报表）。"
        )
    return result
