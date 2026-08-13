"""API v1 异常处理器 — V12 baseline + Phase D #1 故障识别.

将异常转换为 RFC 9457 Problem Details 格式。
Phase D #1：识别基础设施故障（MySQL/Neo4j/Chroma/LLM），
返回可恢复的结构化错误码，而非笼统 INTERNAL_ERROR。
"""

import logging
import uuid

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ErrorCode, ProblemDetail

logger = logging.getLogger(__name__)

# 已知基础设施故障 → 错误码/可恢复性/状态码
# 复用 ErrorCode 既有规范码：DATASTORE_UNAVAILABLE（MySQL/Chroma）、
# GRAPH_UNAVAILABLE（Neo4j）、LLM_TIMEOUT（LLM）。
_KNOWN_FAULTS = [
    # MySQL / SQLAlchemy
    (("pymysql", "OperationalError"), "DATASTORE_UNAVAILABLE", 503, True),
    (("sqlalchemy", "OperationalError"), "DATASTORE_UNAVAILABLE", 503, True),
    (("sqlalchemy", "DBAPIError"), "DATASTORE_UNAVAILABLE", 503, True),
    # Neo4j
    (("neo4j", "ServiceUnavailable"), "GRAPH_UNAVAILABLE", 503, True),
    (("neo4j", "AuthError"), "GRAPH_UNAVAILABLE", 503, False),
    (("neo4j.exceptions", "ServiceUnavailable"), "GRAPH_UNAVAILABLE", 503, True),
    # Chroma
    (("chromadb", ""), "DATASTORE_UNAVAILABLE", 503, True),
    # LLM / OpenAI
    (("openai", "APITimeoutError"), "LLM_TIMEOUT", 503, True),
    (("openai", "APIStatusError"), "LLM_TIMEOUT", 503, True),
    (("openai", "APIConnectionError"), "LLM_TIMEOUT", 503, True),
]


def _classify_fault(exc: Exception) -> tuple[str, int, bool] | None:
    """识别异常类型 → (error_code, status, recoverable)；未知返回 None。"""
    exc_type = type(exc)
    module_name = exc_type.__module__ or ""
    class_name = exc_type.__name__
    for (mod, cls), code, status, rec in _KNOWN_FAULTS:
        if cls and class_name == cls and (not mod or mod in module_name):
            return code, status, rec
        if not cls and mod in module_name:
            return code, status, rec
    return None


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器 — Phase D #1 识别基础设施故障。"""
    trace_id = str(uuid.uuid4())
    fault = _classify_fault(exc)
    if fault is not None:
        error_code, status, recoverable = fault
        logger.warning(
            "基础设施故障: error_code=%s trace_id=%s exc=%s",
            error_code,
            trace_id,
            type(exc).__name__,
        )
        detail = ProblemDetail(
            type=f"https://truthnet/errors/{error_code.lower()}",
            title=error_code,
            status=status,
            detail=f"基础设施服务不可用（{type(exc).__name__}），请稍后重试或检查服务状态",
            instance=str(request.url),
            error_code=error_code,
            trace_id=trace_id,
            recoverable=recoverable,
        )
        return JSONResponse(
            status_code=status,
            content=detail.model_dump(),
            media_type="application/problem+json",
        )
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
        media_type="application/problem+json",
    )


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """404 处理器.

    路由层抛出的 HTTPException 若携带自定义 detail dict
    （如 error_code），原样透传，避免覆盖业务错误码。
    """
    trace_id = str(uuid.uuid4())
    detail_dict = getattr(exc, "detail", None)
    if isinstance(detail_dict, dict):
        content = {**detail_dict, "trace_id": trace_id}
        return JSONResponse(
            status_code=404,
            content=content,
            media_type="application/problem+json",
        )

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
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 请求校验错误 → 顶层 ProblemDetail（SCHEMA_VALIDATION_FAILED）.

    修复：之前 RequestValidationError 未注册，422 返回 FastAPI 默认
    {"detail": [...]} 结构，与 V12 错误码体系（§11.6）断档。
    """
    trace_id = str(uuid.uuid4())
    detail = ProblemDetail(
        type="about:blank",
        title="Validation Error",
        status=422,
        detail="请求参数校验失败",
        instance=str(request.url),
        error_code=ErrorCode.SCHEMA_VALIDATION_FAILED,
        trace_id=trace_id,
        recoverable=False,
        extra={"errors": jsonable_encoder(exc.errors())},
    )
    return JSONResponse(
        status_code=422,
        content=detail.model_dump(),
        media_type="application/problem+json",
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """非 404 HTTPException → 统一顶层 ProblemDetail.

    修复：之前未注册，其他 HTTPException 走 FastAPI 默认 {"detail": {...}}
    嵌套结构；dict detail 携带的业务错误码/可恢复性现在透传到顶层，
    media_type 统一为 application/problem+json（RFC 9457）。
    """
    trace_id = str(uuid.uuid4())
    detail = exc.detail
    if isinstance(detail, dict):
        content = {
            # type 由路由层指定（如 https://truthnet.dev/errors/invalid-period），
            # 不得固定覆盖为 about:blank
            "type": detail.get("type", "about:blank"),
            "title": detail.get("title", str(exc.status_code)),
            "status": exc.status_code,
            "detail": detail.get("detail", ""),
            "instance": str(request.url),
            "error_code": detail.get("error_code", "HTTP_ERROR"),
            "trace_id": detail.get("trace_id", trace_id),
            "recoverable": detail.get("recoverable", False),
            "extra": detail.get("extra", {}),
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
            headers=dict(exc.headers or {}),
        )
    problem = ProblemDetail(
        type="about:blank",
        title=str(exc.status_code),
        status=exc.status_code,
        detail=str(detail),
        instance=str(request.url),
        error_code="HTTP_ERROR",
        trace_id=trace_id,
        recoverable=False,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )
