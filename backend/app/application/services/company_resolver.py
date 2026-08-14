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


# 中间验收 P2-1：应用级 Repository 复用——resolve_entity_node 每轮调用
# 工厂时不再新建 Repository/Engine（连接池）。审查 P1（2026-08-14）：
# 缓存 key 从「仅 backend」升级为完整 profile（backend/user/host/port/
# database、sqlite 含 SQLITE_PATH）——同一 backend 下切换数据库不得
# 复用旧实例/旧 Engine（否则旧库连接会被新 profile 复用）。
# 测试直接构造实例（repo._engine 注入）不受影响。
_repo_cache: dict[str, CompanyRepository] = {}


def _profile_key() -> str:
    """连接 profile 完整身份 key（Repository 与 NameIndexProvider 共用）。"""
    if settings.SQL_BACKEND == "mysql":
        return (
            f"mysql:{settings.MYSQL_USER}:{settings.MYSQL_HOST}:"
            f"{settings.MYSQL_PORT}:{settings.MYSQL_DATABASE}"
        )
    sqlite_path = settings.SQLITE_PATH or "data/truthnet.db"
    return f"sqlite:{sqlite_path}"


def _dispose_other_profile_engines(cache: dict, active_key: str) -> None:
    """审查 P2：切换 profile 时 dispose 其他 profile 实例的 Engine。

    实例仍留在缓存字典（切回时懒重建 Engine），但连接池不滞留——
    避免频繁动态切库（演示库/测试库）累积旧库连接。
    """
    for key, obj in list(cache.items()):
        if key == active_key:
            continue
        engine = getattr(obj, "_engine", None)
        if engine is None:
            continue
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001 — dispose 失败不阻断工厂
            pass


def get_company_repository() -> CompanyRepository:
    """返回 profile-aware 公司仓库（full→MySQL，lite→SQLite fixture）。

    按完整 profile key 缓存实例（审查 P1）：Engine 懒建于实例内，
    实例创建时捕获连接配置；切换 host/port/database/user 后返回
    新实例，旧实例 Engine 不跨库复用且被 dispose（审查 P2）。
    """
    key = _profile_key()
    if key not in _repo_cache:
        if key.startswith("mysql:"):
            _repo_cache[key] = MySQLCompanyRepository()
        else:
            _repo_cache[key] = SQLiteCompanyRepository(db_path=key[len("sqlite:") :])
        _dispose_other_profile_engines(_repo_cache, key)
    return _repo_cache[key]


# v3.3.3 收口批次 B（方案 §3.3）：spotter 名称索引 provider 复用同一
# profile 缓存策略——MySQL/SQLite 各自 infrastructure adapter，
# 应用服务（exact_company_spotter）不再创建 Engine。
_name_provider_cache: dict[str, object] = {}


def get_company_name_index_provider():
    """返回 profile-aware 公司名称索引 provider（mysql→MySQL / 其余→SQLite）。

    与 get_company_repository 相同的完整 profile key 缓存（审查 P1）
    与切库 dispose 策略（审查 P2）。
    """
    from app.infrastructure.persistence.mysql.company_name_provider import (
        MySQLCompanyNameIndexProvider,
    )
    from app.infrastructure.persistence.sqlite.company_name_provider import (
        SQLiteCompanyNameIndexProvider,
    )

    key = _profile_key()
    if key not in _name_provider_cache:
        if key.startswith("mysql:"):
            _name_provider_cache[key] = MySQLCompanyNameIndexProvider()
        else:
            _name_provider_cache[key] = SQLiteCompanyNameIndexProvider(
                db_path=key[len("sqlite:") :]
            )
        _dispose_other_profile_engines(_name_provider_cache, key)
    return _name_provider_cache[key]


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
