"""PersistTurn 节点单元测试 — V12 §7.2.

覆盖：SQL_BACKEND 开关、会话 upsert、turn_index 递增、字段落库、异常吞掉。
使用内存 SQLite 建 conversation 两张表，不依赖真实 MySQL。
"""

import pytest
from sqlalchemy import create_engine, text

from app.agents.nodes import persist_turn as pt
from app.agents.state import AgentState, FinalResponse, ModuleStatus, RuntimeState
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
            trace_id="trace_01", session_id=session_id, turn_id=turn_id
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
                text("SELECT session_id, title, status FROM conversation_sessions")
            )
            .mappings()
            .one()
        )
        assert session["session_id"] == "ses_test"
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
