"""行业分类覆盖补全 — 领域服务包（档案 v1.1）。

唯一正式入口：scripts/industry_fill.py（CLI 编排）。
本包提供 provider / normalizer / staging / validation / guards / db / report / service。
"""

from app.application.services.industry_fill.constants import (  # noqa: F401
    DEFAULT_CACHE_DIR,
    PROVIDER_AKSHARE,
    QueryStatus,
)
from app.application.services.industry_fill.service import (  # noqa: F401
    RunConfig,
    run_pipeline,
)

__all__ = [
    "RunConfig",
    "run_pipeline",
    "QueryStatus",
    "PROVIDER_AKSHARE",
    "DEFAULT_CACHE_DIR",
]
