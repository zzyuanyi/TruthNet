"""轻量比较服务 — v3.3.3 收口整改（方案 §2.3/§2.4/§3.2/§3.3）。

职责：
  1. 用 validate_comparison_spec 在服务入口校验规格与参与方（fail closed，
     绝不静默截取前两家）；
  2. 查询各参与方指标（复用 indicator_query_service.query_metric）；
  3. 共同期间选择：可计算期间集合交集 + 不晚于 as_of 的最新期
     （explicit_period 精确匹配，不 fallback）；
  4. 校验单位；
  5. 程序化计算（Decimal；delta 恒为有符号 A-B，operation 只表达用户
     询问形式，不得覆盖事实方向）；
  6. 返回 structured result（claims/evidence 由 generate_answer 组装）。

不做：不改公司身份、不生成答案、不写 evidence ID。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.state import (
    MAX_MULTI_COMPARISON_PARTICIPANTS,
    ComparisonSpec,
    validate_comparison_spec,
)
from app.application.services.indicator_query_service import (
    IndicatorQueryResult,
    query_metric,
)


class ComparisonValue(BaseModel):
    """单个参与方的指标值（原始值 + 可回查 observation）。"""

    company_code: str
    sec_name: str
    metric_id: str
    metric_label: str
    period: str
    value: Decimal
    unit: str
    observations: list = Field(default_factory=list)


class OverviewMetricRow(BaseModel):
    """概览单指标行（v3.3.4 方案 §3.3）——逐指标状态，不复用单值 difference。"""

    metric_id: str
    metric_label: str
    status: Literal["ok", "insufficient_data", "unsupported"]
    unit: str = ""
    period: str = ""
    values: list[ComparisonValue] = Field(default_factory=list)
    # 恒为 primary - comparison_peer（与单指标比较同一符号约定）
    difference: Decimal | None = None
    difference_unit: str = ""
    conclusion: str = ""
    warnings: list[str] = Field(default_factory=list)


class ComparisonNextStep(BaseModel):
    """v3.3.4 方案 §3.3：结构化下一步导航动作。

    只提供导航（动作类型、主体代码、参数），不改变任何数值、期间、
    主体、证据或结论；主体代码必须来自已校验的 finalized participant。
    """

    kind: Literal[
        "open_full_comparison",
        "open_industry_comparison",
        "open_multi_company_comparison",
        "choose_comparison_pair",
        "compare_metric",
    ]
    label: str
    target: str = ""
    participant_codes: list[str] = Field(default_factory=list)
    params: dict[str, str] = Field(default_factory=dict)


class LightComparisonResult(BaseModel):
    """轻量比较结构化结果。

    comparison_mode：indicator/company_fact/risk 保持旧语义；
    overview 时结果由 overview_rows 承载（participants/difference
    仍服务单指标比较，概览不用空字段表达未执行）。
    """

    status: Literal["ok", "partial", "insufficient_data", "unsupported"]
    scope: str
    operation: str
    participants: list[ComparisonValue] = Field(default_factory=list)
    period: str = ""
    # 恒为有符号 A-B（方案 §2.3），operation 不改变本字段含义
    difference: Decimal | None = None
    difference_unit: str = ""
    conclusion: str = ""
    warnings: list[str] = Field(default_factory=list)
    # v3.3.4 方案 §3.3：比较模式与概览行（向后兼容：默认 indicator）
    comparison_mode: str = "indicator"
    overview_rows: list[OverviewMetricRow] = Field(default_factory=list)
    # v3.3.4 Preview First（方案 §3.3）：用户请求范围与结构化下一步
    requested_scope: Literal[
        "indicator", "overview", "risk", "company_fact", "full", "industry"
    ] = "indicator"
    next_steps: list[ComparisonNextStep] = Field(default_factory=list)


# v3.3.4 方案 §3.2：概览固定指标 profile（服务端注入，禁止用户/LLM 提供）。
# 每个 ID 必须属于 indicator_query_service.supported_indicator_ids()
# （registry 指标 ∪ 基础指标 ∪ 单字段基础指标 _growth），不得复制新公式；
# 不混入风险等级/行业分位/行情类未接入数据。
OVERVIEW_METRIC_IDS: tuple[str, ...] = (
    "operating_revenue_growth",
    "r5_gross_margin",
    "r4_turnover_days",
    "debt_to_assets",
    "operating_cash_flow",
)

# v3.3.4 方案 §6.1：next_steps 跳转目标（前端真实路由 /compare，
# App.tsx:18；行业对比页尚未实现，暂以 params 区分并标记 [推断]）。
_FULL_COMPARISON_TARGET = "/compare"


def build_preview_next_steps(
    requested_scope: str,
    participant_codes: list[str],
) -> list[ComparisonNextStep]:
    """两家已确认比较的结构化下一步（v3.3.4 方案 §6.1）。

    - full/overview/indicator/risk/company_fact → open_full_comparison；
    - industry → open_industry_comparison（行业分位由页面承载，对话不执行）。
    只提供导航动作；主体代码直接使用已校验的 finalized codes（去重保序），
    不改变任何数值、期间、证据或结论。
    """
    codes = list(dict.fromkeys(str(c) for c in participant_codes if str(c)))
    if not codes:
        return []
    if requested_scope == "industry":
        return [
            ComparisonNextStep(
                kind="open_industry_comparison",
                label="查看行业对比",
                target=_FULL_COMPARISON_TARGET,
                participant_codes=codes,
                params={"scope": "industry"},
            )
        ]
    return [
        ComparisonNextStep(
            kind="open_full_comparison",
            label="查看完整对比",
            target=_FULL_COMPARISON_TARGET,
            participant_codes=codes,
        )
    ]


def build_multi_company_next_steps(
    participant_codes: list[str],
    *,
    multi_page_enabled: bool,
    cap: int = MAX_MULTI_COMPARISON_PARTICIPANTS,
) -> list[ComparisonNextStep]:
    """三家及以上保底下一步（v3.3.4 方案 §2.4/§6.1）：不查询、不截断。

    - 超过 cap → 空列表（调用方负责文案要求缩小范围，不携带任何代码，
      不传入部分主体、不默认选择）；
    - 页面支持多主体 → open_multi_company_comparison（全部去重代码）；
    - 否则 → choose_comparison_pair（让用户明确选择两家）。
    """
    codes = list(dict.fromkeys(str(c) for c in participant_codes if str(c)))
    if not codes or len(codes) > cap:
        return []
    if multi_page_enabled:
        return [
            ComparisonNextStep(
                kind="open_multi_company_comparison",
                label="多公司对比",
                target=_FULL_COMPARISON_TARGET,
                participant_codes=codes,
            )
        ]
    return [
        ComparisonNextStep(
            kind="choose_comparison_pair",
            label="选择两家对比",
            target=_FULL_COMPARISON_TARGET,
            participant_codes=codes,
        )
    ]


def _unit_category(unit: str) -> str:
    """单位类别：比例/金额/天数，跨类不得计算差值。"""
    if unit in ("percent", "ratio", "pp"):
        return "ratio"
    if unit == "CNY":
        return "amount"
    if unit == "days":
        return "days"
    return "other"


def _difference_unit(unit: str) -> str:
    if unit in ("percent", "ratio", "pp"):
        return "个百分点"
    if unit == "CNY":
        return "元"
    if unit == "days":
        return "天"
    return ""


def _format_value(value: Decimal, unit: str) -> str:
    if unit in ("percent", "ratio", "pp"):
        return f"{value:.2f}%"
    if unit == "days":
        return f"{value:.2f}天"
    return f"{value:,.2f}"


def _resolve_common_period(
    results: list[IndicatorQueryResult],
    *,
    period_policy: str,
    as_of: str,
) -> tuple[str, list[str]]:
    """共同期间选择（方案 §3.3）。

    - 可计算期间集合（available_periods）取交集；
    - explicit_period：目标期必须精确在交集中，否则空（不 fallback）；
    - latest_common_period：交集中不晚于 as_of 的最新期
      （available_periods 已由 fetch as_of 过滤）。
    返回 (target, common 升序列表)。
    """
    avail_sets = [set(r.available_periods or []) for r in results]
    if not avail_sets or any(not s for s in avail_sets):
        return "", []
    common = sorted(set.intersection(*avail_sets))
    if period_policy == "explicit_period":
        return (as_of if as_of in common else ""), common
    return (common[-1] if common else ""), common


def _direction_text(delta: Decimal, unit: str, operation: str) -> str:
    """有符号 delta 的结论方向（方案 §2.3）。

    operation 只表达用户询问形式；事实方向由 delta 符号决定，
    前提不成立时明确纠正，不得输出反事实结论。
    """
    diff_unit = _difference_unit(unit)
    if delta == 0:
        return "持平"
    if operation == "less_than":
        if delta < 0:
            return f"低 {abs(delta):.2f}{diff_unit}"
        return f"并不低，反而高 {abs(delta):.2f}{diff_unit}"
    if operation == "greater_than":
        if delta > 0:
            return f"高 {abs(delta):.2f}{diff_unit}"
        return f"并不高，反而低 {abs(delta):.2f}{diff_unit}"
    if delta > 0:
        return f"高 {abs(delta):.2f}{diff_unit}"
    return f"低 {abs(delta):.2f}{diff_unit}"


def _comparison_values(
    results: list[IndicatorQueryResult],
    *,
    company_code: str,
    sec_name: str,
) -> list[ComparisonValue]:
    return [
        ComparisonValue(
            company_code=company_code,
            sec_name=sec_name,
            metric_id=r.indicator,
            metric_label=r.label,
            period=r.period,
            value=Decimal(str(r.value)),
            unit=r.unit,
            observations=list(r.observations),
        )
        for r in results
        if r.status == "ok" and r.value is not None
    ]


def compare_same_company_indicators(
    company_code: str,
    sec_name: str,
    spec: ComparisonSpec,
    *,
    as_of: str = "",
) -> LightComparisonResult:
    """同主体两个指标的轻量比较（共同期间交集 + signed delta）。"""
    base = LightComparisonResult(
        status="insufficient_data",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
    )
    issues = validate_comparison_spec(spec, [company_code])
    if issues:
        base.warnings = issues
        return base

    metric_ids = spec.metric_ids
    probe = [query_metric(company_code, mid, as_of=as_of) for mid in metric_ids]
    target, common = _resolve_common_period(
        probe, period_policy=spec.period_policy, as_of=as_of
    )
    if not target:
        base.warnings = [
            f"无共同可计算期间（两侧期间交集 {common or '为空'}），不得跨期相减"
        ]
        return base

    results = [
        query_metric(company_code, mid, as_of=target, require_exact_period=True)
        for mid in metric_ids
    ]
    participants = _comparison_values(
        results, company_code=company_code, sec_name=sec_name
    )
    if len(participants) != 2:
        base.participants = participants
        base.period = participants[0].period if participants else ""
        base.warnings = (
            ["一侧指标数据不可用，仅列可得一侧，不比较高低"]
            if participants
            else ["两侧均无可用数据"]
        )
        if participants:
            base.status = "partial"
        return base

    first, second = participants
    if _unit_category(first.unit) != _unit_category(second.unit):
        base.status = "unsupported"
        base.participants = participants
        base.period = first.period
        base.warnings = [f"单位不兼容（{first.unit} vs {second.unit}），不得直接相减"]
        return base
    if _unit_category(first.unit) not in ("ratio", "amount", "days"):
        base.status = "unsupported"
        base.participants = participants
        base.period = first.period
        base.warnings = [f"暂不支持单位 {first.unit} 的差值比较"]
        return base

    difference = first.value - second.value  # 恒 A-B
    diff_unit = _difference_unit(first.unit)
    diff_text = _direction_text(difference, first.unit, spec.operation)
    conclusion = (
        f"{first.metric_label}（{_format_value(first.value, first.unit)}）比"
        f"{second.metric_label}（{_format_value(second.value, second.unit)}）"
        f"{diff_text}（共同期间 {first.period}，母公司口径）"
    )

    return LightComparisonResult(
        status="ok",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
        participants=participants,
        period=first.period,
        difference=difference,
        difference_unit=diff_unit,
        conclusion=conclusion,
    )


def compare_cross_company_indicators(
    participants,
    spec: ComparisonSpec,
    *,
    as_of: str = "",
) -> LightComparisonResult:
    """双公司单指标轻量比较。

    恰好两家不同公司（validate 保证）；三家/重复/不足两家 fail closed，
    不静默截取；delta 恒 A-B；问句前提不成立时纠正。
    """
    base = LightComparisonResult(
        status="insufficient_data",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
    )
    codes = sorted(
        {str(p.wind_code) for p in participants if getattr(p, "wind_code", "")}
    )
    issues = validate_comparison_spec(spec, codes)
    if issues:
        base.warnings = issues
        return base

    # 去重后的恰好两家（validate 已保证；保原文顺序）
    distinct: list = []
    seen: set[str] = set()
    for p in participants:
        c = str(getattr(p, "wind_code", "") or "")
        if c and c not in seen:
            seen.add(c)
            distinct.append(p)

    metric_id = spec.metric_ids[0]
    codes_ordered = [str(p.wind_code) for p in distinct]
    probe = [query_metric(c, metric_id, as_of=as_of) for c in codes_ordered]
    target, common = _resolve_common_period(
        probe, period_policy=spec.period_policy, as_of=as_of
    )
    if not target:
        base.warnings = [
            f"双方无共同可计算期间（交集 {common or '为空'}），不得跨期相减"
        ]
        return base

    results = [
        query_metric(c, metric_id, as_of=target, require_exact_period=True)
        for c in codes_ordered
    ]
    values = [
        ComparisonValue(
            company_code=str(p.wind_code),
            sec_name=str(getattr(p, "sec_name", "") or ""),
            metric_id=r.indicator,
            metric_label=r.label,
            period=r.period,
            value=Decimal(str(r.value)),
            unit=r.unit,
            observations=list(r.observations),
        )
        for p, r in zip(distinct, results)
        if r.status == "ok" and r.value is not None
    ]
    if len(values) != 2:
        base.participants = values
        base.period = values[0].period if values else ""
        base.warnings = (
            ["仅一侧指标数据可用，不比较高低"] if values else ["双方均无可用数据"]
        )
        if values:
            base.status = "partial"
        return base

    first, second = values
    difference = first.value - second.value  # 恒 A-B（方案 §2.3）
    diff_unit = _difference_unit(first.unit)
    diff_text = _direction_text(difference, first.unit, spec.operation)
    conclusion = (
        f"{first.sec_name}（{first.company_code}）{first.metric_label}为"
        f"{_format_value(first.value, first.unit)}；"
        f"{second.sec_name}（{second.company_code}）为"
        f"{_format_value(second.value, second.unit)}。"
        f"{first.metric_label}：{first.sec_name}比{second.sec_name}"
        f"{diff_text}（共同期间 {first.period}，母公司口径）"
    )

    return LightComparisonResult(
        status="ok",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
        participants=values,
        period=first.period,
        difference=difference,
        difference_unit=diff_unit,
        conclusion=conclusion,
    )


def _parse_listing_date(text: str):
    """解析 'YYYY-MM-DD' 上市日期 → date；解析失败返回 None。"""
    from datetime import date as _date

    try:
        return _date.fromisoformat(text[:10])
    except ValueError:
        return None


def _overview_supported_ids() -> frozenset[str]:
    """概览 profile 白名单：仅接受 indicator_query_service 支持的 canonical ID。"""
    from app.application.services.indicator_query_service import (
        supported_indicator_ids,
    )

    return supported_indicator_ids()


def _overview_row_for_metric(
    distinct: list,
    metric_id: str,
    spec: ComparisonSpec,
    as_of: str,
) -> OverviewMetricRow:
    """概览单指标行（v3.3.4 方案 §5.1/§5.2）。

    共同期间取双方 available_periods 交集（explicit 精确匹配不
    fallback）；双方 exact 重查同期间、单位一致才计算差值；
    报表口径由 fetch 契约固定母公司（PARENT_STATEMENT_SCOPE），
    结构上不存在跨口径值。任一侧缺失只影响本行。
    """
    label = metric_id
    row = OverviewMetricRow(
        metric_id=metric_id,
        metric_label=label,
        status="insufficient_data",
    )
    if metric_id not in _overview_supported_ids():
        row.status = "unsupported"
        row.warnings = [f"指标 {metric_id} 不在受支持集合，跳过该维度"]
        return row

    codes_ordered = [str(p.wind_code) for p in distinct]
    probe = [query_metric(c, metric_id, as_of=as_of) for c in codes_ordered]
    labels = {r.label for r in probe if r.label}
    if labels:
        label = next(iter(labels))
    row.metric_label = label

    target, common = _resolve_common_period(
        probe, period_policy=spec.period_policy, as_of=as_of
    )
    if not target:
        row.warnings = [f"双方无共同可计算期间（交集 {common or '为空'}），不跨期比较"]
        return row

    results = [
        query_metric(c, metric_id, as_of=target, require_exact_period=True)
        for c in codes_ordered
    ]
    values = [
        ComparisonValue(
            company_code=str(p.wind_code),
            sec_name=str(getattr(p, "sec_name", "") or ""),
            metric_id=metric_id,
            metric_label=r.label,
            period=r.period,
            value=Decimal(str(r.value)),
            unit=r.unit,
            observations=list(r.observations),
        )
        for p, r in zip(distinct, results)
        if r.status == "ok" and r.value is not None and r.period == target
    ]
    if len(values) != 2:
        missing = [
            str(getattr(p, "sec_name", "") or "")
            for p, r in zip(distinct, results)
            if not (r.status == "ok" and r.value is not None and r.period == target)
        ]
        row.values = values
        row.warnings = [f"{'、'.join(missing) or '一侧'}数据不足，本维度不比较"]
        return row

    first, second = values
    if first.unit != second.unit or _unit_category(first.unit) != _unit_category(
        second.unit
    ):
        row.values = values
        row.period = first.period
        row.warnings = [f"双方单位不一致（{first.unit} vs {second.unit}），不计算差值"]
        return row

    difference = first.value - second.value  # 恒 primary - peer
    diff_unit = _difference_unit(first.unit)
    diff_text = _direction_text(difference, first.unit, "difference")
    return OverviewMetricRow(
        metric_id=metric_id,
        metric_label=label,
        status="ok",
        unit=first.unit,
        period=first.period,
        values=values,
        difference=difference,
        difference_unit=diff_unit,
        conclusion=f"{first.sec_name}比{second.sec_name}{diff_text}",
    )


def compare_cross_company_overview(
    participants,
    spec: ComparisonSpec,
    *,
    as_of: str = "",
) -> LightComparisonResult:
    """双公司轻量整体概览（v3.3.4 方案 §3/§5）。

    固定 OVERVIEW_METRIC_IDS 逐指标比较（服务端 profile，禁止用户/
    LLM 提供指标列表）；每个指标独立取共同期间、exact 重查与单位
    校验；任一维度缺失只标该行，不影响其他行；不生成综合评分、
    总排名或「整体谁更好」结论；成功行 < 2 → partial/insufficient。
    """
    base = LightComparisonResult(
        status="insufficient_data",
        scope=spec.scope,
        operation=spec.operation,
        comparison_mode="overview",
        requested_scope=spec.requested_scope,
    )
    codes = sorted(
        {str(p.wind_code) for p in participants if getattr(p, "wind_code", "")}
    )
    issues = validate_comparison_spec(spec, codes)
    if issues:
        base.warnings = issues
        return base

    distinct: list = []
    seen: set[str] = set()
    for p in participants:
        c = str(getattr(p, "wind_code", "") or "")
        if c and c not in seen:
            seen.add(c)
            distinct.append(p)

    rows = [
        _overview_row_for_metric(distinct, metric_id, spec, as_of)
        for metric_id in OVERVIEW_METRIC_IDS
    ]
    ok_rows = [r for r in rows if r.status == "ok"]

    lines: list[str] = []
    if ok_rows:
        lines.append(f"已成功比较 {len(ok_rows)}/{len(rows)} 个维度。")
        for r in ok_rows:
            first, second = r.values
            lines.append(
                f"{r.metric_label}：{first.sec_name}"
                f"{_format_value(first.value, r.unit)}；{second.sec_name}"
                f"{_format_value(second.value, r.unit)}；{r.conclusion}"
                f"（共同期间 {r.period}）"
            )
    missing_rows = [r for r in rows if r.status != "ok"]
    if missing_rows:
        names = "、".join(r.metric_label for r in missing_rows)
        lines.append(f"{names}因数据不足或期间不一致无法比较。")
    if ok_rows:
        lines.append(
            "以上为轻量概览，仅覆盖可比维度，不构成整体优劣判断；"
            "可继续指定单项指标或风险等级比较，全面维度请使用跨公司页面。"
        )

    if len(ok_rows) >= 2:
        status = "ok"
    elif ok_rows:
        status = "partial"
    else:
        status = "insufficient_data"

    return LightComparisonResult(
        status=status,
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
        participants=[],
        period="",
        difference=None,
        difference_unit="",
        conclusion="\n".join(lines),
        warnings=(
            []
            if ok_rows
            else ["全部维度均无可比较数据，仅如实披露缺失，不做整体高低判断"]
        ),
        comparison_mode="overview",
        overview_rows=rows,
    )


def compare_cross_company_risk(
    participants,
    spec: ComparisonSpec,
    *,
    as_of: str = "",
) -> LightComparisonResult:
    """两家公司窄风险比较（v3.3.3 收口批次 D，方案 §3.7/§5 D1/D2）。

    一期口径：两家公司最新风险评估记录（同 rule_version 与
    dataset_version 才可比），按 risk_assessments.level 表契约
    （none/low/medium/high/critical，domain/risk/assessment_levels）
    排序回答「谁风险更高」；任一侧无记录/等级未知/口径不一致 →
    partial，不猜测。不把等级差换算成「高多少分」；触发信号详情
    不在此伪造（页面）。

    as_of 契约（方案 §5 D2，竞赛窗口选择「暂不支持历史风险比较」）：
    显式历史截止期下返回 unsupported 并说明「当前仅支持最新风险
    评估」，不得静默读取截止期之后的最新记录。
    """
    from app.application.services.indicator_query_service import (
        query_latest_risk_assessment,
    )
    from app.domain.risk.assessment_levels import (
        RISK_LEVEL_LABELS,
        RISK_LEVEL_ORDER,
    )

    base = LightComparisonResult(
        status="insufficient_data",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
    )
    codes = sorted(
        {str(p.wind_code) for p in participants if getattr(p, "wind_code", "")}
    )
    issues = validate_comparison_spec(spec, codes)
    if issues:
        base.warnings = issues
        return base
    if as_of:
        # 方案 §5 D2：显式历史截止期 → 明确拒绝，不静默取最新记录
        base.status = "unsupported"
        base.warnings = [
            f"暂不支持按截止期（as_of={as_of}）的历史风险比较；"
            "当前仅支持最新风险评估"
        ]
        return base

    distinct: list = []
    seen: set[str] = set()
    for p in participants:
        c = str(getattr(p, "wind_code", "") or "")
        if c and c not in seen:
            seen.add(c)
            distinct.append(p)

    assessments = {
        str(p.wind_code): query_latest_risk_assessment(str(p.wind_code))
        for p in distinct
    }
    missing = [
        str(getattr(p, "sec_name", "") or "")
        for p in distinct
        if assessments.get(str(p.wind_code)) is None
    ]
    if missing:
        base.status = "partial"
        base.warnings = [f"{'、'.join(missing)}无风险评估记录，无法比较风险高低"]
        return base

    first, second = distinct[0], distinct[1]
    a = assessments[str(first.wind_code)]
    b = assessments[str(second.wind_code)]
    if (a["rule_version"], a["dataset_version"]) != (
        b["rule_version"],
        b["dataset_version"],
    ):
        base.status = "partial"
        base.warnings = ["两侧风险评估口径不一致（规则集/数据版本不同），无法比较"]
        return base

    order_a = RISK_LEVEL_ORDER.get(a["level"], -1)
    order_b = RISK_LEVEL_ORDER.get(b["level"], -1)
    if order_a < 0 or order_b < 0:
        base.status = "partial"
        base.warnings = ["一侧风险等级未知，无法比较"]
        return base

    label_a = RISK_LEVEL_LABELS.get(a["level"], a["level"])
    label_b = RISK_LEVEL_LABELS.get(b["level"], b["level"])
    if order_a > order_b:
        relation = f"高于{second.sec_name}的「{label_b}」"
    elif order_a < order_b:
        relation = f"低于{second.sec_name}的「{label_b}」"
    else:
        relation = f"与{second.sec_name}持平（同为「{label_b}」）"
    conclusion = (
        f"{first.sec_name}（{first.wind_code}）最新综合风险等级为"
        f"「{label_a}」，{relation}（评估口径：规则集 {a['rule_version']}，"
        f"数据 {a['dataset_version']}）。触发信号详情请使用页面跨公司对比。"
    )
    return LightComparisonResult(
        status="ok",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
        participants=[],
        period="",
        difference=None,
        difference_unit="",
        conclusion=conclusion,
    )


def compare_cross_company_facts(
    participants,
    spec: ComparisonSpec,
) -> LightComparisonResult:
    """双公司公司事实轻量比较（listing_date；恰好两家 fail closed）。"""
    base = LightComparisonResult(
        status="insufficient_data",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
    )
    codes = sorted(
        {str(p.wind_code) for p in participants if getattr(p, "wind_code", "")}
    )
    issues = validate_comparison_spec(spec, codes)
    if issues:
        base.warnings = issues
        return base
    if spec.fact_key != "listing_date":
        base.status = "unsupported"
        base.warnings = [f"暂不支持事实 {spec.fact_key} 的比较"]
        return base

    distinct: list = []
    seen: set[str] = set()
    for p in participants:
        c = str(getattr(p, "wind_code", "") or "")
        if c and c not in seen:
            seen.add(c)
            distinct.append(p)

    pairs = [
        (p, _parse_listing_date(str(getattr(p, "listing_date", "") or "")))
        for p in distinct
    ]
    missing = [str(getattr(p, "sec_name", "") or "") for p, d in pairs if d is None]
    if missing:
        base.status = "partial"
        base.warnings = [f"{'、'.join(missing)}上市日期数据不可用，不比较先后"]
        return base

    first_p, second_p = distinct[0], distinct[1]
    first_d = next(d for p, d in pairs if p is first_p)
    second_d = next(d for p, d in pairs if p is second_p)
    days = (second_d - first_d).days  # A 比 B 早 → 正数
    years = round(abs(days) / 365.25, 1)
    if days > 0:
        relation = f"早约 {years} 年"
    elif days < 0:
        relation = f"晚约 {years} 年"
    else:
        relation = "同日"
    conclusion = (
        f"{first_p.sec_name}（{first_p.wind_code}）上市日期为"
        f"{first_d.isoformat()}；{second_p.sec_name}（{second_p.wind_code}）"
        f"为{second_d.isoformat()}。{first_p.sec_name}比{second_p.sec_name}"
        f"{relation}上市。"
    )
    return LightComparisonResult(
        status="ok",
        scope=spec.scope,
        operation=spec.operation,
        requested_scope=spec.requested_scope,
        participants=[],
        period="",
        difference=Decimal(days),
        difference_unit="天",
        conclusion=conclusion,
    )
