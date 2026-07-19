"""Alembic migration environment -- V12 baseline.

Supports lite (SQLite) and full (MySQL) dual profiles.
Database URL is built from env vars; falls back to alembic.ini.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL as EngineURL

from alembic import context

# Load .env file before any settings resolution
_repo_root = Path(__file__).resolve().parents[5]  # migrations -> persistence -> infrastructure -> app -> backend -> repo
_env_path = _repo_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Ensure backend/ is on sys.path
_src = Path(__file__).resolve().parents[4]  # migrations -> persistence -> infrastructure -> app -> backend
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.infrastructure.persistence.models import Base  # noqa: E402

target_metadata = Base.metadata


def _build_database_url():
    """Build database URL from environment variables.

    TRUTHNET_PROFILE=lite  -> SQLite
    TRUTHNET_PROFILE=full  -> MySQL
    Env vars take priority over alembic.ini.
    """
    profile = os.getenv("TRUTHNET_PROFILE", "lite")
    sql_backend = os.getenv("SQL_BACKEND", "sqlite")

    if profile == "full" or sql_backend == "mysql":
        host = os.getenv("MYSQL_HOST", "localhost")
        port = int(os.getenv("MYSQL_PORT", "3306"))
        database = os.getenv("MYSQL_DATABASE", "truthnet")
        user = os.getenv("MYSQL_USER", "truthnet")
        password = os.getenv("MYSQL_PASSWORD", "")

        return EngineURL.create(
            "mysql+pymysql",
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
            query={"charset": "utf8mb4"},
        )
    else:
        # lite/sqlite -- fall back to sqlalchemy.url in alembic.ini
        return config.get_main_option("sqlalchemy.url", "sqlite:///data/truthnet.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = _build_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    url = _build_database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
