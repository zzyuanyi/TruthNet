"""SQLite CompanyNameIndexProvider — lite profile 名称索引。

与 SQLiteCompanyRepository 同一确定性 fixture 公司集合，Spotter 在
lite profile 下不再静默失败（v3.3.3 收口批次 B，方案 §3.3）。
"""

from __future__ import annotations


class SQLiteCompanyNameIndexProvider:
    """SQLite（lite）全量名称索引 adapter。"""

    def __init__(self, db_path: str = "data/truthnet.db"):
        self._db_path = db_path

    @property
    def profile_key(self) -> str:
        """缓存隔离 key：包含 SQLITE_PATH（不同 db 文件不共用 profile）。"""
        return f"sqlite:{self._db_path}"

    def list_company_names(self) -> frozenset[str]:
        from app.infrastructure.persistence.sqlite.company_repository import (
            _MOCK_COMPANIES,
        )

        names: set[str] = set()
        for record in _MOCK_COMPANIES:
            if record.sec_name:
                names.add(record.sec_name)
            for alias in record.aliases or []:
                alias = str(alias).strip()
                if alias:
                    names.add(alias)
        return frozenset(names)
