"""方案 v3.1 §7 关键测试 — 步骤 3（原子 pending 状态机）.

对应审查测试项：
- company.candidates 发出后、来源 turn 删除前立即确认，最终恰好一个 T+1；
- T+1 启动失败时 pending 不丢失，可幂等恢复；
- 两个连接并发提交同 revision，只有一个成功；
- 身份全部确认但 relation 未解析时不重跑。
"""

from app.application.services.ws_session_manager import (
    ActiveTurn,
    WsSessionManager,
)


def _candidate(code: str, name: str) -> dict:
    return {
        "entity_id": f"company_{code}",
        "wind_code": code,
        "sec_name": name,
        "exchange": "XSHG",
    }


def _mention(mention_id: str, text: str, start: int, end: int, *codes: dict) -> dict:
    return {
        "mention_id": mention_id,
        "text": text,
        "start": start,
        "end": end,
        "candidates": list(codes),
        "truncated": False,
        "status": "needs_confirmation",
        "selected_wind_code": None,
        "role": None,
        "resolution_source": None,
    }


def _pending(
    *mentions: dict,
    relation: str = "comparison",
    relation_status: str = "resolved",
    revision: int = 0,
    lifecycle: str = "collecting",
) -> dict:
    # v3.3 批次 A：resolver 确定性路径已按原文顺序补默认 role；
    # fixture 同样补齐（comparison 第一个 primary 其余 peer），
    # 满足 validate_pending_resume_state 的 role 完整性要求
    for idx, m in enumerate(mentions):
        if m.get("role") is None:
            m["role"] = (
                "primary" if relation != "comparison" or idx == 0 else "comparison_peer"
            )
    return {
        "origin_turn_id": "t1",
        "revision": revision,
        "lifecycle_status": lifecycle,
        "resolution_version": 1,
        "question": "平安和茅台对比",
        "query_fingerprint": "fp-abc",
        "relation": relation,
        "relation_status": relation_status,
        "segmentation_alternatives": [],
        "selected_alternative_id": None,
        "mentions": {m["mention_id"]: m for m in mentions},
        "resumed_turn_id": None,
    }


def _manager():
    mgr = WsSessionManager()
    return mgr, mgr.get_or_create_session("s1")


def _confirm(mgr, session, mention_id, code, revision=0):
    return mgr.confirm_pending_mention(session, "t1", mention_id, code, revision)


def _dummy_task():
    """在独立 loop 上创建 dummy task。

    pytest-asyncio STRICT（loop scope=function）下同步测试没有当前
    loop，不能依赖 asyncio.get_event_loop()（全量跑时抛
    "no current event loop"）。返回 (loop, task) 供 finally 清理。
    """
    import asyncio

    loop = asyncio.new_event_loop()
    task = loop.create_task(asyncio.sleep(0))
    return loop, task


def _close_dummy_task(loop, task) -> None:
    """取消 dummy task 并关闭其独立 loop（吸收取消异常）。"""
    import asyncio

    task.cancel()
    try:
        loop.run_until_complete(asyncio.sleep(0))
    except Exception:  # noqa: BLE001
        pass
    loop.close()


# ── P0-1 竞态：来源 turn 未移除时确认 → 最终恰好一个 T+1 ──────


def test_confirm_before_origin_turn_removed_exactly_one_t11():
    """客户端在 company.candidates 发出后、remove_turn(T) 前立即确认。

    确认成功写入（RESUME_READY）；claim 因来源 turn 仍在而拒绝；
    remove_turn 后 claim 成功且仅登记一个 T+1；重复 claim 拒绝。
    """
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
    )
    # 来源 turn 仍在 session.turns（_run_ws_turn finally 尚未 remove）
    session.turns["t1"] = ActiveTurn(
        turn_id="t1", session_id="s1", question="平安和茅台对比"
    )

    status, _ = _confirm(mgr, session, "m_pingan", "000001.SZ")
    assert status == "WAITING"  # 茅台仍待确认
    status, _ = _confirm(mgr, session, "m_maotai", "600519.SH", revision=1)
    assert status == "RESUME_READY"
    assert session.pending_disambiguation["lifecycle_status"] == "ready_to_resume"

    # 来源 turn 尚未移除 → claim 拒绝（竞态窗口）
    status, _ = mgr.claim_pending_resume(session, "t1", 2, "t2")
    assert status == "ORIGIN_TURN_ACTIVE"
    assert "t2" not in session.turns  # 未登记 T+1

    # remove_turn(T) 后 claim 成功，恰好登记一个 T+1
    mgr.remove_turn(session, "t1")
    status, snapshot = mgr.claim_pending_resume(session, "t1", 2, "t2")
    assert status == "OK"
    assert session.turns.keys() == {"t2"}
    assert session.pending_disambiguation["lifecycle_status"] == "resuming"
    assert session.pending_disambiguation["resumed_turn_id"] == "t2"
    # override 快照保留 relation/role
    assert snapshot["override"]["relation"] == "comparison"
    assert snapshot["question"] == "平安和茅台对比"

    # 重复 claim → RESUME_IN_PROGRESS（v3.2.1 批次 5：区分已领取，
    # 不会启动第二个 T+1）
    status, _ = mgr.claim_pending_resume(session, "t1", 2, "t3")
    assert status == "RESUME_IN_PROGRESS"
    assert "t3" not in session.turns

    # T+1 成功接受后 consume
    assert mgr.consume_pending_resume(session, "t1", "t2")
    assert session.pending_disambiguation["lifecycle_status"] == "consumed"


# ── P0-1：T+1 启动失败时 pending 不丢失、可幂等恢复 ────────────


def test_claim_retry_after_failed_resume():
    """claim 失败（来源 turn 活跃）后 pending 保持 ready_to_resume；
    来源 turn 移除后同一确认幂等重试成功，不重复计费/登记。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
    )
    session.turns["t1"] = ActiveTurn(
        turn_id="t1", session_id="s1", question="平安和茅台对比"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "WAITING"
    assert (
        _confirm(mgr, session, "m_maotai", "600519.SH", revision=1)[0] == "RESUME_READY"
    )

    # 第一次 claim 被竞态拒绝，pending 不被破坏
    assert mgr.claim_pending_resume(session, "t1", 2, "t2")[0] == "ORIGIN_TURN_ACTIVE"
    assert session.pending_disambiguation["lifecycle_status"] == "ready_to_resume"

    # 来源 turn 移除后幂等重试成功
    mgr.remove_turn(session, "t1")
    status, _ = mgr.claim_pending_resume(session, "t1", 2, "t2")
    assert status == "OK"


# ── P0-2：并发同 revision 只有一个成功 ─────────────────────────


def test_concurrent_same_revision_only_one_succeeds():
    """两个连接并发提交同 revision：第一个写入（WAITING），第二个为
    幂等重放（v3.2.1 批次 5：不增 revision、不报 REVISION_MISMATCH）。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
    )
    # 两个连接同时确认同一 mention、同一 revision 0
    s1, _ = _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)
    s2, _ = _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)
    assert s1 == "WAITING"
    assert s2 == "WAITING"  # 同值重放：不产生写入
    assert session.pending_disambiguation["revision"] == 1  # 只增一次
    # 用新 revision 确认另一 mention → 正常
    assert (
        _confirm(mgr, session, "m_maotai", "600519.SH", revision=1)[0] == "RESUME_READY"
    )


# ── P0-3：身份全确认但 relation 未解析 → 不重跑 ───────────────


def test_relation_not_resolved_blocks_resume():
    """身份全部确认但 relation_status != resolved → RELATION_BLOCKED，
    不进入 ready_to_resume，不启动 T+1。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
        relation_status="needs_clarification",
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "WAITING"
    status, _ = _confirm(mgr, session, "m_maotai", "600519.SH", revision=1)
    assert status == "RELATION_BLOCKED"
    assert session.pending_disambiguation["lifecycle_status"] == "collecting"
    assert mgr.claim_pending_resume(session, "t1", 2, "t2")[0] == "NOT_READY"
    assert "t2" not in session.turns


# ── P0-2：relation 不可执行（reference）同样不重跑 ─────────────


def test_reference_relation_not_executable_blocks_resume():
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        relation="reference",
        relation_status="resolved",
    )
    status, _ = _confirm(mgr, session, "m_pingan", "000001.SZ")
    assert status == "RELATION_BLOCKED"


# ── 校验拒绝路径 ──────────────────────────────────────────────


def test_confirm_validation_rejections():
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        relation="single",
    )

    # 无 pending
    assert (
        mgr.confirm_pending_mention(session, "tx", "m_pingan", "000001.SZ", 0)[0]
        == "NO_PENDING"
    )
    # revision 不匹配
    assert (
        _confirm(mgr, session, "m_pingan", "000001.SZ", revision=5)[0]
        == "REVISION_MISMATCH"
    )
    # 未知 mention_id
    assert (
        _confirm(mgr, session, "m_unknown", "000001.SZ", revision=0)[0]
        == "INVALID_MENTION"
    )
    # 非候选 code（库外）
    assert (
        _confirm(mgr, session, "m_pingan", "601318.SH", revision=0)[0] == "INVALID_CODE"
    )
    # 合法确认后：重复确认同一 mention（已 user_confirmed，lifecycle=
    # ready_to_resume）→ v3.2.1 幂等重放 RESUME_READY，不增 revision
    assert (
        _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)[0] == "RESUME_READY"
    )
    assert (
        _confirm(mgr, session, "m_pingan", "000001.SZ", revision=1)[0] == "RESUME_READY"
    )
    assert session.pending_disambiguation["revision"] == 1  # 重放不增 revision
    # 同 mention 不同 code → NOT_ACCEPTING（重放值不一致）
    assert (
        _confirm(mgr, session, "m_pingan", "601318.SH", revision=1)[0] == "INVALID_CODE"
    )


def test_confirm_candidate_match_dict_form():
    """candidates 为 CandidateMatch 形态（company 嵌套）也能校验候选。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mention = _mention("m_pingan", "平安", 0, 2)
    mention["candidates"] = [
        {"company": pa, "match_kind": "exact_name", "matched_text": "平安", "rank": 0}
    ]
    session.pending_disambiguation = _pending(mention, relation="single")
    status, _ = _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)
    assert status == "RESUME_READY"


def test_consume_pending_validation():
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        relation="single",
    )
    assert not mgr.consume_pending_resume(session, "t1", "t2")  # 尚未 resuming
    session.pending_disambiguation["resumed_turn_id"] = "t2"
    assert mgr.consume_pending_resume(session, "t1", "t2")
    assert session.pending_disambiguation["lifecycle_status"] == "consumed"
    assert not mgr.consume_pending_resume(session, "t1", "t9")  # resumed 不匹配


# ── v3.2.1 批次 5：幂等重放四生命周期 ────────────────────────


def test_replay_after_resume_ready_returns_resume_ready():
    """ready_to_resume 同值重放 → RESUME_READY + 最新快照，不增 revision。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa), relation="single"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "RESUME_READY"
    assert session.pending_disambiguation["lifecycle_status"] == "ready_to_resume"
    # 同值重放（revision 已过期也接受——重放不产生写入）
    status, snapshot = _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)
    assert status == "RESUME_READY"
    assert snapshot["revision"] == 1
    assert session.pending_disambiguation["revision"] == 1  # 不增


def test_replay_while_resuming_returns_resume_in_progress():
    """resuming 同值重放 → RESUME_IN_PROGRESS。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        relation="single",
        lifecycle="resuming",
    )
    session.pending_disambiguation["mentions"]["m_pingan"].update(
        {"status": "user_confirmed", "selected_wind_code": "000001.SZ"}
    )
    assert (
        _confirm(mgr, session, "m_pingan", "000001.SZ", revision=9)[0]
        == "RESUME_IN_PROGRESS"
    )


def test_replay_after_consumed_returns_already_resumed():
    """consumed 同值重放 → ALREADY_RESUMED。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        relation="single",
        lifecycle="consumed",
    )
    session.pending_disambiguation["mentions"]["m_pingan"].update(
        {"status": "user_confirmed", "selected_wind_code": "000001.SZ"}
    )
    assert (
        _confirm(mgr, session, "m_pingan", "000001.SZ", revision=9)[0]
        == "ALREADY_RESUMED"
    )


def test_replay_collecting_partial_returns_waiting():
    """collecting 期部分确认后的同值重放 → WAITING，不增 revision。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "WAITING"
    status, snapshot = _confirm(mgr, session, "m_pingan", "000001.SZ", revision=0)
    assert status == "WAITING"
    assert snapshot["revision"] == 1
    assert session.pending_disambiguation["revision"] == 1


def test_replay_different_code_not_accepting():
    """已确认 mention 重放不同 code（但属于候选集）→ NOT_ACCEPTING。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    zg = _candidate("601318.SH", "中国平安")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa, zg), relation="single"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "RESUME_READY"
    assert (
        _confirm(mgr, session, "m_pingan", "601318.SH", revision=1)[0]
        == "NOT_ACCEPTING"
    )


# ── v3.2.1 批次 5：claim 状态码与 rollback ────────────────────


def test_claim_resuming_returns_resume_in_progress():
    """lifecycle=resuming 时 claim → RESUME_IN_PROGRESS（不压成 NOT_READY）。"""
    mgr, session = _manager()
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, _candidate("000001.SZ", "平安银行")),
        relation="single",
        lifecycle="resuming",
    )
    session.pending_disambiguation["resumed_turn_id"] = "t2"
    assert mgr.claim_pending_resume(session, "t1", 0, "t3")[0] == "RESUME_IN_PROGRESS"
    assert "t3" not in session.turns


def test_claim_consumed_returns_already_resumed():
    """lifecycle=consumed 时 claim → ALREADY_RESUMED。"""
    mgr, session = _manager()
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, _candidate("000001.SZ", "平安银行")),
        relation="single",
        lifecycle="consumed",
    )
    assert mgr.claim_pending_resume(session, "t1", 0, "t3")[0] == "ALREADY_RESUMED"


def test_abort_claimed_resume_restores_ready_to_resume():
    """claim 后启动失败 → abort（claim token）恢复 ready_to_resume，可重试成功。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa), relation="single"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "RESUME_READY"
    status, resume = mgr.claim_pending_resume(session, "t1", 1, "t2")
    assert status == "OK"
    claim_id = resume["claim_id"]
    assert session.pending_disambiguation["lifecycle_status"] == "resuming"
    assert session.pending_disambiguation["resume_claim_id"] == claim_id
    # 启动失败 → abort：pending 恢复、claim 字段清除；turn 由 caller
    # 按 outcome.turn_present 定向移除
    outcome = mgr.abort_claimed_resume(session, "t1", "t2", claim_id)
    assert outcome.owned is True
    assert outcome.pending_restored is True
    assert outcome.turn_present is True
    if outcome.turn_present:
        mgr.remove_turn(session, "t2")
    assert session.pending_disambiguation["lifecycle_status"] == "ready_to_resume"
    assert session.pending_disambiguation["resumed_turn_id"] is None
    assert session.pending_disambiguation["resume_claim_id"] is None
    assert "t2" not in session.turns  # 新 turn 已定向移除
    # abort 后可重试成功
    status, _ = mgr.claim_pending_resume(session, "t1", 1, "t3")
    assert status == "OK"
    assert "t3" in session.turns


def test_abort_claimed_resume_claim_token_validation():
    """abort 三件套不匹配 → owned=False，不误删 turn、不覆盖 pending。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa), relation="single"
    )
    # 来源 turn 存在（活跃）——abort 不匹配时不得删除
    session.turns["t1"] = ActiveTurn(turn_id="t1", session_id="s1", question="q")
    # resumed_turn_id 不匹配
    session.pending_disambiguation["resumed_turn_id"] = "t9"
    session.pending_disambiguation["lifecycle_status"] = "resuming"
    outcome = mgr.abort_claimed_resume(session, "t1", "t2", "claim_x")
    assert outcome.owned is False
    assert outcome.pending_restored is False
    assert "t1" in session.turns  # 来源 turn 未被误删
    assert session.pending_disambiguation["lifecycle_status"] == "resuming"  # 未覆盖
    # claim_id 不匹配（pending 属于其他 claim）
    session.pending_disambiguation["resumed_turn_id"] = "t2"
    session.pending_disambiguation["resume_claim_id"] = "claim_other"
    outcome = mgr.abort_claimed_resume(session, "t1", "t2", "claim_x")
    assert outcome.owned is False
    assert session.pending_disambiguation["resume_claim_id"] == "claim_other"


# ── v3.3 批次 A（P0-2）：严格终态校验 ────────────────────────


def test_validate_pending_resume_state_accepts_valid():
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pa = _candidate("000001.SZ", "平安银行")
    mt = _candidate("600519.SH", "贵州茅台")
    pending = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, mt),
    )
    pending["mentions"]["m_pingan"].update(
        {"status": "user_confirmed", "selected_wind_code": "000001.SZ"}
    )
    pending["mentions"]["m_maotai"].update(
        {"status": "auto_selected", "selected_wind_code": "600519.SH"}
    )
    ok, _ = validate_pending_resume_state(pending)
    assert ok


def test_validate_pending_resume_state_rejects_not_found():
    """P0-2：pending 同时含 user_confirmed + not_found → 不得恢复。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pa = _candidate("000001.SZ", "平安银行")
    pending = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_unknown", "台泥", 4, 6),
        relation="comparison",
    )
    pending["mentions"]["m_pingan"].update(
        {"status": "user_confirmed", "selected_wind_code": "000001.SZ"}
    )
    pending["mentions"]["m_unknown"].update(
        {"status": "not_found", "selected_wind_code": None, "role": None}
    )
    ok, reason = validate_pending_resume_state(pending)
    assert not ok
    assert "not_found" in reason


def test_validate_pending_resume_state_rejects_duplicate_codes():
    """P0-2：comparison 两个 mention 同一 code → 不得恢复。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pa = _candidate("000001.SZ", "平安银行")
    pa2 = _candidate("000001.SZ", "平安银行")
    pending = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_maotai", "茅台", 4, 6, pa2),
    )
    for mid in ("m_pingan", "m_maotai"):
        pending["mentions"][mid].update(
            {"status": "user_confirmed", "selected_wind_code": "000001.SZ"}
        )
    ok, reason = validate_pending_resume_state(pending)
    assert not ok
    # v3.3.1 §7.1：复用 validate_finalized_relation_roles（同一套终态闸门）
    assert "严格终态" in reason


def test_confirm_identity_blocked_on_not_found_mention():
    """P0-2 端到端：确认唯一可确认 mention 后，另一 not_found mention
    使终态校验失败 → IDENTITY_BLOCKED，不进入 ready_to_resume。"""
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa),
        _mention("m_unknown", "台泥", 4, 6),
        relation="single",
    )
    session.pending_disambiguation["mentions"]["m_unknown"].update(
        {"status": "not_found", "role": None}
    )
    status, _ = _confirm(mgr, session, "m_pingan", "000001.SZ")
    assert status == "IDENTITY_BLOCKED"
    assert session.pending_disambiguation["lifecycle_status"] == "collecting"
    # claim 仍被拒（未进入 ready_to_resume）
    assert mgr.claim_pending_resume(session, "t1", 1, "t2")[0] == "NOT_READY"


# ── v3.3 批次 A（P0-1）：attach + consume 锁内原子 ────────────


def test_attach_and_consume_pending_resume_atomic():
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa), relation="single"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "RESUME_READY"
    status, resume = mgr.claim_pending_resume(session, "t1", 1, "t2")
    assert status == "OK"
    claim_id = resume["claim_id"]

    loop, task = _dummy_task()
    try:
        assert mgr.attach_and_consume_pending_resume(
            session, "t1", "t2", task, claim_id
        )
        assert session.pending_disambiguation["lifecycle_status"] == "consumed"
        assert session.turns["t2"].task is task
    finally:
        _close_dummy_task(loop, task)


def test_attach_and_consume_state_conflicts():
    mgr, session = _manager()
    pa = _candidate("000001.SZ", "平安银行")
    session.pending_disambiguation = _pending(
        _mention("m_pingan", "平安", 0, 2, pa), relation="single"
    )
    assert _confirm(mgr, session, "m_pingan", "000001.SZ")[0] == "RESUME_READY"
    status, resume = mgr.claim_pending_resume(session, "t1", 1, "t2")
    assert status == "OK"
    claim_id = resume["claim_id"]

    loop, task = _dummy_task()
    try:
        # resumed_turn_id 不匹配 → conflict，不修改任何状态
        assert not mgr.attach_and_consume_pending_resume(
            session, "t1", "t9", task, claim_id
        )
        assert session.pending_disambiguation["lifecycle_status"] == "resuming"
        # origin 不匹配 → conflict
        assert not mgr.attach_and_consume_pending_resume(
            session, "tx", "t2", task, claim_id
        )
        assert session.pending_disambiguation["lifecycle_status"] == "resuming"
        # claim_id 不匹配 → conflict（v3.3.1 §7.2 三件套）
        assert not mgr.attach_and_consume_pending_resume(
            session, "t1", "t2", task, "claim_wrong"
        )
        assert session.pending_disambiguation["lifecycle_status"] == "resuming"
        # 新 turn 不存在 → conflict
        mgr.remove_turn(session, "t2")
        assert not mgr.attach_and_consume_pending_resume(
            session, "t1", "t2", task, claim_id
        )
    finally:
        _close_dummy_task(loop, task)


# ── v3.3.1 §7.1：pending 严格角色结构（§7.4 反例）─────────────


def _confirmed_comparison(roles: dict[str, str]) -> dict:
    """构造 comparison pending：两个 mention 已确认，role 按传入覆盖。"""
    pa = _candidate("000001.SZ", "平安银行")
    pb = _candidate("600519.SH", "贵州茅台")
    pending = _pending(
        _mention("m_a", "平安", 0, 2, pa),
        _mention("m_b", "茅台", 3, 5, pb),
    )
    for mid, code in (("m_a", "000001.SZ"), ("m_b", "600519.SH")):
        pending["mentions"][mid].update(
            {"status": "user_confirmed", "selected_wind_code": code}
        )
    for mid, role in roles.items():
        pending["mentions"][mid]["role"] = role
    return pending


def test_validate_pending_rejects_two_primaries():
    """comparison 两个 primary → 拒绝（§7.4 反例 1）。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pending = _confirmed_comparison({"m_a": "primary", "m_b": "primary"})
    ok, reason = validate_pending_resume_state(pending)
    assert not ok
    assert "严格终态" in reason


def test_validate_pending_rejects_no_primary():
    """comparison 无 primary → 拒绝（§7.4 反例 2）。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pending = _confirmed_comparison(
        {"m_a": "comparison_peer", "m_b": "comparison_peer"}
    )
    ok, reason = validate_pending_resume_state(pending)
    assert not ok
    assert "严格终态" in reason


def test_validate_pending_rejects_non_peer_role():
    """comparison 存在非 peer 的其余 mention → 拒绝。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pending = _confirmed_comparison({"m_a": "primary", "m_b": "referenced"})
    ok, reason = validate_pending_resume_state(pending)
    assert not ok
    assert "严格终态" in reason


def test_validate_pending_accepts_valid_comparison():
    """合法 comparison（1 primary + 1 peer、两个不同 code）→ 通过。"""
    from app.application.services.ws_session_manager import (
        validate_pending_resume_state,
    )

    pending = _confirmed_comparison({"m_a": "primary", "m_b": "comparison_peer"})
    ok, reason = validate_pending_resume_state(pending)
    assert ok, reason


def test_build_override_decisions_covers_final_mentions():
    """claim 前 override 构造：完整覆盖 + 严格终态（§7.1 检查点）。"""
    from app.application.services.ws_session_manager import (
        build_and_validate_override_decisions,
    )

    pending = _confirmed_comparison({"m_a": "primary", "m_b": "comparison_peer"})
    decisions, error = build_and_validate_override_decisions(pending)
    assert decisions is not None, error
    assert {d["mention_id"] for d in decisions} == {"m_a", "m_b"}
    assert all(d["wind_code"] and d["role"] for d in decisions)


def test_build_override_decisions_rejects_bad_roles():
    """claim 前 override 构造：角色结构非法 → None + 错误原因。"""
    from app.application.services.ws_session_manager import (
        build_and_validate_override_decisions,
    )

    pending = _confirmed_comparison({"m_a": "primary", "m_b": "primary"})
    decisions, error = build_and_validate_override_decisions(pending)
    assert decisions is None
    assert error
