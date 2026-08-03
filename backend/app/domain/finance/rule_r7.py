"""R7 · 盈利质量与非经常性依赖 — RULES_SPEC §8.

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


def evaluate_r7(company_code: str, as_of: str = "20260331", periods: int = 8):
    result = RuleResult(
        rule_id="R7",
        rule_version="1.0.0",
        rule_name="盈利质量与非经常性依赖",
        status="not_triggered",
    )

    # ── 1. 公司类型 Gate ──
    gate = check_company_type(company_code)
    if gate.status != "eligible":
        return build_gate_result("R7", "盈利质量与非经常性依赖", gate)

    net_profit_sr = fetch_series(
        company_code, "net_profit_excl_min_int_inc", periods, as_of
    )
    core_profit_sr = fetch_series(
        company_code, "net_profit_after_ded_nr_lp", periods, as_of
    )
    oper_rev_sr = fetch_series(company_code, "oper_rev", periods, as_of)
    oper_profit_sr = fetch_series(company_code, "oper_profit", periods, as_of)
    tot_profit_sr = fetch_series(company_code, "tot_profit", periods, as_of)
    oper_cf_sr = fetch_series(company_code, "net_cash_flows_oper_act", periods, as_of)
    net_profit = net_profit_sr.values
    core_profit = core_profit_sr.values
    oper_rev = oper_rev_sr.values
    oper_profit = oper_profit_sr.values
    tot_profit = tot_profit_sr.values
    oper_cf = oper_cf_sr.values

    field_warnings = [
        w
        for w in (
            net_profit_sr.warning,
            core_profit_sr.warning,
            oper_rev_sr.warning,
            oper_profit_sr.warning,
            tot_profit_sr.warning,
            oper_cf_sr.warning,
        )
        if w
    ]

    # 检查扣非字段是否可用
    core_available = core_profit and any(v is not None for v in core_profit)
    simplified = not core_available

    valid_np = count_valid(net_profit, 4)
    if valid_np < 3:
        result.status = "insufficient_data"
        result.explanation = f"数据不足: profit有效{valid_np}期"
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=round(valid_np / 4, 2),
            missing_periods=4 - valid_np,
            extra={
                "core_profit_available": core_available,
                "simplified_mode": simplified,
            },
        )
        result.warnings = field_warnings
        return result

    t_idx, t4_idx = -1, -5
    np_current = net_profit[t_idx]
    if np_current is None or np_current <= 0:
        result.status = "not_applicable"
        result.explanation = "公司亏损，盈利质量规则不适用"
        result.quality = build_parent_scope_quality(
            coverage=net_profit_sr.coverage,
            data_completeness=round(valid_np / 4, 2),
            missing_periods=4 - valid_np,
            extra={
                "core_profit_available": core_available,
                "simplified_mode": simplified,
            },
        )
        result.warnings = field_warnings
        return result

    # 扣非利润占比
    core_ratio = None
    if core_available and core_profit[t_idx] is not None and np_current != 0:
        core_ratio = core_profit[t_idx] / abs(np_current)

    # 非经常性损益占比
    non_recurring_ratio = None
    if core_available and core_profit[t_idx] is not None:
        non_recurring = np_current - core_profit[t_idx]
        non_recurring_ratio = (
            non_recurring / abs(np_current) if abs(np_current) > 0 else 0
        )

    # YoY 增速对比
    np_yoy = (
        yoy_growth(net_profit[t_idx], net_profit[t4_idx])
        if len(net_profit) >= 5
        else None
    )
    core_yoy = (
        yoy_growth(core_profit[t_idx], core_profit[t4_idx])
        if core_available and len(core_profit) >= 5
        else None
    )
    rev_yoy = (
        yoy_growth(oper_rev[t_idx], oper_rev[t4_idx]) if len(oper_rev) >= 5 else None
    )
    cf_yoy = yoy_growth(oper_cf[t_idx], oper_cf[t4_idx]) if len(oper_cf) >= 5 else None

    quality_div = (
        ((np_yoy or 0) - (core_yoy or 0)) * 100
        if np_yoy is not None and core_yoy is not None
        else None
    )
    revenue_div = (
        ((np_yoy or 0) - (rev_yoy or 0)) * 100
        if np_yoy is not None and rev_yoy is not None
        else None
    )
    cash_div = (
        ((np_yoy or 0) - (cf_yoy or 0)) * 100
        if np_yoy is not None and cf_yoy is not None
        else None
    )

    # 营业外收支占比
    non_oper_ratio = None
    if (
        oper_profit[t_idx] is not None
        and tot_profit[t_idx] is not None
        and tot_profit[t_idx] != 0
    ):
        non_oper_ratio = (
            (tot_profit[t_idx] - oper_profit[t_idx]) / abs(tot_profit[t_idx]) * 100
        )

    severity = "green"
    if not simplified:
        # 完整版
        if (
            core_ratio is not None
            and core_ratio < 0.3
            and (
                quality_div is not None
                and quality_div > 30
                or revenue_div is not None
                and revenue_div > 20
            )
        ):
            severity = "red"
        elif (
            core_ratio is not None
            and core_ratio < 0.5
            and quality_div is not None
            and quality_div > 30
        ):
            severity = "orange"
        elif (
            core_ratio is not None
            and core_ratio < 0.5
            and revenue_div is not None
            and revenue_div > 20
        ):
            severity = "orange"
        elif core_ratio is not None and core_ratio < 0.3:
            severity = "orange"
        elif non_oper_ratio is not None and non_oper_ratio > 50:
            severity = "orange"
        elif core_ratio is not None and core_ratio < 0.5:
            severity = "yellow"
        elif quality_div is not None and quality_div > 30:
            severity = "yellow"
        elif revenue_div is not None and revenue_div > 20:
            severity = "yellow"
        elif non_oper_ratio is not None and non_oper_ratio > 30:
            severity = "yellow"
    else:
        # 简化版：仅用 revenue + cash 判断，上限 orange
        if (
            revenue_div is not None
            and revenue_div > 20
            and cash_div is not None
            and cash_div > 30
        ):
            severity = "orange"
        elif revenue_div is not None and revenue_div > 20:
            severity = "yellow"
        elif cash_div is not None and cash_div > 30:
            severity = "yellow"

    result.status = "triggered" if severity != "green" else "not_triggered"
    result.severity = severity
    result.current = {}
    if core_ratio is not None:
        result.current["core_profit_ratio"] = {
            "value": round(core_ratio * 100, 1),
            "unit": "percent",
        }
    if non_recurring_ratio is not None:
        result.current["non_recurring_ratio"] = {
            "value": round(non_recurring_ratio * 100, 1),
            "unit": "percent",
        }
    if np_yoy is not None:
        result.current["net_profit_yoy"] = {
            "value": round(np_yoy * 100, 1),
            "unit": "percent",
        }
    if quality_div is not None:
        result.current["quality_divergence"] = {
            "value": round(quality_div, 1),
            "unit": "percentage_point",
        }
    if revenue_div is not None:
        result.current["revenue_divergence"] = {
            "value": round(revenue_div, 1),
            "unit": "percentage_point",
        }
    result.quality = build_parent_scope_quality(
        coverage=net_profit_sr.coverage,
        data_completeness=round(valid_np / 4, 2),
        missing_periods=4 - valid_np,
        extra={
            "core_profit_available": core_available,
            "simplified_mode": simplified,
        },
    )
    result.warnings = field_warnings
    # 证据 = 实际参与判断的字段（build_claims 按规则归属绑定，不再静态要求全字段）
    result.evidence_ids = [f"ev_is_net_profit_{as_of}"]
    if core_available:
        result.evidence_ids.append(f"ev_is_core_profit_{as_of}")
    if revenue_div is not None:
        result.evidence_ids.append(f"ev_is_oper_rev_{as_of}")
    if cash_div is not None:
        result.evidence_ids.append(f"ev_cf_oper_{as_of}")
    if non_oper_ratio is not None:
        result.evidence_ids.append(f"ev_is_oper_profit_{as_of}")
        result.evidence_ids.append(f"ev_is_tot_profit_{as_of}")

    if simplified:
        result.warnings.append("扣非净利润字段不可用，使用简化版判断（上限 orange）")

    if severity == "red" and core_ratio is not None:
        result.explanation = (
            f"扣非利润占净利润仅 {core_ratio*100:.1f}%，盈利对非经常性损益严重依赖，"
            f"主营业务盈利能力需审视。"
        )
    elif severity == "orange":
        if core_ratio is not None:
            result.explanation = (
                f"扣非净利润占比较低（{core_ratio*100:.1f}%），盈利质量有待改善。"
            )
        else:
            result.explanation = (
                "净利润增速与现金流/营收增速存在背离，盈利质量有待改善。"
            )
    elif severity == "yellow":
        if core_ratio is not None and core_ratio < 0.5:
            result.explanation = f"扣非净利润占净利润比重偏低（{core_ratio*100:.1f}%），建议关注盈利可持续性。"
        else:
            result.explanation = "净利润增速与现金流/营收增速存在背离，建议关注。"
    return result
