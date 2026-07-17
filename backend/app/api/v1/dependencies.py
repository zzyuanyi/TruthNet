"""API v1 依赖注入 — V12 baseline.

提供 profile-aware 的 Adapter 注入。
"""

from app.core.config import settings


def get_profile() -> str:
    """获取当前运行 profile."""
    return settings.TRUTHNET_PROFILE


def is_full_profile() -> bool:
    """是否 full profile."""
    return settings.TRUTHNET_PROFILE == "full"
