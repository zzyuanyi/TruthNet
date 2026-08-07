"""报告路由 — Phase D #8.

POST /api/v1/reports                     → 202 创建（幂等）
GET  /api/v1/reports/{report_id}         → 状态
GET  /api/v1/reports/{report_id}/file    → 下载（仅 succeeded）

Router 职责：参数校验、创建任务、路径穿越防护、错误信封。
生成逻辑在 report_service（受控后台任务，状态机持久化）。
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as FPath
from fastapi.responses import FileResponse

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.api.v1.schemas.reports import (
    ReportCreateRequest,
    ReportJobStatusData,
)
from app.application.services import report_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


def _trace() -> str:
    return str(uuid.uuid4())


@router.post(
    "/reports",
    status_code=202,
    response_model=V12Response[ReportJobStatusData],
    responses={
        # 200 也声明非空 schema（契约测试要求所有操作有 200 schema；
        # 实际语义仍为 202 已接受）
        200: {"model": V12Response[ReportJobStatusData], "description": "任务状态"},
    },
)
async def create_report(request: ReportCreateRequest):
    """创建 PDF 报告任务（HTTP 202；幂等键重试不重复建任务）。"""
    trace_id = _trace()

    # 校验 company_code 存在
    try:
        from app.application.services.company_resolver import resolve_company

        rec = await resolve_company(request.company_code)
        if rec is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "https://truthnet.dev/errors/company-not-found",
                    "title": "Company Not Found",
                    "status": 404,
                    "detail": f"未找到公司: {request.company_code}",
                    "error_code": "COMPANY_NOT_FOUND",
                    "trace_id": trace_id,
                    "recoverable": True,
                },
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — 解析失败不阻塞创建（报告仍可尝试）
        logger.warning("report: 公司解析失败 %s", request.company_code, exc_info=True)

    try:
        report_id, created = report_service.create_report_job(
            company_code=request.company_code,
            session_id=request.session_id,
            idempotency_key=request.idempotency_key,
            request_payload=request.model_dump(),
            trace_id=trace_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("report: 创建任务失败")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "https://truthnet.dev/errors/report-create-failed",
                "title": "Report Create Failed",
                "status": 500,
                "detail": f"创建报告任务失败: {exc}",
                "error_code": "REPORT_CREATE_FAILED",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # 幂等命中 → 直接返回既有任务（不重新启动）
    if not created:
        job = report_service.get_report_job(report_id)
        return _status_response(job, trace_id)

    # 启动受控后台生成
    await report_service.start_report_generation(report_id)
    job = report_service.get_report_job(report_id)
    return _status_response(job, trace_id)


@router.get("/reports/{report_id}", response_model=V12Response[ReportJobStatusData])
async def get_report_status(report_id: str = FPath(...)):
    """报告任务状态（含进度/错误/可下载标志）。"""
    trace_id = _trace()
    job = report_service.get_report_job(report_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/report-not-found",
                "title": "Report Not Found",
                "status": 404,
                "detail": f"报告任务不存在: {report_id}",
                "error_code": "REPORT_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )
    return _status_response(job, trace_id)


@router.get(
    "/reports/{report_id}/file",
    responses={
        # OpenAPI 契约：声明 200 引用报告状态模型（实际响应为二进制 PDF；
        # 该声明供前端类型/契约测试消费，保证所有操作有非空 200 schema）
        200: {
            "model": V12Response[ReportJobStatusData],
            "description": "PDF 报告文件（application/pdf）",
        }
    },
)
async def download_report(report_id: str = FPath(...)):
    """下载报告文件（仅 succeeded；路径穿越防护）。"""
    trace_id = _trace()
    job = report_service.get_report_job(report_id)
    if job is None:
        raise HTTPException(status_code=404, detail="报告任务不存在")
    if job["status"] != "succeeded" or not job.get("file_path"):
        raise HTTPException(
            status_code=409,
            detail={
                "type": "https://truthnet.dev/errors/report-not-ready",
                "title": "Report Not Ready",
                "status": 409,
                "detail": "报告尚未生成完成或生成失败",
                "error_code": "REPORT_NOT_READY",
                "trace_id": trace_id,
                "recoverable": False,
            },
        )

    # 路径穿越防护：文件必须在配置的报告根目录下
    root = _report_root_resolved()
    file_path = (root / job["file_path"]).resolve()
    if not str(file_path).startswith(str(root.resolve())):
        logger.warning(
            "report: 路径穿越拦截 report=%s path=%s", report_id, job["file_path"]
        )
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="报告文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
    )


def _report_root_resolved() -> Path:
    path = Path(settings.REPORT_ROOT_DIR)
    if not path.is_absolute():
        path = report_service._repo_root() / path
    return path.resolve()


def _status_response(job: dict, trace_id: str) -> V12Response[ReportJobStatusData]:
    download = job["status"] == "succeeded" and bool(job.get("file_path"))
    data = ReportJobStatusData(
        report_id=job["report_id"],
        status=job["status"],
        progress=int(job["progress"] or 0),
        created_at=job.get("created_at"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        download_available=download,
        file_sha256=job.get("file_sha256"),
        company_code=job.get("company_code"),
        session_id=job.get("session_id"),
    )
    return V12Response(
        data=data,
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )
