"""R3 · 存贷双高 — RULES_SPEC §4.

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
from app.domain.finance.rule_utils import count_valid


def evaluate_r3(company_code: str, as_of: str = "20260331", periods: int = 8):
    config = get_rule_config("R3")
    if not config.enabled:
        return disabled_rule_result("R3", "存贷双高")
    thresholds = config.thresholds
    result = RuleResult(
        rule_id="R3",
        rule_version=get_execution_version(),
        rule_name="存贷双高",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R3", "存贷双高", gate)

    monetary_cap_sr = fetch_series(company_code, "monetary_cap", periods, as_of)
    st_borrow_sr = fetch_series(company_code, "st_borrow", periods, as_of)
    lt_borrow_sr = fetch_series(company_code, "lt_borrow", periods, as_of)
    # bonds_payable / non_cur_liab_due_within_1y 在当前数据集中不存在，仅用 st_borrow + lt_borrow
    tot_assets_sr = fetch_series(company_code, "tot_assets", periods, as_of)
    fin_exp_sr = fetch_series(company_code, "less_fin_exp", periods, as_of)
    monetary_cap = monetary_cap_sr.values
    tot_assets = tot_assets_sr.values

    field_warnings = [
        w
        for w in (
            monetary_cap_sr.warning,
            st_borrow_sr.warning,
            lt_borrow_sr.warning,
            tot_assets_sr.warning,
            fin_exp_sr.warning,
        )
        if w
    ]

    valid_cash = count_valid(monetary_cap, 2)
    valid_assets = count_valid(tot_assets, 2)
    if valid_cash < 2 or valid_assets < 2:
        result.status = "insufficient_data"
        result.explanation = (
            f"数据不足: cash有效{valid_cash}期, assets有效{valid_assets}期"
        )
        result.quality = build_parent_scope_quality(
            coverage=monetary_cap_sr.coverage,
            data_completeness=round(valid_cash / 2, 2),
            missing_periods=2 - valid_cash,
        )
        result.warnings = field_warnings
        return result

    # P2-3：按期次对齐（current 判定、前期比较、history 统一走对齐结果，
    # 不再按下标拼接——各字段期次错位时不误配）。
    from app.domain.finance._fetch import align_by_period

    aligned = align_by_period(
        cash=monetary_cap_sr,
        st_borrow=st_borrow_sr,
        lt_borrow=lt_borrow_sr,
        assets=tot_assets_sr,
        fin_exp=fin_exp_sr,
    )
    ordered_periods = sorted(aligned.keys())

    # P2-3（核验修订）：current 取核心字段（货币资金/总资产）有效的最后一期，
    # 而非对齐并集的最后一期——辅助字段（如借款）多出更新一期时，
    # 并集最后一期核心字段为空会错误返回 insufficient_data。
    cur_period = next(
        (
            p
            for p in reversed(ordered_periods)
            if aligned[p].get("cash") is not None
            and aligned[p].get("assets") is not None
            and aligned[p].get("assets") > 0
        ),
        None,
    )
    if cur_period is None:
        result.status = "insufficient_data"
        result.explanation = "无核心字段（货币资金/总资产）同时有效的报告期"
        result.quality = build_parent_scope_quality(
            coverage=monetary_cap_sr.coverage,
            data_completeness=round(valid_cash / 2, 2),
            missing_periods=2 - valid_cash,
        )
        result.warnings = field_warnings
        return result
    cur = aligned[cur_period]
    # P1-3（第二轮审查修订）：前期趋势比较向前查找"核心字段共同有效 + 借款
    # 至少一项有效"的最近期次——直接取并集上一期可能只有财务费用/单个借款
    # 字段，导致持续扩大判断被静默跳过。
    prev = {}
    for p in reversed(ordered_periods):
        if p >= cur_period:
            continue
        row = aligned[p]
        if (
            row.get("cash") is not None
            and row.get("assets") is not None
            and row.get("assets") > 0
            and (row.get("st_borrow") is not None or row.get("lt_borrow") is not None)
        ):
            prev = row
            break

    # 当前期：核心字段（总资产/货币资金）缺失 → 数据不足，不按零处理
    assets_val = cur.get("assets")
    cash_val = cur.get("cash")
    if assets_val is None or assets_val <= 0 or cash_val is None:
        result.status = "insufficient_data"
        result.explanation = "当前期总资产或货币资金缺失，无法计算存贷占比"
        result.quality = build_parent_scope_quality(
            coverage=monetary_cap_sr.coverage,
            data_completeness=round(valid_cash / 2, 2),
            missing_periods=2 - valid_cash,
        )
        result.warnings = field_warnings
        return result

    # 有息负债（P2-3：借款分项全部缺失 → 视为数据不完整，返回 limitation，
    # 不默认"不存在负债"）
    st_v = cur.get("st_borrow")
    lt_v = cur.get("lt_borrow")
    if st_v is None and lt_v is None:
        result.status = "insufficient_data"
        result.explanation = "短期/长期借款数据均缺失，无法计算有息负债"
        result.quality = build_parent_scope_quality(
            coverage=monetary_cap_sr.coverage,
            data_completeness=round(valid_cash / 2, 2),
            missing_periods=2 - valid_cash,
        )
        result.warnings = field_warnings
        return result
    missing_borrow = [f for f in ("st_borrow", "lt_borrow") if cur.get(f) is None]
    # P1-3（第二轮审查修订）：单个借款分项缺失时，有息负债取现有分项之和
    # 为**下界**。下界已触发双高 → 保守触发（真实负债只会更高，不漏报），
    # 并标记 borrow_partial；下界未触发 → 不能证明真实负债未触发
    # （缺失项可能使真实占比越过阈值），返回 insufficient_data 而非绿色。
    total_debt = (st_v or 0) + (lt_v or 0)
    borrow_partial = bool(missing_borrow)

    cash_to_assets = cash_val / assets_val * 100
    debt_to_assets = total_debt / assets_val * 100
    if borrow_partial and not (
        cash_to_assets > thresholds.dual_high_cash_pct
        and debt_to_assets > thresholds.dual_high_debt_pct
    ):
        result.status = "insufficient_data"
        result.explanation = (
            f"借款分项缺失（{','.join(missing_borrow)}），有息负债下界 "
            f"{debt_to_assets:.1f}% 未触发双高，但真实负债可能更高，无法确认"
        )
        result.quality = build_parent_scope_quality(
            coverage=monetary_cap_sr.coverage,
            data_completeness=round(valid_cash / 2, 2),
            missing_periods=2 - valid_cash,
            extra={
                "borrow_field_missing": missing_borrow,
                "borrow_partial": True,
            },
        )
        result.warnings = field_warnings
        return result

    # 隐含利率。P1-2（第三轮审查修订）：借款分项缺失（partial）时**不计算**
    # 隐含利率——下界负债会高估利率（实测下界 6.67% vs 真实 3.33% 误判 red），
    # 利率作为 red 必要条件的意义在于精确负债，partial 下不可得。
    fin_cur = cur.get("fin_exp")
    implied_rate = None
    if not borrow_partial and fin_cur is not None and total_debt > 0:
        implied_rate = abs(fin_cur) / total_debt * 100

    dual_high = (
        cash_to_assets > thresholds.dual_high_cash_pct
        and debt_to_assets > thresholds.dual_high_debt_pct
    )

    severity = "green"
    if (
        not borrow_partial
        and cash_to_assets > thresholds.red_cash_pct
        and debt_to_assets > thresholds.red_debt_pct
        and implied_rate is not None
        and implied_rate > thresholds.red_implied_interest_rate_pct
    ):
        severity = "red"
    elif not borrow_partial and dual_high:
        # 检查是否持续扩大（前期按对齐结果取，缺失则不比）
        prev_assets = prev.get("assets")
        prev_cash = prev.get("cash")
        prev_st = prev.get("st_borrow")
        prev_lt = prev.get("lt_borrow")
        if (
            prev_assets is not None
            and prev_assets > 0
            and prev_cash is not None
            # 第四轮审查修订：前期借款必须 st/lt **都完整**才做趋势升级——
            # 前期缺失时其负债下界可能低估，真实负债可能反而下降，
            # 用下界判断"持续扩大"会误升 red，应跳过升级保留 orange。
            and prev_st is not None
            and prev_lt is not None
        ):
            prev_debt = (prev_st or 0) + (prev_lt or 0)
            prev_cash_ratio = prev_cash / prev_assets * 100
            prev_debt_ratio = prev_debt / prev_assets * 100
            if cash_to_assets > prev_cash_ratio and debt_to_assets > prev_debt_ratio:
                severity = "red"

    if severity == "green" and dual_high:
        severity = "orange"
    if (
        severity == "green"
        and cash_to_assets > thresholds.yellow_cash_pct
        and total_debt > 0
    ):
        severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {
        "cash_to_assets": {"value": round(cash_to_assets, 1), "unit": "percent"},
        "debt_to_assets": {"value": round(debt_to_assets, 1), "unit": "percent"},
    }
    if implied_rate is not None:
        result.current["implied_interest_rate"] = {
            "value": round(implied_rate, 2),
            "unit": "percent",
        }
    result.quality = build_parent_scope_quality(
        coverage=monetary_cap_sr.coverage,
        data_completeness=round(valid_cash / 2, 2),
        missing_periods=2 - valid_cash,
        extra={
            "bonds_payable_included": False,  # 当前数据集无此字段
            "implied_rate_calculable": implied_rate is not None,
            # P1-3：借款分项缺失列表（有息负债为下界，非确定值）
            "borrow_field_missing": missing_borrow,
            # P1-3（第二轮审查修订）：单缺失且下界已触发 → 保守触发 + partial
            "borrow_partial": borrow_partial,
        },
    )
    if missing_borrow:
        field_warnings = [*field_warnings, f"借款分项缺失: {','.join(missing_borrow)}"]
    result.warnings = field_warnings
    # 多期展示序列（P2-3）：按期次对齐结果构建（最近 8 期，升序），
    # 分子缺失跳过该点，分母非正跳过——不制造零值
    dq_series: list[dict] = []
    for p in ordered_periods[-8:]:
        row = aligned[p]
        assets = row.get("assets")
        cash = row.get("cash")
        if assets is None or assets <= 0 or cash is None:
            continue
        st_v2 = row.get("st_borrow")
        lt_v2 = row.get("lt_borrow")
        # P1-3：任一借款分项缺失 → 该期有息负债不完整，跳过（不按 0 计算）
        if st_v2 is None or lt_v2 is None:
            continue
        debt_v = (st_v2 or 0) + (lt_v2 or 0)
        dq_series.append(
            {
                "period": p,
                "cash_to_assets": round(cash / assets * 100, 1),
                "debt_to_assets": round(debt_v / assets * 100, 1),
            }
        )
    if dq_series:
        result.history = dq_series

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
        result.explanation = (
            "货币资金和有息负债占总资产比例偏高，建议结合业务判断合理性。"
        )
    return result
