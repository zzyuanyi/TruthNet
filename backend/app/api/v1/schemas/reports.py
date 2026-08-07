"""PDF 报告 REST Schema — Phase D #8."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    """创建报告请求."""

    session_id: str | None = Field(None, description="关联会话 ID（可选）")
    company_code: str = Field(..., description="目标公司代码，如 600518.SH")
    idempotency_key: str | None = Field(
        None, description="幂等键（同一键重试不重复建任务）"
    )
    as_of: str | None = Field(None, description="数据截止日期 (YYYY-MM-DD / YYYYQn)")


class ReportJobStatusData(BaseModel):
    """报告任务状态."""

    report_id: str = Field(..., description="报告 ID")
    status: str = Field(..., description="queued/running/succeeded/failed/cancelled")
    progress: int = Field(0, ge=0, le=100, description="进度 0-100")
    created_at: datetime | None = Field(None, description="创建时间")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")
    error_code: str | None = Field(None, description="错误码")
    error_message: str | None = Field(None, description="错误信息")
    download_available: bool = Field(False, description="是否可下载")
    file_sha256: str | None = Field(None, description="文件 SHA-256")
    company_code: str | None = Field(None, description="公司代码")
    session_id: str | None = Field(None, description="会话 ID")
