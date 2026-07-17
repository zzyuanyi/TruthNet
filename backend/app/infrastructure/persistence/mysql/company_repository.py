"""MySQL CompanyRepository Adapter — full profile (骨架).

实现 CompanyRepository Port 协议。
当前为空实现，不要求真实 MySQL 连接。
"""

import logging

from app.core.config import settings
from app.domain.company.models import CompanyRef, CompanySearchResult

logger = logging.getLogger(__name__)


class MySQLCompanyRepository:
    """MySQL 公司仓库 — full profile 骨架.

    TODO: 接入 SQLAlchemy + PyMySQL 实现真实查询。
    """

    def __init__(self):
        self._available = False
        logger.info("MySQLCompanyRepository: 骨架已加载，连接未激活")

    async def check_connection(self) -> bool:
        """检查 MySQL 连接可用性."""
        try:
            import pymysql

            conn = pymysql.connect(
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                database=settings.MYSQL_DATABASE,
                connect_timeout=3,
            )
            conn.close()
            self._available = True
            return True
        except Exception as e:
            logger.warning(f"MySQL 连接不可用: {e}")
            self._available = False
            return False

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司 (空实现)."""
        if not self._available:
            logger.warning("MySQL 不可用，返回空结果")
        return CompanySearchResult(companies=[], total=0)

    async def get_by_code(self, code: str) -> CompanyRef | None:
        """按代码获取 (空实现)."""
        return None

    async def list_all(self, limit: int = 100) -> list[CompanyRef]:
        """列出所有 (空实现)."""
        return []
