"""PersistTurn 节点单元测试 — V12 §7.2.

覆盖：SQL_BACKEND 开关、会话 upsert、turn_index 递增、字段落库、异常吞掉。
使用内存 SQLite 建 conversation 两张表，不依赖真实 MySQL。
"""

import pytest
from sqlalchemy import create_engine, text

from app.agents.nodes import persist_turn as pt
from app.agents.state import (
    AgentState,
    ExecutionPlan,
    FinalResponse,
    ModuleStatus,
    RuntimeState,
)
from app.infrastructure.persistence.models import ConversationSession, ConversationTurn


@pytest.fixture
def sqlite_engine():
    """内存 SQLite：仅建 conversation 两张表。"""
    engine = create_engine("sqlite:///:memory:")
    ConversationSession.__table__.create(engine)
    ConversationTurn.__table__.create(engine)
    yield engine
    engine.dispose()


def _patch_mysql(monkeypatch, engine):
    """切换模块到 mysql 模式并注入 SQLite 引擎。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(pt, "_get_engine", lambda: engine)


def _make_state(
    query: str = "康美药业有风险吗",
    session_id: str = "ses_test",
    answer: str = "康美药业存在高风险信号。",
    turn_id: str = "turn_01",
    user_id: str = "",
) -> AgentState:
    """构造完整轮次状态。"""
    return {
        "user_query": query,
        "messages": [{"role": "user", "content": query}],
        "module_status": {
            "finance": ModuleStatus(state="success", duration_ms=120),
            "equity": ModuleStatus(state="skipped"),
        },
        "final_response": FinalResponse(answer=answer, risk_level="red"),
        "runtime": RuntimeState(
            trace_id="trace_01",
            session_id=session_id,
            user_id=user_id,
            turn_id=turn_id,
        ),
    }


# ── no-op 开关 ──────────────────────────────────────────────


def test_db_error_marks_partial(monkeypatch):
    """数据库异常被吞掉，但标记 persist_turn=partial + warning（不静默）。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "mysql")

    def _should_not_be_called():
        raise AssertionError("数据库引擎不可用")

    monkeypatch.setattr(pt, "_get_engine", _should_not_be_called)
    result = pt.persist_turn_node(_make_state())
    assert result["messages"] == []
    assert result["module_status"]["persist_turn"].state == "partial"
    assert (
        result["module_status"]["persist_turn"].error_code
        == "PROVENANCE_PERSIST_FAILED"
    )


def test_noop_without_session_id(monkeypatch, sqlite_engine):
    """无 session_id 时 no-op。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state(session_id="")
    result = pt.persist_turn_node(state)
    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one()
            == 0
        )


def test_noop_without_question(monkeypatch, sqlite_engine):
    """无问题时 no-op。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = pt.persist_turn_node(_make_state(query=""))
    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one()
            == 0
        )


# ── 首轮写入 ────────────────────────────────────────────────


def test_persist_first_turn(monkeypatch, sqlite_engine):
    """首轮：创建会话 + 写入 turn_index=1。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = pt.persist_turn_node(_make_state())

    assert result == {"messages": []}

    with sqlite_engine.connect() as conn:
        session = (
            conn.execute(
                text(
                    "SELECT session_id, user_id, title, status "
                    "FROM conversation_sessions"
                )
            )
            .mappings()
            .one()
        )
        assert session["session_id"] == "ses_test"
        assert session["user_id"] == pt.settings.SESSION_DEFAULT_USER_ID
        assert session["title"] == "康美药业有风险吗"  # question 前 30 字
        assert session["status"] == "active"

        turn = conn.execute(text("SELECT * FROM conversation_turns")).mappings().one()
        assert turn["turn_index"] == 1
        assert turn["question"] == "康美药业有风险吗"
        assert turn["answer"] == "康美药业存在高风险信号。"
        assert turn["company_code"] is None
        assert turn["trace_id"] == "trace_01"
        assert "finance" in turn["module_status"]


def test_panel_data_has_rule_evidence_ids(monkeypatch, sqlite_engine):
    """面板摘要：triggered 规则携带 canonical 证据 ID（对齐审计 P1-2）.

    曾硬编码 evidence_ids=[]；后又误用 FinanceRuleItem.evidence_ids
    （ev_bs_*/ev_is_* 不落 evidence_refs）。正确来源是
    rule_details[rid]["evidence_ids"]（finance.py 写入的 ev_fin_* canonical ID）。
    """
    from app.agents.state import FinanceResult, ModuleResults

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["results"] = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered", "R2": "not_triggered"},
            rule_details={
                "R1": {
                    "rule_name": "应收-营收背离",
                    "evidence_ids": ["ev_fin_hash_r1_a", "ev_fin_hash_r1_b"],
                }
            },
        )
    )

    pt.persist_turn_node(state)

    with sqlite_engine.connect() as conn:
        turn = (
            conn.execute(text("SELECT panel_data FROM conversation_turns"))
            .mappings()
            .one()
        )
    import json

    panel = (
        json.loads(turn["panel_data"])
        if isinstance(turn["panel_data"], str)
        else turn["panel_data"]
    )
    assert panel["risk_level"] == "red"
    rules = panel["triggered_rules"]
    assert [r["rule_id"] for r in rules] == ["R1"], "仅 triggered 规则入面板"
    assert rules[0]["rule_name"] == "应收-营收背离"
    assert rules[0]["evidence_ids"] == [
        "ev_fin_hash_r1_a",
        "ev_fin_hash_r1_b",
    ], "R1 应携带 rule_details 的 canonical 证据 ID（ev_fin_*）"


def test_chitchat_does_not_persist_analysis_panel(monkeypatch, sqlite_engine):
    """闲聊轮次 panel_data 必须为 NULL，历史恢复不得显示未知风险卡。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state(query="你好", answer="你好！我是织网鉴真。")
    state["plan"] = ExecutionPlan(intent="chitchat", requested_modules=[])

    pt.persist_turn_node(state)

    with sqlite_engine.connect() as conn:
        panel_data = conn.execute(
            text("SELECT panel_data FROM conversation_turns")
        ).scalar_one()
    assert panel_data is None


def test_existing_new_session_gets_first_question_title(monkeypatch, sqlite_engine):
    """前端预创建“新对话”后，首轮持久化应写入可识别标题。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_test', '新对话', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    pt.persist_turn_node(_make_state(query="分析康美药业的现金流"))

    with sqlite_engine.connect() as conn:
        title = conn.execute(
            text("SELECT title FROM conversation_sessions WHERE session_id='ses_test'")
        ).scalar_one()
    assert title == "分析康美药业的现金流"


def test_existing_default_new_session_gets_first_question_title(
    monkeypatch, sqlite_engine
):
    """API default placeholder '新会话' is replaced just like legacy '新对话'."""
    _patch_mysql(monkeypatch, sqlite_engine)
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_test', '新会话', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    pt.persist_turn_node(_make_state(query="分析康美药业 2025 年报"))
    with sqlite_engine.connect() as conn:
        title = conn.execute(
            text("SELECT title FROM conversation_sessions WHERE session_id='ses_test'")
        ).scalar_one()
    assert title == "分析康美药业 2025 年报"


def test_persist_turn_writes_explicit_user_id(monkeypatch, sqlite_engine):
    """显式 user_id 随自动会话写入，供会话 API 隔离。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state(user_id="user_a"))
    with sqlite_engine.connect() as conn:
        user_id = conn.execute(
            text(
                "SELECT user_id FROM conversation_sessions WHERE session_id='ses_test'"
            )
        ).scalar_one()
    assert user_id == "user_a"


def test_persist_turn_rejects_cross_user_session_reuse(monkeypatch, sqlite_engine):
    """同 session_id 不允许被其他 user_id 追加轮次。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state(user_id="user_a"))
    result = pt.persist_turn_node(
        _make_state(query="第二轮", turn_id="turn_02", user_id="user_b")
    )

    assert result["module_status"]["persist_turn"].state == "partial"
    with sqlite_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM conversation_turns")
        ).scalar_one()
    assert count == 1


def test_response_meta_persisted(monkeypatch, sqlite_engine):
    """Historical turns retain terminal metadata without changing panel semantics."""
    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["plan"] = ExecutionPlan(intent="diagnose", requested_period_text="2025 年报")
    state["final_response"] = FinalResponse(
        answer="回答", risk_level="orange", follow_ups=["继续核查"]
    )
    pt.persist_turn_node(state)
    with sqlite_engine.connect() as conn:
        raw = conn.execute(
            text("SELECT response_meta FROM conversation_turns")
        ).scalar_one()
    import json

    meta = json.loads(raw) if isinstance(raw, str) else raw
    assert meta["intent"] == "diagnose"
    assert meta["follow_ups"] == ["继续核查"]
    assert meta["requested_period_text"] == "2025 年报"
    assert meta["supporting_evidence_ids"] == []


def test_executed_metric_ok_persisted_in_response_meta(monkeypatch, sqlite_engine):
    """v3.3.3 批次 B（方案 §5.4）：status=ok 的 executed_metric 落库。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["plan"] = ExecutionPlan(intent="indicator", indicator="r5_gross_margin")
    state["final_response"] = FinalResponse(answer="毛利率为 62.00%")
    state["executed_metric"] = {
        "metric_id": "r5_gross_margin",
        "period": "20250331",
        "unit": "percent",
        "status": "ok",
    }
    pt.persist_turn_node(state)
    with sqlite_engine.connect() as conn:
        raw = conn.execute(
            text("SELECT response_meta FROM conversation_turns")
        ).scalar_one()
    meta = json.loads(raw) if isinstance(raw, str) else raw
    assert meta["executed_metrics"] == [state["executed_metric"]]


def test_failed_metric_turn_does_not_pollute_executed_metrics(
    monkeypatch, sqlite_engine
):
    """v3.3.3 批次 B 完成标准：失败/unsupported 轮不写 executed_metrics。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["plan"] = ExecutionPlan(intent="indicator", indicator="r5_gross_margin")
    state["final_response"] = FinalResponse(answer="该指标暂未覆盖。")
    state["executed_metric"] = {
        "metric_id": "r5_gross_margin",
        "status": "insufficient_data",
    }
    pt.persist_turn_node(state)
    with sqlite_engine.connect() as conn:
        raw = conn.execute(
            text("SELECT response_meta FROM conversation_turns")
        ).scalar_one()
    meta = json.loads(raw) if isinstance(raw, str) else raw
    assert meta["executed_metrics"] == []


def test_executed_metrics_list_persisted_for_comparison_turn(
    monkeypatch, sqlite_engine
):
    """v3.3.3 批次 C：轻量比较轮产出 executed_metrics 列表（仅 ok 项）。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["plan"] = ExecutionPlan(intent="light_comparison")
    state["final_response"] = FinalResponse(answer="高 4.50个百分点")
    state["executed_metrics"] = [
        {
            "metric_id": "accounts_receivable_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
        },
        {
            "metric_id": "operating_revenue_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
        },
        {"metric_id": "r5_gross_margin", "status": "insufficient_data"},
    ]
    pt.persist_turn_node(state)
    with sqlite_engine.connect() as conn:
        raw = conn.execute(
            text("SELECT response_meta FROM conversation_turns")
        ).scalar_one()
    meta = json.loads(raw) if isinstance(raw, str) else raw
    assert meta["executed_metrics"] == state["executed_metrics"][:2]


def test_persist_with_company_code(monkeypatch, sqlite_engine):
    """company 存在时写入 wind_code。"""
    from app.agents.state import CompanyRef

    _patch_mysql(monkeypatch, sqlite_engine)
    state = _make_state()
    state["company"] = CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )
    pt.persist_turn_node(state)

    with sqlite_engine.connect() as conn:
        code = conn.execute(
            text("SELECT company_code FROM conversation_turns")
        ).scalar_one()
        assert code == "600518.SH"


# ── 中间验收批次 A3：active_company 终态守卫（P1-3）──────────────


def _resolution_with_mentions(intent, mentions, needs_confirmation=False):
    from app.application.models.company_resolution import EntityResolutionResult

    return EntityResolutionResult(
        intent=intent,
        mentions=mentions,
        needs_confirmation=needs_confirmation,
    )


def _mention(code, status="auto_selected", role="primary"):
    from app.application.models.company_resolution import EntityMention

    return EntityMention(
        mention_id=f"m_{code}",
        text=code,
        status=status,
        selected_wind_code=code,
        role=role,
    )


def test_pending_ambiguous_turn_does_not_persist_active_company():
    """P1-3：歧义未决轮（一绑定一待确认）不得写 active_company_code。"""
    resolution = _resolution_with_mentions(
        intent="ambiguous",
        mentions=[
            _mention("600519.SH", status="auto_selected", role="primary"),
            _mention("000001.SZ", status="needs_confirmation", role="comparison_peer"),
        ],
        needs_confirmation=True,
    )
    state = {"entity_resolution_result": resolution}
    code, source = pt._active_company_from_resolution(state)
    assert code == ""
    assert source == ""


def test_not_found_mention_does_not_persist_active_company():
    """P1-3：存在 not_found mention 的轮次不得写活跃主体。"""
    resolution = _resolution_with_mentions(
        intent="single",
        mentions=[
            _mention("600519.SH", status="auto_selected", role="primary"),
            _mention("", status="not_found", role="comparison_peer"),
        ],
    )
    state = {"entity_resolution_result": resolution}
    code, _ = pt._active_company_from_resolution(state)
    assert code == ""


def test_finalized_comparison_persists_primary_active_company():
    """P1-3：完整终态 comparison 轮写 role=primary 的已绑定公司。"""
    resolution = _resolution_with_mentions(
        intent="comparison",
        mentions=[
            _mention("600519.SH", status="auto_selected", role="primary"),
            _mention("000858.SZ", status="auto_selected", role="comparison_peer"),
        ],
        needs_confirmation=False,
    )
    state = {"entity_resolution_result": resolution}
    code, source = pt._active_company_from_resolution(state)
    assert code == "600519.SH"


def test_finalized_single_persists_active_company():
    """P1-3：正常 single 终态轮照常写活跃主体。"""
    resolution = _resolution_with_mentions(
        intent="single", mentions=[_mention("600518.SH", role="primary")]
    )
    state = {"entity_resolution_result": resolution}
    code, _ = pt._active_company_from_resolution(state)
    assert code == "600518.SH"


def test_persist_second_turn_increments_index(monkeypatch, sqlite_engine):
    """第二轮：turn_index 递增为 2，不重复建会话。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state())
    pt.persist_turn_node(
        _make_state(
            query="它的应收账款呢", answer="应收账款增速47.2%。", turn_id="turn_02"
        )
    )

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM conversation_sessions")
            ).scalar_one()
            == 1
        )
        indices = (
            conn.execute(
                text("SELECT turn_index FROM conversation_turns ORDER BY turn_index")
            )
            .scalars()
            .all()
        )
        assert list(indices) == [1, 2]

        # title 保持首轮
        title = conn.execute(
            text("SELECT title FROM conversation_sessions")
        ).scalar_one()
        assert title == "康美药业有风险吗"


def test_title_truncated_to_30(monkeypatch, sqlite_engine):
    """超长 question 截断为 30 字。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    long_q = "长" * 50
    pt.persist_turn_node(_make_state(query=long_q))

    with sqlite_engine.connect() as conn:
        title = conn.execute(
            text("SELECT title FROM conversation_sessions")
        ).scalar_one()
        assert len(title) == 30


# ── 同 turn 重试幂等（Phase C 任务 8） ─────────────────────


def test_same_turn_retry_is_idempotent(monkeypatch, sqlite_engine):
    """同 turn_id 二次写入 → UPDATE 而非重复 INSERT，行数与序号不变。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state())
    # 重试同一 turn（模拟 WS 重发）
    pt.persist_turn_node(_make_state(answer="重试后的回答"))

    with sqlite_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one()
            == 1
        )
        turn = (
            conn.execute(text("SELECT turn_index, answer FROM conversation_turns"))
            .mappings()
            .one()
        )
        assert turn["turn_index"] == 1  # 序号不递增
        assert turn["answer"] == "重试后的回答"  # 内容更新


def test_same_turn_retry_does_not_increment_index(monkeypatch, sqlite_engine):
    """同 turn 重试后接新 turn，序号应为 2（不是 3）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    pt.persist_turn_node(_make_state())  # turn_01
    pt.persist_turn_node(_make_state())  # turn_01 重试
    pt.persist_turn_node(
        _make_state(query="第二轮", answer="第二轮回答", turn_id="turn_02")
    )  # turn_02

    with sqlite_engine.connect() as conn:
        indices = (
            conn.execute(
                text("SELECT turn_index FROM conversation_turns ORDER BY turn_index")
            )
            .scalars()
            .all()
        )
        assert list(indices) == [1, 2]


# ── 异常容错 ────────────────────────────────────────────────


def test_db_error_not_crashes(monkeypatch):
    """数据库异常不抛给 Agent 主流程，返回可处理结果。"""
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "mysql")

    def _broken_engine():
        raise RuntimeError("db down")

    monkeypatch.setattr(pt, "_get_engine", _broken_engine)
    result = pt.persist_turn_node(_make_state())
    assert result["messages"] == []
    assert result["module_status"]["persist_turn"].state == "partial"


# ── R7 回归：Evidence/Claim 同 ID 不同内容冲突 → 回滚 + partial ───


@pytest.fixture
def sqlite_provenance_engine():
    """内存 SQLite：conversation + evidence_refs + claims + links 全建。"""
    from app.infrastructure.persistence.models import (
        Claim,
        ClaimEvidenceLink,
        EvidenceRef,
    )

    engine = create_engine("sqlite:///:memory:")
    ConversationSession.__table__.create(engine)
    ConversationTurn.__table__.create(engine)
    EvidenceRef.__table__.create(engine)
    Claim.__table__.create(engine)
    ClaimEvidenceLink.__table__.create(engine)
    yield engine
    engine.dispose()


def _insert_evidence(engine, eid: str, source_record_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
                "company_code, dataset_version, retrieved_at) "
                "VALUES (:eid, 'financial_statement', :src, '600518.SH', 'test-v1', "
                "CURRENT_TIMESTAMP)"
            ),
            {"eid": eid, "src": source_record_id},
        )


def _insert_claim(engine, cid: str, company_code: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO claims (claim_id, company_code, claim_type, "
                "severity, verification_status, module, text, generated_at) "
                "VALUES (:cid, :cc, 'rule', 'red', 'pending', 'finance', '旧内容', "
                "CURRENT_TIMESTAMP)"
            ),
            {"cid": cid, "cc": company_code},
        )


@pytest.mark.parametrize("conflict_kind", ["evidence", "claim"])
def test_id_conflict_rolls_back_all_and_marks_partial(
    monkeypatch, sqlite_provenance_engine, conflict_kind
):
    """R7：同 ID 不同内容 → 异常不外溢 + 全事务回滚 + partial + warning。

    先插入一条合法新证据（ID 不同），再触发冲突——若冲突回滚，合法证据
    也未落库，证明"前序写入已回滚"而非只跳过冲突项。
    """
    _patch_mysql(monkeypatch, sqlite_provenance_engine)

    # 预插入与 state 冲突的旧记录
    if conflict_kind == "evidence":
        _insert_evidence(sqlite_provenance_engine, "ev_conflict_1", "rec_old")
    else:
        _insert_claim(sqlite_provenance_engine, "clm_conflict_1", "600518.SH")

    state = _make_state()
    state["evidence"] = [
        # 合法新证据（先写入，应被回滚）
        {
            "evidence_id": "ev_legit_new",
            "source_type": "financial_statement",
            "source_record_id": "rec_new",
            "company_code": "600518.SH",
            "module": "finance",
        },
        # 冲突证据：同 ID 不同内容
        {
            "evidence_id": "ev_conflict_1",
            "source_type": "financial_statement",
            "source_record_id": "rec_different",
            "company_code": "600518.SH",
            "module": "finance",
        },
    ]
    state["claims"] = [
        {
            "claim_id": "clm_conflict_1" if conflict_kind == "claim" else "clm_legit",
            "text": "新内容",
            "company_code": "600518.SH",
            "module": "finance",
        }
    ]

    # 1. 不抛异常（ValueError 不逃逸）
    result = pt.persist_turn_node(state)

    # 2. partial + warning
    assert result["module_status"]["persist_turn"].state == "partial"
    assert "PROVENANCE_PERSIST_FAILED" in (
        result["module_status"]["persist_turn"].error_code
    )
    assert any("PROVENANCE_PERSIST_FAILED" in w for w in state["runtime"].warnings)

    # 3. 全事务回滚：合法新证据也未落库
    with sqlite_provenance_engine.connect() as conn:
        legit = conn.execute(
            text(
                "SELECT COUNT(*) FROM evidence_refs WHERE evidence_id = 'ev_legit_new'"
            )
        ).scalar()
        assert legit == 0, "合法新证据应随冲突一并回滚"
        if conflict_kind == "evidence":
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM evidence_refs WHERE evidence_id = 'ev_conflict_1'"
                )
            ).scalar()
            assert n == 1  # 仍是预插入的旧记录
        else:
            n = conn.execute(
                text("SELECT COUNT(*) FROM claims WHERE claim_id = 'clm_legit'")
            ).scalar()
            assert n == 0, "Claim 冲突时合法证据外的写入也应回滚"


def test_evidence_gap_fill_idempotent(monkeypatch, sqlite_provenance_engine):
    """P2-4：先写空 title/uri，后写非空 → 只补空字段、不覆盖非空值；幂等。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)

    # 第一轮：证据 title/uri 为空
    state1 = _make_state()
    state1["evidence"] = [
        {
            "evidence_id": "ev_gap_1",
            "source_type": "announcement",
            "source_record_id": "rec_1",
            "company_code": "600518.SH",
            "module": "events",
            "source_title": "",
            "source_uri": "",
        }
    ]
    pt.persist_turn_node(state1)

    # 第二轮：同 ID 但 title/uri 非空（补全）
    state2 = _make_state()
    state2["evidence"] = [
        {
            "evidence_id": "ev_gap_1",
            "source_type": "announcement",
            "source_record_id": "rec_1",
            "company_code": "600518.SH",
            "module": "events",
            "source_title": "公告标题",
            "source_uri": "https://example.com/ann.pdf",
        }
    ]
    result2 = pt.persist_turn_node(state2)
    assert result2 == {"messages": []}  # 不冲突、不报错

    with sqlite_provenance_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT source_title, source_uri FROM evidence_refs WHERE evidence_id='ev_gap_1'"
            )
        ).first()
        assert row[0] == "公告标题"  # 空字段被补全
        assert row[1] == "https://example.com/ann.pdf"

    # 第三轮：已有非空值 + 不同新值 → 不覆盖
    state3 = _make_state()
    state3["evidence"] = [
        {
            "evidence_id": "ev_gap_1",
            "source_type": "announcement",
            "source_record_id": "rec_1",
            "company_code": "600518.SH",
            "module": "events",
            "source_title": "另一个标题",
            "source_uri": "",
        }
    ]
    pt.persist_turn_node(state3)
    with sqlite_provenance_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT source_title, source_uri FROM evidence_refs WHERE evidence_id='ev_gap_1'"
            )
        ).first()
        assert row[0] == "公告标题"  # 已有非空值不被覆盖
        assert row[1] == "https://example.com/ann.pdf"  # 非空值保持


def test_dict_claim_evidence_links_persist_ok(monkeypatch, sqlite_provenance_engine):
    """P1-2（核验修订）：dict 形式的 Claim + Evidence + link 全部成功落库。

    此前 _persist_links 收到原始 dict 列表访问 .evidence_ids 触发
    AttributeError，非冲突 dict Claim 的 link 恒空；统一转模型后应完整落库。
    """
    _patch_mysql(monkeypatch, sqlite_provenance_engine)
    # _persist_links 的 INSERT IGNORE 是 MySQL 语法，SQLite 需 OR IGNORE；
    # 引擎已注入 SQLite，这里切回 sqlite 分支即可（不依赖真实 MySQL）
    monkeypatch.setattr(pt.settings, "SQL_BACKEND", "sqlite")
    state = _make_state()
    state["claims"] = [
        {
            "claim_id": "claim_dict_1",
            "text": "应收账款增速显著高于营收增速",
            "claim_type": "rule",
            "severity": "orange",
            "verification_status": "verified",
            "evidence_ids": ["ev_dict_1"],
            "module": "finance",
            "company_code": "600518.SH",
        }
    ]
    state["evidence"] = [
        {
            "evidence_id": "ev_dict_1",
            "source_type": "financial_statement",
            "source_record_id": "bs_600518_20251231",
            "company_code": "600518.SH",
            "module": "finance",
            "value": "123456789",
        }
    ]
    result = pt.persist_turn_node(state)
    assert result == {"messages": []}

    with sqlite_provenance_engine.connect() as conn:
        claim = conn.execute(
            text("SELECT claim_id, text FROM claims WHERE claim_id='claim_dict_1'")
        ).first()
        assert claim is not None
        assert claim[1] == "应收账款增速显著高于营收增速"
        ev = conn.execute(
            text(
                "SELECT evidence_id, value FROM evidence_refs "
                "WHERE evidence_id='ev_dict_1'"
            )
        ).first()
        assert ev is not None and ev[1] == "123456789"
        link = conn.execute(
            text(
                "SELECT claim_id, evidence_id FROM claim_evidence_links "
                "WHERE claim_id='claim_dict_1'"
            )
        ).first()
        assert link is not None
        assert link[0] == "claim_dict_1" and link[1] == "ev_dict_1"


def test_evidence_value_gap_fill(monkeypatch, sqlite_provenance_engine):
    """P2-3（核验修订）：已有空 value 后续获得真实值 → 补全
    （CASE WHEN 覆盖 value 列，不覆盖非空值）。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)

    state1 = _make_state()
    state1["evidence"] = [
        {
            "evidence_id": "ev_val_1",
            "source_type": "announcement",
            "source_record_id": "rec_v",
            "company_code": "600518.SH",
            "module": "events",
            "value": "",
        }
    ]
    pt.persist_turn_node(state1)

    state2 = _make_state()
    state2["evidence"] = [
        {
            "evidence_id": "ev_val_1",
            "source_type": "announcement",
            "source_record_id": "rec_v",
            "company_code": "600518.SH",
            "module": "events",
            "value": "2024年净利润下滑20%",
        }
    ]
    pt.persist_turn_node(state2)

    with sqlite_provenance_engine.connect() as conn:
        row = conn.execute(
            text("SELECT value FROM evidence_refs WHERE evidence_id='ev_val_1'")
        ).first()
        assert row[0] == "2024年净利润下滑20%"  # 空 value 被补全


# ── P0（8.11）：Evidence 空值兼容与冲突安全 ─────────────────


def test_evidence_null_period_filled_with_new_period(
    monkeypatch, sqlite_provenance_engine
):
    """P0（8.11）：历史记录 period=NULL，新值=公告日期 → 兼容补全不冲突
    （ev_ann_* 反复落库失败根因场景）。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)
    with sqlite_provenance_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
                "company_code, dataset_version, retrieved_at) "
                "VALUES ('ev_ann_1', 'announcement', 'ann_rec_1', '600518.SH', "
                "'test-v1', CURRENT_TIMESTAMP)"
            )
        )

    state = _make_state()
    state["evidence"] = [
        {
            "evidence_id": "ev_ann_1",
            "source_type": "announcement",
            "source_record_id": "ann_rec_1",
            "company_code": "600518.SH",
            "module": "events",
            "period": "2026-01-15",
        }
    ]
    result = pt.persist_turn_node(state)
    assert result == {"messages": []}  # 空 period 兼容，不冲突

    with sqlite_provenance_engine.connect() as conn:
        period = conn.execute(
            text("SELECT period FROM evidence_refs WHERE evidence_id='ev_ann_1'")
        ).scalar()
        assert period == "2026-01-15"  # 空 period 被补全


def test_evidence_unknown_source_type_filled_with_real(
    monkeypatch, sqlite_provenance_engine
):
    """P0（8.11）：source_type='unknown' 视为缺失，可被真实类型补全。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)
    with sqlite_provenance_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
                "company_code, dataset_version, retrieved_at) "
                "VALUES ('ev_unk_1', 'unknown', 'rec_u', '600518.SH', 'test-v1', "
                "CURRENT_TIMESTAMP)"
            )
        )

    state = _make_state()
    state["evidence"] = [
        {
            "evidence_id": "ev_unk_1",
            "source_type": "announcement",
            "source_record_id": "rec_u",
            "company_code": "600518.SH",
            "module": "events",
        }
    ]
    result = pt.persist_turn_node(state)
    assert result == {"messages": []}

    with sqlite_provenance_engine.connect() as conn:
        st = conn.execute(
            text("SELECT source_type FROM evidence_refs WHERE evidence_id='ev_unk_1'")
        ).scalar()
        assert st == "announcement"


def test_evidence_real_source_type_conflict_rejected(
    monkeypatch, sqlite_provenance_engine
):
    """P0（8.11）：两个已知且不同的 source_type → 冲突回滚，保留旧值。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)
    with sqlite_provenance_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
                "company_code, dataset_version, retrieved_at) "
                "VALUES ('ev_ct_1', 'announcement', 'rec_1', '600518.SH', 'test-v1', "
                "CURRENT_TIMESTAMP)"
            )
        )

    state = _make_state()
    state["evidence"] = [
        {
            "evidence_id": "ev_ct_1",
            "source_type": "financial_statement",
            "source_record_id": "rec_1",
            "company_code": "600518.SH",
            "module": "finance",
        }
    ]
    result = pt.persist_turn_node(state)
    assert result["module_status"]["persist_turn"].state == "partial"
    assert any("PROVENANCE_PERSIST_FAILED" in w for w in state["runtime"].warnings)

    with sqlite_provenance_engine.connect() as conn:
        st = conn.execute(
            text("SELECT source_type FROM evidence_refs WHERE evidence_id='ev_ct_1'")
        ).scalar()
        assert st == "announcement"  # 旧值保留


def test_evidence_nonempty_period_conflict_rejected(
    monkeypatch, sqlite_provenance_engine
):
    """P0（8.11）：双方 period 均非空且不同 → 冲突回滚。"""
    _patch_mysql(monkeypatch, sqlite_provenance_engine)
    with sqlite_provenance_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
                "company_code, period, dataset_version, retrieved_at) "
                "VALUES ('ev_pc_1', 'announcement', 'rec_1', '600518.SH', "
                "'2025-12-31', 'test-v1', CURRENT_TIMESTAMP)"
            )
        )

    state = _make_state()
    state["evidence"] = [
        {
            "evidence_id": "ev_pc_1",
            "source_type": "announcement",
            "source_record_id": "rec_1",
            "company_code": "600518.SH",
            "module": "events",
            "period": "2026-03-31",
        }
    ]
    result = pt.persist_turn_node(state)
    assert result["module_status"]["persist_turn"].state == "partial"

    with sqlite_provenance_engine.connect() as conn:
        period = conn.execute(
            text("SELECT period FROM evidence_refs WHERE evidence_id='ev_pc_1'")
        ).scalar()
        assert period == "2025-12-31"  # 旧值保留
