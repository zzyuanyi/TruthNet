"""Market Pulse 舆情脉搏 DTO（旋转地球监控数据契约）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketPulseItemDTO(BaseModel):
    """一条监控到的全球金融资讯（映射到地球坐标）。"""

    id: str = Field(..., description="稳定 ID（链接哈希），前端用于去重与 TTL 管理")
    title: str
    url: str
    source_name: str
    region_code: str = Field(..., description="区域码：US/CN/ASIA/EU")
    country: str
    lat: float
    lng: float
    published_at: datetime
    severity: str = Field("info", description="严重度：info/warning/critical（标题关键词推断）")


class MarketPulseClusterDTO(BaseModel):
    """国家热点聚合（驱动地球亮点的大小与亮度）。"""

    country: str
    region_code: str
    lat: float
    lng: float
    count: int = Field(..., description="该国 24h 内资讯条数")
    critical: int = 0
    warning: int = 0
    info: int = 0
    top_severity: str = Field("info", description="该国最高严重度")
    top_title: str = Field("", description="最新一条标题")
    intensity: float = Field(..., ge=0, le=1, description="热点强度 0-1，条数越多越亮")
    latest_published_at: datetime


class MarketPulseData(BaseModel):
    """全球舆情脉搏载荷。"""

    fetched_at: datetime
    ttl_seconds: int = Field(86400, description="存量保留窗口（秒），当前为 24h")
    poll_seconds: int = Field(600, description="建议轮询间隔（秒），当前 10 分钟")
    regions: list[str] = Field(default_factory=list)
    items: list[MarketPulseItemDTO] = Field(default_factory=list)
    clusters: list[MarketPulseClusterDTO] = Field(default_factory=list)
    ok_sources: int = Field(0, description="成功拉取的源数量")
    failed_sources: list[str] = Field(default_factory=list)
