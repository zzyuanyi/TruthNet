"""Provenance 追溯路由 — Phase C 任务 16.

GET /api/v1/evidence/{evidence_id}   证据正向追溯（含来源定位）
GET /api/v1/claims/{claim_id}        声明反向追溯（含全部证据 + turn 上下文）
GET /api/v1/traces/{trace_id}/provenance  整轮 Claim/Evidence 图（辅助）

不存在 → 标准 404 Problem Details；非法 ID → 422。
不泄露内部凭据；来源记录找不到时 EvidenceRef 仍返回 + SOURCE_RECORD_NOT_FOUND。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Path as FPath
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.provenance import (
    ClaimLookupDataV1,
    EvidenceLookupDataV1,
    TraceProvenanceDataV1,
)
from app.application.services.source_resolver import resolve_source
from app.core.errors import ProblemDetail

router = APIRouter(tags=["provenance"])


def _get_engine() -> Engine:
    """8/19 全面审查：改用完整 profile key + 切 profile 即 dispose 旧 Engine。

    原实现以模块级单例缓存，进程内切库后（conftest 运行时改写
    MYSQL_DATABASE、验收双库探针）会复用指向旧库的 Engine。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def _trace() -> str:
    return str(uuid.uuid4())


def _meta(trace_id: str) -> ApiMeta:
    return ApiMeta(
        request_id=trace_id,
        trace_id=trace_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


_ID_RE = re.compile(r"^[A-Za-z0-9_:-]{1,128}$")


def _validate_id(evidence_id: str) -> None:
    if not _ID_RE.match(evidence_id or ""):
        raise HTTPException(
            status_code=422,
            detail="非法 ID 格式（仅允许字母/数字/下划线/冒号/连字符）。",
        )


def _fetch_evidence_row(evidence_id: str) -> dict | None:
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text("SELECT * FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"),
                {"eid": evidence_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


def _fetch_claim_row(claim_id: str) -> dict | None:
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text("SELECT * FROM claims WHERE claim_id = :cid LIMIT 1"),
                {"cid": claim_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


def _claims_for_evidence(evidence_id: str) -> list[dict]:
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT DISTINCT c.* FROM claims c "
                    "JOIN claim_evidence_links l ON l.claim_id = c.claim_id "
                    "WHERE l.evidence_id = :eid ORDER BY c.claim_id"
                ),
                {"eid": evidence_id},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def _evidence_for_claim(claim_id: str) -> list[dict]:
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT e.* FROM evidence_refs e "
                    "JOIN claim_evidence_links l ON l.evidence_id = e.evidence_id "
                    "WHERE l.claim_id = :cid ORDER BY l.sequence_no, e.evidence_id"
                ),
                {"cid": claim_id},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def _turn_context(turn_id: str) -> dict:
    if not turn_id:
        return {"session_id": None, "turn_id": None, "trace_id": None}
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT session_id, turn_id, trace_id, question, created_at "
                    "FROM conversation_turns WHERE turn_id = :tid LIMIT 1"
                ),
                {"tid": turn_id},
            )
            .mappings()
            .first()
        )
    if not row:
        return {"session_id": None, "turn_id": turn_id, "trace_id": None}
    d = dict(row)
    return {
        "session_id": d.get("session_id"),
        "turn_id": d.get("turn_id"),
        "trace_id": d.get("trace_id"),
        "question": d.get("question"),
        "created_at": d.get("created_at"),
    }


def _jsonable(value):
    """datetime 等序列化兜底."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@router.get(
    "/evidence/{evidence_id}",
    response_model=V12Response[EvidenceLookupDataV1],
    responses={404: {"model": ProblemDetail}, 422: {"model": ProblemDetail}},
)
async def get_evidence_lookup(
    evidence_id: str = FPath(..., description="Evidence ID"),
):
    trace_id = _trace()
    _validate_id(evidence_id)
    warnings: list[WarningItem] = []

    row = _fetch_evidence_row(evidence_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/evidence-not-found",
                "title": "Evidence Not Found",
                "status": 404,
                "detail": f"未找到证据: {evidence_id}",
                "error_code": "EVIDENCE_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    claims = _claims_for_evidence(evidence_id)

    source = resolve_source(
        source_type=str(row.get("source_type") or ""),
        source_record_id=str(row.get("source_record_id") or ""),
        source_table=row.get("source_table"),
    )
    if not source.get("resolved"):
        warnings.append(
            WarningItem(
                code="SOURCE_RECORD_NOT_FOUND",
                message=f"来源记录无法定位: {row.get('source_record_id')}",
                module="provenance",
                recoverable=True,
            )
        )

    return V12Response(
        data={
            "evidence": {k: _jsonable(v) for k, v in row.items()},
            "claims": [{k: _jsonable(v) for k, v in c.items()} for c in claims],
            "source": {
                "source_type": row.get("source_type"),
                "source_record_id": row.get("source_record_id"),
                "resolved": source.get("resolved", False),
                "record": source.get("record", {}),
            },
        },
        meta=_meta(trace_id),
        warnings=warnings,
    )


@router.get(
    "/claims/{claim_id}",
    response_model=V12Response[ClaimLookupDataV1],
    responses={404: {"model": ProblemDetail}, 422: {"model": ProblemDetail}},
)
async def get_claim_lookup(
    claim_id: str = FPath(..., description="Claim ID"),
):
    trace_id = _trace()
    _validate_id(claim_id)
    warnings: list[WarningItem] = []

    row = _fetch_claim_row(claim_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/claim-not-found",
                "title": "Claim Not Found",
                "status": 404,
                "detail": f"未找到声明: {claim_id}",
                "error_code": "CLAIM_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    evidence = _evidence_for_claim(claim_id)
    turn = _turn_context(str(row.get("turn_id") or ""))

    return V12Response(
        data={
            "claim": {k: _jsonable(v) for k, v in row.items()},
            "evidence": [{k: _jsonable(v) for k, v in e.items()} for e in evidence],
            "turn": turn,
        },
        meta=_meta(trace_id),
        warnings=warnings,
    )


@router.get(
    "/traces/{trace_id}/provenance",
    response_model=V12Response[TraceProvenanceDataV1],
    responses={404: {"model": ProblemDetail}, 422: {"model": ProblemDetail}},
)
async def get_trace_provenance(
    trace_id: str = FPath(..., description="Trace ID"),
):
    """一次查看整轮 Claim/Evidence 图（辅助端点，不替代按 ID 查询）。"""
    _validate_id(trace_id)
    with _get_engine().connect() as conn:
        turns = (
            conn.execute(
                text("SELECT turn_id FROM conversation_turns WHERE trace_id = :t"),
                {"t": trace_id},
            )
            .scalars()
            .all()
        )
        claims = []
        if turns:
            rows = (
                conn.execute(
                    text("SELECT * FROM claims WHERE turn_id IN :tids"),
                    {"tids": tuple(turns)},
                )
                .mappings()
                .all()
            )
            claims = [dict(r) for r in rows]
        evidence = []
        if claims:
            cids = tuple(c["claim_id"] for c in claims)
            erows = (
                conn.execute(
                    text(
                        "SELECT DISTINCT e.* FROM evidence_refs e "
                        "JOIN claim_evidence_links l ON l.evidence_id = e.evidence_id "
                        "WHERE l.claim_id IN :cids"
                    ),
                    {"cids": cids},
                )
                .mappings()
                .all()
            )
            evidence = [dict(r) for r in erows]

    return V12Response(
        data={
            "trace_id": trace_id,
            "claims": [{k: _jsonable(v) for k, v in c.items()} for c in claims],
            "evidence": [{k: _jsonable(v) for k, v in e.items()} for e in evidence],
        },
        meta=_meta(trace_id),
        warnings=[],
    )
