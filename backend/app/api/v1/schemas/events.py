"""舆情事件 REST Schema — V12 §11.11."""

from pydantic import BaseModel, Field


class SentimentSummary(BaseModel):
    """情绪统计."""

    positive_count: int = Field(default=0)
    negative_count: int = Field(default=0)
    neutral_count: int = Field(default=0)
    total_count: int = Field(default=0)
    negative_ratio: float = Field(default=0.0, description="负面占比 0-1")


class EventCluster(BaseModel):
    """事件簇 — V12 §11.11."""

    cluster_id: str = Field(..., description="事件簇 ID")
    topic: str = Field(..., description="簇主题")
    event_count: int = Field(default=0, description="包含事件数")
    date_range: str = Field(default="", description="日期范围，如 '2024Q1-2025Q2'")
    sentiment: str = Field(default="neutral", description="主导情绪")
    summary: str = Field(default="", description="簇摘要")
    evidence_ids: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """时间线事件."""

    date: str = Field(..., description="日期 YYYY-MM-DD")
    title: str = Field(..., description="事件标题")
    category: str = Field(default="公告", description="事件类别")
    fcode_label: str = Field(default="", description="fcode 中文标签")
    sentiment: str = Field(default="neutral", description="情绪")
    summary: str = Field(default="", description="摘要")
    sources: list[str] = Field(default_factory=list, description="来源")
    evidence_ids: list[str] = Field(default_factory=list)


class RatingChange(BaseModel):
    """评级变化."""

    date: str = Field(default="", description="日期")
    org_name: str = Field(..., description="评级机构")
    prev_rating: str = Field(default="", description="前次评级")
    new_rating: str = Field(default="", description="当前评级")
    change: str = Field(default="maintain", description="up / down / maintain")
    title: str = Field(default="", description="研报标题")


class KeywordSummary(BaseModel):
    """关键词摘要."""

    top_keywords: list[dict] = Field(
        default_factory=list, description="高频关键词及频次"
    )
    negative_keywords: list[str] = Field(default_factory=list, description="负面关键词")


class EventsResponseData(BaseModel):
    """舆情事件响应数据 — V12 §11.11."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    sentiment_summary: SentimentSummary = Field(default_factory=SentimentSummary)
    event_clusters: list[EventCluster] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    rating_changes: list[RatingChange] = Field(default_factory=list)
    keyword_summary: KeywordSummary = Field(default_factory=KeywordSummary)
    evidence_ids: list[str] = Field(default_factory=list)
    announcements_available: bool = Field(default=True, description="公告数据是否可用")
    months_covered: int = Field(default=36, description="覆盖月数")
    warnings: list[str] = Field(default_factory=list)
