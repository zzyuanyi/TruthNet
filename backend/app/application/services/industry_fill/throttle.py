"""有界自适应请求节流（档案 v1.1 §6.4 扩展；最终收口批次）。

设计目标：数千证券规模下不对上游接口硬顶，限流时主动退让。

  - 并发有严格上下限 [MIN_CONCURRENCY, MAX_CONCURRENCY]；
  - 连续限流/超时 → 并发减半（指数降低）；
  - 稳定成功 → 每 RECOVER_EVERY 次成功并发 +1（缓慢恢复）；
  - 每次查询后 sleep = base_sleep * (1 + pressure) + 抖动；
  - host cooldown：某主机连续失败达到阈值进入冷却窗口，暂时跳过；
  - 所有重试有上限（由调用方 max_retries 决定），禁止无限循环。

线程安全：enter / exit / adjust / sleep / host 状态共用一把 Condition。
"""

from __future__ import annotations

import random
import threading
import time

from backend.app.application.services.industry_fill.constants import (
    MAX_CONCURRENCY,
    MIN_CONCURRENCY,
)

# 连续成功多少次后并发 +1（缓慢恢复，避免抖动回弹）
RECOVER_EVERY = 25
# 压力上界（sleep 放大系数：base * (1 + pressure)，pressure ∈ [0, 3]）
PRESSURE_MAX = 3.0
# host 连续失败多少次进入冷却；冷却窗口秒数
HOST_FAIL_LIMIT = 3
HOST_COOLDOWN_SECONDS = 30.0


def _now() -> float:
    return time.monotonic()


class RateController:
    """自适应并发闸门 + host 冷却 + 负载感知 sleep。"""

    def __init__(self, capacity: int, *, max_concurrency: int = MAX_CONCURRENCY):
        self._min = MIN_CONCURRENCY
        self._max_capacity = max(max_concurrency, MIN_CONCURRENCY)
        self._capacity = max(self._min, min(capacity, self._max_capacity))
        self._cv = threading.Condition()
        self._active = 0
        self._consecutive_ok = 0
        self._pressure = 0.0
        self._host_failures: dict[str, int] = {}
        self._host_cooldown_until: dict[str, float] = {}

    # ── 并发闸门 ─────────────────────────────────────────
    def enter(self) -> None:
        with self._cv:
            while self._active >= self._capacity:
                self._cv.wait()
            self._active += 1

    def exit(self) -> None:
        with self._cv:
            self._active -= 1
            self._cv.notify()

    @property
    def capacity(self) -> int:
        with self._cv:
            return self._capacity

    @property
    def pressure(self) -> float:
        with self._cv:
            return self._pressure

    def set_capacity(self, capacity: int) -> None:
        """设置并发，并把恢复上限也钳制为调用方请求值（--concurrency 即天花板）。

        若不改 _max_capacity，稳定成功后 on_success 会一路回升到构造默认的
        MAX_CONCURRENCY=8，静默越过用户显式设定的并发（对抗审查 B）。
        此处把两者都钳到 [min, MAX_CONCURRENCY]；notify 唤醒等待线程。
        """
        with self._cv:
            ceiling = max(self._min, min(capacity, MAX_CONCURRENCY))
            self._max_capacity = ceiling
            self._capacity = max(self._min, min(capacity, self._max_capacity))
            self._cv.notify_all()

    # ── 负载自适应 ───────────────────────────────────────
    def on_throttle(self) -> None:
        """连续限流/超时：并发减半（指数降低）、压力上升。"""
        with self._cv:
            self._consecutive_ok = 0
            self._capacity = max(self._min, self._capacity // 2)
            self._pressure = min(PRESSURE_MAX, self._pressure + 0.5)
            self._cv.notify_all()

    def on_success(self) -> None:
        """稳定成功：压力衰减；每 RECOVER_EVERY 次成功并发 +1。"""
        with self._cv:
            self._consecutive_ok += 1
            # round 消除浮点残差（0.5 - 5×0.1 ≠ 精确 0.0）
            self._pressure = max(0.0, round(self._pressure - 0.1, 6))
            if (
                self._consecutive_ok >= RECOVER_EVERY
                and self._capacity < self._max_capacity
            ):
                self._capacity += 1
                self._consecutive_ok = 0
            self._cv.notify_all()

    def sleep_seconds(self, base_sleep: float) -> float:
        """负载感知请求间隔：base * (1 + pressure) + 有限抖动。"""
        with self._cv:
            return base_sleep * (1.0 + self._pressure) + random.uniform(
                0, max(0.001, base_sleep * 0.5)
            )

    # ── host 冷却 ────────────────────────────────────────
    def host_allowed(self, host: str) -> bool:
        with self._cv:
            return self._host_cooldown_until.get(host, 0.0) <= _now()

    def host_failed(self, host: str) -> bool:
        """记录主机失败；达到阈值进入冷却并清零计数。返回是否已进入冷却。"""
        with self._cv:
            n = self._host_failures.get(host, 0) + 1
            if n >= HOST_FAIL_LIMIT:
                self._host_cooldown_until[host] = _now() + HOST_COOLDOWN_SECONDS
                self._host_failures[host] = 0
                return True
            self._host_failures[host] = n
            return False

    def host_ok(self, host: str) -> None:
        with self._cv:
            self._host_failures[host] = 0

    # ── 报告 ─────────────────────────────────────────────
    def snapshot(self) -> dict:
        with self._cv:
            return {
                "effective_concurrency": self._capacity,
                "pressure": round(self._pressure, 2),
            }
