"""通用 Schema：统一响应格式、健康检查、错误响应。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UnifiedResponse(BaseModel, Generic[T]):
    """统一 REST 响应格式。

    所有 API 接口必须使用此格式包裹返回值。
    """

    code: int = Field(default=0, description="状态码：0=成功，400/404/422/500/503")
    data: T | None = Field(default=None, description="响应数据")
    message: str = Field(default="ok", description="提示信息")
    trace_id: str = Field(..., description="请求追踪 ID (UUID4)")


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(default="healthy", description="服务状态")
    version: str = Field(..., description="应用版本号")


class ErrorDetail(BaseModel):
    """错误详情。"""

    field: str | None = Field(default=None, description="出错的字段名")
    reason: str = Field(..., description="错误原因")


class ErrorResponse(BaseModel):
    """错误响应结构。"""

    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    trace_id: str = Field(..., description="请求追踪 ID")
    details: list[ErrorDetail] | None = Field(default=None, description="详细错误列表")
