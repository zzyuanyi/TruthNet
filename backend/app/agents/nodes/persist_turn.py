"""PersistTurn — V12 §7.2 + Phase C 任务 16.

同一数据库事务内完成：
  1. conversation_sessions upsert
  2. conversation_turns upsert
  3. evidence_refs upsert（幂等）
  4. claims upsert（幂等）
  5. claim_evidence_links upsert

幂等要求：
  - 同一 turn 重试不重复插入；
  - 相同 Evidence ID + 相同内容可安全复用；
  - 相同 ID 不同内容 → 报错（不写入，整事务 rollback）；
  - 失败时整个 provenance 事务 rollback，不留下半成品。
写入失败：主流程按现有容错继续，但产生 PROVENANCE_PERSIST_FAILED warning。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState, Claim, EvidenceRef, ModuleStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def _repo_root() -> Path:
    # backend/app/agents/nodes/persist_turn.py -> 项目根
    return Path(__file__).resolve().parents[4]


def _get_engine() -> Engine:
    """惰性缓存引擎，尊重 SQL_BACKEND（sqlite/mysql）。"""
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
    else:  # sqlite
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _engines[backend] = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return _engines[backend]


def _session_id(state: AgentState) -> str | None:
    """从 runtime 获取会话 ID。"""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    sid = getattr(runtime, "session_id", "") or ""
    return sid or None


def _to_json(value) -> str | None:
    """JSON 序列化，Pydantic model 走 model_dump。"""
    if value is None:
        return None
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
        )
    except (TypeError, ValueError):
        logger.warning("module_status 序列化失败，跳过持久化该字段", exc_info=True)
        return None


def _evidence_fingerprint(ev: EvidenceRef) -> str:
    return "|".join(
        [
            ev.source_type or "",
            ev.source_record_id or "",
            ev.field_path or "",
            ev.period or "",
            ev.value or "",
            ev.company_code or "",
            ev.module or "",
            ev.source_table or "",
        ]
    )


def _claim_fingerprint(cl: Claim) -> str:
    return "|".join(
        [
            cl.turn_id or "",
            cl.company_code or "",
            cl.claim_type or "",
            cl.severity or "",
            str(cl.confidence or ""),
            cl.rule_id or "",
            cl.rule_version or "",
            cl.verification_status or "",
            cl.module or "",
            cl.text or "",
        ]
    )


def _upsert_evidence(conn, ev: EvidenceRef, turn_id: str) -> None:
    """幂等 upsert evidence_refs；同 ID 不同内容 → 冲突报错。"""
    if not ev.evidence_id:
        return
    existing = conn.execute(
        text(
            "SELECT source_type, source_record_id, field_path, period, value, "
            "company_code, module, source_table "
            "FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
        ),
        {"eid": ev.evidence_id},
    ).first()
    if existing is not None:
        stored = _evidence_fingerprint(
            EvidenceRef(
                evidence_id=ev.evidence_id,
                source_type=str(existing[0] or ""),
                source_record_id=str(existing[1] or ""),
                field_path=existing[2],
                period=existing[3],
                value=existing[4],
                company_code=str(existing[5] or ""),
                module=str(existing[6] or ""),
                source_table=existing[7],
            )
        )
        if stored != _evidence_fingerprint(ev):
            raise ValueError(
                f"Evidence ID 冲突（同 ID 不同内容，拒绝覆盖）: {ev.evidence_id}"
            )
        return  # 已存在且内容一致 → 幂等复用

    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            "INSERT INTO evidence_refs "
            "(evidence_id, source_type, source_record_id, company_code, field_path, "
            " period, value, unit, statement_scope, source_title, source_uri, "
            " source_excerpt, retrieval_score, dataset_version, retrieved_at, "
            " turn_id, trace_id, module, source_table) "
            "VALUES (:eid, :st, :srid, :cc, :fp, :per, :val, :unit, :scope, "
            " :title, :uri, :excerpt, :score, :dv, :retrieved, "
            " :turn, :trace, :module, :table)"
        ),
        {
            "eid": ev.evidence_id,
            "st": ev.source_type or "unknown",
            "srid": ev.source_record_id or "",
            "cc": ev.company_code or None,
            "fp": ev.field_path,
            "per": ev.period,
            "val": ev.value,
            "unit": ev.unit,
            "scope": ev.statement_scope,
            "title": ev.source_title,
            "uri": ev.source_uri,
            "excerpt": ev.source_excerpt,
            "score": None,
            "dv": ev.dataset_version or settings.DATASET_VERSION,
            "retrieved": now,
            "turn": turn_id,
            "trace": ev.trace_id,
            "module": ev.module or None,
            "table": ev.source_table,
        },
    )


def _upsert_claim(conn, cl: Claim, turn_id: str) -> None:
    """幂等 upsert claims；同 ID 不同内容 → 冲突报错。"""
    if not cl.claim_id:
        return
    existing = conn.execute(
        text(
            "SELECT turn_id, company_code, claim_type, severity, confidence, "
            "rule_id, rule_version, verification_status, module, text "
            "FROM claims WHERE claim_id = :cid LIMIT 1"
        ),
        {"cid": cl.claim_id},
    ).first()
    if existing is not None:
        stored = _claim_fingerprint(
            Claim(
                claim_id=cl.claim_id,
                text=str(existing[9] or ""),
                claim_type=str(existing[2] or ""),
                severity=str(existing[3] or ""),
                confidence=existing[4],
                rule_id=existing[5],
                rule_version=existing[6],
                verification_status=str(existing[7] or ""),
                module=str(existing[8] or ""),
                company_code=str(existing[1] or ""),
                turn_id=str(existing[0] or ""),
                evidence_ids=[],
            )
        )
        if stored != _claim_fingerprint(cl):
            raise ValueError(
                f"Claim ID 冲突（同 ID 不同内容，拒绝覆盖）: {cl.claim_id}"
            )
        return

    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            "INSERT INTO claims "
            "(claim_id, turn_id, text, claim_type, severity, confidence, "
            " rule_id, rule_version, verification_status, limitations, generated_at, "
            " trace_id, company_code, module) "
            "VALUES (:cid, :turn, :text, :ct, :sev, :conf, "
            " :rid, :rver, :vs, :lim, :gen, "
            " :trace, :cc, :module)"
        ),
        {
            "cid": cl.claim_id,
            "turn": turn_id,
            "text": cl.text,
            "ct": cl.claim_type,
            "sev": cl.severity,
            "conf": cl.confidence,
            "rid": cl.rule_id,
            "rver": cl.rule_version,
            "vs": cl.verification_status,
            "lim": _to_json(cl.limitations),
            "gen": now,
            "trace": cl.trace_id,
            "cc": cl.company_code,
            "module": cl.module,
        },
    )


def _persist_links(conn, claims: list[Claim], turn_id: str) -> None:
    """持久化 claim_evidence_links（幂等，MySQL/SQLite 语法适配）。"""
    ignore_keyword = "IGNORE" if settings.SQL_BACKEND == "mysql" else "OR IGNORE"
    sql = text(
        f"INSERT {ignore_keyword} INTO claim_evidence_links "
        "(claim_id, evidence_id, relation_type, sequence_no, created_at) "
        "VALUES (:cid, :eid, 'supports', :seq, CURRENT_TIMESTAMP)"
    )
    for cl in claims:
        for seq, eid in enumerate(cl.evidence_ids):
            conn.execute(sql, {"cid": cl.claim_id, "eid": eid, "seq": seq})


def persist_turn_node(state: AgentState) -> dict:
    """持久化当前轮次 + Claim/Evidence/关联关系（单事务）。"""
    session_id = _session_id(state)
    question = state.get("user_query", "")
    if not session_id or not question:
        return {"messages": []}

    final_response = state.get("final_response")
    answer = ""
    if final_response is not None:
        answer = getattr(final_response, "answer", "") or ""

    company = state.get("company")
    company_code = company.wind_code if company else None

    runtime = state.get("runtime")
    trace_id = ""
    turn_id = ""
    if runtime is not None:
        trace_id = getattr(runtime, "trace_id", "") or ""
        turn_id = getattr(runtime, "turn_id", "") or ""
    db_turn_id = turn_id or f"turn_{uuid.uuid4().hex[:12]}"

    module_status_json = _to_json(state.get("module_status", {}))
    title = question[:30]
    provenance_ok = True
    provenance_error = ""

    try:
        with _get_engine().begin() as conn:
            # 会话 upsert
            existing = conn.execute(
                text(
                    "SELECT session_id FROM conversation_sessions WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).first()
            if existing:
                conn.execute(
                    text(
                        "UPDATE conversation_sessions "
                        "SET status = 'active', updated_at = CURRENT_TIMESTAMP "
                        "WHERE session_id = :sid"
                    ),
                    {"sid": session_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO conversation_sessions "
                        "(session_id, title, status, created_at, updated_at) "
                        "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"sid": session_id, "title": title},
                )

            # turn upsert
            turn_index = conn.execute(
                text(
                    "SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_index "
                    "FROM conversation_turns WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).scalar_one()

            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, answer, "
                    " company_code, trace_id, module_status, created_at) "
                    "VALUES (:turn_id, :sid, :index, :q, :a, :cc, :trace, :ms, CURRENT_TIMESTAMP)"
                ),
                {
                    "turn_id": db_turn_id,
                    "sid": session_id,
                    "index": turn_index,
                    "q": question,
                    "a": answer,
                    "cc": company_code,
                    "trace": trace_id,
                    "ms": module_status_json,
                },
            )

            # Provenance 持久化（同一事务，顺序满足外键）
            evidence = state.get("evidence", [])
            claims = state.get("claims", [])
            for ev in evidence:
                _upsert_evidence(conn, ev, db_turn_id)
            for cl in claims:
                _upsert_claim(conn, cl, db_turn_id)
            _persist_links(conn, claims, db_turn_id)

        logger.info(
            "PersistTurn: session=%s turn_index=%d company=%s claims=%d evidence=%d",
            session_id,
            turn_index,
            company_code,
            len(state.get("claims", [])),
            len(state.get("evidence", [])),
        )
    except Exception:
        logger.exception(
            "PersistTurn 写入失败: session=%s trace=%s", session_id, trace_id
        )
        provenance_ok = False
        provenance_error = "PROVENANCE_PERSIST_FAILED"

    # 写入失败 → 主流程继续，但标记 partial + warning（不静默吞掉）
    if not provenance_ok:
        if runtime is not None and hasattr(runtime, "warnings"):
            warn = (
                f"{provenance_error}: 本轮 Claim/Evidence 未持久化 (trace={trace_id})"
            )
            if warn not in runtime.warnings:
                runtime.warnings.append(warn)
        return {
            "messages": [],
            "module_status": {
                "persist_turn": ModuleStatus(
                    state="partial",
                    error_code=provenance_error,
                    recoverable=True,
                )
            },
        }

    return {"messages": []}
