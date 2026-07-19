"""持久化层 Adapters — V12 baseline.

SQLAlchemy ORM 模型（14 张表，严格对齐 V12 §10）。
"""

from app.infrastructure.persistence.models import (
    Announcement,
    BalanceSheet,
    Base,
    CashFlow,
    Claim,
    Company,
    ConversationSession,
    ConversationTurn,
    EvidenceRef,
    IncomeStatement,
    ResearchReport,
    RiskAssessment,
    RuleDefinition,
    RuleEvaluation,
    TopShareholder,
)

__all__ = [
    "Announcement",
    "BalanceSheet",
    "Base",
    "CashFlow",
    "Claim",
    "Company",
    "ConversationSession",
    "ConversationTurn",
    "EvidenceRef",
    "IncomeStatement",
    "ResearchReport",
    "RiskAssessment",
    "RuleDefinition",
    "RuleEvaluation",
    "TopShareholder",
]
