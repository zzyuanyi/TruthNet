"""Risk 风险领域模型 — V12 baseline."""

from pydantic import BaseModel, Field

from app.core.enums import RiskLevel


class RiskScore(BaseModel):
    """风险评分 — V12 增强版.

    从 Prompt4 的 4 维度扩展为 V12 的多维度结构。
    """

    overall: float = Field(default=0.0, ge=0.0, le=1.0, description="综合风险 0-1")
    financial: float = Field(default=0.0, ge=0.0, le=1.0, description="财务风险 0-1")
    ownership: float = Field(default=0.0, ge=0.0, le=1.0, description="股权风险 0-1")
    sentiment: float = Field(default=0.0, ge=0.0, le=1.0, description="舆情风险 0-1")
    level: RiskLevel = Field(default=RiskLevel.LOW, description="风险等级")


class RiskFactor(BaseModel):
    """风险因子."""

    category: str = Field(..., description="风险类别")
    level: RiskLevel = Field(default=RiskLevel.LOW, description="严重程度")
    detail: str = Field(..., description="详细描述")


class CompanyRiskProfile(BaseModel):
    """公司风险画像."""

    company_id: str = Field(..., description="公司 ID")
    company_name: str = Field(..., description="公司名称")
    risk_score: RiskScore = Field(default_factory=RiskScore)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    last_updated: str = Field(default="", description="最后更新时间 (ISO 8601)")
