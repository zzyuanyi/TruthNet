"""pytest 全局配置 — V12."""

import logging
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


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
