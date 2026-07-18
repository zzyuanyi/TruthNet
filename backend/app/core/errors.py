"""V12 错误模型 — RFC 9457 Problem Details."""

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details 错误响应.

    用于 V12 所有 API 错误响应。
    """

    type: str = Field(
        default="about:blank",
        description="错误类型 URI",
        examples=["https://truthnet/errors/module-timeout"],
    )
    title: str = Field(
        default="Internal Server Error",
        description="简短错误标题",
    )
    status: int = Field(
        default=500,
        description="HTTP 状态码",
    )
    detail: str = Field(
        default="",
        description="详细错误描述",
    )
    instance: str = Field(
        default="",
        description="出错的请求路径",
    )
    error_code: str = Field(
        default="INTERNAL_ERROR",
        description="业务错误码",
    )
    trace_id: str = Field(
        default="",
        description="请求追踪 ID",
    )
    recoverable: bool = Field(
        default=False,
        description="是否可恢复",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="额外上下文信息",
    )
