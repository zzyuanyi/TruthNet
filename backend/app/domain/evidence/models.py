"""Evidence 证据领域模型 — V12 baseline.

EvidenceRef 和 Claim 是回答可信性的核心边界。
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """证据类型."""

    FINANCIAL_STATEMENT = "financial_statement"
    OWNERSHIP_RECORD = "ownership_record"
    NEWS_ARTICLE = "news_article"
    REGULATION = "regulation"
    CALCULATION = "calculation"
    EXPERT_OPINION = "expert_opinion"


class ConfidenceLevel(str, Enum):
    """置信度等级."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


class EvidenceRef(BaseModel):
    """证据引用 — V12 核心模型.

    每条回答中的证据锚点，将结论与原始数据关联。
    """

    id: str = Field(..., description="证据唯一标识")
    type: EvidenceType = Field(..., description="证据类型")
    source: str = Field(..., description="数据来源，如'2023年报 利润表'")
    field: str = Field(..., description="字段名，如'营业收入'")
    value: str = Field(..., description="字段值")
    page: str | None = Field(None, description="年报页码或文档位置")
    retrieval_score: float | None = Field(
        None, ge=0.0, le=1.0, description="检索相关性分数"
    )


class Claim(BaseModel):
    """结论声明 — V12 核心模型.

    每个回答由若干 Claim 组成，每个 Claim 有独立的证据链和置信度。
    """

    id: str = Field(..., description="声明唯一标识")
    statement: str = Field(..., description="声明内容")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.UNVERIFIED)
    evidence: list[EvidenceRef] = Field(default_factory=list, description="支撑证据")
    counter_evidence: list[EvidenceRef] = Field(
        default_factory=list, description="反面证据"
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="生成时间 (ISO 8601)",
    )
