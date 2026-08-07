"""性能计时单元测试 — Phase D #7.

覆盖:
- Timer 可注入时钟，start/stop 返回毫秒
- MetricRecord 结构
- MetricsCollector 记录/快照/清除
- P50/P95/mean 摘要计算
- timed 上下文管理器
- 线程安全并发记录
"""

import threading

from app.infrastructure.observability.timing import (
    MetricRecord,
    MetricsCollector,
    Timer,
)


class _FakeClock:
    """可手动推进的时钟，用于确定性计时。"""

    def __init__(self, start: float = 1000.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def test_timer_injectable_clock():
    clock = _FakeClock()
    t = Timer(clock=clock)
    t.start()
    clock.advance(0.5)  # 500ms
    ms = t.stop()
    assert ms == 500.0


def test_timer_requires_start():
    t = Timer(clock=_FakeClock())
    assert t.stop() == 0.0  # 未 start → 0


def test_timer_context_manager():
    clock = _FakeClock()
    t = Timer(clock=clock)
    with t:
        clock.advance(0.25)
    assert t.stop() == 250.0


def test_metric_record_structure():
    r = MetricRecord(name="x", duration_ms=12.5, trace_id="tr", degraded=True)
    assert r.name == "x"
    assert r.duration_ms == 12.5
    assert r.trace_id == "tr"
    assert r.degraded is True
    assert r.timeout is False


def test_collector_record_and_snapshot():
    c = MetricsCollector()
    c.record("a", 10.0)
    c.record("a", 20.0)
    c.record("b", 5.0)
    assert len(c.snapshot()) == 3
    assert len(c.snapshot("a")) == 2
    assert len(c.snapshot("b")) == 1
    c.clear()
    assert c.snapshot() == []


def test_summary_percentiles():
    c = MetricsCollector()
    # 1..10 均匀分布 → P50≈5, P95≈10
    for i in range(1, 11):
        c.record("m", float(i))
    s = c.summary("m")
    assert s["count"] == 10
    assert s["p50_ms"] == 5.0
    assert s["p95_ms"] == 10.0
    assert s["mean_ms"] == 5.5
    assert s["timeout_count"] == 0
    assert s["degraded_count"] == 0


def test_summary_empty():
    c = MetricsCollector()
    s = c.summary("none")
    assert s["count"] == 0
    assert s["p50_ms"] is None
    assert s["p95_ms"] is None


def test_summary_timeout_degraded():
    c = MetricsCollector()
    c.record("m", 100.0, timeout=True, degraded=True)
    c.record("m", 50.0)
    s = c.summary("m")
    assert s["timeout_count"] == 1
    assert s["degraded_count"] == 1


def test_timed_context():
    clock = _FakeClock()
    c = MetricsCollector()
    with _TimedContextWithClock(c, "op", clock=clock):
        clock.advance(0.3)
    rec = c.snapshot("op")[0]
    assert round(rec.duration_ms, 3) == 300.0
    assert rec.name == "op"


class _TimedContextWithClock:
    """测试用：替换计时器时钟的上下文管理器。"""

    def __init__(self, collector, name, clock):
        self._c = collector
        self._name = name
        self._t = Timer(clock=clock)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._c.record(self._name, self._t.stop())


def test_thread_safe_concurrent_records():
    c = MetricsCollector()
    threads = []

    def worker(i: int):
        for j in range(100):
            c.record(f"t{i}", float(j))

    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(c.snapshot()) == 500
