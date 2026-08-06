"""会话模块响应 DTO — V12 §11.2.

对齐 backend/app/api/v1/routers/sessions.py 实际返回结构，
使 OpenAPI 可作为前端类型来源（对齐审计 P1-4/P2-5）。
"""

from pydantic import BaseModel, Field


class SessionV1(BaseModel):
    """会话摘要（列表/详情通用）."""

    session_id: str
    title: str | None = None
    user_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    turn_count: int | None = Field(default=None, description="仅列表返回")


class SessionListDataV1(BaseModel):
    """会话列表: {sessions, total}."""

    sessions: list[SessionV1] = []
    total: int = 0


class SessionCreateDataV1(BaseModel):
    """创建会话响应（不返回 turn_count）."""

    session_id: str
    title: str
    status: str = "active"
    created_at: str
    updated_at: str


class SessionTurnV1(BaseModel):
    """单轮历史."""

    turn_id: str
    turn_index: int = 0
    question: str
    answer: str | None = None
    company_code: str | None = None
    trace_id: str | None = None
    module_status: dict | None = None
    panel_data: dict | None = None  # 面板摘要（v7；旧数据为 None）
    evidence_ids: list[str] = []
    created_at: str | None = None


class SessionDetailDataV1(BaseModel):
    """会话详情: {session, turns}."""

    session: SessionV1
    turns: list[SessionTurnV1] = []


class SessionDeleteDataV1(BaseModel):
    """删除会话响应."""

    deleted: bool
    session_id: str
