"""Provenance 领域模型 — Phase C 任务 16.

验证报告 + Lookup 视图模型。
"""

from pydantic import BaseModel, Field


class ProvenanceValidationReport(BaseModel):
    """验证报告 — 稳定输出结构."""

    claim_count: int = Field(default=0)
    evidence_count: int = Field(default=0)
    link_count: int = Field(default=0)
    dangling_evidence_ids: list[str] = Field(default_factory=list)
    duplicate_claim_ids: list[str] = Field(default_factory=list)
    duplicate_evidence_ids: list[str] = Field(default_factory=list)
    conflicting_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="ok", description="ok / issues")
