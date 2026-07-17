"""Conversation 对话领域模型 — V12 baseline."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.evidence.models import Claim


class ChatContext(BaseModel):
    """对话附加上下文."""

    company_code: str | None = Field(None, description="公司代码")
    fiscal_year: int | None = Field(None, description="财年")
    report_type: str | None = Field(None, description="报表类型")


class TurnRequest(BaseModel):
    """对话轮次请求."""

    question: str = Field(..., min_length=1, description="用户问题")
    session_id: str | None = Field(None, description="会话 ID")
    context: ChatContext | None = Field(None, description="附加上下文")


class TurnResponse(BaseModel):
    """对话轮次响应 — V12 增强版."""

    answer: str = Field(..., description="Markdown 格式的主回答")
    claims: list[Claim] = Field(default_factory=list, description="结构化结论声明")
    evidence: list[dict] = Field(
        default_factory=list, description="证据列表（兼容旧格式）"
    )
    graph: dict = Field(default_factory=dict, description="图谱数据")
    timeline: list[dict] = Field(default_factory=list, description="事件时间线")
    risk_score: dict = Field(default_factory=dict, description="风险评分")
    warnings: list[str] = Field(default_factory=list, description="预警点")
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块")
    trace_id: str = Field(default="", description="追踪 ID")
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="生成时间",
    )
