"""Agent events_node 故障行为单元测试（第四轮核查补）。

固定两个纯单元行为（REST 测试覆盖不到 Agent 节点）：
  1. 公告查询异常 → 仍执行评级/事件簇查询并保留结果；
     模块 partial + DB_ERROR + recoverable=True。
  2. 公告为空 → 模块 partial + NO_ANNOUNCEMENT_DATA + recoverable=True；
     评级/事件簇仍保留。
"""

import pytest

from app.agents.nodes.events import events_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    ExecutionPlan,
    RuntimeState,
)


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


@pytest.fixture
def _mysql_backend(monkeypatch):
    """固定 full-profile 语义（CI 默认 SQLite 会早退 DATA_SOURCE_UNAVAILABLE）。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")


def _state(monkeypatch, announcements, rating_rows, cluster_rows) -> AgentState:
    """mock 三个 fetch，返回 (state, calls)；announcements 可为 Exception。"""
    import app.agents.nodes.events as ev

    calls = {"ann": 0, "rating": 0, "clusters": 0}

    def _fake_ann(*a, **k):
        calls["ann"] += 1
        if isinstance(announcements, Exception):
            raise announcements
        return announcements

    def _fake_rating(*a, **k):
        calls["rating"] += 1
        return rating_rows

    def _fake_clusters(*a, **k):
        calls["clusters"] += 1
        return (cluster_rows, None)

    monkeypatch.setattr(ev, "_fetch_announcements", _fake_ann)
    monkeypatch.setattr(ev, "_fetch_rating_changes", _fake_rating)
    monkeypatch.setattr(ev, "_fetch_event_clusters", _fake_clusters)

    state: AgentState = {
        "user_query": "分析康美",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    return state, calls


_RATING_ROW = {
    "quarter": "2025Q1",
    "direction": "down",
    "institution": "测试证券",
    "current_rating": "增持",
}
_CLUSTER_ROW = {
    "event_cluster_id": "cl_1",
    "topic": "诉讼",
    "sentiment": "negative",
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
}


def test_announcement_error_keeps_rating_and_clusters(monkeypatch, _mysql_backend):
    """P1：公告查询异常 → 评级/事件簇各执行 1 次并保留；partial + DB_ERROR + recoverable=True。"""
    state, calls = _state(
        monkeypatch, RuntimeError("DB 断开"), [_RATING_ROW], [_CLUSTER_ROW]
    )
    out = events_node(state)

    ms = out["module_status"]["events"]
    assert ms.state == "partial"
    assert ms.error_code == "DB_ERROR"
    assert ms.recoverable is True
    # 评级/事件簇仍被查询（各 1 次）且结果保留
    assert calls["rating"] == 1
    assert calls["clusters"] == 1
    ev_res = out["results"].events
    assert ev_res.rating_changes == [_RATING_ROW]
    assert ev_res.clusters == [_CLUSTER_ROW]


def test_no_announcement_recoverable_true(monkeypatch, _mysql_backend):
    """P2：公告为空 → partial + NO_ANNOUNCEMENT_DATA + recoverable=True；评级/事件簇保留。"""
    state, calls = _state(monkeypatch, [], [_RATING_ROW], [_CLUSTER_ROW])
    out = events_node(state)

    ms = out["module_status"]["events"]
    assert ms.state == "partial"
    assert ms.error_code == "NO_ANNOUNCEMENT_DATA"
    assert ms.recoverable is True  # 回归原行为（不得为 false）
    ev_res = out["results"].events
    assert ev_res.rating_changes == [_RATING_ROW]
    assert ev_res.clusters == [_CLUSTER_ROW]
    # NO_ANNOUNCEMENT_DATA warning 写入 runtime
    assert any("NO_ANNOUNCEMENT_DATA" in w for w in state["runtime"].warnings)


def test_rating_and_cluster_evidence_join_module_output(monkeypatch, _mysql_backend):
    rating = {
        **_RATING_ROW,
        "evidence_id": "ev_rating_1",
        "report_id": "report_1",
        "published_at": "2025-03-01",
        "previous_rating": "买入",
        "source_title": "评级报告",
        "dataset_version": "dv",
    }
    cluster = {
        **_CLUSTER_ROW,
        "dataset_version": "dv",
        "evidence_ids": ["ev_cluster_1"],
        "sources": [
            {
                "source_type": "announcement",
                "source_record_id": "ann_1",
                "published_at": "2025-02-01",
                "title": "处罚公告",
                "evidence_id": "ev_cluster_1",
            }
        ],
    }
    state, _calls = _state(monkeypatch, [], [rating], [cluster])
    evidence = events_node(state)["results"].events.evidence
    by_id = {item.evidence_id: item for item in evidence}
    assert by_id["ev_rating_1"].source_type == "research_report"
    assert by_id["ev_rating_1"].field_path == "rating_change"
    assert by_id["ev_cluster_1"].source_record_id == "ann_1"


def test_cluster_data_error_partial_status(monkeypatch, _mysql_backend):
    """批次 E：事件簇数据错误 → partial/EVENT_CLUSTER_DATA_ERROR + runtime warning。"""
    import app.agents.nodes.events as ev

    state, _calls = _state(monkeypatch, [], [], [])
    # 覆盖 _state 内的默认 mock：显式返回 DATA_ERROR issue
    monkeypatch.setattr(
        ev, "_fetch_event_clusters", lambda *a, **k: ([], "EVENT_CLUSTER_DATA_ERROR")
    )
    out = events_node(state)

    ms = out["module_status"]["events"]
    assert ms.state == "partial"
    assert ms.error_code == "EVENT_CLUSTER_DATA_ERROR"
    assert any("EVENT_CLUSTER_DATA_ERROR" in w for w in state["runtime"].warnings)


def test_cluster_not_ready_warning_preserved(monkeypatch, _mysql_backend):
    """批次 E：真无数据 → NOT_READY warning（语义不与数据错误混淆）。"""
    import app.agents.nodes.events as ev

    state, _calls = _state(monkeypatch, [], [], [])
    monkeypatch.setattr(
        ev,
        "_fetch_event_clusters",
        lambda *a, **k: ([], "EVENT_CLUSTER_DATA_NOT_READY"),
    )
    events_node(state)
    assert any("EVENT_CLUSTER_DATA_NOT_READY" in w for w in state["runtime"].warnings)
    assert not any("EVENT_CLUSTER_DATA_ERROR" in w for w in state["runtime"].warnings)


class TestFetchEventClustersIssue:
    """_fetch_event_clusters 三态 issue 语义（批次 E）。"""

    def _patch(self, monkeypatch, repo_result, has_rows):
        import app.agents.nodes.events as ev

        class _FakeRepo:
            def list_by_company_sync(self, *a, **k):
                if isinstance(repo_result, Exception):
                    raise repo_result
                return list(repo_result)

        monkeypatch.setattr(
            "app.infrastructure.persistence.mysql.event_cluster_repository"
            ".MySQLEventClusterRepository",
            lambda: _FakeRepo(),
        )

        class _FakeConn:
            def __init__(self, first):
                self._first = first

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, *a, **k):
                return self

            def first(self):
                return self._first

        monkeypatch.setattr(
            ev,
            "_get_engine",
            lambda: type(
                "E", (), {"connect": lambda s: _FakeConn(("1",) if has_rows else None)}
            )(),
        )

    def test_repo_raises_returns_data_error(self, monkeypatch, _mysql_backend):
        self._patch(monkeypatch, RuntimeError("boom"), True)
        import app.agents.nodes.events as ev

        clusters, issue = ev._fetch_event_clusters("600518.SH")
        assert clusters == []
        assert issue == "EVENT_CLUSTER_DATA_ERROR"

    def test_rows_exist_but_unparseable_returns_data_error(
        self, monkeypatch, _mysql_backend
    ):
        self._patch(monkeypatch, [], True)
        import app.agents.nodes.events as ev

        clusters, issue = ev._fetch_event_clusters("600518.SH")
        assert clusters == []
        assert issue == "EVENT_CLUSTER_DATA_ERROR"

    def test_no_rows_returns_not_ready(self, monkeypatch, _mysql_backend):
        self._patch(monkeypatch, [], False)
        import app.agents.nodes.events as ev

        clusters, issue = ev._fetch_event_clusters("600518.SH")
        assert clusters == []
        assert issue == "EVENT_CLUSTER_DATA_NOT_READY"
