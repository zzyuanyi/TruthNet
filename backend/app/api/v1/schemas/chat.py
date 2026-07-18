"""API v1 对话 Schema — V12 baseline."""

from pydantic import BaseModel, Field

from app.domain.conversation.models import ChatContext


class ChatRequestV1(BaseModel):
    """POST /api/v1/chat 请求体 — V12."""

    question: str = Field(..., min_length=1, description="用户问题")
    session_id: str | None = Field(None, description="会话 ID，用于多轮对话")
    context: ChatContext | None = Field(None, description="附加上下文信息")


class ChatDataV1(BaseModel):
    """对话响应核心数据 — V12."""

    answer: str = Field(..., description="Markdown 格式的主回答")
    evidence: list[dict] = Field(default_factory=list, description="证据列表")
    graph: dict = Field(default_factory=dict, description="图谱数据")
    timeline: list[dict] = Field(default_factory=list, description="事件时间线")
    risk_score: dict = Field(default_factory=dict, description="风险评分")
    warnings: list[str] = Field(default_factory=list, description="财务预警点")
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块列表")
    trace_id: str = Field(..., description="追踪 ID")
