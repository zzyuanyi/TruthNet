"""轻量性能计时 — Phase D #7.

提供可注入时钟的 Timer / MetricRecord / MetricsCollector：
  - 不引入 Prometheus/OpenTelemetry 重型依赖；
  - 计时使用 time.perf_counter（默认时钟可注入，便于确定性测试）；
  - 采集结果可通过结构化日志输出或内部快照读取；
  - 不记录用户完整问题、不把 session_id/turn_id 作为高基数 label。

约束：
  - 单一职责：只计时与聚合，不做业务；
  - 线程安全：REST 线程池 + WS 事件循环 + 后台报告任务均可能并发写入。
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

Clock = Callable[[], float]


def _perf_clock() -> float:
    return time.perf_counter()


class Timer:
    """可注入时钟的秒表."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or _perf_clock
        self._start: float | None = None

    def start(self) -> "Timer":
        self._start = self._clock()
        return self

    def stop(self) -> float:
        """返回经过毫秒；未 start 时返回 0。"""
        if self._start is None:
            return 0.0
        return (self._clock() - self._start) * 1000.0

    def __enter__(self) -> "Timer":
        return self.start()

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.stop()


@dataclass
class MetricRecord:
    """单条计时记录."""

    name: str  # 指标名，如 search.total_ms / rest.total_ms / ws.first_delta_ms
    duration_ms: float
    trace_id: str = ""
    degraded: bool = False
    timeout: bool = False
    extra: dict = field(default_factory=dict)


class MetricsCollector:
    """线程安全的计时采集器（进程内快照，供 smoke 与结构化日志）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[MetricRecord] = []

    def record(
        self,
        name: str,
        duration_ms: float,
        *,
        trace_id: str = "",
        degraded: bool = False,
        timeout: bool = False,
        **extra,
    ) -> None:
        """记录一条计时。"""
        rec = MetricRecord(
            name=name,
            duration_ms=duration_ms,
            trace_id=trace_id,
            degraded=degraded,
            timeout=timeout,
            extra=extra,
        )
        with self._lock:
            self._records.append(rec)

    def timed(self, name: str, **kwargs):
        """上下文管理器：with collector.timed('search.total'): ..."""
        return _TimedContext(self, name, **kwargs)

    def snapshot(self, name: str | None = None) -> list[MetricRecord]:
        """返回匹配指标名的快照（拷贝，线程安全）。"""
        with self._lock:
            if name is None:
                return list(self._records)
            return [r for r in self._records if r.name == name]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    # ── 汇总 ──────────────────────────────────────────────

    def summary(self, name: str) -> dict:
        """P50/P95/count/timeout/degraded 摘要（供 smoke 与报告）。"""
        recs = self.snapshot(name)
        if not recs:
            return {
                "metric": name,
                "count": 0,
                "p50_ms": None,
                "p95_ms": None,
                "mean_ms": None,
                "timeout_count": 0,
                "degraded_count": 0,
            }
        vals = sorted(r.duration_ms for r in recs)
        return {
            "metric": name,
            "count": len(vals),
            "p50_ms": _percentile(vals, 0.50),
            "p95_ms": _percentile(vals, 0.95),
            "mean_ms": round(sum(vals) / len(vals), 3),
            "timeout_count": sum(1 for r in recs if r.timeout),
            "degraded_count": sum(1 for r in recs if r.degraded),
        }

    def all_summaries(self) -> dict[str, dict]:
        """全部指标名 → 摘要。"""
        names = {r.name for r in self.snapshot()}
        return {n: self.summary(n) for n in sorted(names)}


class _TimedContext:
    """with collector.timed(...) 上下文管理器."""

    def __init__(self, collector: MetricsCollector, name: str, **kwargs) -> None:
        self._c = collector
        self._name = name
        self._kw = kwargs
        self._t = Timer()

    def __enter__(self) -> "_TimedContext":
        self._t.start()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self._c.record(self._name, self._t.stop(), **self._kw)


def _percentile(values: list[float], q: float) -> float:
    """线性插值分位（nearest-rank 简化：排序后按索引）。"""
    if not values:
        return 0.0
    idx = min(len(values) - 1, int(math.ceil(q * len(values))) - 1)
    return round(values[idx], 3)


# 进程内全局采集器（供埋点与 smoke 读取）
metrics_collector = MetricsCollector()
