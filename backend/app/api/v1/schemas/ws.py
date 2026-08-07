"""WebSocket 事件 Schema — Phase D 契约冻结（#5/#6/#10）.

定义客户端→服务端控制事件载荷与服务端生命周期事件的统一结构。
只追加字段，不删除 V12 已有字段；旧格式兼容由路由层保留。

字段只增约定（D2 契约冻结后不再随意增加）：
  - turn.cancel.payload:   {turn_id}
  - stream.resume.payload: {session_id, last_sequence}
  - turn.cancelled.payload:{turn_id, cancelled_at, message}
  - stream.resume_ack.payload: {session_id, last_sequence, replay_from, replay_count, gap}
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TurnCancelPayload(BaseModel):
    """turn.cancel — 协作式取消请求载荷.

    只允许取消当前会话中指定的 turn；重复取消幂等；
    已完成 turn 的取消返回明确终态，不改变历史记录。
    """

    turn_id: str = Field(..., description="要取消的轮次 ID")
    reason: str | None = Field(None, description="可选取消原因")


class StreamResumePayload(BaseModel):
    """stream.resume — 断线重连补发请求载荷.

    last_sequence 之后的缓存事件按原 event_id/sequence 补发；
    早于缓存起点的序号返回可恢复 gap 错误。
    """

    session_id: str = Field(..., description="目标会话 ID")
    last_sequence: int = Field(0, ge=0, description="客户端已收到的最后序号")
    turn_id: str | None = Field(None, description="可选：仅补发该轮次事件")


class TurnCancelledPayload(BaseModel):
    """turn.cancelled — 服务端取消确认载荷.

    语义：当前不可中断节点结束后立即停止，不再启动新节点；
    本 turn 不会再有 turn.completed / turn.failed。
    """

    turn_id: str = Field(..., description="已取消的轮次 ID")
    cancelled_at: str = Field(default_factory=_utcnow_iso, description="取消确认时间")
    message: str = Field(default="当前轮次已取消", description="确认文案")
    sequence: int | None = Field(None, description="取消发生时已发送的最大序号")


class StreamResumeAckPayload(BaseModel):
    """stream.resume_ack — 断线补发结果确认载荷.

    gap=True 表示请求序号早于缓存起点，需客户端从缓存起点重连或重新发起 query。
    """

    session_id: str = Field(..., description="目标会话 ID")
    last_sequence: int = Field(..., description="当前服务端最新序号")
    replay_from: int = Field(..., description="补发起始序号（last_sequence+1）")
    replay_count: int = Field(0, description="本次补发事件数")
    gap: bool = Field(False, description="是否发生不可恢复的序列断档")
    message: str = Field("", description="补发结果说明")


class WsEventEnvelope(BaseModel):
    """V12 九字段事件信封（Phase D 校验用 DTO）.

    实际发送使用 dict（保持与既有实现一致），此模型用于契约测试校验。
    """

    schema_version: str = Field(default="1.0")
    event_id: str = Field(..., description="事件唯一 ID")
    event_type: str = Field(..., description="事件类型")
    session_id: str = Field(..., description="会话 ID")
    turn_id: str = Field(..., description="轮次 ID")
    sequence: int = Field(..., description="单调递增序号")
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    trace_id: str = Field(..., description="追踪 ID")
    payload: dict[str, Any] = Field(default_factory=dict, description="事件数据")
