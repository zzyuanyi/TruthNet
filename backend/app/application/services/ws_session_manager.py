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
import uuid
from copy import deepcopy
from dataclasses import dataclass, field

from app.application.models.company_resolution import (
    EntityMention,
    validate_finalized_relation_roles,
)
from app.application.services.ws_event_journal import WsEventJournal
from app.core.config import settings

logger = logging.getLogger(__name__)


def _deepcopy_dict(value: dict) -> dict:
    """不可变快照：返回深拷贝，调用方修改不影响锁内状态。"""
    return deepcopy(value)


# v3.3 批次 A（P0-2）：可恢复重跑的严格终态校验（纯函数）
_EXECUTABLE_RELATION_SET = frozenset({"single", "continuation", "switch", "comparison"})


def _entity_mentions_from_pending(pending: dict) -> list[EntityMention]:
    """Materialize pending mentions for the final relation verifier."""
    return [
        EntityMention(
            mention_id=str(m.get("mention_id") or mid),
            text=str(m.get("text") or ""),
            start=int(m.get("start") or 0),
            end=int(m.get("end") or 0),
            status=str(m.get("status") or "needs_confirmation"),
            selected_wind_code=str(m.get("selected_wind_code") or "") or None,
            role=m.get("role"),
        )
        for mid, m in (pending.get("mentions") or {}).items()
    ]


def validate_pending_resume_state(pending: dict) -> tuple[bool, str]:
    """在最后一个确认写入后、置 ready_to_resume 前执行（v3.3.1 §7.1）。

    不再手写"role 非空"检查：将 pending mentions 解析为 EntityMention
    后复用 validate_finalized_relation_roles()（override 终态闸门），
    保证 T+1 前与 override 重跑前同一套严格校验，杜绝"确认通过但
    T+1 被 override 拒绝"的循环：

    - mentions 非空，每个 mention 都有 selected_wind_code；
    - 不存在 not_found / needs_refinement / needs_confirmation；
    - relation 可执行且 relation_status == resolved；
    - 角色结构严格（single/continuation/switch 唯一 primary；
      comparison 全绑定 + 至少两个不同 code + 恰好一个 primary +
      其余全 peer）——由 validate_finalized_relation_roles 保证。

    Returns:
        (True, "") 或 (False, 失败原因)
    """
    mentions = pending.get("mentions") or {}
    if not mentions:
        return False, "mentions 为空"
    entity_mentions: list[EntityMention] = []
    for mid, m in mentions.items():
        status = m.get("status")
        if status in ("not_found", "needs_refinement", "needs_confirmation"):
            return False, f"mention {mid} 状态为 {status}"
        code = str(m.get("selected_wind_code") or "").strip()
        if not code:
            return False, f"mention {mid} 缺少 selected_wind_code"
        if not m.get("role"):
            return False, f"mention {mid} 缺少 role"
        entity_mentions.append(
            EntityMention(
                mention_id=mid,
                text=str(m.get("text") or ""),
                start=int(m.get("start") or 0),
                end=int(m.get("end") or 0),
                status=str(status),
                selected_wind_code=code,
                role=m.get("role"),
            )
        )
    relation = pending.get("relation")
    if relation not in _EXECUTABLE_RELATION_SET:
        return False, f"relation {relation} 不可执行"
    if pending.get("relation_status") != "resolved":
        return False, f"relation_status={pending.get('relation_status')}"
    if not validate_finalized_relation_roles(str(relation), entity_mentions):
        return False, f"relation={relation} 的角色/身份结构不满足严格终态要求"
    return True, ""


def build_and_validate_override_decisions(
    pending: dict,
) -> tuple[list[dict] | None, str]:
    """v3.3.1 §7.1：从 pending 最终 mentions 构造 override decisions 并
    严格校验（claim_pending_resume 在注册 T+1 之前唯一调用）。

    校验：
      1. mentions 非空且 ID 无重复；
      2. 每条 decision 的 mention_id/text/start/end/wind_code/role 完整；
      3. decisions 的 ID 集与 pending 最终 mention ID 集完全相等；
      4. validate_finalized_relation_roles 通过（与 T+1 override 重跑
         同一套终态闸门）。

    Returns:
        (decisions|None, 错误原因)
    """
    mentions = pending.get("mentions") or {}
    if not mentions:
        return None, "pending mentions 为空"
    decisions: list[dict] = []
    for mid, m in mentions.items():
        code = str(m.get("selected_wind_code") or "").strip()
        if not code:
            return None, f"mention {mid} 缺少 selected_wind_code"
        if not m.get("role"):
            return None, f"mention {mid} 缺少 role"
        decisions.append(
            {
                "mention_id": mid,
                "text": str(m.get("text") or ""),
                "start": int(m.get("start") or 0),
                "end": int(m.get("end") or 0),
                "wind_code": code,
                "role": m.get("role"),
            }
        )
    ids = [d["mention_id"] for d in decisions]
    if len(ids) != len(set(ids)):
        return None, "mention_id 重复"
    if set(ids) != set(mentions.keys()):
        return None, "decisions 未完整覆盖最终 mention 集"
    relation = pending.get("relation")
    entity_mentions = [
        EntityMention(
            mention_id=str(m.get("mention_id") or mid),
            text=str(m.get("text") or ""),
            start=int(m.get("start") or 0),
            end=int(m.get("end") or 0),
            status=str(m.get("status") or "user_confirmed"),
            selected_wind_code=str(m.get("selected_wind_code") or ""),
            role=m.get("role"),
        )
        for mid, m in mentions.items()
    ]
    if not validate_finalized_relation_roles(str(relation), entity_mentions):
        return None, f"relation={relation} 的角色/身份结构不满足严格终态要求"
    return decisions, ""


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
    # v3.3.1 §7.2：T+1 一次性 claim 所有权（attach/abort 三件套校验）
    resume_claim_id: str | None = None


@dataclass
class ResumeAbortOutcome:
    """v3.3.1 §7.2：claim token 收敛后的 abort 结构化结果。

    - owned：本 claim 拥有该 turn（origin/resumed/claim 三件套通过）；
    - terminal_claimed：锁内已抢占精确新 turn 的终态发送权（caller 必须
      按 accepted 是否已写决定是否发送终态）；
    - pending_restored：pending 已恢复 ready_to_resume 并清 claim 字段；
    - turn_present：abort 时 turn 是否仍在 session.turns（caller 定向移除）。
    """

    owned: bool
    terminal_claimed: bool = False
    pending_restored: bool = False
    turn_present: bool = False


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

    # ── 实体确认原子状态机（v3.1 冻结方案 P0-1/P0-2/P0-3）────────

    @staticmethod
    def _mention_candidate_codes(mention: dict) -> set[str]:
        """取 mention 候选 wind_code 集合（CandidateMatch 或 CompanyRef 两种 dict 形态）。"""
        codes: set[str] = set()
        for c in mention.get("candidates", []) or []:
            if (
                isinstance(c, dict)
                and "company" in c
                and isinstance(c["company"], dict)
            ):
                codes.add(str(c["company"].get("wind_code") or ""))
            elif isinstance(c, dict) and c.get("wind_code"):
                codes.add(str(c["wind_code"]))
        return {c for c in codes if c}

    def confirm_pending_mention(
        self,
        session: WsSession,
        pending_turn_id: str,
        mention_id: str,
        wind_code: str,
        expected_revision: int,
    ) -> tuple[str, dict]:
        """原子确认单个 mention（v3.1 P0-1/P0-2/P0-3 + v3.2.1 幂等重放）。

        v3.2.1 批次 5：先判"同值重放"（mention 已 user_confirmed 且
        wind_code 一致）再判首次 revision——重放不产生写入、不增 revision、
        可忽略旧 expected revision；首次写入仍严格校验 revision。
        最后一个确认**不直接清空** pending：生命周期改为 ready_to_resume，
        由 claim_pending_resume 原子领取启动 T+1。

        Returns:
            (状态码, 不可变快照 dict)
            NO_PENDING / TURN_MISMATCH / REVISION_MISMATCH /
            INVALID_MENTION / INVALID_CODE / NOT_ACCEPTING
            WAITING（仍有 needs_confirmation）
            RESUME_READY（身份全确认且 relation 可执行，可领取）
            RESUME_IN_PROGRESS（resuming 期同值重放）
            ALREADY_RESUMED（consumed 后同值重放）
            RELATION_BLOCKED（身份全确认但 relation 未解析/不可执行——
                v3.1 P0-3：不启动 T+1，进入 relation_clarify）
        """
        with self._lock:
            pending = session.pending_disambiguation
            if pending is None or pending.get("origin_turn_id") != pending_turn_id:
                return "NO_PENDING", {}
            lifecycle = pending.get("lifecycle_status")
            mention = pending.get("mentions", {}).get(mention_id)
            if mention is None:
                return "INVALID_MENTION", {}
            # 候选校验（首次写入与重放一致：code 必须属于候选集）
            if wind_code not in self._mention_candidate_codes(mention):
                return "INVALID_CODE", {}

            # ── v3.2.1 幂等重放：已确认的同值请求不产生写入 ──
            if mention.get("status") == "user_confirmed":
                if mention.get("selected_wind_code") != wind_code:
                    return "NOT_ACCEPTING", {}
                snapshot = _deepcopy_dict(pending)
                if lifecycle == "collecting":
                    remaining = [
                        mid
                        for mid, m in pending.get("mentions", {}).items()
                        if m.get("status") == "needs_confirmation"
                    ]
                    if remaining:
                        return "WAITING", snapshot
                    # 全部身份已确认且仍 collecting：只在 relation 不可执行
                    # 路径出现（首次确认已返 RELATION_BLOCKED）
                    return "RELATION_BLOCKED", snapshot
                if lifecycle == "ready_to_resume":
                    return "RESUME_READY", snapshot
                if lifecycle == "resuming":
                    return "RESUME_IN_PROGRESS", snapshot
                if lifecycle == "consumed":
                    return "ALREADY_RESUMED", snapshot
                return "NOT_ACCEPTING", {}

            # ── 首次写入：仅 needs_confirmation + collecting ──
            if mention.get("status") != "needs_confirmation":
                return "INVALID_MENTION", {}
            if lifecycle != "collecting":
                return "NOT_ACCEPTING", {}
            if pending.get("revision") != expected_revision:
                return "REVISION_MISMATCH", {}

            mention["selected_wind_code"] = wind_code
            mention["status"] = "user_confirmed"
            mention["resolution_source"] = "user_confirm"
            pending["revision"] += 1

            remaining = [
                mid
                for mid, m in pending.get("mentions", {}).items()
                if m.get("status") == "needs_confirmation"
            ]
            snapshot = _deepcopy_dict(pending)
            if remaining:
                return "WAITING", snapshot
            # A comparison may have been intentionally kept in an
            # intermediate needs_clarification state while its last identity
            # was pending. Re-evaluate the strict terminal invariant now that
            # all identities are selected; unsupported relations remain
            # blocked below.
            relation = pending.get("relation")
            if (
                relation in _EXECUTABLE_RELATION_SET
                and pending.get("relation_waiting_for_identity") is True
                and validate_finalized_relation_roles(
                    str(relation), _entity_mentions_from_pending(pending)
                )
            ):
                pending["relation_status"] = "resolved"
                snapshot = _deepcopy_dict(pending)
            # v3.3 P0-2：relation 不可执行 → RELATION_BLOCKED（P0-3 语义）；
            # 可执行但身份集不完整（not_found/needs_refinement/重复代码/
            # role 缺失）→ IDENTITY_BLOCKED，均不得进入 ready_to_resume
            relation = pending.get("relation")
            relation_status = pending.get("relation_status")
            if not (
                relation_status == "resolved" and relation in _EXECUTABLE_RELATION_SET
            ):
                return "RELATION_BLOCKED", snapshot
            valid, reason = validate_pending_resume_state(pending)
            if not valid:
                logger.warning(
                    "WsSessionManager: 身份确认后终态校验失败（%s），IDENTITY_BLOCKED",
                    reason,
                )
                return "IDENTITY_BLOCKED", snapshot
            pending["lifecycle_status"] = "ready_to_resume"
            return "RESUME_READY", _deepcopy_dict(pending)

    def claim_pending_resume(
        self,
        session: WsSession,
        origin_turn_id: str,
        expected_revision: int,
        new_turn_id: str,
    ) -> tuple[str, dict]:
        """原子领取确认结果并登记 T+1（v3.1 P0-1）。

        同一把锁内完成：
          1. pending 必须为 ready_to_resume；2. revision 匹配；
          3. 来源 turn 已不在 session.turns（P0-1 竞态：等待 remove_turn）；
          4. 当前会话无其他活跃 turn；5. 创建并登记 T+1；
          6. pending → resuming 并记录 resumed_turn_id；
          7. 返回不可变的 question + override 快照。
        启动失败（异常）时 pending 回滚 ready_to_resume，允许幂等重试。
        """
        with self._lock:
            pending = session.pending_disambiguation
            if pending is None or pending.get("origin_turn_id") != origin_turn_id:
                return "NO_PENDING", {}
            if pending.get("revision") != expected_revision:
                return "REVISION_MISMATCH", {}
            lifecycle = pending.get("lifecycle_status")
            if lifecycle == "resuming":
                # v3.2.1 批次 5：区分"已被他人领取"与普通未就绪
                return "RESUME_IN_PROGRESS", {}
            if lifecycle == "consumed":
                return "ALREADY_RESUMED", {}
            if lifecycle != "ready_to_resume":
                return "NOT_READY", {}
            if session.turns.get(origin_turn_id) is not None:
                # 来源 turn 尚未移除：确认已写入，等待其收尾后再领取
                return "ORIGIN_TURN_ACTIVE", {}
            if session.turns:
                return "TURN_IN_PROGRESS", {}

            # v3.3.1 §7.1：注册 T+1 之前构造并严格校验 override
            # decisions（与 T+1 override 重跑同一套终态闸门）；失败保持
            # ready_to_resume，不登记新 ActiveTurn
            decisions, override_error = build_and_validate_override_decisions(pending)
            if decisions is None:
                logger.warning(
                    "WsSessionManager: claim 前 override 构造校验失败（%s），"
                    "pending 保持 ready_to_resume",
                    override_error,
                )
                return "OVERRIDE_INVALID", {}

            # v3.3.1 §7.2：一次性 claim token——attach/abort 必须同时
            # 校验 origin/resumed/claim 三件套，收敛 abort 所有权
            claim_id = uuid.uuid4().hex[:12]
            turn = ActiveTurn(
                turn_id=new_turn_id,
                session_id=session.session_id,
                question=str(pending.get("question") or ""),
                resume_claim_id=claim_id,
            )
            try:
                session.turns[new_turn_id] = turn
            except Exception:  # noqa: BLE001 — 登记失败回滚，允许幂等重试
                pending["lifecycle_status"] = "ready_to_resume"
                logger.warning(
                    "WsSessionManager: T+1 登记失败，pending 保持 ready_to_resume",
                    exc_info=True,
                )
                return "TURN_IN_PROGRESS", {}
            pending["lifecycle_status"] = "resuming"
            pending["resumed_turn_id"] = new_turn_id
            pending["resume_claim_id"] = claim_id
            session.last_activity = self._clock()

            # 构造不可变 override 快照（保留 relation/role，防 reference/sequence 错当比较）
            return "OK", {
                "claim_id": claim_id,
                "question": str(pending.get("question") or ""),
                "query_fingerprint": str(pending.get("query_fingerprint") or ""),
                "override": {
                    "resolution_version": pending.get("resolution_version", 1),
                    "query_fingerprint": str(pending.get("query_fingerprint") or ""),
                    "relation": pending.get("relation"),
                    "selected_alternative_id": pending.get("selected_alternative_id"),
                    "decisions": decisions,
                },
            }

    def consume_pending_resume(
        self, session: WsSession, origin_turn_id: str, resumed_turn_id: str
    ) -> bool:
        """T+1 成功接受后标记 pending consumed（P0-1：不提前清除）。

        Returns:
            True = 已置 consumed；False = pending 缺失或 resumed_turn_id 不匹配。
        """
        with self._lock:
            pending = session.pending_disambiguation
            if pending is None or pending.get("origin_turn_id") != origin_turn_id:
                return False
            if pending.get("resumed_turn_id") != resumed_turn_id:
                return False
            pending["lifecycle_status"] = "consumed"
            return True

    def attach_and_consume_pending_resume(
        self,
        session: WsSession,
        origin_turn_id: str,
        resumed_turn_id: str,
        task: asyncio.Task,
        claim_id: str,
    ) -> bool:
        """v3.3 批次 A（P0-1）：attach task 与 consume pending 的锁内原子合并。

        同一把锁内校验 origin/resumed_turn_id/claim_id/lifecycle==resuming
        且新 turn 存在后，绑定 task 并置 consumed——杜绝 attach 成功但
        consume 失败的中间状态（旧实现两步分离，consume 返回 False 被
        调用方忽略）。v3.3.1 §7.2：claim token 三件套校验。

        Returns:
            True = 已 attach 且 consumed；
            False = state conflict（调用方必须取消 task、abort 回滚
            pending、抢占唯一终态，不得返回 OK）。
        """
        with self._lock:
            pending = session.pending_disambiguation
            if pending is None or pending.get("origin_turn_id") != origin_turn_id:
                return False
            if pending.get("resumed_turn_id") != resumed_turn_id:
                return False
            if pending.get("resume_claim_id") != claim_id:
                return False
            if pending.get("lifecycle_status") != "resuming":
                return False
            turn = session.turns.get(resumed_turn_id)
            if turn is None:
                return False
            if turn.resume_claim_id != claim_id:
                return False
            turn.task = task
            pending["lifecycle_status"] = "consumed"
            return True

    def abort_claimed_resume(
        self,
        session: WsSession,
        origin_turn_id: str,
        resumed_turn_id: str,
        claim_id: str,
    ) -> ResumeAbortOutcome:
        """v3.3.1 §7.2：claim token 收敛 abort 所有权的锁内原子回滚
        （取代 rollback_resume——旧实现仅校验 lifecycle==resuming 且
        返回值被调用方忽略，可能误回滚他人 claim 或遗留孤儿状态）。

        规则：
        - 只修改本 claim 拥有的 turn（origin/resumed/claim 三件套）；
        - pending 仍属于本 claim 时恢复 ready_to_resume 并清 claim 字段；
        - pending 已被其他合法状态替换时不得覆盖（owned=False 不动）；
        - 精确新 turn 的终态发送权在锁内抢占（terminal_claimed）；
        - caller 必须处理并记录返回值：按 terminal_claimed/accepted
          决定是否写终态，再定向移除该 turn。
        """
        with self._lock:
            pending = session.pending_disambiguation
            turn = session.turns.get(resumed_turn_id)
            owned = (
                pending is not None
                and pending.get("origin_turn_id") == origin_turn_id
                and pending.get("resumed_turn_id") == resumed_turn_id
                and pending.get("resume_claim_id") == claim_id
            )
            terminal_claimed = False
            pending_restored = False
            if owned and pending.get("lifecycle_status") == "resuming":
                pending["lifecycle_status"] = "ready_to_resume"
                pending["resumed_turn_id"] = None
                pending["resume_claim_id"] = None
                pending_restored = True
            if owned and turn is not None and not turn.terminal_event_sent:
                turn.terminal_event_sent = True
                terminal_claimed = True
            return ResumeAbortOutcome(
                owned=owned,
                terminal_claimed=terminal_claimed,
                pending_restored=pending_restored,
                turn_present=turn is not None,
            )

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
