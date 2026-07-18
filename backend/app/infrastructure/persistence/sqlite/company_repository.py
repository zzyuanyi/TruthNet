"""SQLite CompanyRepository Adapter — lite profile.

实现 CompanyRepository Port 协议。
"""

from app.domain.company.models import CompanyRef, CompanySearchResult

# Mock 数据
_MOCK_COMPANIES: list[CompanyRef] = [
    CompanyRef(
        code="600519",
        name="贵州茅台酒股份有限公司",
        short_name="贵州茅台",
        industry="白酒",
    ),
    CompanyRef(
        code="000858", name="五粮液股份有限公司", short_name="五粮液", industry="白酒"
    ),
    CompanyRef(
        code="600518",
        name="康美药业股份有限公司",
        short_name="康美药业",
        industry="中药",
    ),
    CompanyRef(
        code="300750",
        name="宁德时代新能源科技股份有限公司",
        short_name="宁德时代",
        industry="电池",
    ),
]


class SQLiteCompanyRepository:
    """SQLite 公司仓库 — lite profile.

    当前为 mock 实现，后续接入真实 SQLite。
    """

    def __init__(self, db_path: str = "data/truthnet.db"):
        self._db_path = db_path
        self._companies: dict[str, CompanyRef] = {c.code: c for c in _MOCK_COMPANIES}

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司."""
        results = [
            c
            for c in self._companies.values()
            if query.lower() in c.code.lower()
            or query.lower() in c.name.lower()
            or (c.short_name and query.lower() in c.short_name.lower())
        ][:limit]
        if not results and not query:
            results = list(self._companies.values())[:limit]
        return CompanySearchResult(companies=results, total=len(results))

    async def get_by_code(self, code: str) -> CompanyRef | None:
        """按代码获取."""
        return self._companies.get(code)

    async def list_all(self, limit: int = 100) -> list[CompanyRef]:
        """列出所有."""
        return list(self._companies.values())[:limit]
