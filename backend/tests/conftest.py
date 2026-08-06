"""pytest 全局配置 — V12."""

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── WS/REST 测试会话兜底清理（对齐审计 P2-2）────────────────
# 单个测试的 autouse fixture 在全量并发场景偶发失效，
# session 级基线+兜底确保测试产生的会话不污染演示数据库。

_session_baseline: set[str] | None = None


def _session_ids() -> set[str]:
    if settings.SQL_BACKEND != "mysql":
        return set()
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return set(
                conn.execute(
                    text("SELECT session_id FROM conversation_sessions")
                ).scalars()
            )
    finally:
        engine.dispose()


def pytest_sessionstart(session) -> None:
    """记录测试开始前的会话基线（仅 mysql）。"""
    global _session_baseline
    _session_baseline = _session_ids()
    logger.info("[ws-cleanup] sessionstart baseline=%s", len(_session_baseline))


def pytest_sessionfinish(session, exitstatus) -> None:
    """测试结束后检查会话数量（对齐审计 P1-4：只告警，不删除）.

    删除仅由各测试的 ws_session_tracker 按信封归属执行；
    此处若发现测试产生未清理会话，只记录告警（可能来自并发智能体/
    用户操作，不得代删）。
    """
    global _session_baseline
    if _session_baseline is None:
        return
    after = _session_ids()
    new_ids = after - _session_baseline
    if new_ids:
        logger.warning(
            "[ws-cleanup] 测试后有 %s 个未清理会话（仅告警，不删除）：%s",
            len(new_ids),
            ", ".join(sorted(new_ids))[:200],
        )


def pytest_configure(config):
    """注册自定义 markers."""
    config.addinivalue_line(
        "markers", "integration: integration tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "external: tests requiring external services (MySQL, Neo4j)"
    )
    config.addinivalue_line("markers", "mysql: MySQL integration tests")
    config.addinivalue_line("markers", "neo4j: Neo4j integration tests")
    config.addinivalue_line(
        "markers", "full_profile: tests requiring full profile (MySQL + Neo4j)"
    )


@pytest.fixture(scope="session", autouse=True)
def _seed_lite_kangmei_fixture():
    """CI 自包含：lite profile 下确保 SQLite 有表 + 康美 fixture 数据.

    背景: Finance/load_context/persist_turn 在 lite 模式读取 SQLite。本地
    data/truthnet.db 含康美 fixture，但 CI 全新 checkout 无此文件，导致
    websocket 集成测试因 0 条财务数据而无 Claim。

    本 fixture:
    - 仅当 settings.SQL_BACKEND == 'sqlite' 时生效（full/mysql 不动）；
    - 用 ORM 建全量表（含 conversation 表，消除 load_context/persist_turn
      的 'no such table' 噪音）；
    - balance_sheet 为空时从 load_kangmei_fixture 加载康美数据（幂等）。
    """
    from app.core.config import settings

    if settings.SQL_BACKEND != "sqlite":
        return

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.infrastructure.persistence.models import Base

    _repo_root = Path(__file__).resolve().parents[2]
    db_path = Path(settings.SQLITE_PATH)
    if not db_path.is_absolute():
        db_path = _repo_root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM balance_sheet")).scalar()
        except Exception:  # noqa: BLE001 — 表不存在视为空
            cnt = 0
    if cnt == 0:
        import sys

        scripts_dir = str(_repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from load_kangmei_fixture import run_load  # noqa: E402

        session_factory = sessionmaker(bind=engine)
        stats = run_load(session_factory, "kangmei-fixture-v1", dry_run=False)
        logger.info("Seeded lite SQLite kangmei fixture: %s", stats)
    engine.dispose()
