"""健康检查响应 DTO — V12.

对齐 backend/app/api/v1/routers/health.py 实际返回结构。
"""

from pydantic import BaseModel


class HealthDataV1(BaseModel):
    """healthz 进程存活探针."""

    status: str
    version: str
    profile: str


class ReadyDataV1(BaseModel):
    """readyz 就绪探针（依赖服务可达性）. checks 为动态探针结果集。"""

    status: str
    profile: str
    checks: dict[str, dict] = {}
