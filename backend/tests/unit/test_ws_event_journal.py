"""WsEventJournal 单元测试 — Phase D #6 断线补发核心.

覆盖:
- append / events_after 顺序严格递增
- 跨"重连"保持 sequence（不重置）
- 补发使用原 event_id / sequence / turn_id（不重新生成）
- 不重复补发
- 有最大事件数（内存受限，丢弃最旧）
- TTL 过期清理
- gap 检测：请求序号早于缓存起点
- 空缓冲行为
- 并发访问安全
"""

import threading

from app.application.services.ws_event_journal import WsEventJournal


def _env(seq: int, eid: str = "evt_x", turn: str = "turn_x") -> dict:
    return {
        "schema_version": "1.0",
        "event_id": eid,
        "event_type": "answer.delta",
        "session_id": "ses_x",
        "turn_id": turn,
        "sequence": seq,
        "timestamp": "2026-08-07T00:00:00+00:00",
        "trace_id": "trace_x",
        "payload": {"text": f"seg-{seq}"},
    }


def test_append_and_events_after():
    j = WsEventJournal()
    for i in range(1, 4):
        j.append(_env(i, eid=f"evt_{i}"))
    after = j.events_after(1)
    assert [e["sequence"] for e in after] == [2, 3]
    assert [e["event_id"] for e in after] == ["evt_2", "evt_3"]


def test_sequence_not_reset_across_reconnect():
    """跨 socket 重连，sequence 持续单调（不归零不重置）。"""
    j = WsEventJournal()
    for i in range(1, 3):
        j.append(_env(i))
    assert j.latest_sequence() == 2
    # 模拟重连后继续：新事件序号递增
    j.append(_env(3))
    assert j.latest_sequence() == 3
    assert len(j.events_after(0)) == 3


def test_replay_uses_original_ids():
    """补发使用原 event_id/sequence/turn_id，不重新生成。"""
    j = WsEventJournal()
    j.append(_env(1, eid="orig_1", turn="turn_a"))
    j.append(_env(2, eid="orig_2", turn="turn_a"))
    replayed = j.events_after(0)
    assert [e["event_id"] for e in replayed] == ["orig_1", "orig_2"]
    assert [e["turn_id"] for e in replayed] == ["turn_a", "turn_a"]
    assert [e["sequence"] for e in replayed] == [1, 2]


def test_no_duplicate_replay():
    j = WsEventJournal()
    for i in range(1, 4):
        j.append(_env(i))
    a = j.events_after(1)
    b = j.events_after(1)
    assert a == b  # 两次读取一致，不重复不丢失
    assert [e["sequence"] for e in a] == [2, 3]


def test_max_events_drops_oldest():
    j = WsEventJournal(max_events=3)
    for i in range(1, 6):
        j.append(_env(i, eid=f"evt_{i}"))
    assert j.count() == 3
    assert j.earliest_sequence() == 3
    assert j.latest_sequence() == 5
    # 早于 3 的序号无法补发 → gap
    assert j.is_gap(1) is True
    assert j.is_gap(2) is False  # 2 >= earliest-1(2) → 可恢复


def test_ttl_expiry():
    clock = {"now": 1000.0}
    j = WsEventJournal(ttl_seconds=100, clock=lambda: clock["now"])
    j.append(_env(1))
    j.append(_env(2))
    clock["now"] = 1101.0  # 超过 100s TTL
    expired = j.expire()
    assert expired == 2
    assert j.count() == 0
    assert j.latest_sequence() is None


def test_ttl_partial_expiry():
    clock = {"now": 1000.0}
    j = WsEventJournal(ttl_seconds=100, clock=lambda: clock["now"])
    j.append(_env(1))  # t=1000
    clock["now"] = 1050.0
    j.append(_env(2))  # t=1050
    clock["now"] = 1149.0  # 事件1 过期(149s>100s)，事件2 未过期(99s<100s)
    expired = j.expire()
    assert expired == 1
    assert j.latest_sequence() == 2


def test_gap_detection():
    j = WsEventJournal(max_events=2)
    j.append(_env(4))
    j.append(_env(5))
    # 客户端 last_sequence=2 → 需补 3（已丢弃）→ gap
    assert j.is_gap(2) is True
    # 客户端 last_sequence=3 → 需补 4（缓存内有）→ 无 gap
    assert j.is_gap(3) is False
    assert j.is_gap(4) is False
    assert j.is_gap(5) is False


def test_empty_journal():
    j = WsEventJournal()
    assert j.earliest_sequence() is None
    assert j.latest_sequence() is None
    assert j.events_after(0) == []
    assert j.is_gap(0) is True  # 空缓冲：无事件可补发


def test_clear_and_close():
    j = WsEventJournal()
    j.append(_env(1))
    j.clear()
    assert j.count() == 0
    j.append(_env(2))
    j.close()
    j.append(_env(3))  # 关闭后忽略写入
    assert j.count() == 0  # close 清空且拒绝后续写入


def test_concurrent_append():
    """多线程并发 append 不丢事件、不破坏顺序。"""
    j = WsEventJournal(max_events=1000)

    def worker(prefix: str, start: int, end: int):
        for i in range(start, end + 1):
            e = _env(i, eid=f"{prefix}_{i}")
            e["_w"] = prefix
            j.append(e)

    threads = [
        threading.Thread(target=worker, args=("a", 1, 100)),
        threading.Thread(target=worker, args=("b", 101, 200)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = [e["sequence"] for e in j.events_after(0)]
    assert seqs == sorted(seqs)  # 单调递增
    assert len(seqs) == 200
