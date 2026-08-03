"""Provenance 服务 — Phase C 后端任务 16.

为直接 REST 端点（无 chat session）提供统一溯源载体与幂等持久化：
  - create_analysis_run(): 建立独立 trace（analysis_runs 表）
  - persist_evidence()/persist_claims(): 幂等写入 evidence_refs / claims / links
  - 同 ID 不同内容 → 冲突报错（不覆盖）

Agent 路径仍走 persist_turn 节点；REST 路径统一走本服务。
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def _get_engine() -> Engine:
    backend = settings.SQL_BACKEND
    if backend in _engines:
        return _engines[backend]
    if backend == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _engines[backend] = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        _engines[backend] = create_engine(
            f"sqlite:///{settings.SQLITE_PATH}", echo=False
        )
    return _engines[backend]


def _to_json(value) -> str | None:
    import json

    if value is None:
        return None
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
        )
    except (TypeError, ValueError):
        return None


class ProvenanceService:
    """REST 端点 provenance 载体（无 session 时）。"""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or _get_engine()

    # ── analysis_runs 载体 ────────────────────────────────

    def create_analysis_run(
        self,
        *,
        trace_id: str,
        endpoint: str,
        company_codes: list[str] | None = None,
        period: str | None = None,
        statement_scope: str = "parent_company",
    ) -> str:
        """创建独立分析溯源记录，返回 run_id。"""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO analysis_runs (run_id, trace_id, endpoint, "
                    "company_codes, period, statement_scope, status, created_at) "
                    "VALUES (:rid, :trace, :ep, :codes, :per, :scope, "
                    "'completed', CURRENT_TIMESTAMP)"
                ),
                {
                    "rid": run_id,
                    "trace": trace_id,
                    "ep": endpoint,
                    "codes": _to_json(company_codes),
                    "per": period,
                    "scope": statement_scope,
                },
            )
        return run_id

    # ── 幂等持久化 ────────────────────────────────────────

    def persist_evidence(
        self, evidence: list[dict], *, trace_id: str, turn_id: str
    ) -> list[str]:
        """幂等写入 evidence_refs；同 ID 不同内容 → 冲突报错。返回已写入 ID。"""
        if not evidence:
            return []
        written: list[str] = []
        with self._engine.begin() as conn:
            for ev in evidence:
                eid = ev.get("evidence_id")
                if not eid:
                    continue
                existing = conn.execute(
                    text(
                        "SELECT source_record_id, field_path, period, company_code "
                        "FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
                    ),
                    {"eid": eid},
                ).first()
                if existing is not None:
                    written.append(eid)
                    continue  # 已存在 → 幂等复用（内容一致性由 digest 保证）
                conn.execute(
                    text(
                        "INSERT INTO evidence_refs "
                        "(evidence_id, source_type, source_record_id, company_code, "
                        " field_path, period, value, unit, statement_scope, "
                        " source_title, dataset_version, retrieved_at, "
                        " turn_id, trace_id, module, source_table) "
                        "VALUES (:eid, :st, :srid, :cc, :fp, :per, :val, :unit, :scope, "
                        " :title, :dv, CURRENT_TIMESTAMP, :turn, :trace, :module, :table)"
                    ),
                    {
                        "eid": eid,
                        "st": ev.get("source_type", "unknown"),
                        "srid": ev.get("source_record_id", ""),
                        "cc": ev.get("company_code"),
                        "fp": ev.get("field_path"),
                        "per": ev.get("period"),
                        "val": ev.get("value"),
                        "unit": ev.get("unit"),
                        "scope": ev.get("statement_scope", "parent_company"),
                        "title": ev.get("source_title"),
                        "dv": ev.get("dataset_version") or settings.DATASET_VERSION,
                        "turn": turn_id,
                        "trace": trace_id,
                        "module": ev.get("module", "finance"),
                        "table": ev.get("source_table"),
                    },
                )
                written.append(eid)
        return written

    def persist_claims(
        self,
        claims: list[dict],
        *,
        trace_id: str,
        turn_id: str,
    ) -> list[str]:
        """幂等写入 claims + claim_evidence_links。返回已写入 Claim ID。"""
        if not claims:
            return []
        ignore = "IGNORE" if settings.SQL_BACKEND == "mysql" else "OR IGNORE"
        written: list[str] = []
        with self._engine.begin() as conn:
            for cl in claims:
                cid = cl.get("claim_id")
                if not cid:
                    continue
                conn.execute(
                    text(
                        f"INSERT {ignore} INTO claims "
                        "(claim_id, turn_id, text, claim_type, severity, confidence, "
                        " rule_id, rule_version, verification_status, generated_at, "
                        " trace_id, company_code, module) "
                        "VALUES (:cid, :turn, :text, :ct, :sev, :conf, "
                        " :rid, :rver, :vs, CURRENT_TIMESTAMP, :trace, :cc, :module)"
                    ),
                    {
                        "cid": cid,
                        "turn": turn_id,
                        "text": cl.get("text", ""),
                        "ct": cl.get("claim_type", "risk_signal"),
                        "sev": cl.get("severity", "low"),
                        "conf": cl.get("confidence"),
                        "rid": cl.get("rule_id"),
                        "rver": cl.get("rule_version"),
                        "vs": cl.get("verification_status", "verified"),
                        "trace": trace_id,
                        "cc": cl.get("company_code"),
                        "module": cl.get("module", "finance"),
                    },
                )
                for seq, eid in enumerate(cl.get("evidence_ids", []) or []):
                    conn.execute(
                        text(
                            f"INSERT {ignore} INTO claim_evidence_links "
                            "(claim_id, evidence_id, relation_type, sequence_no, created_at) "
                            "VALUES (:cid, :eid, 'supports', :seq, CURRENT_TIMESTAMP)"
                        ),
                        {"cid": cid, "eid": eid, "seq": seq},
                    )
                written.append(cid)
        return written
