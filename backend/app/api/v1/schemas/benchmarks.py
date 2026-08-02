"""行业对标 REST Schema — V12 §11.13."""

from pydantic import BaseModel, Field


class IndustryPercentile(BaseModel):
    """单个指标的分位值."""

    indicator: str = Field(..., description="指标标识，如 'receivable_yoy'")
    label: str = Field(default="", description="中文标签")
    rule_id: str | None = Field(default=None, description="关联规则 ID")
    company_value: float | None = Field(default=None, description="目标公司值")
    unit: str = Field(default="", description="单位")
    p25: float | None = Field(default=None)
    p50: float | None = Field(default=None)
    p75: float | None = Field(default=None)
    p90: float | None = Field(default=None)
    peer_count: int = Field(default=0, description="同行业有效样本数")


class BenchmarksResponseData(BaseModel):
    """行业对标响应数据 — V12 §11.13."""

    wind_code: str = Field(..., description="公司代码")
    sec_name: str = Field(default="", description="公司名称")
    industry_l1: str = Field(default="", description="一级行业")
    period: str = Field(default="", description="对标期间，如 2026Q2")
    percentiles: list[IndustryPercentile] = Field(default_factory=list)
    peer_count: int = Field(default=0, description="同行业公司总数")
    is_sample_sufficient: bool = Field(default=True, description="样本是否充足（≥5）")
    generic_thresholds_only: bool = Field(
        default=False,
        description="样本不足时仅展示通用阈值，不展示伪造分位",
    )
    warnings: list[str] = Field(default_factory=list)
