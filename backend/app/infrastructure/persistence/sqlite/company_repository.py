"""SQLite CompanyRepository Adapter — lite profile.

实现 CompanyRepository Port 协议。
Lite 使用确定性 fixture 公司（不依赖外部服务）；通过同一 Repository 接口暴露，
Router 不应知道 Mock 列表。
"""

from app.domain.company.models import CompanyRecord, CompanySearchResult

# Lite fixture 公司（确定性，仅 lite profile 使用）
_MOCK_COMPANIES: list[CompanyRecord] = [
    CompanyRecord(
        entity_id="company_600519_SH",
        wind_code="600519.SH",
        sec_name="贵州茅台",
        legal_name="贵州茅台酒股份有限公司",
        exchange_code="XSHG",
        industry_l1="白酒",
        comp_type_code=1,
    ),
    CompanyRecord(
        entity_id="company_000858_SZ",
        wind_code="000858.SZ",
        sec_name="五粮液",
        legal_name="宜宾五粮液股份有限公司",
        exchange_code="XSHE",
        industry_l1="白酒",
        comp_type_code=1,
    ),
    CompanyRecord(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        legal_name="康美药业股份有限公司",
        exchange_code="XSHG",
        industry_l1="中药",
        comp_type_code=1,
    ),
    CompanyRecord(
        entity_id="company_300750_SZ",
        wind_code="300750.SZ",
        sec_name="宁德时代",
        legal_name="宁德时代新能源科技股份有限公司",
        exchange_code="XSHE",
        industry_l1="电池",
        comp_type_code=1,
    ),
]


class SQLiteCompanyRepository:
    """SQLite 公司仓库 — lite profile fixture adapter."""

    def __init__(self, db_path: str = "data/truthnet.db"):
        self._db_path = db_path
        self._companies: dict[str, CompanyRecord] = {c.code: c for c in _MOCK_COMPANIES}

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司（精确代码优先，其次名称包含）。"""
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

    async def get_by_code(self, code: str) -> CompanyRecord | None:
        """按代码获取（6 位数字或完整 Wind Code）。"""
        norm = code.strip()
        if "." in norm:
            norm = norm.split(".")[0]
        if norm.endswith("_SH") or norm.endswith("_SZ") or norm.endswith("_BJ"):
            norm = norm.split("_")[0]
        return self._companies.get(norm)

    async def get_by_entity_id(self, entity_id: str) -> CompanyRecord | None:
        """按实体 ID 获取."""
        for c in self._companies.values():
            if c.entity_id == entity_id:
                return c
        return None

    async def list_all(self, limit: int = 100) -> list[CompanyRecord]:
        """列出所有."""
        return list(self._companies.values())[:limit]
