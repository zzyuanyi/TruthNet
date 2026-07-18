"""Company 领域模型 — V12 baseline."""

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


class CompanySearchResult(BaseModel):
    """公司搜索结果."""

    companies: list[CompanyRef] = Field(default_factory=list)
    total: int = Field(default=0)
