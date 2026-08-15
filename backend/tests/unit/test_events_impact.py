"""B2 舆情影响分析（⑧ 第一阶段）— 2026-08-11.

覆盖：
- 事实构造：build_impact_facts（事件簇/公告/评级 → 输入证据集合）；
- 证据 ⊆ 输入集合程序校验：非输入证据单条丢弃 + warning；
- statement_type 合法化 + display_tag 后端确定性渲染；
- LLM mock/空结论 → 空列表 + warning（降级，不 500）；
- LLM 失败 → 空列表 + warning；
- 路由 include_impacts=true 时响应含 impact_conclusions 字段
  （mock LLM 下为空 + warning，基础事件仍 200）。
"""

import pytest

from app.api.v1.schemas.events import EventCluster, RatingChange, TimelineEvent


def _cluster(eids=("ev_ann_1",)) -> EventCluster:
    return EventCluster(
        event_cluster_id="c1",
        topic="股权变动",
        summary="大股东质押比例上升",
        evidence_ids=list(eids),
    )


def _timeline(eid="ev_ann_2") -> TimelineEvent:
    return TimelineEvent(
        date="2026-06-01",
        title="关于股东减持的公告",
        sentiment="negative",
        evidence_ids=[eid],
    )


def _rating(eid="ev_ann_3") -> RatingChange:
    return RatingChange(
        date="2026-06-05",
        org_name="某证券",
        prev_rating="增持",
        new_rating="中性",
        change="down",
        evidence_id=eid,
    )


def test_build_facts_collects_evidence_ids():
    from app.application.services.events_impact_service import build_impact_facts

    facts, eids = build_impact_facts(
        event_clusters=[_cluster()],
        timeline=[_timeline()],
        rating_changes=[_rating()],
    )
    assert eids == {"ev_ann_1", "ev_ann_2", "ev_ann_3"}
    assert len(facts) == 3
    assert all("text" in f and "evidence_ids" in f for f in facts)


def test_build_facts_from_dicts():
    """B2 第二阶段：Agent 节点产出 dict（而非 REST schema 对象）也能正确构造 facts。

    字段名差异（institution/previous_rating/current_rating/direction/
    published_at vs REST 的 org_name/prev_rating/new_rating/change/date）
    由 _pick 双通道兼容，且 clusters/timeline 携带 evidence_ids。
    """
    from app.application.services.events_impact_service import build_impact_facts

    facts, eids = build_impact_facts(
        event_clusters=[
            {
                "topic": "股权变动",
                "summary": "质押上升",
                "evidence_ids": ["c1"],
            }
        ],
        timeline=[
            {
                "date": "2026-06-01",
                "title": "减持公告",
                "sentiment": "negative",
                "evidence_ids": ["t1"],
            }
        ],
        rating_changes=[
            {
                "published_at": "2026-06-05",
                "institution": "某证券",
                "previous_rating": "增持",
                "current_rating": "中性",
                "direction": "down",
                "evidence_id": "r1",
            }
        ],
    )
    assert eids == {"c1", "t1", "r1"}
    assert len(facts) == 3
    texts = [f["text"] for f in facts]
    assert any("股权变动" in t and "质押上升" in t for t in texts)
    assert any("减持公告" in t for t in texts)
    assert any("某证券" in t and "增持→中性" in t for t in texts)


@pytest.mark.asyncio
async def test_mock_backend_returns_empty_with_warning(monkeypatch):
    """LLM_BACKEND=mock/空 → 不调用 LLM，返回空 + 可恢复 warning。"""
    from app.application.services.events_impact_service import generate_impacts
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    conclusions, warnings = await generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert conclusions == []
    assert any("IMPACT_LLM_UNAVAILABLE" in w for w in warnings)


@pytest.mark.asyncio
async def test_invalid_evidence_dropped(monkeypatch):
    """引用非输入证据的结论被丢弃 + warning（程序化校验）。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    called = {}

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            called["n"] = True
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "质押上升可能带来控制权风险",
                        "impact_type": "equity_structure",
                        "direction": "negative",
                        "severity": "medium",
                        "evidence_ids": ["ev_ann_1"],  # 在输入集合内
                        "causality_chain": [
                            {
                                "text": "质押比例上升",
                                "statement_type": "observed",
                                "evidence_ids": ["ev_ann_1"],
                            },
                        ],
                        "statement_type": "inference",
                    },
                    {
                        "conclusion": "编造证据的结论",
                        "evidence_ids": ["ev_fake_999"],  # 非输入证据
                        "statement_type": "projection",
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["ev_ann_1"]}],
        input_evidence_ids={"ev_ann_1"},
    )
    assert called.get("n") is True
    assert len(conclusions) == 1  # 无效结论被丢弃
    c = conclusions[0]
    assert c.evidence_ids == ["ev_ann_1"]
    assert c.statement_type == "inference"
    assert c.display_tag == "推断"  # 后端确定性渲染
    assert c.causality_chain[0].statement_type == "observed"
    assert any("已丢弃" in w for w in warnings)


@pytest.mark.asyncio
async def test_llm_failure_degrades_gracefully(monkeypatch):
    """LLM 抛异常 → 空 + warning（基础事件保持 200）。"""
    from app.application.services import events_impact_service as svc

    class _FailingProvider:
        async def structured_chat(self, messages, output_schema):
            raise RuntimeError("provider down")

    def _fake_provider():
        return _FailingProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert conclusions == []
    assert any("IMPACT_LLM_FAILED" in w for w in warnings)


@pytest.mark.asyncio
async def test_empty_evidence_conclusion_dropped(monkeypatch):
    """v3.4：未引用任何输入证据的结论被丢弃 + warning。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "无证据支撑的结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "high",
                        "evidence_ids": [],  # 空证据 → 丢弃
                        "statement_type": "projection",
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert conclusions == []
    assert any("未引用任何输入证据" in w for w in warnings)


@pytest.mark.asyncio
async def test_invalid_enum_conclusion_dropped(monkeypatch):
    """v3.4：枚举字段非法（impact_type/direction/severity）→ 单条丢弃，不炸整体。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "合法结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "medium",
                        "evidence_ids": ["e1"],
                        "statement_type": "inference",
                    },
                    {
                        "conclusion": "非法 impact_type 的结论",
                        "impact_type": "money_laundering",  # 非白名单
                        "direction": "negative",
                        "severity": "high",
                        "evidence_ids": ["e1"],
                        "statement_type": "projection",
                    },
                    {
                        "conclusion": "非法 severity 的结论",
                        "impact_type": "financing",
                        "direction": "neutral",
                        "severity": "catastrophic",  # 非白名单
                        "evidence_ids": ["e1"],
                        "statement_type": "inference",
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert len(conclusions) == 1  # 非法两条被丢弃，合法一条保留
    assert conclusions[0].impact_type == "operation"
    assert sum("枚举字段非法" in w for w in warnings) == 2


@pytest.mark.asyncio
async def test_cache_hit_and_singleflight(monkeypatch):
    """v3.4：同键并发共享一次 LLM 调用（singleflight）+ 缓存命中不再调用。"""
    import asyncio

    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    calls = {"n": 0}

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            calls["n"] += 1
            await asyncio.sleep(0.02)  # 模拟慢 LLM，暴露并发窗口
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "并发共享结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "medium",
                        "evidence_ids": ["e1"],
                        "statement_type": "inference",
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()

    facts = [{"text": "f1", "evidence_ids": ["e1"]}]
    kwargs = dict(
        wind_code="600518.SH",
        sec_name="康美药业",
        months=36,
        facts=facts,
        input_evidence_ids={"e1"},
    )
    # 并发同键 → singleflight 只调一次
    r1, r2 = await asyncio.gather(
        svc.generate_impacts(**kwargs),
        svc.generate_impacts(**kwargs),
    )
    assert calls["n"] == 1
    assert len(r1[0]) == 1 and len(r2[0]) == 1
    # 缓存命中 → 不再调用
    r3 = await svc.generate_impacts(**kwargs)
    assert calls["n"] == 1
    assert len(r3[0]) == 1
    # 键变化（months）→ 重新调用
    await svc.generate_impacts(**{**kwargs, "months": 12})
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_invalid_statement_type_dropped(monkeypatch):
    """v3.5：statement_type 非法不再静默改写——丢弃该结论 + warning。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "非法 statement_type 的结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "medium",
                        "evidence_ids": ["e1"],
                        "statement_type": "happened",  # 非白名单
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert conclusions == []
    assert any("statement_type 非法" in w for w in warnings)


@pytest.mark.asyncio
async def test_invalid_causality_step_dropped(monkeypatch):
    """v3.5：因果步骤引用非输入证据/无证据 → 丢弃该步骤 + warning。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "含合法与非法步骤的结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "medium",
                        "evidence_ids": ["e1"],
                        "causality_chain": [
                            {
                                "text": "合法步骤",
                                "statement_type": "observed",
                                "evidence_ids": ["e1"],
                            },
                            {
                                "text": "引用伪造证据的步骤",
                                "statement_type": "observed",
                                "evidence_ids": ["ev_fake_9"],
                            },
                            {
                                "text": "无证据步骤",
                                "statement_type": "observed",
                                "evidence_ids": [],
                            },
                        ],
                        "statement_type": "inference",
                    },
                ]
            )

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    conclusions, warnings = await svc.generate_impacts(
        wind_code="600518.SH",
        sec_name="康美药业",
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    assert len(conclusions) == 1  # 结论保留，非法步骤被丢弃
    assert [s.text for s in conclusions[0].causality_chain] == ["合法步骤"]
    assert sum("已丢弃该步骤" in w for w in warnings) == 2


@pytest.mark.asyncio
async def test_cache_ttl_expiry(monkeypatch):
    """v3.5：成功缓存 TTL——过期后重新调用 LLM。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    calls = {"n": 0}

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            calls["n"] += 1
            return _ImpactsOutput(conclusions=[])

    def _fake_provider():
        return _FakeProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    kwargs = dict(
        wind_code="600518.SH",
        sec_name="康美药业",
        months=36,
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    await svc.generate_impacts(**kwargs)
    await svc.generate_impacts(**kwargs)
    assert calls["n"] == 1  # TTL 内命中
    # Windows time.monotonic() 分辨率 ~15.6ms，连续调用 diff 可能恰为 0.0，
    # TTL=0 时 `0.0 <= 0` 会误命中——用负值强制过期
    svc._CACHE_TTL = -1
    await svc.generate_impacts(**kwargs)
    assert calls["n"] == 2  # 过期后重算
    svc._CACHE_TTL = 300  # 恢复（模块常量，避免污染后续测试）


@pytest.mark.asyncio
async def test_llm_failure_not_cached(monkeypatch):
    """v3.5：LLM 失败不缓存——连续两次调用都走 LLM。"""
    import asyncio

    from app.application.services import events_impact_service as svc

    calls = {"n": 0}

    class _FailingProvider:
        async def structured_chat(self, messages, output_schema):
            calls["n"] += 1
            raise RuntimeError("provider down")

    def _fake_provider():
        return _FailingProvider()

    from app.infrastructure.llm import factory as llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_provider", _fake_provider)
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")
    svc._impact_cache.clear()
    svc._impact_flights.clear()
    kwargs = dict(
        wind_code="600518.SH",
        sec_name="康美药业",
        months=36,
        facts=[{"text": "f1", "evidence_ids": ["e1"]}],
        input_evidence_ids={"e1"},
    )
    r1, r2 = await asyncio.gather(
        svc.generate_impacts(**kwargs), svc.generate_impacts(**kwargs)
    )
    assert calls["n"] == 1  # singleflight 并发只调一次
    r3 = await svc.generate_impacts(**kwargs)  # 失败不缓存 → 再次调用
    assert calls["n"] == 2
    assert any("IMPACT_LLM_FAILED" in w for w in r3[1])


@pytest.mark.skipif(
    __import__("app.core.config", fromlist=["settings"]).settings.SQL_BACKEND
    != "mysql",
    reason="需 mysql 模式真库事件数据",
)
def test_router_include_impacts_true(monkeypatch):
    """v3.5：include_impacts=true 真实路由——mock LLM 引用输入证据渲染结论。"""
    import json
    import re

    from fastapi.testclient import TestClient

    from app.application.services.events_impact_service import _ImpactsOutput
    from app.infrastructure.llm import factory as llm_factory

    class _EchoProvider:
        async def structured_chat(self, messages, output_schema):
            user = messages[-1]["content"]
            m = re.search(r"可用证据 ID：(\[.*?\])", user)
            ids = json.loads(m.group(1)) if m else []
            return _ImpactsOutput(
                conclusions=(
                    [
                        {
                            "conclusion": "真实路由影响结论",
                            "impact_type": "operation",
                            "direction": "negative",
                            "severity": "medium",
                            "evidence_ids": [ids[0]] if ids else [],
                            "causality_chain": [],
                            "statement_type": "inference",
                        }
                    ]
                    if ids
                    else []
                )
            )

    monkeypatch.setattr(llm_factory, "create_llm_provider", lambda: _EchoProvider())
    monkeypatch.setattr("app.core.config.settings.LLM_BACKEND", "deepseek")

    from app.application.services import events_impact_service as svc

    svc._impact_cache.clear()
    svc._impact_flights.clear()
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    resp = client.get("/api/v1/companies/600518.SH/events?include_impacts=true")
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()["data"]
    assert "impact_conclusions" in data
    # 康美测试库有事件数据 + 可用证据 ID → 应渲染出 mock 结论
    if data.get("announcements_available"):
        assert data["impact_conclusions"], "应有影响结论（mock 引用输入证据）"
        assert data["impact_conclusions"][0]["display_tag"] == "推断"


def test_router_include_impacts_default_off():
    """include_impacts 默认 false（不触发 LLM）；响应结构含 impact_conclusions。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/companies/600518.SH/events")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "impact_conclusions" in data  # 字段存在（默认空）
