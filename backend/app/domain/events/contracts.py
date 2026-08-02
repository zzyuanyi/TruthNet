"""Event Cluster 事件簇交接契约 — Phase C 任务 15.

数据组 → 后端交接的唯一结构。
正式字段为 event_cluster_id（领域模型、数据库、导入合同统一），
不提供 cluster_id 作为领域层正式字段。
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SourceType = Literal["announcement", "research_report", "news", "regulation"]
Sentiment = Literal["positive", "negative", "neutral", "mixed", "unknown"]

# sentiment_score 固定范围（合同写死，禁止越界）
SENTIMENT_SCORE_MIN = -1.0
SENTIMENT_SCORE_MAX = 1.0

# 允许的事件簇 ID 前缀
EVENT_CLUSTER_ID_PREFIX = "evtcl_"


class EventSourceRef(BaseModel):
    """事件来源引用 — 每条来源必须可追溯到具体公告/研报/新闻/监管记录."""

    source_id: str = Field(..., description="来源在本文件内的唯一 ID")
    source_type: SourceType = Field(..., description="来源类型")
    source_record_id: str = Field(
        ..., description="底层来源记录 ID（如公告 object_id）"
    )
    title: str = Field(..., description="来源标题")
    published_at: date | None = Field(default=None, description="发布日期")
    source_uri: str | None = Field(default=None, description="来源 URI")
    content_hash: str | None = Field(default=None, description="内容哈希")
    fcode: str | None = Field(default=None, description="公告类型代码（公告来源适用）")


class EventClusterRecord(BaseModel):
    """事件簇交接记录 — 后端消费的正式结构."""

    event_cluster_id: str = Field(..., description="事件簇唯一 ID（evtcl_ 前缀）")
    entity_id: str = Field(..., description="公司 entity_id（与 companies 表对齐）")
    wind_code: str = Field(..., description="Wind 代码")
    topic: str = Field(..., description="事件簇主题")
    summary: str = Field(default="", description="事件簇摘要")
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="结束日期")
    event_count: int = Field(..., ge=1, description="事件数量（>=1）")
    sentiment: Sentiment = Field(..., description="事件簇情感")
    sentiment_score: float | None = Field(
        default=None,
        ge=SENTIMENT_SCORE_MIN,
        le=SENTIMENT_SCORE_MAX,
        description="情感得分，范围 [-1,1]",
    )
    sources: list[EventSourceRef] = Field(..., min_length=1, description="来源列表")
    evidence_ids: list[str] = Field(..., min_length=1, description="关联 Evidence ID")
    cluster_method: str = Field(default="", description="聚类方法")
    cluster_version: str = Field(default="", description="聚类版本")
    dataset_version: str = Field(default="", description="数据集版本")
    quality_flags: list[str] = Field(default_factory=list, description="质量标记")
    created_at: datetime = Field(..., description="创建时间 (ISO-8601)")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    # ── 校验 ────────────────────────────────────────────

    @field_validator("event_cluster_id")
    @classmethod
    def _check_event_cluster_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("event_cluster_id 不能为空")
        if not v.startswith(EVENT_CLUSTER_ID_PREFIX):
            raise ValueError(
                f"event_cluster_id 必须以 {EVENT_CLUSTER_ID_PREFIX!r} 开头: {v!r}"
            )
        if any(not ch.isalnum() and ch not in "_" for ch in v):
            raise ValueError(f"event_cluster_id 含非法字符: {v!r}")
        return v

    @model_validator(mode="after")
    def _check_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date 不得晚于 end_date")
        # event_count 与去重后 sources 数量一致性
        unique_sources = {(s.source_type, s.source_record_id) for s in self.sources}
        if len(unique_sources) != len(self.sources):
            raise ValueError("sources 存在重复来源 (source_type + source_record_id)")
        if self.event_count != len(self.sources):
            raise ValueError(
                f"event_count({self.event_count}) 与 sources 数量({len(self.sources)}) 不一致"
            )
        return self


def make_event_cluster_id(
    wind_code: str,
    topic: str,
    start_date: date,
    end_date: date,
    source_record_ids: list[str],
    cluster_version: str,
) -> str:
    """生成确定性事件簇 ID.

    evtcl_<sha256(wind_code | normalized_topic | start_date | end_date |
                  sorted_source_record_ids | cluster_version)[:24]>
    """
    raw = "|".join(
        [
            wind_code,
            " ".join(topic.split()).strip(),
            start_date.isoformat(),
            end_date.isoformat(),
            "|".join(sorted(source_record_ids)),
            cluster_version,
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{EVENT_CLUSTER_ID_PREFIX}{digest}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
