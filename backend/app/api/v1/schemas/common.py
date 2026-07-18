"""API v1 通用 Schema — V12 baseline.

定义 V12 响应 envelope：{data, meta, warnings}。
"""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.config import settings

T = TypeVar("T")


class ApiMeta(BaseModel):
    """API 响应元数据 — V12 standard."""

    request_id: str = Field(..., description="请求 ID (UUID4)")
    trace_id: str = Field(..., description="追踪 ID (UUID4)")
    schema_version: str = Field(default="1.0", description="Schema 版本")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="生成时间 (ISO 8601)",
    )
    data_as_of: str = Field(default="", description="数据截止日期")
    dataset_version: str = Field(
        default_factory=lambda: settings.DATASET_VERSION,
        description="数据集版本",
    )
    rule_set_version: str = Field(
        default_factory=lambda: settings.RULE_SET_VERSION,
        description="规则集版本",
    )
    graph_version: str = Field(
        default_factory=lambda: settings.GRAPH_VERSION,
        description="图谱版本",
    )


class WarningItem(BaseModel):
    """警告项."""

    code: str = Field(..., description="警告代码")
    message: str = Field(..., description="警告信息")
    module: str | None = Field(None, description="来源模块")
    recoverable: bool = Field(default=True, description="是否可恢复")


class V12Response(BaseModel, Generic[T]):
    """V12 统一响应 envelope.

    新接口使用此格式。旧接口保留 UnifiedResponse 兼容。
    """

    data: T | None = Field(default=None, description="响应数据")
    meta: ApiMeta = Field(..., description="响应元数据")
    warnings: list[WarningItem] = Field(default_factory=list, description="警告列表")
