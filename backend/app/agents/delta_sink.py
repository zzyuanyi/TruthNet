"""answer.delta 真流式 sink 注册表 — Phase D #10.

generate_answer 是同步 graph 节点（在 LangGraph 内部线程执行），无法直接 await。
WsTurnRunner 在启动 turn 前注册一个按 turn_id 索引的线程安全 sink；
generate_answer 在构造四层回答的每个真实分段时，把分段文本 push 到该 sink，
由 WsTurnRunner 在事件循环内转成 answer.delta 事件发送。

设计要点:
  - 按 turn_id 隔离，多会话并发不串扰；
  - 线程安全（queue.Queue），graph 内部线程 push，事件循环 pop；
  - 无 sink 时（REST / 非流式）零开销（generate_answer 原样走模板+润色）；
  - 铁律：分段必须在生成过程中产生（构造各层时实时 push），
    绝不在最终 answer 完成后拆句冒充流式。
"""

from __future__ import annotations

import logging
import queue
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_sinks: dict[str, "DeltaSink"] = {}


class DeltaSink:
    """线程安全分段缓冲：generate_answer 写入，WsTurnRunner 消费."""

    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self._closed = False

    def push(self, segment: str) -> None:
        """写入一个真实回答分段（graph 内部线程调用）. 关闭后忽略。"""
        if self._closed:
            return
        if segment:
            self._q.put(segment)

    def get_nowait(self) -> str | None:
        """非阻塞取一段；空缓冲返回 None."""
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        """标记关闭（不再接受新分段）。"""
        self._closed = True
        self._q.put(None)  # 哨兵：通知消费者结束

    def drained(self) -> list[str]:
        """取尽当前缓冲（供测试断言 delta 拼接 == 最终答案）。"""
        out: list[str] = []
        while True:
            s = self.get_nowait()
            if s is None:
                break
            out.append(s)
        return out


def register_sink(turn_id: str, sink: DeltaSink) -> None:
    with _lock:
        _sinks[turn_id] = sink


def get_sink(turn_id: str) -> DeltaSink | None:
    with _lock:
        return _sinks.get(turn_id)


def unregister_sink(turn_id: str) -> None:
    with _lock:
        _sinks.pop(turn_id, None)
