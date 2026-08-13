"""行业对标 REST Schema — V12 §11.13."""

from pydantic import BaseModel, Field


class IndustryPercentile(BaseModel):
    """单个指标的分位值 — Phase C 任务 12 扩展（真实 percentile）。"""

    indicator: str = Field(..., description="指标标识，如 'r1_gap'")
    label: str = Field(default="", description="中文标签")
    rule_id: str | None = Field(default=None, description="关联规则 ID")
    metric_id: str | None = Field(default=None, description="指标 ID")
    company_value: float | None = Field(default=None, description="目标公司值")
    company_percentile: float | None = Field(
        default=None, description="公司值在同行中的百分位排名 (0-100)"
    )
    unit: str = Field(default="", description="单位")
    sample_count: int = Field(default=0, description="该指标当期有效样本数")
    p05: float | None = Field(default=None)
    p25: float | None = Field(default=None)
    p50: float | None = Field(default=None)
    p75: float | None = Field(default=None)
    p95: float | None = Field(default=None)
    peer_count: int = Field(default=0, description="同行业公司总数")
    statement_scope: str = Field(default="parent_company", description="报表口径")


class BenchmarksResponseData(BaseModel):
    """行业对标响应数据 — V12 §11.13 + Phase C 任务 12."""

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
    dataset_version: str = Field(default="", description="数据集版本")
    statement_scope: str = Field(default="parent_company", description="报表口径")
    warnings: list[str] = Field(default_factory=list)
