"""MySQL CompanyNameIndexProvider — 一次性全量公司名称索引。

Spotter 名称索引的 full profile 实现：从 companies 表读取全部
is_latest=1 的 sec_name 与有效 aliases（无 LIMIT 截断）。Engine
生命周期由本 infrastructure adapter 管理（v3.3.3 收口批次 B，
方案 §3.3：应用服务不再自建连接）。
"""

from __future__ import annotations

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

# 名称最小长度（与 spotter 的 _MIN_NAME_LEN 契约一致，避免单字命中）
_MIN_NAME_LEN = 2


class MySQLCompanyNameIndexProvider:
    """MySQL 全量名称索引 adapter（sync，供 spotter 一次性加载）。

    连接配置在实例创建时**一次性捕获**（审查 P1：实例生命周期内不再
    读取可变全局 settings），profile_key 与 Engine 都基于捕获值——
    中途切换 settings.MYSQL_DATABASE 不会让旧实例的 Engine 连到
    新库或把旧库名称缓存到新 profile 下。
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self._engine: Engine | None = None
        self._host = host if host is not None else settings.MYSQL_HOST
        self._port = port if port is not None else settings.MYSQL_PORT
        self._database = database if database is not None else settings.MYSQL_DATABASE
        self._user = user if user is not None else settings.MYSQL_USER
        self._password = password if password is not None else settings.MYSQL_PASSWORD

    @property
    def profile_key(self) -> str:
        """缓存隔离 key：backend + user + host + port + database（捕获值）。"""
        return f"mysql:{self._user}:{self._host}:{self._port}:{self._database}"

    def _get_engine(self) -> Engine:
        if self._engine is None:
            # v3.1 P1-6：URL.create() 防密码含 @/: 等特殊字符解析失败
            url = URL.create(
                "mysql+pymysql",
                username=self._user,
                password=self._password,
                host=self._host,
                port=self._port,
                database=self._database,
            )
            self._engine = create_engine(url, echo=False, pool_pre_ping=True)
        return self._engine

    def list_company_names(self) -> frozenset[str]:
        """全量 sec_name + 有效 aliases（不截断）。"""
        from app.domain.company.aliases import aliases_to_list

        names: set[str] = set()
        with self._get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT sec_name, aliases FROM companies "
                        "WHERE is_latest = 1 "
                        "AND sec_name IS NOT NULL AND sec_name <> ''"
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                name = str(row["sec_name"]).strip()
                if len(name) >= _MIN_NAME_LEN:
                    names.add(name)
                for alias in aliases_to_list(row.get("aliases")):
                    alias = str(alias).strip()
                    if len(alias) >= _MIN_NAME_LEN:
                        names.add(alias)
        return frozenset(names)
