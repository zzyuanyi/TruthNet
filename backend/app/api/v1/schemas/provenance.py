"""溯源查询响应 DTO — V12 §6.4.

对齐 backend/app/api/v1/routers/provenance.py 实际返回结构。
evidence/claim/source.record 为数据库行动态映射（JSON 化），
字段级类型以行结构为准；此处固定 envelope 形状。
"""

from pydantic import BaseModel


class EvidenceLookupDataV1(BaseModel):
    """单条证据查询: {evidence, claims, source}."""

    evidence: dict
    claims: list[dict] = []
    source: dict = {}


class ClaimLookupDataV1(BaseModel):
    """单条声明查询: {claim, evidence, turn}."""

    claim: dict
    evidence: list[dict] = []
    turn: dict | None = None


class TraceProvenanceDataV1(BaseModel):
    """整轮溯源: {trace_id, claims, evidence}."""

    trace_id: str
    claims: list[dict] = []
    evidence: list[dict] = []
