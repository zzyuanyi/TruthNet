"""深度数值冲突检测 — Phase D #2.

冻结恰好两种可解释数值冲突模式（CV-NUM-01 / CV-NUM-02），
避免无边界扩张。每个冲突绑定真实 evidence_ids；绝不把会计差异
直接描述为造假。

CV-NUM-01 利润与经营现金流背离：
  - 母公司利润表 net_profit_after_ded_nr_lp 与母公司现金流量表
    net_cash_flows_oper_act，相同报告期、连续时间序列；
  - 检测：净利润持续为正/上升而经营现金流持续为负，
    或现金流/净利润比值低于配置阈值（连续不少于约定有效期数）；
  - 口径固定母公司（408006000），不混用合并报表，缺失值不按 0。

CV-NUM-02 股权持股比例与控制链时间一致性冲突：
  - MySQL top_shareholders 最新同期间持股比例 vs Neo4j 最新有效
    ownership_pct / 控制链逐边乘积 / final_control_pct；
  - 同实体、同目标、同有效期间；超过允许误差即冲突；
  - 事件（增减持/权益变动）仅作为可能的时间差解释上下文；
  - 公告/事件无可验证数值比例时不从标题猜测百分比。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# 固定母公司报表口径（与 _fetch 一致）
PARENT_STATEMENT_TYPE = "408006000"

CV_NUM_01 = "CV-NUM-01"
CV_NUM_02 = "CV-NUM-02"


@dataclass
class NumericalConflict:
    """一条深度数值冲突检测结果."""

    conflict_id: str
    conflict_type: str  # CV-NUM-01 / CV-NUM-02
    status: str  # conflict / pass / insufficient_data
    severity: str  # red / orange / yellow / green
    periods: list[str] = field(default_factory=list)
    left_values: list = field(default_factory=list)
    right_values: list = field(default_factory=list)
    threshold: dict = field(default_factory=dict)
    explanation: str = ""
    alternative_explanation: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "status": self.status,
            "severity": self.severity,
            "periods": self.periods,
            "left_values": self.left_values,
            "right_values": self.right_values,
            "threshold": self.threshold,
            "explanation": self.explanation,
            "alternative_explanation": self.alternative_explanation,
            "evidence_ids": self.evidence_ids,
            "limitations": self.limitations,
            "details": self.details,
        }


# ──────────────────────────────────────────────────────────────
# CV-NUM-01：利润与经营现金流背离
# ──────────────────────────────────────────────────────────────


def detect_profit_cashflow_conflict(
    *,
    company_code: str,
    profit_values: list,
    profit_periods: list[str],
    cashflow_values: list,
    cashflow_periods: list[str],
    evidence_ids: list[str] | None = None,
    min_periods: int | None = None,
    threshold: float | None = None,
) -> NumericalConflict:
    """CV-NUM-01 检测（纯函数，输入已对齐的报告期序列）。

    Args:
        company_code: 公司代码
        profit_values: 净利润序列（升序，缺失为 None）
        profit_periods: 利润表报告期（与 values 对齐）
        cashflow_values: 经营现金流净额序列（升序，缺失为 None）
        cashflow_periods: 现金流量表报告期
        evidence_ids: 绑定证据（真实 evidence_refs 中的 ID）
        min_periods: 至少需观察的有效期数（默认配置）
        threshold: 现金流/净利润比值阈值（默认配置）

    Returns:
        NumericalConflict（status=conflict / pass / insufficient_data）
    """
    min_periods = min_periods or settings.CV_NUM_01_MIN_PERIODS
    threshold = (
        threshold
        if threshold is not None
        else settings.CV_NUM_01_CF_TO_PROFIT_THRESHOLD
    )
    evidence_ids = evidence_ids or []

    # 报告期对齐（取交集，同期间比较）
    common = sorted(set(profit_periods) & set(cashflow_periods))
    if not common:
        return NumericalConflict(
            conflict_id=f"{CV_NUM_01}_{company_code}",
            conflict_type=CV_NUM_01,
            status="insufficient_data",
            severity="green",
            explanation="利润表与现金流量表无重叠报告期，无法比对",
            alternative_explanation="两表报告期覆盖不一致，可能为数据导入时序差异",
            evidence_ids=evidence_ids,
            limitations=["无重叠报告期，无法进行期间对齐比较"],
        )

    profit_by_p = dict(zip(profit_periods, profit_values))
    cash_by_p = dict(zip(cashflow_periods, cashflow_values))

    profit_seq: list = []
    cash_seq: list = []
    valid_periods: list[str] = []
    for p in common:
        pv = profit_by_p.get(p)
        cv = cash_by_p.get(p)
        if pv is None or cv is None:
            continue  # 缺失值不按 0
        profit_seq.append(float(pv))
        cash_seq.append(float(cv))
        valid_periods.append(p)

    if len(valid_periods) < min_periods:
        return NumericalConflict(
            conflict_id=f"{CV_NUM_01}_{company_code}",
            conflict_type=CV_NUM_01,
            status="insufficient_data",
            severity="green",
            periods=valid_periods,
            left_values=profit_seq,
            right_values=cash_seq,
            threshold={"cf_to_profit_ratio": threshold, "min_periods": min_periods},
            explanation=f"有效可比期数 {len(valid_periods)} < 最低要求 {min_periods}",
            alternative_explanation="数据覆盖不足，无法形成时间序列判断",
            evidence_ids=evidence_ids,
            limitations=[
                f"有效可比期数 {len(valid_periods)} < {min_periods}",
                "缺失值未按 0 处理，可能低估覆盖率",
            ],
        )

    # 比值序列（净利润为 0 或负 → 无法计算比值，单独处理）
    ratios: list[float] = []
    ratio_periods: list[str] = []
    for i, p in enumerate(valid_periods):
        npv = profit_seq[i]
        if npv <= 0:
            continue
        ratios.append(cash_seq[i] / npv)
        ratio_periods.append(p)

    # 判定条件：净利润为正/上升而经营现金流持续为负，或比值低于阈值
    profit_positive = [p > 0 for p in profit_seq]
    cash_negative = [c < 0 for c in cash_seq]

    # 连续期数中"利润为正但现金流为负"或"比值 < 阈值"
    divergence_count = 0
    divergence_periods: list[str] = []
    for i, p in enumerate(valid_periods):
        npv = profit_seq[i]
        cv = cash_seq[i]
        low_ratio = False
        if npv > 0:
            low_ratio = cv / npv < threshold
        if (npv > 0 and cv < 0) or low_ratio:
            divergence_count += 1
            divergence_periods.append(p)

    if divergence_count >= min_periods:
        severity = "red" if all(cash_negative) and all(profit_positive) else "orange"
        return NumericalConflict(
            conflict_id=f"{CV_NUM_01}_{company_code}",
            conflict_type=CV_NUM_01,
            status="conflict",
            severity=severity,
            periods=valid_periods,
            left_values=profit_seq,
            right_values=cash_seq,
            threshold={"cf_to_profit_ratio": threshold, "min_periods": min_periods},
            explanation=(
                f"{divergence_count} 期净利润为正而经营现金流为负或比值低于 "
                f"{threshold}，利润与现金流持续背离"
            ),
            alternative_explanation=(
                "利润与现金流背离可能是业务结算节奏、大额赊销回款滞后、"
                "季节性经营或重大投资支出所致，不必然构成造假信号"
            ),
            evidence_ids=evidence_ids,
            limitations=[
                "仅基于母公司报表口径（408006000）",
                "比值口径为经营现金流/净利润，未考虑非付现成本",
                "背离不等于造假，需结合审计意见与监管文件进一步核验",
            ],
            details={
                "company_code": company_code,
                "divergence_count": divergence_count,
                "divergence_periods": divergence_periods,
                "profit_positive_all": all(profit_positive),
                "cashflow_negative_all": all(cash_negative),
            },
        )

    return NumericalConflict(
        conflict_id=f"{CV_NUM_01}_{company_code}",
        conflict_type=CV_NUM_01,
        status="pass",
        severity="green",
        periods=valid_periods,
        left_values=profit_seq,
        right_values=cash_seq,
        threshold={"cf_to_profit_ratio": threshold, "min_periods": min_periods},
        explanation="利润与经营现金流在可比期间内未呈现持续背离",
        alternative_explanation="无显著背离信号",
        evidence_ids=evidence_ids,
        limitations=["仅基于母公司报表口径（408006000）"],
    )


# ──────────────────────────────────────────────────────────────
# CV-NUM-02：股权持股比例与控制链时间一致性冲突
# ──────────────────────────────────────────────────────────────


def detect_ownership_consistency_conflict(
    *,
    company_code: str,
    shareholder_edges: list[dict],
    tolerance: float | None = None,
    evidence_ids: list[str] | None = None,
    event_context: list[dict] | None = None,
) -> NumericalConflict:
    """CV-NUM-02 检测（纯函数，输入为边级比例记录）。

    Args:
        company_code: 目标公司代码
        shareholder_edges: 边级持股记录，每项含：
            {entity_id, owner_name, mysql_pct (0-100), neo4j_pct (0-100),
             report_period, relationship_id}
            其中 mysql_pct 来自 top_shareholders，neo4j_pct 来自图边。
        tolerance: 允许误差（百分点，默认配置）
        evidence_ids: 绑定证据
        event_context: 同期股权变动事件（增减持/权益变动），作时间解释

    Returns:
        NumericalConflict
    """
    tolerance = (
        tolerance if tolerance is not None else settings.CV_NUM_02_OWNERSHIP_TOLERANCE
    )
    evidence_ids = evidence_ids or []
    event_context = event_context or []

    # 只比较同时具备两来源数值的边
    comparable = [
        e
        for e in shareholder_edges
        if e.get("mysql_pct") is not None and e.get("neo4j_pct") is not None
    ]
    if not comparable:
        return NumericalConflict(
            conflict_id=f"{CV_NUM_02}_{company_code}",
            conflict_type=CV_NUM_02,
            status="insufficient_data",
            severity="green",
            explanation="无同时具备 MySQL 股东表与 Neo4j 图数据的可比边",
            alternative_explanation="数据来源覆盖不一致，无法进行数值比对",
            evidence_ids=evidence_ids,
            limitations=[
                "缺少可验证的双来源数值比例",
                "未从公告标题猜测百分比",
            ],
            details={"event_context_count": len(event_context)},
        )

    mismatches: list[dict] = []
    for e in comparable:
        diff = abs(e["mysql_pct"] - e["neo4j_pct"])
        if diff > tolerance:
            mismatches.append(
                {
                    "entity_id": e.get("entity_id"),
                    "owner_name": e.get("owner_name", ""),
                    "mysql_pct": e["mysql_pct"],
                    "neo4j_pct": e["neo4j_pct"],
                    "diff_pp": round(diff, 4),
                    "report_period": e.get("report_period"),
                    "relationship_id": e.get("relationship_id"),
                }
            )

    if not mismatches:
        return NumericalConflict(
            conflict_id=f"{CV_NUM_02}_{company_code}",
            conflict_type=CV_NUM_02,
            status="pass",
            severity="green",
            explanation="MySQL 股东表与 Neo4j 图数据持股比例在允许误差内一致",
            alternative_explanation="两来源数据一致",
            evidence_ids=evidence_ids,
            threshold={"tolerance_pp": tolerance},
            limitations=["允许误差", "仅比较同时具备两来源数值的边"],
            details={"comparable_edges": len(comparable)},
        )

    has_equity_events = any(
        e.get("category") in ("增减持", "权益变动", "股份增减持") for e in event_context
    )
    return NumericalConflict(
        conflict_id=f"{CV_NUM_02}_{company_code}",
        conflict_type=CV_NUM_02,
        status="conflict",
        severity="orange",
        periods=[e.get("report_period", "") for e in mismatches],
        left_values=[e["mysql_pct"] for e in mismatches],
        right_values=[e["neo4j_pct"] for e in mismatches],
        threshold={"tolerance_pp": tolerance},
        explanation=(
            f"{len(mismatches)} 条边的 MySQL 股东表比例与 Neo4j 图比例超过 "
            f"{tolerance}pp 允许误差"
        ),
        alternative_explanation=(
            "比例不一致可能是数据快照时间差（图数据 vs 最新股东表）、"
            "期间权益变动尚未同步至图，或同一股东多条记录合并方式不同"
            + (
                "；同期存在增减持/权益变动事件，可能解释时间差"
                if has_equity_events
                else ""
            )
        ),
        evidence_ids=evidence_ids,
        limitations=[
            "事件仅作为时间差解释，不构成造假认定",
            "未从公告标题猜测百分比",
            "控制链逐边乘积与 final_control_pct 的差异需链路级复核",
        ],
        details={
            "mismatches": mismatches,
            "comparable_edges": len(comparable),
            "event_context_count": len(event_context),
            "has_equity_events": has_equity_events,
        },
    )


def run_numerical_conflicts(
    *,
    company_code: str,
    profit_values: list,
    profit_periods: list[str],
    cashflow_values: list,
    cashflow_periods: list[str],
    finance_evidence_ids: list[str] | None = None,
    shareholder_edges: list[dict] | None = None,
    equity_evidence_ids: list[str] | None = None,
    event_context: list[dict] | None = None,
) -> list[NumericalConflict]:
    """运行全部冻结的数值冲突检测（当前 2 种）。"""
    results: list[NumericalConflict] = []
    results.append(
        detect_profit_cashflow_conflict(
            company_code=company_code,
            profit_values=profit_values,
            profit_periods=profit_periods,
            cashflow_values=cashflow_values,
            cashflow_periods=cashflow_periods,
            evidence_ids=finance_evidence_ids,
        )
    )
    results.append(
        detect_ownership_consistency_conflict(
            company_code=company_code,
            shareholder_edges=shareholder_edges or [],
            evidence_ids=equity_evidence_ids,
            event_context=event_context,
        )
    )
    return results
