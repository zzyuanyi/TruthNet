"""行业分位指标注册表 — Phase C 数据任务 3.

每个指标（metric）必须是 RULES_SPEC 中规则的**真实中间量**，
不得从 explanation 文本反向解析数字。指标值、Finance 端点与 Benchmarks 端点
使用同一注册表，保证 company_value 口径一致。

约定：
- 固定母公司报表口径 statement_type=408006000 / statement_scope=parent_company
  （由调用方 SQL 注入，见 domain/finance/statement_type.py）
- 只对 eligible 非金融公司（comp_type_code=1）计算
- 字段值缺失/非法 → 该样本不参与，返回 None
- 分母为 0/NULL → 返回 None（样本不计入，不当作 0）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# 字段 → 表映射（与 domain/finance/field_mapping.py 保持一致）
_BALANCE = {
    "acct_rcv",
    "oth_rcv",
    "inventories",
    "monetary_cap",
    "st_borrow",
    "lt_borrow",
    "bonds_payable",
    "non_cur_liab_due_within_1y",
    "tot_assets",
}
_INCOME = {
    "oper_rev",
    "less_oper_cost",
    "less_selling_dist_exp",
    "less_gerl_admin_exp",
    "less_fin_exp",
    "net_profit_excl_min_int_inc",
}
_CASHFLOW = {"net_cash_flows_oper_act"}

_FIELD_TABLE: dict[str, str] = {}
for _f in _BALANCE:
    _FIELD_TABLE[_f] = "balance_sheet"
for _f in _INCOME:
    _FIELD_TABLE[_f] = "income_statement"
for _f in _CASHFLOW:
    _FIELD_TABLE[_f] = "cash_flow"


def field_table(field: str) -> str:
    """字段 → 表名（未注册字段抛 ValueError）。"""
    t = _FIELD_TABLE.get(field)
    if t is None:
        raise ValueError(f"未知财务字段: {field}")
    return t


def _safe_div(num: float | None, den: float | None, eps: float = 1e-9) -> float | None:
    """安全除法：任一为 None 或分母接近 0 时返回 None（不当作 0）。"""
    if num is None or den is None:
        return None
    if abs(den) < eps:
        return None
    return num / den


def _yoy(current: float | None, prev: float | None) -> float | None:
    """YoY 增速（RULES_SPEC §1.2）：分母为 0/NULL → None。"""
    if current is None or prev is None or prev == 0:
        return None
    return (current - prev) / abs(prev)


# ── 序列规约辅助 ────────────────────────────────────────────
# 批量取数时按 report_period 升序返回 value 列表（缺失为 None）。
# metric 的 compute_from_series 接收 {field: [values 升序]}。


@dataclass(frozen=True)
class MetricSpec:
    """单个行业分位指标定义."""

    metric_id: str  # 如 "r1_gap"
    rule_id: str  # 对应规则 "R1"~"R7"
    name: str  # 指标中文名
    unit: str  # 单位
    description: str
    fields: tuple[str, ...]  # 需要的财务字段（含所属表）
    periods: int  # 需要的期数（升序序列长度；YoY 指标需 5）
    # 从 {field: [升序 values]} 计算单公司指标值（纯函数，可单测）
    compute_from_series: Callable[[dict[str, list]], float | None]
    # 语义方向（用于报告展示，不影响计算）
    higher_is_riskier: bool = True


def _compute_r1_gap(series: dict[str, list]) -> float | None:
    ar = series.get("acct_rcv") or []
    orv = series.get("oper_rev") or []
    if len(ar) < 5 or len(orv) < 5:
        return None
    ar_yoy = _yoy(ar[-1], ar[-5])
    or_yoy = _yoy(orv[-1], orv[-5])
    if ar_yoy is None or or_yoy is None:
        return None
    return round((ar_yoy - or_yoy) * 100, 4)  # 百分点


def _compute_r2_cf_ratio(series: dict[str, list]) -> float | None:
    profit = (series.get("net_profit_excl_min_int_inc") or [None])[-1]
    cf = (series.get("net_cash_flows_oper_act") or [None])[-1]
    return _safe_div(cf, profit)


def _compute_r3_cash_to_assets(series: dict[str, list]) -> float | None:
    cash = (series.get("monetary_cap") or [None])[-1]
    assets = (series.get("tot_assets") or [None])[-1]
    return _safe_div(cash, assets)


def _compute_r3_debt_to_assets(series: dict[str, list]) -> float | None:
    assets = (series.get("tot_assets") or [None])[-1]
    st = (series.get("st_borrow") or [None])[-1]
    lt = (series.get("lt_borrow") or [None])[-1]
    bond = (series.get("bonds_payable") or [None])[-1]
    due = (series.get("non_cur_liab_due_within_1y") or [None])[-1]
    debt = sum(x for x in (st, lt, bond, due) if x is not None)
    return _safe_div(debt, assets)


def _compute_r4_growth_gap(series: dict[str, list]) -> float | None:
    inv = series.get("inventories") or []
    orv = series.get("oper_rev") or []
    if len(inv) < 5 or len(orv) < 5:
        return None
    inv_yoy = _yoy(inv[-1], inv[-5])
    or_yoy = _yoy(orv[-1], orv[-5])
    if inv_yoy is None or or_yoy is None:
        return None
    return round((inv_yoy - or_yoy) * 100, 4)


def _compute_r4_turnover_days(series: dict[str, list]) -> float | None:
    """存货周转天数（RULES_SPEC §5.3）：单季成本年化。"""
    inv = series.get("inventories") or []
    cost = series.get("less_oper_cost") or []
    if len(inv) < 2 or len(cost) < 2:
        return None
    inv_t = inv[-1]
    inv_t1 = inv[-2]
    cost_t = cost[-1]
    cost_t1 = cost[-2]
    if inv_t is None or inv_t1 is None or cost_t is None:
        return None
    # 单季成本：累计值差值；上期缺失时视为 Q1 直接用当期
    single_q_cost = cost_t if cost_t1 is None else cost_t - cost_t1
    if single_q_cost is None or single_q_cost <= 0:
        return None
    avg_inv = (inv_t + inv_t1) / 2
    annualized = single_q_cost * 4
    return round(avg_inv / annualized * 365, 4)


def _compute_r5_gross_margin(series: dict[str, list]) -> float | None:
    rev = (series.get("oper_rev") or [None])[-1]
    cost = (series.get("less_oper_cost") or [None])[-1]
    if rev is None or rev <= 0 or cost is None:
        return None
    return round((rev - cost) / rev, 4)


def _compute_r5_expense_ratio(series: dict[str, list]) -> float | None:
    rev = (series.get("oper_rev") or [None])[-1]
    selling = (series.get("less_selling_dist_exp") or [None])[-1]
    admin = (series.get("less_gerl_admin_exp") or [None])[-1]
    fin = (series.get("less_fin_exp") or [None])[-1]
    if rev is None or rev <= 0:
        return None
    expense = sum(x for x in (selling, admin, fin) if x is not None)
    return round(expense / rev, 4)


def _compute_r6_oth_rcv_to_assets(series: dict[str, list]) -> float | None:
    oth = (series.get("oth_rcv") or [None])[-1]
    assets = (series.get("tot_assets") or [None])[-1]
    return _safe_div(oth, assets)


# ── 注册表 ──────────────────────────────────────────────────

REGISTRY: dict[str, MetricSpec] = {}


def _register(spec: MetricSpec) -> None:
    REGISTRY[spec.metric_id] = spec


_register(
    MetricSpec(
        metric_id="r1_gap",
        rule_id="R1",
        name="应收-营收背离幅度",
        unit="pp",
        description="R1 核心中间量：应收账款 YoY 与营业收入 YoY 之差（百分点）",
        fields=("acct_rcv", "oper_rev"),
        periods=5,
        compute_from_series=_compute_r1_gap,
    )
)
_register(
    MetricSpec(
        metric_id="r2_cf_ratio",
        rule_id="R2",
        name="现金流/净利润比",
        unit="ratio",
        description="R2 核心中间量：经营现金流净额 / 净利润绝对值",
        fields=("net_profit_excl_min_int_inc", "net_cash_flows_oper_act"),
        periods=1,
        compute_from_series=_compute_r2_cf_ratio,
    )
)
_register(
    MetricSpec(
        metric_id="r3_cash_to_assets",
        rule_id="R3",
        name="货币资金/总资产",
        unit="ratio",
        description="R3 中间量：货币资金占资产比",
        fields=("monetary_cap", "tot_assets"),
        periods=1,
        compute_from_series=_compute_r3_cash_to_assets,
    )
)
_register(
    MetricSpec(
        metric_id="r3_debt_to_assets",
        rule_id="R3",
        name="有息负债/总资产",
        unit="ratio",
        description="R3 中间量：有息负债（短借+长借+应付债券+一年内到期）占资产比",
        fields=(
            "st_borrow",
            "lt_borrow",
            "bonds_payable",
            "non_cur_liab_due_within_1y",
            "tot_assets",
        ),
        periods=1,
        compute_from_series=_compute_r3_debt_to_assets,
    )
)
_register(
    MetricSpec(
        metric_id="r4_growth_gap",
        rule_id="R4",
        name="存货-营收背离幅度",
        unit="pp",
        description="R4 中间量：存货 YoY 与营业收入 YoY 之差（百分点）",
        fields=("inventories", "oper_rev"),
        periods=5,
        compute_from_series=_compute_r4_growth_gap,
    )
)
_register(
    MetricSpec(
        metric_id="r4_turnover_days",
        rule_id="R4",
        name="存货周转天数",
        unit="days",
        description="R4 中间量：基于单季成本年化的存货周转天数",
        fields=("inventories", "less_oper_cost"),
        periods=2,
        compute_from_series=_compute_r4_turnover_days,
    )
)
_register(
    MetricSpec(
        metric_id="r5_gross_margin",
        rule_id="R5",
        name="毛利率",
        unit="ratio",
        description="R5 中间量：(营业收入-营业成本)/营业收入",
        fields=("oper_rev", "less_oper_cost"),
        periods=1,
        compute_from_series=_compute_r5_gross_margin,
    )
)
_register(
    MetricSpec(
        metric_id="r5_expense_ratio",
        rule_id="R5",
        name="期间费用率",
        unit="ratio",
        description="R5 中间量：(销售+管理+财务费用)/营业收入",
        fields=(
            "oper_rev",
            "less_selling_dist_exp",
            "less_gerl_admin_exp",
            "less_fin_exp",
        ),
        periods=1,
        compute_from_series=_compute_r5_expense_ratio,
    )
)
_register(
    MetricSpec(
        metric_id="r6_oth_rcv_to_assets",
        rule_id="R6",
        name="其他应收款/总资产",
        unit="ratio",
        description="R6 核心中间量：其他应收款占资产比",
        fields=("oth_rcv", "tot_assets"),
        periods=1,
        compute_from_series=_compute_r6_oth_rcv_to_assets,
    )
)


def get_metric(metric_id: str) -> MetricSpec:
    """按 metric_id 取指标定义."""
    if metric_id not in REGISTRY:
        raise KeyError(f"未知指标: {metric_id}")
    return REGISTRY[metric_id]


def all_metrics() -> list[MetricSpec]:
    """按注册顺序返回全部指标."""
    return list(REGISTRY.values())
