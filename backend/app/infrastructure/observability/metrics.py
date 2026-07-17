"""指标 — V12 baseline (骨架).

TODO: 接入 Prometheus / OpenTelemetry。
"""


class MetricsCollector:
    """指标收集器 (骨架)."""

    def __init__(self):
        self._counters: dict[str, int] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """增加计数器."""
        self._counters[name] = self._counters.get(name, 0) + value

    def get(self, name: str) -> int:
        """获取计数器."""
        return self._counters.get(name, 0)
