"""Memory 跨轮指代 — 会话持久化恢复流测试.

对应后端任务 7 验收（不是单次传入全量消息）:
- 每轮历史从 conversation_turns 持久化恢复（load_context 回读）；
- 第 20 轮以内仍能恢复正确主体；
- 中途切换公司后"它"指向最近主体；
- 不同 session 之间不串公司（隔离）。
使用内存 SQLite，不访问 MySQL。
"""

import pytest
from sqlalchemy import text

from app.agents.nodes import load_context as lc
from app.agents.nodes.memory import memory_node
from app.agents.state import AgentState, RuntimeState
from app.infrastructure.persistence.models import ConversationSession, ConversationTurn


@pytest.fixture
def conv_engine(monkeypatch):
    """内存 SQLite 会话表 + 注入 load_context 引擎。"""
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    ConversationSession.__table__.create(engine)
    ConversationTurn.__table__.create(engine)
    monkeypatch.setattr(lc, "_get_engine", lambda: engine)
    yield engine
    engine.dispose()


def _make_state(session_id: str, query: str = "") -> AgentState:
    return {
        "user_query": query,
        "messages": [],
        "runtime": RuntimeState(trace_id=f"t_{session_id}", session_id=session_id),
    }


def _persist_turn(engine, session_id: str, query: str, answer: str) -> None:
    """模拟 persist_turn：写入一轮 (question, answer)。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": session_id, "title": "会话"},
        )
        idx = conn.execute(
            text("SELECT COUNT(*) FROM conversation_turns WHERE session_id = :sid"),
            {"sid": session_id},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, answer, created_at) "
                "VALUES (:tid, :sid, :idx, :q, :a, CURRENT_TIMESTAMP)"
            ),
            {
                "tid": f"{session_id}_turn_{idx + 1}",
                "sid": session_id,
                "idx": idx + 1,
                "q": query,
                "a": answer,
            },
        )


def _next_turn_resolution(engine, session_id: str, query: str):
    """新一轮：load_context 从 DB 恢复 → memory 指代消解."""
    loaded = lc.load_context_node(_make_state(session_id, query))
    state = _make_state(session_id, query)
    state["messages"] = loaded["messages"]
    out = memory_node(state)
    return out["memory_context"]


# ── 20 轮窗口内指代正确（从持久化恢复后仍正确）──────────────


def test_twenty_turns_anaphora_via_persistence(conv_engine):
    engine = conv_engine
    sid = "ses_twenty"
    turns = [
        ("康美药业有风险吗", "康美药业财务存在以下高风险信号..."),
        ("它的应收账款增速如何", "康美药业应收账款增速47.2%与营收增速背离..."),
        ("那现金流和利润呢", "康美药业经营现金流为负，与净利润背离..."),
        ("这家公司的股权结构", "康美药业实控人为马兴田..."),
        ("上次提到的存货指标呢", "康美药业存货增速与营收存在异常..."),
        ("它还有其他风险吗", "康美药业还检测到存贷双高信号..."),
        ("该公司的现金流风险怎么样", "康美药业投资活动现金流持续为负..."),
        ("那关联方有什么异常吗", "康美药业其他应收款占比过高..."),
        ("之前分析的结论是什么", "康美药业综合风险为红色预警..."),
    ]
    turns.extend(
        (f"第{i}轮继续核查", "康美药业仍作为当前分析对象。") for i in range(10, 20)
    )
    # 前 19 轮逐轮持久化
    for q, a in turns:
        _persist_turn(engine, sid, q, a)

    # 第 20 轮：含指代"这个"，历史从 DB 恢复（19 轮共 38 条消息）
    ctx = _next_turn_resolution(engine, sid, "这个结论可靠吗")
    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "康美药业"


# ── 中途切换公司 ─────────────────────────────────────────────


def test_entity_switch_via_persistence(conv_engine):
    engine = conv_engine
    sid = "ses_switch"
    _persist_turn(engine, sid, "康美药业有风险吗", "康美药业存在财务风险...")
    _persist_turn(engine, sid, "贵州茅台呢", "贵州茅台财务状况健康...")

    # "它" 应指向最近提到的贵州茅台
    ctx = _next_turn_resolution(engine, sid, "它的营收怎么样")
    assert ctx.resolved_entity_name == "贵州茅台"

    # 继续追问仍指向贵州茅台（上次那家）
    _persist_turn(engine, sid, "它的营收怎么样", "贵州茅台营收稳定增长...")
    ctx2 = _next_turn_resolution(engine, sid, "上次那家的现金流呢")
    assert ctx2.resolved_entity_name == "贵州茅台"


# ── 服务重启模拟 ─────────────────────────────────────────────


def test_service_restart_recovers_from_db(conv_engine):
    engine = conv_engine
    sid = "ses_restart"
    _persist_turn(engine, sid, "康美药业有风险吗", "康美药业存在财务风险...")
    _persist_turn(engine, sid, "它的应收账款如何", "康美药业应收增速异常...")

    # 模拟重启：重新执行 load_context（不依赖进程内 state，仅从 DB）
    ctx = _next_turn_resolution(engine, sid, "它还有其他风险吗")
    assert ctx.resolved_entity_name == "康美药业"


# ── 会话隔离 ─────────────────────────────────────────────────


def test_session_isolation(conv_engine):
    engine = conv_engine
    _persist_turn(engine, "ses_a", "康美药业有风险吗", "康美药业存在财务风险...")
    _persist_turn(engine, "ses_b", "贵州茅台怎么样", "贵州茅台财务健康...")

    # session A 的"它"不能引用 session B 的公司
    ctx_a = _next_turn_resolution(engine, "ses_a", "它的应收如何")
    assert ctx_a.resolved_entity_name == "康美药业"

    ctx_b = _next_turn_resolution(engine, "ses_b", "它的营收如何")
    assert ctx_b.resolved_entity_name == "贵州茅台"


# ── 无历史时"它" ─────────────────────────────────────────────


def test_anaphora_no_history(conv_engine):
    engine = conv_engine
    sid = "ses_empty"
    ctx = _next_turn_resolution(engine, sid, "它有风险吗")
    # 无历史也无当前公司 → 无法消解，不应崩溃
    assert ctx.resolved_entity_name is None or ctx.resolved_entity_name == ""
