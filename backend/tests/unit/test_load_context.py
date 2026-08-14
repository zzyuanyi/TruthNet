"""LoadContext 节点单元测试 — V12 §7.2.

覆盖：SQL_BACKEND 开关、最近 N 轮回读、消息顺序、空历史、异常吞掉。
使用内存 SQLite 建 conversation 两张表，不依赖真实 MySQL。
"""

import pytest
from sqlalchemy import create_engine, text

from app.agents.nodes import load_context as lc
from app.agents.state import AgentState, RuntimeState
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
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(lc, "_get_engine", lambda: engine)


def _make_state(session_id: str = "ses_test") -> AgentState:
    return {
        "user_query": "",
        "messages": [],
        "runtime": RuntimeState(trace_id="trace_01", session_id=session_id),
    }


def _seed_turns(engine, session_id: str = "ses_test", n: int = 3) -> None:
    """预置 n 轮历史（question/answer 成对）。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"sid": session_id, "title": "历史会话"},
        )
        for i in range(1, n + 1):
            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, answer, created_at) "
                    "VALUES (:tid, :sid, :idx, :q, :a, CURRENT_TIMESTAMP)"
                ),
                {
                    "tid": f"turn_{i:02d}",
                    "sid": session_id,
                    "idx": i,
                    "q": f"第{i}轮问题",
                    "a": f"第{i}轮回答",
                },
            )


# ── no-op 开关 ──────────────────────────────────────────────


def test_noop_when_not_mysql(monkeypatch):
    """SQL_BACKEND != mysql 时不读库、返回空 messages。"""
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "sqlite")

    def _should_not_be_called():
        raise AssertionError("sqlite 模式下不应访问数据库")

    monkeypatch.setattr(lc, "_get_engine", _should_not_be_called)
    result = lc.load_context_node(_make_state())
    assert result["messages"] == []
    assert result["runtime"] is not None


def test_noop_without_session_id(monkeypatch, sqlite_engine):
    """无 session_id 时返回空。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = lc.load_context_node(_make_state(session_id=""))
    assert result["messages"] == []


# ── 历史回读 ────────────────────────────────────────────────


def test_loads_history_in_order(monkeypatch, sqlite_engine):
    """回读历史并按时间升序组装 user/assistant 消息。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turns(sqlite_engine, n=2)

    result = lc.load_context_node(_make_state())

    msgs = result["messages"]
    assert len(msgs) == 4
    assert msgs[0] == {"role": "user", "content": "第1轮问题"}
    assert msgs[1] == {"role": "assistant", "content": "第1轮回答"}
    assert msgs[2] == {"role": "user", "content": "第2轮问题"}
    assert msgs[3] == {"role": "assistant", "content": "第2轮回答"}


def test_loads_recent_n_only(monkeypatch, sqlite_engine):
    """超过回读上限时只取最近 N 轮（Phase C: 10 轮窗口）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turns(sqlite_engine, n=12)

    result = lc.load_context_node(_make_state())

    msgs = result["messages"]
    assert len(msgs) == 20  # 10 轮 × 2 条（_HISTORY_LIMIT=10）
    assert msgs[0] == {"role": "user", "content": "第3轮问题"}
    assert msgs[-1] == {"role": "assistant", "content": "第12轮回答"}


def test_empty_history(monkeypatch, sqlite_engine):
    """会话存在但无轮次时返回空 messages。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES ('ses_test', '空会话', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )

    result = lc.load_context_node(_make_state())
    assert result["messages"] == []


def test_session_not_exist(monkeypatch, sqlite_engine):
    """会话不存在时返回空（不抛错）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    result = lc.load_context_node(_make_state(session_id="ses_missing"))
    assert result["messages"] == []


# ── 中间验收批次 A4：response_meta 双形态读取（P1-4）────────────


def test_parse_json_meta_dict():
    """dict 形态直返（ORM JSON 列反序列化结果）。"""
    assert lc._parse_json_meta({"active_company_code": "600519.SH"}) == {
        "active_company_code": "600519.SH"
    }


def test_parse_json_meta_json_string():
    """JSON 字符串形态解析。"""
    assert lc._parse_json_meta('{"active_company_code": "600518.SH"}') == {
        "active_company_code": "600518.SH"
    }


def test_parse_json_meta_bad_json_returns_empty():
    """坏 JSON（如 str(dict) 单引号产物）回退空 dict。"""
    assert lc._parse_json_meta("{'active_company_code': '600519.SH'}") == {}


def test_parse_json_meta_none_returns_empty():
    assert lc._parse_json_meta(None) == {}
    assert lc._parse_json_meta("") == {}


def _seed_turn_with_meta(engine, session_id, turn_idx, q, a, company_code, meta):
    """预置带 company_code/response_meta 的单轮。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"sid": session_id, "title": "历史会话"},
        )
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, answer, "
                "company_code, response_meta, created_at) "
                "VALUES (:tid, :sid, :idx, :q, :a, :cc, :meta, "
                "CURRENT_TIMESTAMP)"
            ),
            {
                "tid": f"turn_{turn_idx:02d}",
                "sid": session_id,
                "idx": turn_idx,
                "q": q,
                "a": a,
                "cc": company_code,
                "meta": meta,
            },
        )


def test_load_context_reads_response_meta_json_string(monkeypatch, sqlite_engine):
    """P1-4：response_meta JSON 字符串形态 → active_company_code 优先。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turn_with_meta(
        sqlite_engine,
        "ses_test",
        1,
        "茅台和五粮液对比",
        "回答",
        "600519.SH",
        json.dumps({"active_company_code": "000858.SZ"}),
    )
    result = lc.load_context_node(_make_state())
    assert result["recent_company_codes"] == ["000858.SZ"]


def test_load_context_bad_meta_falls_back_to_company_code(monkeypatch, sqlite_engine):
    """P1-4：坏 JSON → 回退 company_code（不丢主体）。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turn_with_meta(
        sqlite_engine,
        "ses_test",
        1,
        "问题",
        "回答",
        "600518.SH",
        "{'not': 'valid json'",
    )
    result = lc.load_context_node(_make_state())
    assert result["recent_company_codes"] == ["600518.SH"]


def test_load_context_none_meta_falls_back_to_company_code(monkeypatch, sqlite_engine):
    """P1-4：response_meta NULL → 回退 company_code。"""
    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turn_with_meta(
        sqlite_engine, "ses_test", 1, "问题", "回答", "600518.SH", None
    )
    result = lc.load_context_node(_make_state())
    assert result["recent_company_codes"] == ["600518.SH"]


def test_load_context_recovers_recent_executed_metrics(monkeypatch, sqlite_engine):
    """v3.3.3 批次 B（方案 §5.4）：从 response_meta 恢复最近成功指标。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turn_with_meta(
        sqlite_engine,
        "ses_test",
        1,
        "它的应收账款增速是多少",
        "增速 12.00%",
        "600518.SH",
        json.dumps(
            {
                "executed_metrics": [
                    {
                        "metric_id": "accounts_receivable_growth",
                        "period": "20250331",
                        "unit": "percent",
                        "status": "ok",
                    }
                ]
            }
        ),
    )
    result = lc.load_context_node(_make_state())
    assert result["recent_executed_metrics"] == [
        {
            "metric_id": "accounts_receivable_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
            "company_code": "600518.SH",
        }
    ]


def test_load_context_skips_non_ok_metrics_and_dedups(monkeypatch, sqlite_engine):
    """v3.3.3 批次 B 完成标准：非 ok 轮跳过；同 metric_id 最近优先去重。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    # 较旧轮（turn_index=1）：一次 ok + 一次失败（失败不得污染）
    _seed_turn_with_meta(
        sqlite_engine,
        "ses_test",
        1,
        "和营业收入增速对比呢",
        "答",
        "600518.SH",
        json.dumps(
            {
                "executed_metrics": [
                    {
                        "metric_id": "accounts_receivable_growth",
                        "period": "20241231",
                        "unit": "percent",
                        "status": "ok",
                    },
                    {
                        "metric_id": "r5_gross_margin",
                        "status": "insufficient_data",
                    },
                ]
            }
        ),
    )
    # 最新轮（turn_index=2）：同指标更新期次（去重后保留最近）
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, answer, "
                "company_code, response_meta, created_at) "
                "VALUES (:tid, :sid, :idx, :q, :a, :cc, :meta, "
                "CURRENT_TIMESTAMP)"
            ),
            {
                "tid": "turn_02",
                "sid": "ses_test",
                "idx": 2,
                "q": "它的应收账款增速是多少",
                "a": "答",
                "cc": "600518.SH",
                "meta": json.dumps(
                    {
                        "executed_metrics": [
                            {
                                "metric_id": "accounts_receivable_growth",
                                "period": "20250331",
                                "unit": "percent",
                                "status": "ok",
                            }
                        ]
                    }
                ),
            },
        )
    result = lc.load_context_node(_make_state())
    assert result["recent_executed_metrics"] == [
        {
            "metric_id": "accounts_receivable_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
            "company_code": "600518.SH",
        }
    ]


# ── 异常容错 ────────────────────────────────────────────────


def test_load_context_same_metric_other_company_kept_separately(
    monkeypatch, sqlite_engine
):
    """收口批次 B（方案 §3.4）：不同公司同 metric_id 不去重覆盖。"""
    import json

    _patch_mysql(monkeypatch, sqlite_engine)
    _seed_turn_with_meta(
        sqlite_engine,
        "ses_test",
        1,
        "康美的应收账款增速",
        "答",
        "600518.SH",
        json.dumps(
            {
                "executed_metrics": [
                    {
                        "metric_id": "accounts_receivable_growth",
                        "period": "20250331",
                        "unit": "percent",
                        "status": "ok",
                        "company_code": "600518.SH",
                    }
                ]
            }
        ),
    )
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_turns "
                "(turn_id, session_id, turn_index, question, answer, "
                "company_code, response_meta, created_at) "
                "VALUES (:tid, :sid, :idx, :q, :a, :cc, :meta, "
                "CURRENT_TIMESTAMP)"
            ),
            {
                "tid": "turn_02",
                "sid": "ses_test",
                "idx": 2,
                "q": "茅台的应收账款增速",
                "a": "答",
                "cc": "600519.SH",
                "meta": json.dumps(
                    {
                        "executed_metrics": [
                            {
                                "metric_id": "accounts_receivable_growth",
                                "period": "20240930",
                                "unit": "percent",
                                "status": "ok",
                                "company_code": "600519.SH",
                            }
                        ]
                    }
                ),
            },
        )
    result = lc.load_context_node(_make_state())
    codes = {m["company_code"] for m in result["recent_executed_metrics"]}
    assert codes == {"600518.SH", "600519.SH"}
    assert len(result["recent_executed_metrics"]) == 2


def test_db_error_swallowed(monkeypatch):
    """数据库异常被吞掉，返回空消息。"""
    monkeypatch.setattr(lc.settings, "SQL_BACKEND", "mysql")

    def _broken_engine():
        raise RuntimeError("db down")

    monkeypatch.setattr(lc, "_get_engine", _broken_engine)
    result = lc.load_context_node(_make_state())
    assert result["messages"] == []
