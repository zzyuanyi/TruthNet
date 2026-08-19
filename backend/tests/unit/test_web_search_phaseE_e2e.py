"""Phase E 会5 三触发点 E2E（truthnet_test）— 8/19 组长审查 A8.

覆盖（mock 后端，不污染演示库；只允许 truthnet_test）：
  Case A 公司事实/画像：库内 listing_date 为空 → 联网 → 正确解析 →
         来源标注（warning + profile 回填）；evidence 契约完整。
  Case B 库内已有事实：listing_date 非空 → Web Search 调用数 = 0。
  Case C 舆情无公告：库内无公告 → 联网补充 web evidence，但 module_status
         仍保持 NO_ANNOUNCEMENT_DATA（联网证据不得把"库内无公告"改成
         "数据库有公告"）。

统一契约断言：EvidenceRef.source_type == web_search、source_uri 存在、
source_excerpt 存在、retrieved_at 存在。
"""

import pytest

from app.application.services import web_search_service
from app.core.config import settings
from app.infrastructure.web_search.mock.provider import MockWebSearchProvider

_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql",
    reason="需要真实 MySQL（CI 默认 sqlite）",
)


@pytest.fixture(autouse=True)
def _clean_state():
    """每个测试前重置 web_search 缓存与限流状态。"""
    web_search_service._reset_for_tests()
    yield
    web_search_service._reset_for_tests()


def _dated_hits() -> list[dict]:
    return [
        {
            "title": "康美药业_百度百科",
            "url": "https://baike.baidu.com/item/康美药业",
            "snippet": "上市日期 2001-03-19，于上海证券交易所上市",
        }
    ]


def _counting_mock(hits: list[dict]):
    """可计数的 mock provider。"""

    class _CountingMock(MockWebSearchProvider):
        def __init__(self):
            super().__init__(hits)
            self.calls = 0

        async def search(self, query, max_results=None):
            self.calls += 1
            return await super().search(query, max_results=max_results)

    return _CountingMock()


@_NEED_MYSQL
def test_case_a_profile_fills_listing_date_with_source(monkeypatch):
    """Case A：库内为空 → 联网 → 正确解析 → 来源标注完整。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
    counting = _counting_mock(_dated_hits())
    monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/companies/600518.SH")
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    data = body["data"]
    assert data.get("listing_date") == "2001-03-19"
    warns = [
        w for w in body.get("warnings", []) if w.get("code") == "WEB_SEARCH_SOURCE"
    ]
    assert warns, "应有 WEB_SEARCH_SOURCE warning"
    assert "baike.baidu.com" in warns[0]["message"]
    assert counting.calls == 1, "库内为空 → 恰好一次联网"


@_NEED_MYSQL
def test_case_b_existing_listing_date_no_web_search(monkeypatch):
    """Case B：库内已有事实 → Web Search 调用数 = 0。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from app.core.config import settings as s

    # 只改 truthnet_test（conftest 已把 settings 切到测试库），用例内恢复
    url = (
        f"mysql+pymysql://{s.MYSQL_USER}:{s.MYSQL_PASSWORD}@"
        f"{s.MYSQL_HOST}:{s.MYSQL_PORT}/{s.MYSQL_DATABASE}"
    )
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.begin() as conn:
            assert str(conn.execute(text("SELECT DATABASE()")).scalar()).lower() == (
                s.MYSQL_DATABASE.lower()
            )
            conn.execute(
                text("UPDATE companies SET listing_date=:d WHERE wind_code=:c"),
                {"d": "2001-03-19", "c": "600518.SH"},
            )
        monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "mock")
        counting = _counting_mock(_dated_hits())
        monkeypatch.setattr(web_search_service, "_create_provider", lambda: counting)

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/companies/600518.SH")
        assert resp.status_code == 200
        assert resp.json()["data"].get("listing_date") == "2001-03-19"
        assert counting.calls == 0, "库内已有 listing_date → 0 次联网"
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE companies SET listing_date=NULL WHERE wind_code=:c"),
                {"c": "600518.SH"},
            )
        engine.dispose()


def test_case_c_events_no_announcement_keeps_status(monkeypatch):
    """Case C：无公告 → 联网补 web evidence，module_status 仍 NO_ANNOUNCEMENT_DATA。

    E2E 走 events_node 全链路（mock 三个 fetch 全空 + mock 联网命中）。
    全 mock、不触库 → 不加 @_NEED_MYSQL（避免 CI sqlite 下被跳过，导致 Task A
    回归无人守护）；仅 patch settings.SQL_BACKEND 使 events_node 不提前返回
    DATA_SOURCE_UNAVAILABLE（同 test_events_no_announcement.py 既有模式）。
    """
    from app.agents.nodes.events import events_node
    from app.agents.state import CompanyRef, ExecutionPlan, RuntimeState
    from app.application.ports.web_search_provider import SearchResult

    import app.agents.nodes.events as ev

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(ev, "_fetch_announcements", lambda *a, **k: [])
    monkeypatch.setattr(ev, "_fetch_rating_changes", lambda *a, **k: [])
    monkeypatch.setattr(ev, "_fetch_event_clusters", lambda *a, **k: ([], None))

    hits = [
        SearchResult(
            title="康美药业最新公告与舆情",
            url="https://news.test/1",
            snippet="康美药业 公告 舆情 最新",
            source="mock",
        )
    ]
    monkeypatch.setattr(web_search_service, "web_search", lambda *a, **k: hits)

    state = {
        "user_query": "分析康美",
        "company": CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        "plan": ExecutionPlan(requested_modules=["events"]),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }
    out = events_node(state)
    status = out["module_status"]["events"]
    assert (
        status.error_code == "NO_ANNOUNCEMENT_DATA"
    ), "联网证据不得把库内无公告改成有公告"
    events = out["results"].events
    web_ev = [e for e in events.evidence if e.source_type == "web_search"]
    assert web_ev, "应产生 source_type=web_search 证据"
    ev0 = web_ev[0]
    assert ev0.source_uri == "https://news.test/1"
    assert ev0.source_excerpt, "source_excerpt 必须存在"
    assert ev0.retrieved_at, "retrieved_at 必须存在"


def test_ambiguous_entity_no_web_search_binding(monkeypatch):
    """Section 6 安全边界：实体歧义未确认 → company_disambiguation，绝不启动
    company_fact/联网。Web Search 不得偷偷绕过 resolver 自动绑定公司。"""
    from app.agents.nodes.plan_modules import plan_modules_node
    from app.agents.state import ExecutionPlan
    from app.application.services import web_search_service

    spy = {"calls": 0}

    def _spy(*a, **k):
        spy["calls"] += 1
        return []

    monkeypatch.setattr(web_search_service, "web_search", _spy)

    state = {
        "user_query": "分析平安",
        "company": None,
        "company_candidates": [
            {"entity_id": "c1", "wind_code": "000001.SZ", "sec_name": "平安银行"},
            {"entity_id": "c2", "wind_code": "601318.SH", "sec_name": "中国平安"},
        ],
    }
    out = plan_modules_node(state)
    plan: ExecutionPlan = out["plan"]
    assert plan.intent == "company_disambiguation"
    assert "company_fact" not in (plan.requested_modules or [])
    assert spy["calls"] == 0, "实体歧义未确认 → Web Search 零调用（不得绕过 resolver）"


@_NEED_MYSQL
def test_off_regression_zero_side_effects(monkeypatch):
    """A9 硬门禁：off → 零 Provider 创建、零网络、原降级行为保持。"""
    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    created = []

    def _boom_provider():
        created.append(1)
        raise AssertionError("off 模式不得创建任何 provider")

    monkeypatch.setattr(web_search_service, "_create_provider", _boom_provider)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/companies/600518.SH")
    assert resp.status_code == 200
    # 康美药业库内 listing_date 为空 → off 下保持空，走原降级（不联网不伪造）
    assert resp.json()["data"].get("listing_date") is None
    assert created == [], "off 模式零 Provider 创建"
