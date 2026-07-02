"""对话相关 Schema。

与 docs/API_CONTRACT.md 保持严格一致。
Prompt4 冻结：核心字段进入 MVP 稳定状态，后续只能追加，不得删除/重命名。
"""

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """对话附加上下文。"""

    company_code: str | None = Field(None, description="公司代码，如 600519")
    fiscal_year: int | None = Field(None, description="财年")
    report_type: str | None = Field(None, description="报表类型")


class ChatRequest(BaseModel):
    """POST /api/v1/chat 请求体。"""

    question: str = Field(..., min_length=1, description="用户问题")
    session_id: str | None = Field(None, description="会话 ID，用于多轮对话")
    context: ChatContext | None = Field(None, description="附加上下文信息")


class Evidence(BaseModel):
    """证据条目。"""

    source: str = Field(..., description="数据来源（如'利润表'）")
    field: str = Field(..., description="字段名（如'营业收入'）")
    value: str = Field(..., description="字段值")


class GraphNode(BaseModel):
    """图谱节点。"""

    id: str = Field(..., description="节点唯一标识")
    label: str = Field(..., description="节点显示名称")
    type: str = Field(..., description="节点类型: company / controller / subsidiary")
    depth: int | None = Field(None, description="在图中的深度（从目标公司起算）")


class GraphEdge(BaseModel):
    """图谱边。"""

    source: str = Field(..., description="起始节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation: str = Field(..., description="关系描述（如'54%控股'）")


class GraphData(BaseModel):
    """图谱数据。"""

    nodes: list[GraphNode] = Field(default_factory=list, description="节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="边列表")


class TimelineEvent(BaseModel):
    """时间线事件。"""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    title: str = Field(..., description="事件标题")
    category: str = Field(default="其他", description="事件类别")
    summary: str = Field(default="", description="事件摘要")
    sentiment: str = Field(
        default="neutral", description="情感倾向: positive/negative/neutral"
    )
    sources: list[str] = Field(default_factory=list, description="信息来源")


class RiskScore(BaseModel):
    """风险评分（Prompt4 冻结为对象结构）。"""

    overall: float = Field(default=0.0, ge=0.0, le=1.0, description="综合风险 0-1")
    financial: float = Field(default=0.0, ge=0.0, le=1.0, description="财务风险 0-1")
    ownership: float = Field(default=0.0, ge=0.0, le=1.0, description="股权风险 0-1")
    sentiment: float = Field(default=0.0, ge=0.0, le=1.0, description="舆情风险 0-1")


class ChatData(BaseModel):
    """对话响应核心数据。

    与 API_CONTRACT.md 中对应接口的响应字段严格一致。
    Prompt4 冻结：以下字段进入 MVP 稳定状态。
    """

    answer: str = Field(..., description="Markdown 格式的主回答")
    evidence: list[Evidence] = Field(default_factory=list, description="证据列表")
    graph: GraphData = Field(default_factory=GraphData, description="图谱数据")
    timeline: list[TimelineEvent] = Field(
        default_factory=list, description="事件时间线"
    )
    risk_score: RiskScore = Field(
        default_factory=RiskScore, description="风险评分（对象）"
    )
    warnings: list[str] = Field(default_factory=list, description="财务预警点")
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块列表")
    trace_id: str = Field(..., description="追踪 ID")


class MissingModule(BaseModel):
    """缺失模块信息。"""

    module: str = Field(..., description="模块名称")
    reason: str = Field(..., description="缺失/失败原因")
    fallback: str = Field(default="", description="降级措施")


class EnhancedChatData(ChatData):
    """增强版对话响应（Agent 实现后使用）。

    追加字段，不影响前端兼容性。
    """

    missing_modules_detail: list[MissingModule] = Field(
        default_factory=list,
        description="缺失模块详细信息（替换 missing_modules 字符串列表）",
    )


# ============================================================
# WebSocket 消息 Schema
# ============================================================


class WSMessage(BaseModel):
    """WebSocket 消息基类。"""

    type: str = Field(
        ..., description="消息类型: status / partial_answer / final_answer / error"
    )
    data: dict = Field(..., description="消息数据")


class WSStatusData(BaseModel):
    """WebSocket 状态消息。"""

    message: str = Field(..., description="状态描述")
    trace_id: str = Field("", description="追踪 ID")


class WSPartialAnswerData(BaseModel):
    """WebSocket 部分回答。"""

    text: str = Field(..., description="部分回答文本")
    sequence: int = Field(..., ge=1, description="序号")
    trace_id: str = Field("", description="追踪 ID")
