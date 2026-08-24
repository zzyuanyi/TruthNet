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

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState, Claim, EvidenceRef, ModuleStatus
from app.core.config import settings
from app.domain.conversation.models import SESSION_TITLE_PLACEHOLDERS
from app.domain.evidence.models import supporting_evidence_ids

logger = logging.getLogger(__name__)


def _get_engine() -> Engine:
    """惰性缓存引擎，尊重 SQL_BACKEND（sqlite/mysql）。

    8/19 全面审查 P0：改用完整 profile key（mysql=user/host/port/database，
    sqlite 含路径）+ 切 profile 即 dispose 旧 Engine（与 _fetch._ENGINES
    同契约）——persist_turn 是写路径，按 backend-only key 缓存在进程内
    切库后会复用旧库 Engine，把轮次/证据写进错误数据库（演示库误写）。
    """
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def _session_id(state: AgentState) -> str | None:
    """从 runtime 获取会话 ID。"""
    runtime = state.get("runtime")
    if runtime is None:
        return None
    sid = getattr(runtime, "session_id", "") or ""
    return sid or None


def _user_id(state: AgentState) -> str:
    """从 runtime 获取用户 ID；未传时归属默认本地用户。"""
    runtime = state.get("runtime")
    user_id = getattr(runtime, "user_id", "") if runtime is not None else ""
    return (user_id or "").strip() or settings.SESSION_DEFAULT_USER_ID


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


_MISSING_SOURCE_TYPES = {"", "unknown"}


def _norm_source_record_id(value: str) -> str:
    """8/23 双轨 ID 统一兼容：source_record_id 归一化比较。

    旧行可能是三段式（code|period|408006000，显式母公司口径），新落库为
    两段式（code|period，默认母公司口径）——语义等价，比较时只取前两段。
    """
    parts = (value or "").split("|")
    return "|".join(parts[:2]) if len(parts) >= 2 else (value or "")


def _evidence_core_conflict(existing: EvidenceRef, new: EvidenceRef) -> bool:
    """核心字段冲突判定（空值兼容，P0：ev_ann_* 反复落库失败根因修复）。

    - source_type：NULL/""/"unknown" 视为缺失；两个已知且不同的类型才冲突
    - source_record_id/field_path/period/company_code：一方为空兼容，
      双方非空且不同才冲突（历史记录 period=NULL 而新值为公告日期时
      属于补全，不判冲突）；source_record_id 按两段式归一化比较
    - value：双方非空且不同才冲突（数值按 Decimal 归一化）
    """
    et = (existing.source_type or "").strip()
    nt = (new.source_type or "").strip()
    if et not in _MISSING_SOURCE_TYPES and nt not in _MISSING_SOURCE_TYPES and et != nt:
        return True
    for attr in ("source_record_id", "field_path", "period", "company_code"):
        a = (getattr(existing, attr) or "").strip()
        b = (getattr(new, attr) or "").strip()
        if attr == "source_record_id":
            a = _norm_source_record_id(a)
            b = _norm_source_record_id(b)
        if a and b and a != b:
            return True
    return _evidence_value_conflict(existing, new)


def _evidence_value_conflict(existing: EvidenceRef, new: EvidenceRef) -> bool:
    """value 冲突判定：双方都有值且不同才算真冲突；一方为空视为可补充。

    8/23 数值归一化：Decimal 尾零差异（'1976120882.73' vs '1976120882.7300'）
    属同一数值，不算冲突（双轨 ID 统一后 agent 落库与既有行比较常见）。
    """
    a = (existing.value or "").strip()
    b = (new.value or "").strip()
    if not a or not b:
        return False
    if a == b:
        return False
    try:
        from decimal import Decimal

        if Decimal(a) == Decimal(b):
            return False
    except Exception:  # noqa: BLE001 — 非数值字符串原样比较
        pass
    return True


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
    """幂等 upsert evidence_refs；同 ID 不同内容 → 冲突报错。

    额外收口（P2-4）：已存记录的空字段（source_title/source_uri/
    source_excerpt/unit）后续获得非空值时，只填补空字段（CASE WHEN
    NULL OR ''），绝不覆盖已有非空事实。
    """
    if not ev.evidence_id:
        return
    existing = conn.execute(
        text(
            "SELECT source_type, source_record_id, field_path, period, value, "
            "company_code, module, source_table, source_title, source_uri, "
            "source_excerpt, unit "
            "FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
        ),
        {"eid": ev.evidence_id},
    ).first()
    if existing is not None:
        stored = EvidenceRef(
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
        conflict = _evidence_core_conflict(stored, ev)
        if conflict:
            raise ValueError(
                f"Evidence ID 冲突（同 ID 不同内容，拒绝覆盖）: {ev.evidence_id}"
            )
        # P2-4：内容一致 → 幂等复用；同时只填补空字段（不覆盖非空值）
        _fill_evidence_gap_fields(conn, ev, existing)
        return

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


_GAP_FILLABLE_COLS = (
    ("source_title", "source_title"),
    ("source_uri", "source_uri"),
    ("source_excerpt", "source_excerpt"),
    ("unit", "unit"),
    # P2-3（核验修订）：已有空 value 后续获得真实值时同样补全
    ("value", "value"),
    # P0（8.11）：历史公告证据 period/source_type 等为 NULL/"unknown"，
    # 后续获得真实值时补全；source_type 特判 unknown 视为缺失可覆盖
    ("source_type", "source_type"),
    ("source_record_id", "source_record_id"),
    ("field_path", "field_path"),
    ("period", "period"),
    ("company_code", "company_code"),
)


def _fill_evidence_gap_fields(conn, ev: EvidenceRef, existing_row) -> None:
    """P2-4：已存证据的空字段用新值补全（CASE WHEN NULL OR ''），
    不覆盖已有非空值。source_type 额外把 "unknown" 视为缺失可补全。
    无空字段可补时零开销返回。"""
    sets = []
    params: dict = {}
    for col, attr in _GAP_FILLABLE_COLS:
        new_val = getattr(ev, attr)
        if new_val is None or str(new_val).strip() == "":
            continue
        params[attr] = str(new_val)
        if col == "source_type":
            cond = f"{col} IS NULL OR {col} = '' OR {col} = 'unknown'"
        else:
            cond = f"{col} IS NULL OR {col} = ''"
        sets.append(f"{col} = CASE WHEN {cond} THEN :{attr} ELSE {col} END")
    if not sets:
        return
    params["eid"] = ev.evidence_id
    conn.execute(
        text(f"UPDATE evidence_refs SET {', '.join(sets)} " "WHERE evidence_id = :eid"),
        params,
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


def _build_panel_data(state: AgentState) -> dict | None:
    """构建本轮面板摘要（历史会话分析面板恢复，对齐审计 P1-3）.

    最小结构 {risk_level, triggered_rules, key_metrics, follow_ups}；
    final_response 缺失时返回 None（不伪造风险等级）。
    """
    final_response = state.get("final_response")
    if final_response is None:
        return None
    plan = state.get("plan")
    intent = getattr(plan, "intent", "") if plan is not None else ""
    # 闲聊、使用引导、范围外问题和无公司研报不属于风险分析面板。
    # P2-1/P2-2：公司事实与多公司引导同样不属于风险分析面板
    if intent in {
        "chitchat",
        "guide",
        "unsupported",
        "research",
        "company_fact",
        "comparison_guide",
    }:
        return None
    results = state.get("results")
    has_analysis_result = bool(
        results
        and any(
            getattr(results, module_name, None) is not None
            for module_name in ("finance", "equity", "events")
        )
    )
    if state.get("company") is None and not has_analysis_result:
        return None
    panel: dict = {
        "risk_level": getattr(final_response, "risk_level", None),
        "triggered_rules": [],
        "key_metrics": {},
        "follow_ups": getattr(final_response, "follow_ups", None) or [],
    }
    results = state.get("results")
    finance = getattr(results, "finance", None) if results is not None else None
    if finance is not None:
        details = finance.rule_details or {}
        for rid, status in (finance.rule_statuses or {}).items():
            if status == "triggered":
                detail = details.get(rid, {}) or {}
                entry = {
                    "rule_id": rid,
                    "rule_name": detail.get("rule_name") or rid,
                    # canonical 证据 ID：rule_details 由 finance.py 写入
                    # ev_fin_<hash>（与 evidence_refs 一致）。勿用
                    # FinanceRuleItem.evidence_ids（ev_bs_*/ev_is_* 不落库）
                    # ——对齐审计 P1-2
                    "evidence_ids": detail.get("evidence_ids") or [],
                    # 2026-08-16：历史面板同样带严重度/触发解释
                    "severity": detail.get("severity") or "",
                    "explanation": detail.get("explanation") or "",
                }
                # 任务①：触发规则条目带上相似案例（若 finance.py 已写入）
                if "similar_cases" in detail:
                    entry["similar_cases"] = detail["similar_cases"]
                panel["triggered_rules"].append(entry)
    return panel


def _build_response_meta(state: AgentState) -> dict:
    """Persist terminal metadata needed to restore a historical turn."""
    final_response = state.get("final_response")
    plan = state.get("plan")
    active_code, active_source = _active_company_from_resolution(state)
    # v3.3.3 批次 B（方案 §5.4）：只落 status=ok 的指标执行记录，
    # 失败/澄清/unsupported 轮不得覆盖最近成功指标。
    # 批次 C：轻量比较轮产出 executed_metrics（list，两指标），
    # 单指标短答轮产出 executed_metric（单 dict），两者兼容。
    executed = state.get("executed_metrics") or []
    if not executed and state.get("executed_metric"):
        executed = [state.get("executed_metric")]
    executed_metrics: list[dict] = [
        item
        for item in executed
        if isinstance(item, dict) and item.get("status") == "ok"
    ]
    return {
        "intent": getattr(plan, "intent", "") if plan is not None else "",
        "follow_ups": (
            getattr(final_response, "follow_ups", None) or []
            if final_response is not None
            else []
        ),
        "supporting_evidence_ids": supporting_evidence_ids(state.get("claims", [])),
        "requested_period_text": (
            getattr(plan, "requested_period_text", "") if plan is not None else ""
        ),
        # v3.3.2-R1 §8.1：活跃主体独立于 state.company——comparison/
        # reference 轮次的 primary 同样持久化，下一轮可恢复当前主体
        "active_company_code": active_code,
        "active_company_source": active_source,
        "executed_metrics": executed_metrics,
    }


def _active_company_from_resolution(state: AgentState) -> tuple[str, str]:
    """v3.3.2-R1 §8.1：从权威实体解析结果派生当前轮活跃主体。

    - single/switch/continuation 的唯一 primary；
    - comparison/reference/sequence 中 role=primary 的已绑定公司；
    - 无确定 primary、身份歧义或 not_found → 不写（""，""）。

    中间验收 P1-3 终态守卫：未决轮（needs_confirmation 或任一
    not_found/needs_refinement/needs_confirmation mention）不写，
    避免局部锁定污染下一轮 current subject。
    """
    resolution = state.get("entity_resolution_result")
    if resolution is None:
        return "", ""
    mentions = getattr(resolution, "mentions", [])
    if getattr(resolution, "needs_confirmation", False):
        return "", ""
    pending_statuses = ("not_found", "needs_refinement", "needs_confirmation")
    if any(getattr(m, "status", None) in pending_statuses for m in mentions):
        return "", ""
    primaries = [
        m
        for m in mentions
        if getattr(m, "role", None) == "primary"
        and getattr(m, "selected_wind_code", None)
    ]
    if len(primaries) != 1:
        return "", ""
    return str(primaries[0].selected_wind_code), "explicit_primary"


def persist_turn_node(state: AgentState) -> dict:
    """持久化当前轮次 + Claim/Evidence/关联关系（单事务）。"""
    session_id = _session_id(state)
    question = state.get("user_query", "")
    if not session_id or not question:
        return {"messages": []}
    user_id = _user_id(state)

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
    panel_data_json = _to_json(_build_panel_data(state))
    response_meta_json = _to_json(_build_response_meta(state))
    # 会话列表展示两行主题；保留更多首问上下文，避免相近的分析问题难以区分。
    title = question[:48]
    provenance_ok = True
    provenance_error = ""

    try:
        from app.core.write_guard import assert_db_writable

        assert_db_writable()  # 8/19 P0：写路径运行时守卫（演示库零写入）
        with _get_engine().begin() as conn:
            # 会话 upsert
            existing = conn.execute(
                text(
                    "SELECT session_id, user_id FROM conversation_sessions "
                    "WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).first()
            if existing:
                existing_user = existing[1] or settings.SESSION_DEFAULT_USER_ID
                if existing_user != user_id:
                    raise PermissionError(
                        f"session belongs to another user: {session_id}"
                    )
                conn.execute(
                    text(
                        "UPDATE conversation_sessions "
                        "SET user_id = COALESCE(user_id, :user_id), "
                        "status = 'active', "
                        "title = CASE WHEN title IS NULL OR title = '' "
                        "OR title IN (:placeholder_a, :placeholder_b) "
                        "THEN :title ELSE title END, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE session_id = :sid"
                    ),
                    {
                        "sid": session_id,
                        "user_id": user_id,
                        "title": title,
                        "placeholder_a": sorted(SESSION_TITLE_PLACEHOLDERS)[0],
                        "placeholder_b": sorted(SESSION_TITLE_PLACEHOLDERS)[1],
                    },
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO conversation_sessions "
                        "(session_id, user_id, title, status, created_at, updated_at) "
                        "VALUES (:sid, :user_id, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"sid": session_id, "user_id": user_id, "title": title},
                )

            # turn upsert（幂等：同 turn_id 重试 → UPDATE，不新增行/不新增序号）
            existing_turn = conn.execute(
                text(
                    "SELECT turn_id, turn_index FROM conversation_turns "
                    "WHERE turn_id = :tid"
                ),
                {"tid": db_turn_id},
            ).first()
            if existing_turn:
                conn.execute(
                    text(
                        "UPDATE conversation_turns "
                        "SET answer = :a, company_code = :cc, "
                        "trace_id = :trace, module_status = :ms, "
                        "panel_data = :pd, response_meta = :rm "
                        "WHERE turn_id = :tid"
                    ),
                    {
                        "a": answer,
                        "cc": company_code,
                        "trace": trace_id,
                        "ms": module_status_json,
                        "pd": panel_data_json,
                        "rm": response_meta_json,
                        "tid": db_turn_id,
                    },
                )
                turn_index = existing_turn[1]
            else:
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
                        " company_code, trace_id, module_status, panel_data, response_meta, "
                        " created_at) "
                        "VALUES (:turn_id, :sid, :index, :q, :a, :cc, :trace, :ms, :pd, :rm, "
                        "CURRENT_TIMESTAMP)"
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
                        "pd": panel_data_json,
                        "rm": response_meta_json,
                    },
                )

            # Provenance 持久化（同一事务，顺序满足外键）
            evidence = state.get("evidence", [])
            claims = state.get("claims", [])
            # P1-2（核验修订）：统一转换为 Pydantic 模型列表（节点产出对象、
            # 测试/REST 可能传 dict），后续 upsert 与 link 全部使用模型——
            # 此前 _persist_links 收到原始 dict 访问 .evidence_ids 会 AttributeError。
            evidence_models = [
                ev if isinstance(ev, EvidenceRef) else EvidenceRef(**ev)
                for ev in evidence
            ]
            claim_models = [
                cl if isinstance(cl, Claim) else Claim(**cl) for cl in claims
            ]
            for ev in evidence_models:
                _upsert_evidence(conn, ev, db_turn_id)
            for cl in claim_models:
                _upsert_claim(conn, cl, db_turn_id)
            _persist_links(conn, claim_models, db_turn_id)

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
