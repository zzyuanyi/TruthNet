"""pytest 全局配置 — V12."""

import logging
import os
import re
from pathlib import Path

import pytest
from sqlalchemy import URL, create_engine, text

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── MySQL 测试库强制隔离守卫（v3.1，2026-08-11）──────────────
# 背景：本地 mysql 模式曾直连演示库 truthnet 跑测试——conftest 的基线
# 查询与会话兜底清理都是对演示库的读写。隔离规则：
#   1. 测试必须显式配置 MYSQL_TEST_DATABASE/USER/PASSWORD，默认全空 = 拒绝；
#   2. 测试库名严格等于显式配置值（allowlist），且不得等于演示库、
#      不得是系统库或不安全命名；
#   3. 连接后 SELECT DATABASE() 二次确认，任何不一致 fail-fast。
# 测试库生命周期：单一 truthnet_test（子集起步 → 全量）；恢复演练用临时
# truthnet_restore_test（见竞赛管理 docs 决策记录 2026-08-11）。

_SAFE_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_FORBIDDEN_DB_NAMES = {
    "truthnet",
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
}


def _validate_test_db_config(
    mysql_database: str,
    test_database: str,
    test_user: str,
    test_password: str = "",
    mysql_user: str = "",
) -> str | None:
    """校验测试库配置，返回错误信息（None = 通过）。纯函数，便于单测。

    v3.4 补强：
    - 空密码拒绝（MySQL 空密码账号风险）；
    - 大小写不敏感（MySQL lower_case_table_names=1 下 TRUTHNET==truthnet）；
    - 测试用户名不得与演示用户名相同。
    """
    if not test_database or not test_user or not test_password:
        return (
            "MySQL 测试必须显式配置 MYSQL_TEST_DATABASE/USER/PASSWORD 三件套。"
            "示例：MYSQL_TEST_DATABASE=truthnet_test MYSQL_TEST_USER=truthnet_test"
            " MYSQL_TEST_PASSWORD=<非空密码>"
        )
    if test_database.lower() == mysql_database.lower():
        return (
            f"测试库 {test_database!r} 与演示库 {mysql_database!r} 相同"
            "（大小写不敏感），禁止以演示库身份跑测试；请配置独立的 MYSQL_TEST_DATABASE"
        )
    if test_user == mysql_user:
        return (
            f"测试用户名 {test_user!r} 与演示用户名相同，禁止复用演示账号；"
            "请创建专用测试账号（仅测试库权限）"
        )
    if test_database.lower() in {n.lower() for n in _FORBIDDEN_DB_NAMES}:
        return f"库名 {test_database!r} 在拒绝名单中（{sorted(_FORBIDDEN_DB_NAMES)}）"
    if not _SAFE_DB_NAME_RE.match(test_database):
        return (
            f"库名 {test_database!r} 含不安全字符，仅允许字母/数字/下划线，"
            "拒绝注入类命名"
        )
    return None


def _check_test_account_isolation(
    *, host: str, port: int, test_user: str, test_password: str, demo_db: str
) -> str | None:
    """测试账号对演示库的越权检查（v3.4）。

    用测试凭据尝试连接演示库（不查固定表——表不存在 ≠ 权限安全）：
    - 成功连接 → 越权，拒绝；
    - MySQL 1044（权限拒绝）→ 符合预期，放行；
    - 未知数据库/网络错误/其他认证错误 → 无法证明隔离，仍拒绝。
    """
    import pymysql

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=test_user,
            password=test_password,
            database=demo_db,
            connect_timeout=5,
        )
        conn.close()
        return f"测试账号 {test_user!r} 竟能连接演示库 {demo_db!r}（越权），拒绝"
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else 0
        if code == 1044:  # Access denied：权限隔离符合预期
            return None
        return f"无法证明测试账号隔离（errno={code}）: {exc}"
    except Exception as exc:  # noqa: BLE001 — 网络/认证类错误同样无法证明隔离
        return f"无法证明测试账号隔离: {exc}"


def _enforce_test_db_isolation() -> None:
    """mysql 模式下：校验并切换到测试库（必须在任何数据库引擎初始化前执行）。"""
    if settings.SQL_BACKEND != "mysql":
        return  # sqlite/CI 模式不受影响
    error = _validate_test_db_config(
        settings.MYSQL_DATABASE,
        settings.MYSQL_TEST_DATABASE,
        settings.MYSQL_TEST_USER,
        settings.MYSQL_TEST_PASSWORD,
        settings.MYSQL_USER,
    )
    if error:
        pytest.exit(f"[test-db-guard] {error}", returncode=2)

    demo_db = settings.MYSQL_DATABASE
    settings.MYSQL_DATABASE = settings.MYSQL_TEST_DATABASE
    settings.MYSQL_USER = settings.MYSQL_TEST_USER
    settings.MYSQL_PASSWORD = settings.MYSQL_TEST_PASSWORD
    # 同步环境变量：后续 Settings() 新实例/子进程读到同一测试库
    os.environ["MYSQL_DATABASE"] = settings.MYSQL_DATABASE
    os.environ["MYSQL_USER"] = settings.MYSQL_USER
    os.environ["MYSQL_PASSWORD"] = settings.MYSQL_PASSWORD

    # 二次确认：连接后实际库名必须等于目标测试库（大小写不敏感）
    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            actual = conn.execute(text("SELECT DATABASE()")).scalar()
    except Exception as exc:  # noqa: BLE001 — 连接失败同样 fail-fast
        pytest.exit(
            f"[test-db-guard] 测试库连接失败（{demo_db} -> {settings.MYSQL_DATABASE}）: {exc}",
            returncode=2,
        )
    finally:
        engine.dispose()
    if str(actual or "").lower() != settings.MYSQL_DATABASE.lower():
        pytest.exit(
            f"[test-db-guard] SELECT DATABASE() = {actual!r}，期望 {settings.MYSQL_DATABASE!r}",
            returncode=2,
        )

    # 越权检查：测试账号不得连接演示库（真实权限验证属 external 集成；
    # 此处失败即拒绝，无法证明隔离不算安全）
    isolation_error = _check_test_account_isolation(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        test_user=settings.MYSQL_USER,
        test_password=settings.MYSQL_PASSWORD,
        demo_db=demo_db,
    )
    if isolation_error:
        pytest.exit(f"[test-db-guard] {isolation_error}", returncode=2)
    logger.info(
        "[test-db-guard] 已切换到测试库 %s（演示库 %s 不再被测试触碰）",
        settings.MYSQL_DATABASE,
        demo_db,
    )


# ── WS/REST 测试会话兜底清理（对齐审计 P2-2）────────────────
# 单个测试的 autouse fixture 在全量并发场景偶发失效，
# session 级基线+兜底确保测试产生的会话不污染演示数据库。

_session_baseline: set[str] | None = None


def _session_ids() -> set[str]:
    if settings.SQL_BACKEND != "mysql":
        return set()
    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
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
    _enforce_test_db_isolation()  # 必须在任何数据库引擎初始化前执行
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
