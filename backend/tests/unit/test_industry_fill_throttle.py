"""有界自适应节流单元测试（档案 v1.1 §6.4 扩展；P0 收口批次）。

验证：并发硬边界 [1, MAX]、限流降并发、稳定成功缓慢恢复、
host 冷却、负载感知 sleep 非负且有下界。
"""

from __future__ import annotations

from backend.app.application.services.industry_fill.constants import (
    MAX_CONCURRENCY,
    MIN_CONCURRENCY,
)
from backend.app.application.services.industry_fill.throttle import (
    RECOVER_EVERY,
    RateController,
)


def _controller(capacity: int = 4) -> RateController:
    return RateController(capacity)


class TestCapacityBounds:
    def test_capacity_clamped_to_hard_bounds(self):
        c = _controller(999)
        assert c.capacity == MAX_CONCURRENCY
        c2 = _controller(-5)
        assert c2.capacity == MIN_CONCURRENCY

    def test_set_capacity_also_clamped(self):
        c = _controller(4)
        c.set_capacity(999)
        assert c.capacity == MAX_CONCURRENCY
        c.set_capacity(-1)
        assert c.capacity == MIN_CONCURRENCY


class TestAdaptive:
    def test_on_throttle_halves_capacity_with_floor(self):
        c = _controller(4)
        c.on_throttle()
        assert c.capacity == 2
        c.on_throttle()
        assert c.capacity == 1  # floor = MIN_CONCURRENCY
        c.on_throttle()
        assert c.capacity == 1  # 不再下降

    def test_success_recovers_capacity_slowly(self):
        c = _controller(8)
        c.on_throttle()  # 8 → 4
        c.on_throttle()  # 4 → 2
        for _ in range(RECOVER_EVERY):  # 每 RECOVER_EVERY 次成功 +1
            c.on_success()
        assert c.capacity == 3
        for _ in range(RECOVER_EVERY):
            c.on_success()
        assert c.capacity == 4

    def test_pressure_tracks_throttle_and_decays_on_success(self):
        c = _controller(4)
        c.on_throttle()
        assert c.pressure == 0.5
        for _ in range(5):
            c.on_success()  # 每次 -0.1
        assert c.pressure == 0.0

    def test_sleep_seconds_respects_pressure_and_never_negative(self):
        c = _controller(4)
        base = 0.05
        s0 = c.sleep_seconds(base)
        assert s0 >= base
        c.on_throttle()
        c.on_throttle()  # pressure = 1.0
        s1 = c.sleep_seconds(base)
        assert s1 >= base * 2.0


class TestHostCooldown:
    def test_three_failures_enters_cooldown(self):
        c = _controller(4)
        host = "push2.eastmoney.com"
        assert c.host_allowed(host)
        assert not c.host_failed(host)
        assert not c.host_failed(host)
        assert c.host_allowed(host)
        assert c.host_failed(host)  # 第三次 → 进入冷却
        assert not c.host_allowed(host)

    def test_host_ok_resets_failure_count(self):
        c = _controller(4)
        host = "82.push2.eastmoney.com"
        c.host_failed(host)
        c.host_failed(host)
        c.host_ok(host)  # 成功清零失败计数
        assert c.host_failed(host) is False  # 重新计数，未达阈值


class TestGate:
    def test_enter_exit_serializes_at_capacity(self):
        c = _controller(2)
        c.enter()
        c.enter()
        assert c.capacity == 2
        c.exit()
        c.exit()
        # 容量释放后可再次进入（不抛错即可）
        c.enter()
        c.exit()

    def test_snapshot_shape(self):
        c = _controller(4)
        snap = c.snapshot()
        assert snap["effective_concurrency"] == 4
        assert "pressure" in snap
