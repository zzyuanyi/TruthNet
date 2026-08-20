"""公共 SQLAlchemy Engine 工厂 — 全面审查 P0/P1 统一修复（8/19）.

背景：多个模块（persist_turn/load_context/events/provenance/risk/sessions/
equity_shareholder/memory_distillation/report_service/event_cluster_repository）
各自实现 `_get_engine`，多数只用 `SQL_BACKEND` 作缓存键，进程内切库后
（tests/conftest 运行时改写 MYSQL_DATABASE、验收双库探针、测试↔演示切换）
会复用指向旧库的 Engine——写路径（persist_turn/provenance/equity_shareholder/
memory_distillation/report）会把数据写进错误数据库（演示库误写），违反
「演示库 truthnet 零写入」铁律。

本模块统一实现（与 `_fetch._ENGINES` / `company_resolver._profile_key` 同契约）：
- 缓存键 = 完整连接 profile：mysql = backend/user/host/port/database；
  sqlite 含绝对路径；
- 新 profile 建立时 dispose 其他 profile 的旧 Engine（连接池不滞留、
  不跨库复用）；
- 幂等：同 profile 复用既有 Engine。

用法：
    from app.domain.finance._engine_utils import get_engine
    engine = get_engine()
"""

from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_lock = threading.Lock()
_ENGINES: dict[str, Engine] = {}


def _repo_root() -> Path:
    # backend/app/domain/finance/_engine_utils.py -> 项目根
    return Path(__file__).resolve().parents[4]


def engine_profile_key(settings) -> str:
    """连接 profile 完整身份 key（mysql 含库名，sqlite 含路径）。"""
    backend = settings.SQL_BACKEND
    if backend == "mysql":
        return (
            f"mysql:{settings.MYSQL_USER}:{settings.MYSQL_HOST}:"
            f"{settings.MYSQL_PORT}:{settings.MYSQL_DATABASE}"
        )
    return f"sqlite:{settings.SQLITE_PATH or 'data/truthnet.db'}"


def get_engine(settings=None):
    """按完整 profile 获取 Engine；切 profile 即 dispose 旧 Engine（线程安全）。

    Args:
        settings: 配置对象（默认 app.core.config.settings）。

    Returns:
        SQLAlchemy Engine（mysql/sqlite 按 SQL_BACKEND）。
    """
    from app.core.config import settings as _settings

    settings = settings or _settings
    key = engine_profile_key(settings)
    with _lock:
        if key in _ENGINES:
            return _ENGINES[key]
        # 新 profile：dispose 其他 profile 的旧 Engine，避免连接池滞留
        for other, engine in list(_ENGINES.items()):
            if other == key:
                continue
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001 — dispose 失败不阻断取数
                pass

        backend = settings.SQL_BACKEND
        if backend == "mysql":
            url = (
                f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
                f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
                f"/{settings.MYSQL_DATABASE}?charset=utf8mb4"
            )
            _ENGINES[key] = create_engine(url, echo=False, pool_pre_ping=True)
        else:  # sqlite
            path = Path(settings.SQLITE_PATH)
            if not path.is_absolute():
                path = _repo_root() / path
            _ENGINES[key] = create_engine(
                f"sqlite:///{path.as_posix()}", echo=False
            )
        return _ENGINES[key]


def dispose_all() -> None:
    """关闭全部缓存 Engine（进程退出/测试清理用）。"""
    with _lock:
        for engine in list(_ENGINES.values()):
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass
        _ENGINES.clear()
