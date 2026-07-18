"""Events 舆情事件领域模型 — V12 baseline."""

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """时间线事件."""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    title: str = Field(..., description="事件标题")
    category: str = Field(default="其他", description="事件类别")
    summary: str = Field(default="", description="事件摘要")
    sentiment: str = Field(
        default="neutral", description="情感倾向: positive/negative/neutral"
    )
    sources: list[str] = Field(default_factory=list, description="信息来源")


class EventCluster(BaseModel):
    """事件簇."""

    topic: str = Field(..., description="话题名称")
    event_count: int = Field(default=0, description="事件数量")
    date_range: str = Field(default="", description="时间范围")
    events: list[TimelineEvent] = Field(default_factory=list)
