"""API v1 异常处理器 — V12 baseline.

将异常转换为 RFC 9457 Problem Details 格式。
"""

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import ProblemDetail


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器."""
    trace_id = str(uuid.uuid4())
    detail = ProblemDetail(
        type="https://truthnet/errors/internal-error",
        title="Internal Server Error",
        status=500,
        detail=str(exc),
        instance=str(request.url),
        error_code="INTERNAL_ERROR",
        trace_id=trace_id,
        recoverable=False,
    )
    return JSONResponse(
        status_code=500,
        content=detail.model_dump(),
    )


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """404 处理器."""
    trace_id = str(uuid.uuid4())
    detail = ProblemDetail(
        type="https://truthnet/errors/not-found",
        title="Resource Not Found",
        status=404,
        detail=str(exc),
        instance=str(request.url),
        error_code="NOT_FOUND",
        trace_id=trace_id,
        recoverable=False,
    )
    return JSONResponse(
        status_code=404,
        content=detail.model_dump(),
    )
