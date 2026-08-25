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


class MarketPulseData(BaseModel):
    """全球舆情脉搏载荷。"""

    fetched_at: datetime
    ttl_seconds: int = Field(600, description="前端亮点保留时长（秒），过期熄灭")
    poll_seconds: int = Field(10, description="建议轮询间隔（秒）")
    regions: list[str] = Field(default_factory=list)
    items: list[MarketPulseItemDTO] = Field(default_factory=list)
    ok_sources: int = Field(0, description="成功拉取的源数量")
    failed_sources: list[str] = Field(default_factory=list)
