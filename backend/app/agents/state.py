"""Agent State — V12 baseline.

基于 LangGraph StateGraph 的 Agent 状态定义。
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.conversation.models import ChatContext
from app.domain.evidence.models import Claim


class AgentState(BaseModel):
    """LangGraph Agent 全局状态 — V12 baseline.

    贯穿整个编排流程的共享状态。
    使用 LangGraph 的 Annotated reducer 机制合并增量更新。
    """

    # 输入
    question: str = Field(default="", description="用户问题")
    session_id: str | None = Field(default=None, description="会话 ID")
    context: ChatContext | None = Field(default=None, description="对话上下文")

    # 编排
    intent: str = Field(default="", description="识别的意图")
    execution_plan: list[str] = Field(default_factory=list, description="执行计划")

    # 模块状态
    module_status: dict[str, str] = Field(
        default_factory=dict, description="各模块执行状态"
    )
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块")

    # 中间结果
    evidence: list[dict] = Field(default_factory=list, description="证据列表")
    claims: list[Claim] = Field(default_factory=list, description="结论声明")
    graph: dict = Field(default_factory=dict, description="图谱数据")
    timeline: list[dict] = Field(default_factory=list, description="事件时间线")
    risk_score: dict = Field(default_factory=dict, description="风险评分")

    # 输出
    answer: str = Field(default="", description="最终回答")
    warnings: list[str] = Field(default_factory=list, description="预警")

    # 追踪
    trace_id: str = Field(default="", description="追踪 ID")
    errors: list[dict] = Field(default_factory=list, description="错误列表")

    model_config = ConfigDict(arbitrary_types_allowed=True)
