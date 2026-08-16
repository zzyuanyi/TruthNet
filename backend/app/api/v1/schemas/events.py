"""事件 REST Schema — V12 §11.11 + Phase C 任务 15 事件簇交接.

正式字段统一为 event_cluster_id（不提供 cluster_id 作为领域层正式字段）。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["announcement", "research_report", "news", "regulation"]
Sentiment = Literal["positive", "negative", "neutral", "mixed", "unknown"]


class SentimentSummary(BaseModel):
    """情绪统计."""

    positive_count: int = Field(default=0)
    negative_count: int = Field(default=0)
    neutral_count: int = Field(default=0)
    total_count: int = Field(default=0)
    negative_ratio: float = Field(default=0.0, description="负面占比 0-1")


class EventSourceDTO(BaseModel):
    """事件簇来源."""

    source_id: str = Field(..., description="来源 ID")
    source_type: SourceType = Field(..., description="来源类型")
    source_record_id: str = Field(..., description="底层来源记录 ID")
    title: str = Field(..., description="标题")
    published_at: date | None = Field(default=None, description="发布日期")
    source_uri: str | None = Field(default=None, description="来源 URI")
    content_hash: str | None = Field(default=None, description="内容哈希")
    fcode: str | None = Field(default=None, description="公告类型代码")


class EventCluster(BaseModel):
    """事件簇 — 正式字段 event_cluster_id."""

    event_cluster_id: str = Field(..., description="事件簇唯一 ID")
    topic: str = Field(..., description="簇主题")
    event_count: int = Field(default=0, description="包含事件数")
    start_date: str = Field(default="", description="起始日期")
    end_date: str = Field(default="", description="结束日期")
    sentiment: str = Field(default="neutral", description="主导情绪")
    summary: str = Field(default="", description="簇摘要")
    cluster_method: str = Field(default="", description="聚类方法")
    cluster_version: str = Field(default="", description="聚类版本")
    sources: list[EventSourceDTO] = Field(default_factory=list, description="来源列表")
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
    object_id: str = Field(
        default="", description="公告原始 object_id（摘要端点定位用）"
    )


class AnnouncementSummaryData(BaseModel):
    """公告 PDF 摘要（按需下载解析，不落库、不保留 PDF）."""

    object_id: str = Field(..., description="公告 object_id")
    title: str = Field(default="", description="公告标题")
    evidence_id: str = Field(default="", description="统一 evidence_id")
    source_uri: str | None = Field(default=None, description="原文链接")
    summary: str = Field(default="", description="公告内容摘要")
    method: str = Field(
        default="pdf_llm", description="pdf_llm | text_excerpt | title_only"
    )


class RatingChange(BaseModel):
    """评级变化."""

    date: str = Field(default="", description="日期")
    org_name: str = Field(..., description="评级机构")
    prev_rating: str = Field(default="", description="前次评级")
    new_rating: str = Field(default="", description="当前评级")
    change: str = Field(default="maintain", description="up / down / maintain")
    title: str = Field(default="", description="研报标题")
    evidence_id: str = Field(default="", description="关联证据 ID（可 Lookup 追溯）")


class KeywordSummary(BaseModel):
    """关键词摘要."""

    top_keywords: list[dict] = Field(
        default_factory=list, description="高频关键词及频次"
    )
    negative_keywords: list[str] = Field(default_factory=list, description="负面关键词")


class CausalityStep(BaseModel):
    """因果链步骤（⑧ B2：结构化步骤数组，每步带 statement_type 与证据）."""

    text: str = Field(..., description="步骤说明")
    statement_type: str = Field(
        default="inference", description="observed | inference | projection"
    )
    evidence_ids: list[str] = Field(default_factory=list)


class ImpactConclusion(BaseModel):
    """舆情影响结论（⑧ B2 第一阶段，include_impacts=true 时生成）."""

    conclusion: str = Field(..., description="影响结论文本")
    impact_type: str = Field(
        default="operation",
        description="equity_structure | operation | financing | market",
    )
    direction: str = Field(
        default="neutral", description="positive | negative | neutral"
    )
    severity: str = Field(default="low", description="low | medium | high")
    evidence_ids: list[str] = Field(
        default_factory=list, description="必须 ⊆ 输入证据集合"
    )
    causality_chain: list[CausalityStep] = Field(default_factory=list)
    statement_type: str = Field(
        default="inference", description="observed | inference | projection"
    )
    display_tag: str = Field(
        default="推断",
        description="后端按 statement_type 确定性渲染：observed=已发生 / "
        "inference=推断 / projection=风险推演（不由 LLM 措辞决定）",
    )


class EventsResponseData(BaseModel):
    """舆情事件响应数据 — V12 §11.11 + Phase C 事件簇."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    sentiment_summary: SentimentSummary = Field(default_factory=SentimentSummary)
    event_clusters: list[EventCluster] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    rating_changes: list[RatingChange] = Field(default_factory=list)
    keyword_summary: KeywordSummary = Field(default_factory=KeywordSummary)
    impact_conclusions: list[ImpactConclusion] = Field(
        default_factory=list,
        description="舆情影响结论（⑧ B2，include_impacts=true 时生成）",
    )
    impact_warnings: list[str] = Field(
        default_factory=list,
        description=(
            "舆情影响分析降级提示（⑧ B2，include_impacts=true 时生成；"
            "LLM 失败/超时/无事实/证据丢弃），与通用 warnings 字段并存不冲突"
        ),
    )
    evidence_ids: list[str] = Field(default_factory=list)
    announcements_available: bool = Field(default=True, description="公告数据是否可用")
    months_covered: int = Field(default=36, description="覆盖月数")
    warnings: list[str] = Field(default_factory=list)
