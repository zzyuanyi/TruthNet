"""V12 错误模型 — RFC 9457 Problem Details."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """V12 错误码 — DESIGN_V12 §11.6 单一事实来源.

    路由层统一引用，防止错误码漂移（曾出现 COMPANY_NOT_FOUND / DB_UNAVAILABLE
    与契约不一致，前端按契约匹配错误分支落空）。
    """

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    COMPANY_NOT_COVERED = "COMPANY_NOT_COVERED"
    TURN_ALREADY_RUNNING = "TURN_ALREADY_RUNNING"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    GRAPH_UNAVAILABLE = "GRAPH_UNAVAILABLE"
    DATASTORE_UNAVAILABLE = "DATASTORE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"


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
