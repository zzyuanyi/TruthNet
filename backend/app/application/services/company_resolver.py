"""CompanyResolver — Phase C 统一公司解析链路.

Router
  → CompanyResolver
  → CompanyRepository Port
  → MySQLCompanyRepository（full）/ SQLiteCompanyRepository（lite）

统一支持:
  - 600518 / 600518.SH / 600518_SH / company_600518_SH
  - 公司简称 / 全称 / 别名
单字符非代码输入拒绝，避免误解析。
"""

import logging

from app.application.ports.company_repository import CompanyRepository
from app.core.config import settings
from app.domain.company.models import CompanyRecord
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)

logger = logging.getLogger(__name__)


def get_company_repository() -> CompanyRepository:
    """返回 profile-aware 公司仓库（full→MySQL，lite→SQLite fixture）。"""
    if settings.SQL_BACKEND == "mysql":
        return MySQLCompanyRepository()
    return SQLiteCompanyRepository()


async def resolve_company(code: str) -> CompanyRecord | None:
    """共享异步入口：解析任意公司输入为真实 CompanyRecord。"""
    return await CompanyResolver().resolve(code)


class CompanyResolver:
    """公司实体解析服务 — 唯一解析链路."""

    def __init__(self, repo: CompanyRepository | None = None):
        self._repo = repo or get_company_repository()

    @property
    def repo(self) -> CompanyRepository:
        """公开仓库引用（Router 侧查询使用）。"""
        return self._repo

    async def resolve(self, input_value: str) -> CompanyRecord | None:
        """解析任意输入为公司记录；无法唯一解析返回 None."""
        value = (input_value or "").strip()
        if not value:
            return None

        # 1. 代码/名称精确匹配（含 company_xxx 形式）
        record = await self._repo.get_by_code(value)
        if record is not None:
            return record

        # 2. entity_id 精确匹配
        record = await self._repo.get_by_entity_id(value)
        if record is not None:
            return record

        # 3. 单字符非代码 → 拒绝
        if len(value) == 1:
            return None

        # 4. 名称/别名搜索：唯一命中才返回
        result = await self._repo.search(value, limit=10)
        if result.total == 0:
            return None
        if result.total == 1:
            return result.companies[0]
        # 多命中：优先精确名称
        exact = [c for c in result.companies if c.sec_name == value]
        if len(exact) == 1:
            return exact[0]
        return None
