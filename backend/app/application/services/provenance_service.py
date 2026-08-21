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

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)


class EvidenceConflictError(Exception):
    """同 evidence_id 已存在但 canonical 内容不一致（调用方应回滚处理）。"""


def _evidence_core_conflict(existing, new_fields: tuple) -> bool:
    """canonical 六字段逐项比较；一方为空（None/""）或 source_type="unknown"
    视为缺失（可补全）。

    与 persist_turn._evidence_core_conflict 同语义（A1，2026-08-11）。
    仅双方非空且不同才算冲突。
    """
    for old, new in zip(existing, new_fields):
        old_empty = old is None or old == "" or old == "unknown"
        new_empty = new is None or new == "" or new == "unknown"
        if old_empty or new_empty:
            continue
        if old != new:
            return True
    return False


_GAP_FILL_COLS = (
    "source_type",
    "source_record_id",
    "field_path",
    "period",
    "company_code",
    "value",
    "unit",
    "source_title",
)


def _gap_fill_evidence(conn, eid: str, ev: dict) -> None:
    """④：一方为空（或 source_type='unknown'）→ UPDATE 补全空字段。

    与 persist_turn._fill_evidence_gap_fields 同语义：只补空，不覆盖非空。
    """
    sets: list[str] = []
    params: dict = {"eid": eid}
    for col in _GAP_FILL_COLS:
        new_val = ev.get(col)
        if new_val is None:
            continue
        if col == "source_type" and new_val == "unknown":
            continue
        if col == "source_type":
            # source_type 的 'unknown' 视为缺失（与 _evidence_core_conflict 一致）
            sets.append(
                f"{col} = COALESCE(NULLIF(NULLIF({col}, ''), 'unknown'), :v_{col})"
            )
        else:
            sets.append(f"{col} = COALESCE(NULLIF({col}, ''), :v_{col})")
        params[f"v_{col}"] = new_val
    if not sets:
        return
    conn.execute(
        text(f"UPDATE evidence_refs SET {', '.join(sets)} WHERE evidence_id = :eid"),
        params,
    )


def _load_evidence(conn, eid: str):
    return conn.execute(
        text(
            "SELECT source_type, source_record_id, field_path, "
            "period, dataset_version, company_code, value "
            "FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
        ),
        {"eid": eid},
    ).first()


def _reuse_existing_evidence(conn, eid: str, ev: dict, existing) -> None:
    new_fields = (
        ev.get("source_type", "unknown"),
        ev.get("source_record_id", ""),
        ev.get("field_path"),
        ev.get("period"),
        ev.get("dataset_version") or settings.DATASET_VERSION,
        ev.get("company_code"),
    )
    conflict = _evidence_core_conflict(existing[:6], new_fields)
    if not conflict:
        old_val = existing[6]
        new_val = ev.get("value")
        old_empty = old_val is None or old_val == ""
        new_empty = new_val is None or new_val == ""
        conflict = not old_empty and not new_empty and str(old_val) != str(new_val)
    if conflict:
        raise EvidenceConflictError(
            f"evidence {eid} 已存在但 canonical 内容不一致: "
            f"现有={existing[:6]}，新={new_fields}"
        )
    _gap_fill_evidence(conn, eid, ev)


def _get_engine() -> Engine:
    """8/19 全面审查：改用完整 profile key + 切 profile 即 dispose 旧 Engine。
    本服务是写路径（persist_evidence），backend-only key 缓存在切库后会
    复用旧库 Engine，把证据写进错误数据库（演示库误写）。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


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
        status: str = "completed",
    ) -> str:
        """创建独立分析溯源记录，返回 run_id。

        v3.5：status 可显式传（comparisons 生命周期 running → 完成后
        经 update_analysis_run_status 更新为 completed/partial/failed）。
        """
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO analysis_runs (run_id, trace_id, endpoint, "
                    "company_codes, period, statement_scope, status, created_at) "
                    "VALUES (:rid, :trace, :ep, :codes, :per, :scope, "
                    ":status, CURRENT_TIMESTAMP)"
                ),
                {
                    "rid": run_id,
                    "trace": trace_id,
                    "ep": endpoint,
                    "codes": _to_json(company_codes),
                    "per": period,
                    "scope": statement_scope,
                    "status": status,
                },
            )
        return run_id

    def update_analysis_run_status(self, run_id: str, status: str) -> bool:
        """v3.5：更新 analysis_run 状态（completed/partial/failed）。

        请求级失败（HTTPException/异常）也须把 running 标记为 failed——
        失败记录不得停留在 running 或误标 completed。
        """
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
        with self._engine.begin() as conn:
            res = conn.execute(
                text("UPDATE analysis_runs SET status = :s WHERE run_id = :rid"),
                {"s": status, "rid": run_id},
            )
        return (res.rowcount or 0) > 0

    # ── 幂等持久化 ────────────────────────────────────────

    def persist_evidence(
        self, evidence: list[dict], *, trace_id: str, turn_id: str
    ) -> list[str]:
        """幂等写入 evidence_refs；同 ID 不同内容 → 冲突报错并回滚。返回已写入 ID。

        ⑥/④（2026-08-11）：原实现"已存在 → 直接复用"不比较内容。现按
        canonical 身份六字段 + value 比较——全部一致（或一方为空视为
        可补全）→ 幂等复用并 **gap-fill 补全空字段**（source_type 的
        "unknown" 视为缺失，与 persist_turn 同语义）；任一字段双方非空
        且不同 → EvidenceConflictError（事务回滚）。
        """
        if not evidence:
            return []
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
        written: list[str] = []
        with self._engine.begin() as conn:
            conflict_clause = (
                "ON DUPLICATE KEY UPDATE evidence_id = evidence_id"
                if self._engine.dialect.name == "mysql"
                else "ON CONFLICT(evidence_id) DO NOTHING"
            )
            for ev in evidence:
                eid = ev.get("evidence_id")
                if not eid:
                    continue
                existing = _load_evidence(conn, eid)
                if existing is None:
                    conn.execute(
                        text(
                            "INSERT INTO evidence_refs "
                            "(evidence_id, source_type, source_record_id, company_code, "
                            " field_path, period, value, unit, statement_scope, "
                            " source_title, dataset_version, retrieved_at, "
                            " turn_id, trace_id, module, source_table) "
                            "VALUES (:eid, :st, :srid, :cc, :fp, :per, :val, :unit, :scope, "
                            " :title, :dv, CURRENT_TIMESTAMP, :turn, :trace, :module, :table) "
                            f"{conflict_clause}"
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
                    existing = _load_evidence(conn, eid)
                    if existing is None:
                        raise RuntimeError(
                            f"evidence {eid} insert was ignored unexpectedly"
                        )
                _reuse_existing_evidence(conn, eid, ev, existing)
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
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
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
