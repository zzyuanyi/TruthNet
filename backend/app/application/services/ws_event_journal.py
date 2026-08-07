"""WsEventJournal — Phase D #6 断线重连事件缓冲.

按逻辑会话（session_id）缓存已发送事件，断线后经 stream.resume 补发：
  - sequence 生命周期绑定 session，不随 socket 重连重置；
  - 补发使用原 event_id / sequence / turn_id，不重新生成事件 ID；
  - 有最大事件数与 TTL，数值来自配置（内存受限）；
  - 并发访问安全（asyncio 单事件循环下 append/read 均为同步临界区）。

设计约束（Phase D 契约冻结）:
  - replay 不重复、顺序严格递增；
  - 请求序号早于缓存起点 → gap=True（可恢复断档）。
"""

from __future__ import annotations

import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)


class WsEventJournal:
    """会话级事件缓冲.

    每 session 一个 journal 实例；所有操作线程安全
    （多 WS 连接可能同时访问同一 session）。
    """

    def __init__(
        self,
        *,
        max_events: int | None = None,
        ttl_seconds: float | None = None,
        clock=None,
    ) -> None:
        self._max_events = max_events or settings.WS_EVENT_BUFFER_MAX_EVENTS
        self._ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else float(settings.WS_EVENT_BUFFER_TTL_SECONDS)
        )
        self._clock = clock or _real_clock
        self._events: list[dict] = []  # 升序，每个含 sequence 与 sent_at
        self._lock = threading.Lock()
        self._closed = False

    # ── 写入 ──────────────────────────────────────────────

    def append(self, event: dict) -> None:
        """追加事件到缓冲（尾部）。

        event 必须是完整九字段信封（含 sequence / event_id / event_type /
        session_id / turn_id / timestamp / trace_id / payload）。
        事件序号必须严格递增；重复 sequence 被拒绝（防乱序）。
        """
        if self._closed:
            return
        seq = event.get("sequence")
        with self._lock:
            if self._events and seq is not None:
                last = self._events[-1].get("sequence")
                if last is not None and seq <= last:
                    logger.warning(
                        "WsEventJournal: 拒绝非递增序号 seq=%s (last=%s)", seq, last
                    )
                    return
            stamped = dict(event)
            stamped.setdefault("_sent_at", self._clock())
            self._events.append(stamped)
            # 内存受限：超出上限丢弃最旧事件（gap 起点随之前移）
            if len(self._events) > self._max_events:
                overflow = len(self._events) - self._max_events
                del self._events[:overflow]

    # ── 读取 ──────────────────────────────────────────────

    def events_after(self, sequence: int) -> list[dict]:
        """返回所有 sequence > sequence 的事件（升序，原样返回）。

        不修改缓冲，不重新生成 event_id。
        """
        with self._lock:
            return [
                _strip_internal(e)
                for e in self._events
                if e.get("sequence", 0) > sequence
            ]

    def events_between(self, start: int, end: int) -> list[dict]:
        """返回 start < sequence <= end 的事件（供测试断言）。"""
        with self._lock:
            return [
                _strip_internal(e)
                for e in self._events
                if start < e.get("sequence", 0) <= end
            ]

    def earliest_sequence(self) -> int | None:
        """缓冲内最小序号；空缓冲返回 None."""
        with self._lock:
            return self._events[0].get("sequence") if self._events else None

    def latest_sequence(self) -> int | None:
        """缓冲内最大序号；空缓冲返回 None."""
        with self._lock:
            return self._events[-1].get("sequence") if self._events else None

    def count(self) -> int:
        """当前缓冲事件数（含内部标记）。"""
        with self._lock:
            return len(self._events)

    def is_gap(self, sequence: int) -> bool:
        """请求序号早于缓存起点 → 发生不可恢复断档。

        请求序号大于等于缓存起点则说明客户端从缓存起点即可完整补发。
        """
        with self._lock:
            earliest = self._events[0].get("sequence") if self._events else None
            if earliest is None:
                # 空缓冲：无事件可补发（客户端请求序号无意义）
                return True
            return sequence < earliest - 1

    # ── 维护 ──────────────────────────────────────────────

    def expire(self) -> int:
        """清除超过 TTL 的旧事件，返回清除数。"""
        now = self._clock()
        with self._lock:
            keep = []
            expired = 0
            for e in self._events:
                if now - e.get("_sent_at", 0) > self._ttl:
                    expired += 1
                else:
                    keep.append(e)
            self._events = keep
            return expired

    def clear(self) -> None:
        """清空缓冲（会话销毁时调用）。"""
        with self._lock:
            self._events = []

    def close(self) -> None:
        """标记关闭并清空。"""
        self.clear()
        self._closed = True

    def __len__(self) -> int:
        return self.count()


def _real_clock() -> float:
    import time

    return time.time()


def _strip_internal(event: dict) -> dict:
    """去掉内部标记字段（_sent_at），返回对外一致的事件。"""
    return {k: v for k, v in event.items() if not k.startswith("_")}
