"""provider 协议、结果 DTO 与重试策略（档案 v1.1 §3.1/§6.3）。"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from backend.app.application.services.industry_fill.constants import (
    RETRYABLE_EXC_TYPES,
    QueryStatus,
)


@dataclass
class ProviderResult:
    """单个股票代码的查询结果（staging 记录的业务字段，档案 §2.2）。"""

    wind_code: str
    security_number: str
    query_status: QueryStatus
    industry_l1: str | None = None
    industry_l2: str | None = None
    sw_indu_code: str | None = None
    provider: str = ""
    provider_endpoint: str = ""
    attempts: int = 0
    last_error: str | None = None
    queried_at: str = ""
    raw_value_hash: str = ""
    # 本次查询是否遇到限流/降级响应（即使经其他主机/兜底恢复也置位）——
    # 供自适应节流降并发，避免接口过载。
    throttled: bool = False

    def __post_init__(self) -> None:
        if not self.queried_at:
            self.queried_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def raw_value_hash(raw_text: str) -> str:
    """原始返回值哈希（用于同码复核与缓存去重）。"""
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


class IndustryProvider(Protocol):
    """行业数据源协议。实现方必须自带口径探测与 fail-closed 行为。"""

    name: str
    mapping_version: str
    dataset_version: str

    def probe(self) -> dict:  # pragma: no cover - 协议定义
        """接口探测：返回 {akshare_version, endpoint, columns, samples, notes}。"""
        ...

    def query_many(
        self,
        codes: list[str],
        *,
        retry_empty: bool = False,
        cached: dict[str, ProviderResult] | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        on_progress: Callable[[int, int, dict[str, int]], None] | None = None,
        on_result: Callable[[ProviderResult], None] | None = None,
        concurrency: int = 4,
    ) -> list[ProviderResult]:
        """查询一批 wind_code，逐码返回 ProviderResult；on_result 逐码回调
        （用于每查询完成一个代码即落盘 staging，档案 §6.2）；concurrency
        控制并发请求数（Session 连接复用 + 线程池，默认 4）。"""
        ...


def is_retryable(exc: BaseException) -> bool:
    """只对可重试异常重试（档案 §6.3）：超时、连接错误、429/5xx、服务端临时错误。

    参数错误、字段解析错误、未知行业不重试。
    """
    if isinstance(exc, RETRYABLE_EXC_TYPES):
        return True
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if isinstance(status, int) and (status == 429 or 500 <= status < 600):
        return True
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if isinstance(code, int) and (code == 429 or 500 <= code < 600):
            return True
    return False


def call_with_retry(
    fn: Callable[[], object],
    *,
    max_retries: int,
    backoff_seconds: float,
) -> tuple[object, int, BaseException | None]:
    """执行 fn，可重试异常按指数退避 + 抖动重试；返回 (结果, 尝试次数, 最后异常)。"""
    attempts = 0
    last_exc: BaseException | None = None
    while True:
        attempts += 1
        try:
            return fn(), attempts, None
        except Exception as exc:  # noqa: BLE001 - 需要按类型分类
            last_exc = exc
            if attempts > max_retries or not is_retryable(exc):
                return None, attempts, last_exc
            delay = backoff_seconds * (2 ** (attempts - 1))
            delay += random.uniform(0, backoff_seconds * 0.5)  # 有限随机抖动
            time.sleep(delay)


@dataclass
class ProgressCounter:
    """查询进度计数（供日志与报告）。"""

    success: int = 0
    empty: int = 0
    unmapped: int = 0
    error: int = 0
    cached: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "success": self.success,
            "empty": self.empty,
            "unmapped": self.unmapped,
            "error": self.error,
            "cached": self.cached,
        }
