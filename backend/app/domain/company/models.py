"""Company 领域模型 — V12 baseline + Phase C (MySQL 真实画像)."""

from datetime import date

from pydantic import BaseModel, Field


class CompanyRef(BaseModel):
    """公司引用 — V12 核心模型.

    用于跨模块传递公司标识，是所有公司相关查询的基础引用。
    """

    code: str = Field(..., description="股票代码，如 600519")
    name: str = Field(..., description="公司全称")
    short_name: str | None = Field(None, description="简称")
    industry: str | None = Field(None, description="行业分类")
    listing_date: str | None = Field(None, description="上市日期 (YYYY-MM-DD)")
    status: str = Field(
        default="active", description="状态: active / suspended / delisted"
    )


# ── 公司类型常量（与 data 组 DATA_CONTRACT 对齐）────────────
COMP_TYPE_NON_FINANCIAL = 1
COMP_TYPE_BANK = 2
COMP_TYPE_INSURANCE = 3
COMP_TYPE_SECURITIES = 4


def company_type_from_code(comp_type_code: int | None) -> str:
    """将 comp_type_code 映射为公司类型标签.

    1=非金融，2=银行，3=保险，4=证券；NULL/非法 → "unknown"。
    禁止把 unknown 默认为非金融（母公司口径 Gate 语义）。
    """
    if comp_type_code == COMP_TYPE_NON_FINANCIAL:
        return "non_financial"
    if comp_type_code in (COMP_TYPE_BANK, COMP_TYPE_INSURANCE, COMP_TYPE_SECURITIES):
        return "financial"
    return "unknown"


class CompanyRecord(BaseModel):
    """公司完整记录 — Phase C 真实画像内部模型.

    从 MySQL companies 表映射；Router / Agent 不传递裸 dict。
    """

    entity_id: str = Field(..., description="内部稳定实体 ID（主键）")
    wind_code: str = Field(..., description="Wind 代码，如 600519.SH")
    sec_name: str = Field(..., description="证券简称")
    legal_name: str | None = Field(default=None, description="公司法定全称")
    aliases: list[str] = Field(default_factory=list, description="曾用名/别名")
    exchange_code: str | None = Field(None, description="交易所代码: XSHG/XSHE")
    industry_l1: str | None = Field(None, description="申万一级行业")
    industry_l2: str | None = Field(None, description="申万二级行业")
    sw_indu_code: str | None = Field(None, description="申万行业代码")
    comp_type_code: int | None = Field(None, description="公司类型代码 1-4")
    listing_date: date | None = Field(None, description="上市日期")
    dataset_version: str | None = Field(None, description="数据集版本")
    source_record_id: str | None = Field(None, description="原始记录 ID")
    source_type: str | None = Field(None, description="来源类型")
    quality_flags: dict = Field(default_factory=dict, description="数据质量标记")
    is_latest: bool = Field(default=True, description="是否最新修订")

    # ── 兼容旧 CompanyRef 字段（Lite fixture / 旧调用方）─────
    @property
    def code(self) -> str:
        """6 位数字代码，如 600519."""
        return self.wind_code.split(".")[0] if "." in self.wind_code else self.wind_code

    @property
    def name(self) -> str:
        return self.legal_name or self.sec_name

    @property
    def short_name(self) -> str:
        return self.sec_name

    @property
    def industry(self) -> str | None:
        return self.industry_l1

    @property
    def exchange(self) -> str:
        return self.exchange_code or ""

    @property
    def company_type(self) -> str:
        """公司类型标签: non_financial / financial / unknown."""
        return company_type_from_code(self.comp_type_code)

    def to_company_ref(self) -> CompanyRef:
        """转为轻量 CompanyRef（Agent state 使用）."""
        return CompanyRef(
            code=self.code,
            name=self.sec_name,
            short_name=self.sec_name,
            industry=self.industry_l1,
            listing_date=self.listing_date.isoformat() if self.listing_date else None,
        )


class CompanySearchResult(BaseModel):
    """公司搜索结果."""

    companies: list[CompanyRecord] = Field(default_factory=list)
    total: int = Field(default=0)
