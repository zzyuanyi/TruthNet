"""L1 严重程度量化服务 — 「多严重」客观数据提示（L0/L1/L2 三层的 L1 补齐）。

答辩叙事「核查导航」：风险点（L0）+ 原因/多严重（L1）+ 核查动作（L2）。
本模块输出 L1 的量化参考（行业分位 / 历史趋势 / 距触发线），
纯确定性渲染、无 LLM，数据缺失时逐句诚实跳过（不硬凑）。

- 分位句：FinanceResult.industry_benchmark.percentiles（rule→metric 映射；
  引擎实际计算 5 个 metric：r1_gap/r2_cf_ratio/r3_cash_to_assets/
  r4_growth_gap/r6_oth_rcv_to_assets，R5/R7 无分位 → 自然跳过）
- 趋势句：rule.history 通用提取（优先主指标同名 key，兜底首个数值 key；
  客观上升/下降 + 连续期数，不加「危险」定性）
- 阈值句：规则主阈值对比（方向表判定「超出/低于」，只并列客观数值）

措辞边界：只给客观数据提示，不做定性（是否造假）、不做预测。
"""

from __future__ import annotations

from app.domain.finance.financial_rule_config import get_rule_config

# 规则 → 行业分位 metric（与 agents/nodes/finance.py `_query_industry_benchmark`
# 实际计算的 metric 一致；缺 R5/R7 表示引擎无对应分位数据）
_RULE_METRICS: dict[str, tuple[str, ...]] = {
    "R1": ("r1_gap",),
    "R2": ("r2_cf_ratio",),
    "R3": ("r3_cash_to_assets", "r3_debt_to_assets"),
    "R4": ("r4_growth_gap",),
    "R6": ("r6_oth_rcv_to_assets",),
}

# 规则 → (阈值键, 主指标 current 键, 主指标中文名, 单位, 风险方向)
# 方向 higher=数值越大越险（超出触发线），lower=越小越险（低于触发线）
_RULE_MAIN_THRESHOLD: dict[str, tuple[str, str, str, str, str]] = {
    "R1": ("orange_gap_pp", "gap", "应收-营收增速差", "pp", "higher"),
    "R2": (
        "orange_cashflow_profit_ratio",
        "cf_to_profit_ratio",
        "现金流/净利润比",
        "比值",
        "lower",
    ),
    "R3": ("dual_high_debt_pct", "debt_to_assets", "有息负债/总资产", "%", "higher"),
    "R4": ("orange_growth_gap_pp", "growth_gap", "存货-营收增速差", "pp", "higher"),
    "R5": (
        "gross_margin_deviation_pct",
        "gm_deviation",
        "毛利率偏离",
        "%",
        "higher",
    ),
    "R6": (
        "orange_assets_ratio_pct",
        "oth_rcv_to_assets",
        "其他应收款/总资产",
        "%",
        "higher",
    ),
    "R7": (
        "quality_divergence_pp",
        "quality_divergence",
        "盈利质量背离",
        "pp",
        "higher",
    ),
}

_SEVERITY_LABELS = {"red": "红色", "orange": "橙色", "yellow": "黄色"}

# 内部单位 → 展示单位（与 _answer_common._METRIC_UNITS 对齐的常用子集）
_UNIT_CN = {
    "percentage_point": "pp",
    "pp": "pp",
    "percent": "%",
    "%": "%",
    "ratio": "比值",
    "days": "天",
    "quarters": "个季度",
    "bool": "",
    "": "",
}


def _fmt_unit(unit: str) -> str:
    return _UNIT_CN.get(unit, unit)


def _fmt(value: float) -> str:
    """数值显示：1 位小数，去掉多余尾零。"""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _percentile_sentences(rule_id: str, percentiles: dict) -> list[str]:
    """分位句：行业分位第 X 百分位（metric 名）。"""
    if not percentiles:
        return []
    from app.domain.benchmarks.metric_registry import all_metrics

    out: list[str] = []
    for metric in all_metrics():
        if metric.rule_id != rule_id:
            continue
        pct = percentiles.get(metric.metric_id)
        if isinstance(pct, (int, float)) and not isinstance(pct, bool):
            out.append(f"行业分位：{metric.name}第 {round(pct)} 百分位")
    return out


def _trend_sentences(rule_id: str, detail: dict) -> list[str]:
    """趋势句：最新 vs 上期 + 连续同向期数（客观方向，不做定性）。"""
    spec = _RULE_MAIN_THRESHOLD.get(rule_id)
    if spec is None:
        return []
    main_key = spec[1]
    history = detail.get("history") or []
    points: list[float] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        v = item.get(main_key)
        if v is None:
            for k, v2 in item.items():
                if k == "period" or not isinstance(v2, (int, float)):
                    continue
                v = v2
                break
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            points.append(float(v))
    if len(points) < 2:
        return []
    latest, prev = points[-1], points[-2]
    unit = ""
    current = detail.get("current") or {}
    cur_meta = (current.get(main_key) or {}) if isinstance(current, dict) else {}
    if isinstance(cur_meta, dict):
        unit = _fmt_unit(str(cur_meta.get("unit") or ""))
    if latest == prev:
        return [f"近 {len(points)} 期最新值 {_fmt(latest)}{unit}，与上期持平"]
    rising = latest > prev
    direction = "上升" if rising else "下降"
    streak = 2
    for i in range(len(points) - 2, 0, -1):
        if (points[i] > points[i - 1]) == rising:
            streak += 1
        else:
            break
    return [
        f"近 {len(points)} 期最新 {_fmt(latest)}{unit}（上期 {_fmt(prev)}{unit}），"
        f"连续 {streak} 期{direction}"
    ]


def _threshold_sentences(rule_id: str, detail: dict, severity: str) -> list[str]:
    """阈值句：当前主指标值 vs 触发线（客观并列 + 超出/低于差值）。"""
    spec = _RULE_MAIN_THRESHOLD.get(rule_id)
    if spec is None:
        return []
    threshold_key, current_key, label, unit, direction = spec
    current = detail.get("current") or {}
    if not isinstance(current, dict):
        return []
    cv = (current.get(current_key) or {}).get("value")
    if not isinstance(cv, (int, float)):
        return []
    config = get_rule_config(rule_id)
    thresholds = getattr(config, "thresholds", None)
    if thresholds is None:
        return []
    th = getattr(thresholds, threshold_key, None)
    if not isinstance(th, (int, float)):
        return []
    delta = round(abs(float(cv) - float(th)), 1)
    over = (float(cv) > float(th)) if direction == "higher" else (float(cv) < float(th))
    over_word = "超出" if over else "低于"
    return [
        f"当前 {label} {_fmt(float(cv))}{unit}，触发线 "
        f"{_fmt(float(th))}{unit}（{over_word} {_fmt(delta)}{unit}）"
    ]


def build_severity_context(
    rule_id: str, detail: dict, percentiles: dict, severity: str = ""
) -> list[str]:
    """组合量化句列表（分位 + 趋势 + 阈值；无数据项自动跳过）。"""
    return [
        *_percentile_sentences(rule_id, percentiles),
        *_trend_sentences(rule_id, detail),
        *_threshold_sentences(rule_id, detail, severity),
    ]


def render_quantified_line(
    rule_id: str, detail: dict, percentiles: dict, severity: str = ""
) -> str:
    """渲染「量化参考：…」单行（无任何量化数据 → 空串，调用方不输出）。"""
    parts = build_severity_context(rule_id, detail, percentiles, severity)
    if not parts:
        return ""
    return "量化参考：" + "；".join(parts) + "。"
