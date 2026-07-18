"""MySQL 真实连接集成测试.

需要设置 TRUTHNET_RUN_EXTERNAL_TESTS=1 才运行。
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


@pytest.fixture
def mysql_config():
    """加载 MySQL 配置."""
    from app.core.config import Settings

    s = Settings()
    if not s.MYSQL_PASSWORD:
        pytest.skip("MYSQL_PASSWORD not configured")
    return s


def test_pymysql_import():
    """PyMySQL driver 可 import."""
    import pymysql

    assert pymysql.__version__


def test_sqlalchemy_import():
    """SQLAlchemy 可 import."""
    from sqlalchemy import create_engine

    assert create_engine is not None


def test_mysql_connection_select_1(mysql_config):
    """MySQL SELECT 1 成功."""
    from sqlalchemy import create_engine, text

    s = mysql_config
    url = (
        f"mysql+pymysql://{s.MYSQL_USER}:{s.MYSQL_PASSWORD}"
        f"@{s.MYSQL_HOST}:{s.MYSQL_PORT}/{s.MYSQL_DATABASE}"
        f"?charset=utf8mb4"
    )
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1
    finally:
        engine.dispose()


def test_mysql_write_smoke(mysql_config):
    """MySQL 写入 smoke 测试."""
    from sqlalchemy import create_engine, text

    s = mysql_config
    url = (
        f"mysql+pymysql://{s.MYSQL_USER}:{s.MYSQL_PASSWORD}"
        f"@{s.MYSQL_HOST}:{s.MYSQL_PORT}/{s.MYSQL_DATABASE}"
        f"?charset=utf8mb4"
    )
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS truthnet_smoke_test ("
                    "  id INT PRIMARY KEY AUTO_INCREMENT,"
                    "  smoke_key VARCHAR(64) NOT NULL,"
                    "  smoke_value VARCHAR(255) NOT NULL,"
                    "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.commit()
            conn.execute(
                text(
                    "INSERT INTO truthnet_smoke_test (smoke_key, smoke_value) "
                    "VALUES ('v12_integration_test', 'ok')"
                )
            )
            conn.commit()
            row = conn.execute(
                text(
                    "SELECT smoke_value FROM truthnet_smoke_test WHERE smoke_key='v12_integration_test'"
                )
            ).fetchone()
            assert row is not None
            assert row[0] == "ok"
            # Cleanup
            conn.execute(
                text(
                    "DELETE FROM truthnet_smoke_test WHERE smoke_key='v12_integration_test'"
                )
            )
            conn.commit()
    finally:
        engine.dispose()
