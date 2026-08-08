"""WsSessionManager — Phase D #5/#6/#10 WS 会话与执行生命周期管理.

按逻辑会话（session_id）维护：
  - 活跃连接（多连接观察/单写多读策略）；
  - 活跃 turn 与各自 cancellation token；
  - 每会话单调递增 sequence；
  - 事件缓冲（WsEventJournal）；
  - 空闲 TTL 回收与显式清理。

策略（契约冻结，D2 后不改）：同一 session 多连接采用「新连接替代旧连接」——
    新连接接管该 session 的事件分发；旧连接断开时不影响正在执行的 turn。
    （对双连接双会话、断线重连场景提供确定语义。）
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.application.services.ws_event_journal import WsEventJournal
from app.core.config import settings

logger = logging.getLogger(__name__)


class CancelToken:
    """协作式取消令牌（thread-safe，供 graph 执行线程轮询）。

    独立于 asyncio.Event：graph 在 to_thread/独立线程中执行时，
    threading.Event 可被取消请求直接 set，无需穿越事件循环。
    """

    def __init__(self) -> None:
        self._event = None
        self._thread_event = None
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True
        if self._event is not None:
            self._event.set()
        if self._thread_event is not None:
            self._thread_event.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def asyncio_event(self) -> asyncio.Event:
        if self._event is None:
            self._event = asyncio.Event()
            if self._cancelled:
                self._event.set()
        return self._event

    def thread_event(self):
        """返回 threading.Event 用于线程内轮询（每次调用可能新建）。"""
        if self._thread_event is None:
            self._thread_event = threading_event()
            if self._cancelled:
                self._thread_event.set()
        return self._thread_event


def threading_event():
    import threading

    return threading.Event()


@dataclass
class ActiveTurn:
    """一个活跃（运行中）的 turn 及其执行控制信息."""

    turn_id: str
    session_id: str
    question: str
    token: CancelToken = field(default_factory=CancelToken)
    started_at: float = field(default_factory=time.time)
    task: asyncio.Task | None = None
    terminal_event_sent: bool = False
    last_sequence_sent: int = 0


@dataclass
class WsSession:
    """逻辑会话状态."""

    session_id: str
    journal: WsEventJournal = field(default_factory=WsEventJournal)
    sequence: int = 0
    turns: dict[str, ActiveTurn] = field(default_factory=dict)
    connection_ids: set[str] = field(default_factory=set)
    primary_connection_id: str | None = None  # 事件分发目标（新连接替代旧连接）
    last_activity: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    closed: bool = False
    pending_disambiguation: dict | None = None


class WsSessionManager:
    """会话管理器（进程内单例）。

    所有方法线程安全（asyncio 单事件循环下为同步临界区；
    Lock 保护供并发连接/后台清理任务访问）。
    """

    def __init__(
        self,
        *,
        idle_ttl: float | None = None,
        clock=None,
    ) -> None:
        self._idle_ttl = (
            idle_ttl
            if idle_ttl is not None
            else float(settings.WS_SESSION_IDLE_TTL_SECONDS)
        )
        self._clock = clock or time.time
        self._sessions: dict[str, WsSession] = {}
        self._lock = __import__("threading").Lock()
        self._next_connection_id = 0

    # ── 会话获取 ──────────────────────────────────────────

    def get_or_create_session(self, session_id: str) -> WsSession:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None or s.closed:
                s = WsSession(session_id=session_id)
                self._sessions[session_id] = s
            s.last_activity = self._clock()
            return s

    def get_session(self, session_id: str) -> WsSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def session_has_activity(self, session_id: str) -> bool:
        """会话是否真正产生过活动（有缓冲事件或有 turn 记录）。

        区分"曾活跃可恢复的会话"与"刚由本连接创建/已过期的空会话"。
        resume 对无活动会话返回 SESSION_NOT_FOUND。
        """
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None or s.closed:
                return False
            return s.journal.count() > 0 or bool(s.turns)

    def attach_connection(self, session_id: str, connection_id: str) -> WsSession:
        """新连接加入会话并成为事件分发主连接（新连接替代旧连接策略）。

        旧连接仍保留在 connection_ids（可继续发控制事件），
        但事件只路由到 primary_connection_id——确定的多连接语义。
        """
        s = self.get_or_create_session(session_id)
        with self._lock:
            s.connection_ids.add(connection_id)
            s.primary_connection_id = connection_id
            s.last_activity = self._clock()
        return s

    def primary_connection(self, session_id: str) -> str | None:
        """当前会话事件分发目标连接 ID；无连接返回 None."""
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            return s.primary_connection_id

    def detach_connection(self, session_id: str, connection_id: str) -> None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return
            s.connection_ids.discard(connection_id)
            if s.primary_connection_id == connection_id:
                # 主连接断开 → 转移到其余连接（如有）
                remaining = s.connection_ids
                s.primary_connection_id = next(iter(remaining), None)
            s.last_activity = self._clock()

    def new_connection_id(self) -> str:
        with self._lock:
            self._next_connection_id += 1
            return f"conn_{self._next_connection_id:04d}"

    # ── sequence ──────────────────────────────────────────

    def next_sequence(self, session: WsSession) -> int:
        """会话内单调递增序号（跨连接不重置）。"""
        with self._lock:
            session.sequence += 1
            session.last_activity = self._clock()
            return session.sequence

    # ── turn 管理 ─────────────────────────────────────────

    def start_turn(self, session: WsSession, turn_id: str, question: str) -> ActiveTurn:
        with self._lock:
            turn = ActiveTurn(
                turn_id=turn_id,
                session_id=session.session_id,
                question=question,
            )
            session.turns[turn_id] = turn
            session.last_activity = self._clock()
            return turn

    def start_turn_if_idle(
        self, session: WsSession, turn_id: str, question: str
    ) -> ActiveTurn | None:
        """Atomically start one turn, rejecting parallel turns in the same session."""
        with self._lock:
            if session.turns:
                return None
            turn = ActiveTurn(
                turn_id=turn_id,
                session_id=session.session_id,
                question=question,
            )
            session.turns[turn_id] = turn
            session.last_activity = self._clock()
            return turn

    def set_pending_disambiguation(
        self, session: WsSession, pending: dict | None
    ) -> None:
        with self._lock:
            session.pending_disambiguation = pending
            session.last_activity = self._clock()

    def get_pending_disambiguation(self, session: WsSession) -> dict | None:
        with self._lock:
            pending = session.pending_disambiguation
            return dict(pending) if pending else None

    def attach_task(self, session: WsSession, turn_id: str, task: asyncio.Task) -> None:
        """将执行 task 绑定到 ActiveTurn（线程安全）。

        expire_idle 依赖 turn.task 判断会话是否有活跃 turn——
        创建 task 后必须立即绑定，否则活跃会话可能被误回收。
        """
        with self._lock:
            turn = session.turns.get(turn_id)
            if turn is not None:
                turn.task = task

    def get_turn(self, session: WsSession, turn_id: str) -> ActiveTurn | None:
        with self._lock:
            return session.turns.get(turn_id)

    def cancel_turn(self, session: WsSession, turn_id: str) -> str:
        """请求取消 turn。

        Returns:
            "cancelled_requested"  已请求取消（幂等）
            "not_found"            turn 不存在（不取消他 session/不存在的 turn）
            "already_terminal"     turn 已终态（不改变历史）
        """
        with self._lock:
            turn = session.turns.get(turn_id)
            if turn is None:
                return "not_found"
            if turn.terminal_event_sent:
                return "already_terminal"
            turn.token.request_cancel()
            session.last_activity = self._clock()
            return "cancelled_requested"

    def mark_turn_terminal(self, session: WsSession, turn_id: str) -> None:
        """记录 turn 已发送终态事件（cancel 幂等 / 单终态保证）。"""
        with self._lock:
            turn = session.turns.get(turn_id)
            if turn is not None:
                turn.terminal_event_sent = True

    def claim_terminal_event(self, session: WsSession, turn_id: str) -> bool:
        """原子抢占 turn 终态发送权。

        同一 turn 的全部终态（turn.cancelled / turn.completed / turn.failed）
        必须经此抢占：成功者唯一发送终态事件，其余调用方跳过。

        Returns:
            True  = 抢占成功（调用方应发送终态事件）
            False = 终态已由其他路径发送 / turn 不存在
        """
        with self._lock:
            turn = session.turns.get(turn_id)
            if turn is None or turn.terminal_event_sent:
                return False
            turn.terminal_event_sent = True
            return True

    def remove_turn(self, session: WsSession, turn_id: str) -> None:
        with self._lock:
            session.turns.pop(turn_id, None)

    # ── 事件缓冲转发 ──────────────────────────────────────

    def append_event(self, session: WsSession, event: dict) -> None:
        """事件写入缓冲（发送前调用，保证补发一致）。"""
        session.journal.append(event)

    def journal(self, session: WsSession) -> WsEventJournal:
        return session.journal

    # ── 清理 / TTL ────────────────────────────────────────

    def expire_idle(self) -> int:
        """回收空闲超时会话（含缓冲与活跃 turn），返回回收数。"""
        now = self._clock()
        expired_ids: list[str] = []
        with self._lock:
            for sid, s in self._sessions.items():
                if s.closed:
                    continue
                idle = now - s.last_activity
                has_active = any(
                    t.task is not None and not t.task.done() for t in s.turns.values()
                )
                if idle > self._idle_ttl and not has_active and not s.connection_ids:
                    expired_ids.append(sid)
            for sid in expired_ids:
                s = self._sessions.pop(sid)
                s.journal.close()
                logger.info("WsSessionManager: 回收空闲会话 %s", sid)
        return len(expired_ids)

    def close_session(self, session_id: str) -> None:
        """显式销毁会话（清空缓冲 + 标记 turn 终态）。"""
        with self._lock:
            s = self._sessions.pop(session_id, None)
            if s is None:
                return
            s.closed = True
            for turn in s.turns.values():
                turn.terminal_event_sent = True
            s.journal.close()

    def janitor(self) -> dict:
        """周期清理：过期缓冲事件 + 空闲超时会话。

        Returns:
            {"expired_events": int, "expired_sessions": int}
        """
        expired_events = 0
        expired_sessions = 0
        # 1. 全部存活 session 的缓冲 TTL 清理
        with self._lock:
            sessions = list(self._sessions.values())
        for s in sessions:
            if s.closed:
                continue
            try:
                expired_events += s.journal.expire()
            except Exception:  # noqa: BLE001 — 单会话清理失败不影响其他
                logger.warning(
                    "WsSessionManager.janitor: 缓冲清理失败 session=%s",
                    s.session_id,
                    exc_info=True,
                )
        # 2. 空闲超时无连接无活跃 turn 的会话回收
        try:
            expired_sessions = self.expire_idle()
        except Exception:  # noqa: BLE001
            logger.warning("WsSessionManager.janitor: 空闲会话回收失败", exc_info=True)
        return {
            "expired_events": expired_events,
            "expired_sessions": expired_sessions,
        }

    def active_session_count(self) -> int:
        with self._lock:
            return len([s for s in self._sessions.values() if not s.closed])


# 进程内单例（FastAPI lifespan 注册清理任务）
session_manager = WsSessionManager()
