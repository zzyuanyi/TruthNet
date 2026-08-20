"""运行时数据库写守卫 — 全面审查 P0（8/19，8/19 拍板降级为 warning）.

背景：tests/conftest.py 的三重守卫只保护 pytest 测试进程（强制
truthnet_test、拒绝演示库）；服务进程（main.py 启动）与 REST/脚本进程
此前没有任何运行时防线——若误以演示库身份启动（.env 配错 MYSQL_DATABASE
或默认值 truthnet），GET 端点落库、会话持久化、报告任务等写路径会直接
写演示库 truthnet，违反「演示库 truthnet 零写入」铁律。

8/19 队长拍板（方案A 收敛 + 降级 warning）：**不做 fail-fast 阻断**——
本地开发 .env 即 `MYSQL_DATABASE=truthnet`，阻断会破坏开发/演示启动；
改为检测到「未授权写演示库」时打印醒目 warning（限频，每 profile 一次），
零行为变更，靠日志发现误配。测试进程有 conftest 三重守卫、验收有
acceptance_server 守卫，运行时防线定位为「告警兜底」。

用法：
    from app.core.write_guard import assert_db_writable, validate_runtime_write_policy

    # 写方法入口（写事务前调用）
    assert_db_writable()

    # lifespan 启动校验（告警不阻断）
    validate_runtime_write_policy()
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# 已告警的 profile（限频：每 profile 只告警一次，避免每次写路径刷屏）
_warned_profiles: set[str] = set()

_WARNING_TEMPLATE = (
    "【写守卫·降级告警】目标库 %r 是演示库（%r），未显式授权写入"
    "（ALLOW_DEMO_DB_WRITE=true 或使用 truthnet_test）。按队长拍板（8/19）"
    "本守卫不阻断写入，仅告警提示；请确认进程确实应写演示库，否则请切换到测试库。"
)


def _demo_db_name() -> str:
    return (settings.DEMO_DATABASE_NAME or "truthnet").strip().lower()


def _target_is_demo_db(database: str | None = None) -> bool:
    """mysql 模式下当前目标库是否为演示库（大小写不敏感）。"""
    if settings.SQL_BACKEND != "mysql":
        return False
    target = (database or settings.MYSQL_DATABASE or "").strip().lower()
    return bool(target) and target == _demo_db_name()


def _warn_once(database: str | None = None) -> None:
    profile = (
        f"{settings.SQL_BACKEND}:{settings.MYSQL_HOST}:{settings.MYSQL_PORT}:"
        f"{database or settings.MYSQL_DATABASE}"
    )
    if profile in _warned_profiles:
        return
    _warned_profiles.add(profile)
    logger.warning(
        _WARNING_TEMPLATE,
        settings.MYSQL_DATABASE,
        settings.DEMO_DATABASE_NAME or "truthnet",
    )


def assert_db_writable(database: str | None = None) -> None:
    """写路径守卫（降级告警）：未授权写演示库 → warning（不抛错、不阻断）。

    正式演示：.env 显式 ALLOW_DEMO_DB_WRITE=true 时静默放行；
    测试进程：conftest 已把目标库改写为 truthnet_test（≠演示库）静默放行。
    """
    if settings.ALLOW_DEMO_DB_WRITE:
        return
    if _target_is_demo_db(database):
        _warn_once(database)


def validate_runtime_write_policy() -> None:
    """lifespan 启动校验（降级告警）：mysql 模式 + 目标库==演示库 + 未授权。

    打印醒目 warning 提示误配，不阻断启动（8/19 队长拍板）。
    """
    if settings.ALLOW_DEMO_DB_WRITE:
        return
    if _target_is_demo_db():
        _warn_once()
