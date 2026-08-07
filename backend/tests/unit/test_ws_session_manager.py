"""WsSessionManager 单元测试 — Phase D #5 会话/取消/多连接.

覆盖:
- 会话创建与复用
- sequence 单调递增（跨连接不重置）
- turn 注册 / 取消令牌 / 幂等取消
- 取消不存在的 turn
- 已完成 turn 的 cancel → already_terminal（不改变历史）
- A 会话取消不影响 B 会话
- 新连接替代旧连接（primary_connection 路由）
- 主连接断开 → 转移到其余连接
- 空闲 TTL 回收
- 显式 close_session
"""

import time

from app.application.services.ws_session_manager import (
    WsSessionManager,
    CancelToken,
)


def _manager():
    return WsSessionManager(idle_ttl=10.0, clock=time.time)


def test_create_and_reuse_session():
    m = _manager()
    s1 = m.get_or_create_session("ses_a")
    s2 = m.get_or_create_session("ses_a")
    assert s1 is s2


def test_sequence_monotonic_across_connections():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    assert m.next_sequence(s) == 1
    assert m.next_sequence(s) == 2
    # 模拟新连接：同会话 sequence 继续递增（不重置）
    s2 = m.get_or_create_session("ses_a")
    assert m.next_sequence(s2) == 3


def test_turn_start_and_cancel():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    turn = m.start_turn(s, "turn_1", "问题")
    assert turn.token.cancelled is False
    assert m.cancel_turn(s, "turn_1") == "cancelled_requested"
    assert turn.token.cancelled is True
    # 幂等：重复取消返回相同状态
    assert m.cancel_turn(s, "turn_1") == "cancelled_requested"


def test_cancel_not_found():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    assert m.cancel_turn(s, "turn_none") == "not_found"


def test_cancel_already_terminal():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    m.start_turn(s, "turn_1", "问题")
    m.mark_turn_terminal(s, "turn_1")
    assert m.cancel_turn(s, "turn_1") == "already_terminal"


def test_cancel_isolation_between_sessions():
    """A 会话取消不影响 B 会话。"""
    m = _manager()
    sa = m.get_or_create_session("ses_a")
    sb = m.get_or_create_session("ses_b")
    turn_a = m.start_turn(sa, "turn_a1", "A问题")
    m.start_turn(sb, "turn_b1", "B问题")
    m.cancel_turn(sa, "turn_a1")
    assert turn_a.token.cancelled is True
    # B 会话 turn 不受影响，仍可取消
    assert m.get_turn(sb, "turn_b1").token.cancelled is False
    assert m.cancel_turn(sb, "turn_b1") == "cancelled_requested"


def test_primary_connection_routing():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    assert s.primary_connection_id is None
    m.attach_connection("ses_a", "conn_1")
    assert m.primary_connection("ses_a") == "conn_1"
    # 新连接替代旧连接
    m.attach_connection("ses_a", "conn_2")
    assert m.primary_connection("ses_a") == "conn_2"


def test_primary_transfer_on_detach():
    m = _manager()
    m.attach_connection("ses_a", "conn_1")
    m.attach_connection("ses_a", "conn_2")
    # 主连接断开 → 转移到 conn_1
    m.detach_connection("ses_a", "conn_2")
    assert m.primary_connection("ses_a") == "conn_1"
    m.detach_connection("ses_a", "conn_1")
    assert m.primary_connection("ses_a") is None


def test_idle_ttl_reclaim():
    clock = {"now": 1000.0}
    m = WsSessionManager(idle_ttl=10.0, clock=lambda: clock["now"])
    m.get_or_create_session("ses_a")
    m.get_or_create_session("ses_b")
    clock["now"] = 1011.0  # 超过 10s 空闲，无连接无活跃 turn
    reclaimed = m.expire_idle()
    assert reclaimed == 2
    assert m.get_session("ses_a") is None


class _FakeTask:
    """最小化 task 桩：done() 可控制，模拟活跃/完成 turn。"""

    def __init__(self, done: bool = False):
        self._done = done

    def done(self) -> bool:
        return self._done


def test_active_turn_blocks_idle_reclaim():
    clock = {"now": 1000.0}
    m = WsSessionManager(idle_ttl=10.0, clock=lambda: clock["now"])
    s = m.get_or_create_session("ses_a")
    turn = m.start_turn(s, "turn_1", "问题")
    turn.task = _FakeTask(done=False)  # 活跃 turn
    clock["now"] = 1011.0
    assert m.expire_idle() == 0  # 活跃 turn 阻止回收
    turn.task = _FakeTask(done=True)  # turn 完成
    assert m.expire_idle() == 1  # 无活跃 turn → 回收


def test_close_session_clears_journal_and_marks_terminal():
    m = _manager()
    s = m.get_or_create_session("ses_a")
    s.journal.append({"sequence": 1, "event_type": "x"})
    m.start_turn(s, "turn_1", "问题")
    m.close_session("ses_a")
    assert m.get_session("ses_a") is None
    # turn 已被标记终态
    assert m.cancel_turn(m.get_or_create_session("ses_a"), "turn_1") == "not_found"


def test_cancel_token_thread_event():
    """CancelToken 提供 threading.Event，供 graph 线程轮询。"""
    t = CancelToken()
    te = t.thread_event()
    assert te.is_set() is False
    t.request_cancel()
    assert t.cancelled is True
    assert te.is_set() is True
    # 新建 asyncio.Event 也立即 set
    ae = t.asyncio_event()
    assert ae.is_set() is True
