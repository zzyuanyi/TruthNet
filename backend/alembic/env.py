"""Alembic 环境 — TruthNet MySQL 8.4.

运行时 sqlalchemy.url 从 alembic.ini 读取，支持环境变量覆盖：
    TRUTHNET_DATABASE_URL=mysql+pymysql://user:pass@host:3306/db
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 允许环境变量覆盖数据库连接
database_url = os.getenv("TRUTHNET_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = None  # 使用原始 SQL（非 ORM 模型）


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接 MySQL 执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
