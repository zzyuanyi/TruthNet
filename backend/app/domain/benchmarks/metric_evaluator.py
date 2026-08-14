"""按报告期对齐的指标评估器 — v3.3.3 收口整改批次 A（方案 §2.1/§3.1）。

统一入口：把各字段的 (period, value) 序列转换为按报告期对齐的窗口，
逐期计算指标值。生产短答（indicator_query_service）与行业 benchmark
（benchmarks/calculator.py）共用同一评估器，禁止用裸列表下标代表
报告期（错期事实 P0）。

对齐不变量（方案 §2.1）：
  - 每个计算期 t 的窗口 = 各字段在 <= t 的最近 metric.periods 期，
    且所有字段窗口末期为 t（t 期输入完整才计算）；
  - 结果期、observation 期与输入窗口末期必须一致；
  - 公式返回 None 的期次不计入可计算期间集合。
"""

from __future__ import annotations

from typing import Callable


def evaluate_metric_per_period(
    metric,
    sequences: dict[str, list[tuple[str, float | None]]],
) -> list[tuple[str, float]]:
    """逐期计算指标值，返回 [(period, value)] 升序。

    metric: MetricSpec（compute_from_aligned 优先，兼容
            compute_from_series 旧纯函数）。
    sequences: {field: [(report_period, value)]}（任意顺序，内部排序）。
    """
    field_maps: dict[str, dict[str, float | None]] = {
        field: {str(p): v for p, v in pairs if str(p)}
        for field, pairs in sequences.items()
    }
    periods = sorted({p for fmap in field_maps.values() for p in fmap})
    results: list[tuple[str, float]] = []
    for target in periods:
        aligned_window: dict[str, dict[str, float | None]] = {}
        legacy_window: dict[str, list] = {}
        complete = True
        for field in metric.fields:
            fmap = field_maps[field]
            if target not in fmap:
                complete = False
                break
            up_to = sorted(p for p in fmap if p <= target)[-metric.periods :]
            aligned_window[field] = {p: fmap[p] for p in up_to}
            legacy_window[field] = [fmap[p] for p in up_to]
        if not complete:
            continue
        compute: Callable | None = getattr(metric, "compute_from_aligned", None)
        if compute is not None:
            value = compute(aligned_window)
        else:
            value = metric.compute_from_series(legacy_window)
        if value is not None:
            results.append((target, value))
    return results


def aligned_inputs_for_period(
    sequences: dict[str, list[tuple[str, float | None]]],
    period: str,
    window: int,
) -> dict[str, dict[str, float | None]]:
    """构造目标期窗口（供 observation/诊断使用）。

    返回 {field: {p: value}}：各字段 <= period 的最近 window 期；
    字段缺目标期时该字段为空 dict（调用方判定 incomplete）。
    """
    out: dict[str, dict[str, float | None]] = {}
    for field, pairs in sequences.items():
        fmap = {str(p): v for p, v in pairs if str(p)}
        if period not in fmap:
            out[field] = {}
            continue
        up_to = sorted(p for p in fmap if p <= period)[-window:]
        out[field] = {p: fmap[p] for p in up_to}
    return out
