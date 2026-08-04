"""Evidence 证据领域模型 — V12 §9.1/9.2 canonical 模型.

Agent 运行时、持久化与 API 统一使用本文件定义的 EvidenceRef/Claim
（agents/state.py re-export 保持导入兼容；ORM 列名镜像见
infrastructure/persistence/models.py）。

历史说明：旧版（id/type/source/field + confidence 枚举）与运行链字段
不一致且零引用，已由本 canonical 版替换（审查对齐）。
"""

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """证据引用 — V12 §9.1 + Phase C 全局追溯字段."""

    evidence_id: str
    source_type: str = ""
    source_record_id: str = ""
    field_path: str | None = None
    period: str | None = None
    value: str | None = None
    source_title: str = ""
    # Phase C: 全局追溯字段
    turn_id: str = ""
    trace_id: str = ""
    company_code: str = ""
    module: str = ""
    # 运行时规则归属（仅内存用，不落库；持久化归属由 claims.rule_id + links 表达）
    rule_id: str | None = None
    source_table: str | None = None
    unit: str | None = None
    statement_scope: str | None = None
    source_uri: str | None = None
    source_excerpt: str | None = None
    dataset_version: str = ""
    retrieved_at: str = ""


class Claim(BaseModel):
    """结论声明 — V12 §9.2 + Phase C 全局追溯字段."""

    claim_id: str
    text: str
    claim_type: str = ""
    severity: str = "unknown"
    confidence: float | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: str = "pending"
    limitations: list[str] = Field(default_factory=list)
    # Phase C: 全局追溯字段
    turn_id: str = ""
    trace_id: str = ""
    company_code: str = ""
    module: str = ""
    generated_at: str = ""
