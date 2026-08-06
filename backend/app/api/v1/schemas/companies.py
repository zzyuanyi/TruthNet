"""公司模块响应 DTO — V12 §9.

对齐 backend/app/api/v1/routers/companies.py 实际返回结构，
使 OpenAPI 可作为前端类型来源（对齐审计 P1-4）。
"""

from pydantic import BaseModel


class CompanyCandidateV1(BaseModel):
    """公司候选（搜索）— 对齐 V12 CompanyRef."""

    entity_id: str
    wind_code: str
    sec_name: str
    exchange: str | None = None
    industry_l1: str | None = None
    industry_l2: str | None = None
    comp_type_code: str | int | None = None  # 真实数据为行业代码数字
    company_type: str | None = None
    listing_date: str | None = None


class CompanySearchData(BaseModel):
    """搜索响应: {query, total, candidates}."""

    query: str
    total: int
    candidates: list[CompanyCandidateV1]


class DataQualityInfo(BaseModel):
    """画像数据质量信息."""

    source: str
    dataset_version: str
    source_record_id: str | None = None
    is_latest: bool = True
    quality_flags: dict = {}
    partial: bool = False


class CompanyProfileV1(BaseModel):
    """企业画像摘要."""

    entity_id: str
    wind_code: str
    sec_name: str
    aliases: list[str] = []
    exchange: str | None = None
    industry_l1: str | None = None
    industry_l2: str | None = None
    sw_indu_code: str | None = None
    comp_type_code: str | int | None = None  # 真实数据为行业代码数字
    company_type: str | None = None
    listing_date: str | None = None
    data_quality: DataQualityInfo
    risk_summary: None = None  # 风险评估数据未交付，不得伪造
