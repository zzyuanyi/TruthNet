"""舆情环节联网触发测试 — Phase E 会5（舆情无公告 → 联网检索 + 来源标注）.

覆盖：
- 库内无公告且非查询异常 → 触发联网检索，web_search 证据附到 events；
- 模块状态保持诚实（NO_ANNOUNCEMENT_DATA 不变）；
- 无命中 / off 默认 → 不产生任何 web_search 证据（行为与现状一致）。
"""

import pytest

from app.agents.nodes.events import events_node
from app.agents.state import (
    AgentState,
    CompanyRef,
    ExecutionPlan,
    RuntimeState,
)
from app.application.ports.web_search_provider import SearchResult
from app.application.services import web_search_service


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


def _state(monkeypatch) -> AgentState:
    """mock 三个 fetch 全空 + 返回 state（无公告/无评级/无事件簇）。"""
    import app.agents.nodes.events as ev

    monkeypatch.setattr(ev, "_fetch_announcements", lambda *a, **k: [])
    monkeypatch.setattr(ev, "_fetch_rating_changes", lambda *a, **k: [])
    monkeypatch.setattr(ev, "_fetch_event_clusters", lambda *a, **k: ([], None))

    return {
        "user_query": "分析康美",
        "company": _company(),
        "plan": ExecutionPlan(requested_modules=["events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def _web_hits() -> list[SearchResult]:
    return [
        SearchResult(
            title="康美药业相关新闻",
            url="https://news.test/1",
            snippet="康美药业最新公告与舆情动态",
            source="mock",
        )
    ]


def test_events_no_announcement_triggers_web_search(monkeypatch, _mysql_backend):
    """无公告 → 触发联网，web_search 证据附到 events + 来源标注。"""
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: _web_hits())
    out = events_node(_state(monkeypatch))
    status = out["module_status"]["events"]
    assert status.error_code == "NO_ANNOUNCEMENT_DATA"  # 状态保持诚实
    events = out["results"].events
    web_ev = [e for e in events.evidence if e.source_type == "web_search"]
    assert web_ev, "应产生 source_type=web_search 的联网证据"
    assert web_ev[0].source_uri == "https://news.test/1"
    assert web_ev[0].source_title == "康美药业相关新闻"


def test_events_no_announcement_web_search_empty(monkeypatch, _mysql_backend):
    """无公告 + 联网无命中 → 不产生 web 证据，状态不变。"""
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: [])
    out = events_node(_state(monkeypatch))
    events = out["results"].events
    assert not [e for e in events.evidence if e.source_type == "web_search"]
    assert out["module_status"]["events"].error_code == "NO_ANNOUNCEMENT_DATA"


def test_events_off_default_no_web_search(monkeypatch, _mysql_backend):
    """off 默认：不 patch web_search → 真实服务 off 门返回 []，无 web 证据。

    （8/19 环境解耦：显式置 off，避免 .env 配置 anysearch 时真实联网。）
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    out = events_node(_state(monkeypatch))
    events = out["results"].events
    assert not [e for e in events.evidence if e.source_type == "web_search"]
