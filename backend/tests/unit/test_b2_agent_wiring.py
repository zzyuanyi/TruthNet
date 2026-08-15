"""B2 舆情深度分析 Agent 第二阶段 — 接线契约测试（2026-08-14）.

覆盖（fake LLM / mock 路径，禁真实 MySQL、禁真实 LLM 调用）：
- 节点级：正常 1-3 条结论 / 空结论 / LLM 失败 / 超时 / 证据越界——
  五种情形下 timeline/clusters 完整不丢、节点不崩；
- 契约：ChatDataV1 字段存在且类型正确；WS turn.completed.events 载荷含两
  字段；/events 的 impact_warnings 不丢失（映射口径断言）；三出口
  ImpactConclusion 结构同构；
- 故障：无公告、无事件簇时影响分析跳过（warning）且公告/事件链路原样。
"""

import asyncio

from app.agents.state import (
    CompanyRef,
    EventsResult,
    ExecutionPlan,
    ModuleResults,
    RuntimeState,
)
from app.api.v1.schemas.events import CausalityStep, ImpactConclusion


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


def _state() -> dict:
    return {
        "plan": ExecutionPlan(requested_modules=["events"], impact_requested=True),
        "company": _company(),
        "runtime": RuntimeState(trace_id="t", turn_id="u"),
    }


def _ann_row(object_id: str = "1", ann_dt: str = "2026-06-01") -> dict:
    return {
        "object_id": object_id,
        "ann_dt": ann_dt,
        "n_info_title": "关于股东减持的公告",
        "n_info_fcode": "010101",
        "sentiment": "negative",
        "source_uri": "http://example/ann",
    }


def _cluster(eids: tuple[str, ...] = ("ev_cluster_1",)) -> dict:
    return {
        "event_cluster_id": "c1",
        "topic": "股权变动",
        "summary": "大股东质押比例上升",
        "evidence_ids": list(eids),
        "sources": [],
        "dataset_version": "v1",
    }


def _rating(eid: str = "ev_rating_1") -> dict:
    return {
        "evidence_id": eid,
        "report_id": "r1",
        "published_at": "2026-06-05",
        "quarter": "2026Q1",
        "institution": "某证券",
        "previous_rating": "增持",
        "current_rating": "中性",
        "direction": "down",
        "source_title": "研报",
        "source_uri": None,
        "dataset_version": "v1",
    }


def _impact(
    conclusion: str = "质押上升带来控制权风险",
    statement_type: str = "inference",
    evidence_ids: tuple[str, ...] = ("ev_ann",),
) -> ImpactConclusion:
    return ImpactConclusion(
        conclusion=conclusion,
        impact_type="operation",
        direction="negative",
        severity="medium",
        evidence_ids=list(evidence_ids),
        causality_chain=[
            CausalityStep(
                text="质押比例上升",
                statement_type="observed",
                evidence_ids=list(evidence_ids),
            )
        ],
        statement_type=statement_type,
        display_tag="推断" if statement_type == "inference" else "风险推演",
    )


def _patch_node_data(monkeypatch, *, rows, clusters, rating_changes) -> None:
    """把节点数据源换成可控 dict（禁真实 MySQL）。"""
    import app.agents.nodes.events as events_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(events_mod, "_fetch_announcements", lambda *a, **k: list(rows))
    monkeypatch.setattr(
        events_mod,
        "_fetch_event_clusters",
        lambda *a, **k: (list(clusters) if clusters is not None else [], None),
    )
    monkeypatch.setattr(
        events_mod, "_fetch_rating_changes", lambda *a, **k: list(rating_changes)
    )


def _patch_impacts(monkeypatch, impacts, warnings):
    """把影响服务换成可控 async 实现（禁真实 LLM / Neo4j）。"""
    from app.application.services import events_impact_service as svc

    captured: dict = {}

    async def _fake_generate(**kwargs):
        captured["kwargs"] = kwargs
        return list(impacts), list(warnings)

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _fake_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    return captured


def _run_node(
    monkeypatch,
    *,
    rows,
    clusters,
    rating_changes,
    impacts=(),
    warnings=(),
):
    from app.agents.nodes.events import events_node

    _patch_node_data(
        monkeypatch, rows=rows, clusters=clusters, rating_changes=rating_changes
    )
    captured = _patch_impacts(monkeypatch, impacts, warnings)
    result = events_node(_state())
    return result, captured


# ── 节点级：五种情形（timeline/clusters 完整不丢、节点不崩）────


def test_node_normal_impacts(monkeypatch):
    """正常 1-3 条结论 → impacts 写入，timeline/clusters 完整，输入证据正确。"""
    impact = _impact()
    result, captured = _run_node(
        monkeypatch,
        rows=[_ann_row()],
        clusters=[_cluster()],
        rating_changes=[_rating()],
        impacts=[impact],
        warnings=[],
    )
    evt = result["results"].events
    assert isinstance(evt, EventsResult)
    assert len(evt.impacts) == 1
    assert evt.impacts[0].conclusion == "质押上升带来控制权风险"
    assert evt.impact_warnings == []
    # timeline/clusters 完整不丢
    assert len(evt.timeline) == 1
    assert evt.clusters[0]["topic"] == "股权变动"
    assert len(evt.rating_changes) == 1
    # 公告/簇/评级证据都进入输入证据集合（dict 兼容）
    timeline_eid = evt.timeline[0]["evidence_ids"][0]
    eids = captured["kwargs"]["input_evidence_ids"]
    assert timeline_eid in eids
    assert "ev_cluster_1" in eids
    assert "ev_rating_1" in eids
    # facts 文本含簇摘要与公告标题
    texts = [f["text"] for f in captured["kwargs"]["facts"]]
    assert any("大股东质押比例上升" in t for t in texts)
    assert any("关于股东减持的公告" in t for t in texts)


def test_node_empty_impacts(monkeypatch):
    """空结论 → impacts=[] + warning，timeline/clusters 完整。"""
    result, _ = _run_node(
        monkeypatch,
        rows=[_ann_row()],
        clusters=[_cluster()],
        rating_changes=[_rating()],
        impacts=[],
        warnings=["IMPACT_EMPTY: LLM 未返回影响结论"],
    )
    evt = result["results"].events
    assert evt.impacts == []
    assert any("IMPACT_EMPTY" in w for w in evt.impact_warnings)
    assert len(evt.timeline) == 1
    assert len(evt.clusters) == 1


def test_node_llm_failure(monkeypatch):
    """LLM 失败（服务返回 IMPACT_LLM_FAILED）→ 空 + warning，节点不崩。"""
    result, _ = _run_node(
        monkeypatch,
        rows=[_ann_row()],
        clusters=[_cluster()],
        rating_changes=[],
        impacts=[],
        warnings=["IMPACT_LLM_FAILED: provider down"],
    )
    evt = result["results"].events
    assert evt.impacts == []
    assert any("IMPACT_LLM_FAILED" in w for w in evt.impact_warnings)
    assert len(evt.timeline) == 1
    assert len(evt.clusters) == 1


def test_node_timeout(monkeypatch):
    """影响分析超时 → 空 + IMPACT_TIMEOUT warning，timeline/clusters 完整。"""
    import app.agents.nodes.events as events_mod
    from app.application.services import events_impact_service as svc

    monkeypatch.setattr(events_mod, "_impact_timeout", lambda: 0.02)

    async def _slow_generate(**kwargs):
        await asyncio.sleep(0.3)
        return [], []

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _slow_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    _patch_node_data(
        monkeypatch, rows=[_ann_row()], clusters=[_cluster()], rating_changes=[]
    )

    result = events_mod.events_node(_state())
    evt = result["results"].events
    assert evt.impacts == []
    assert any("IMPACT_TIMEOUT" in w for w in evt.impact_warnings)
    assert len(evt.timeline) == 1
    assert len(evt.clusters) == 1


def test_node_coroutine_exception_degraded(monkeypatch):
    """影响分析协程抛异常 → 适配层捕获 → IMPACT_ERROR warning，节点不崩。"""
    from app.application.services import events_impact_service as svc

    async def _boom(**kwargs):
        raise RuntimeError("impact service exploded")

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _boom)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    _patch_node_data(
        monkeypatch, rows=[_ann_row()], clusters=[_cluster()], rating_changes=[]
    )

    from app.agents.nodes.events import events_node

    result = events_node(_state())
    evt = result["results"].events
    assert evt.impacts == []
    assert any("IMPACT_ERROR" in w for w in evt.impact_warnings)
    assert len(evt.timeline) == 1
    assert len(evt.clusters) == 1


def test_node_evidence_out_of_bounds_input_set(monkeypatch):
    """证据越界：输入证据集合仅含公告/簇/评级证据，无编造 ID；
    结论引用非输入证据由服务层丢弃（本测试验证输入集合口径正确）。"""
    impact = _impact(evidence_ids=("ev_ann",))
    result, captured = _run_node(
        monkeypatch,
        rows=[_ann_row()],
        clusters=[_cluster()],
        rating_changes=[_rating()],
        impacts=[impact],
        warnings=["X… 引用非输入证据 1 条，已丢弃"],
    )
    evt = result["results"].events
    # 输入集合只含真实输入证据，不含编造证据
    eids = captured["kwargs"]["input_evidence_ids"]
    assert "ev_fake_999" not in eids
    timeline_eid = evt.timeline[0]["evidence_ids"][0]
    assert timeline_eid in eids
    assert "ev_cluster_1" in eids
    assert "ev_rating_1" in eids
    # 结论仍在（服务层已丢弃非法条），节点不崩
    assert len(evt.impacts) == 1


# ── 故障：无公告、无事件簇 → 影响分析跳过（warning）────


def test_node_no_announcement_no_cluster_skips_impact(monkeypatch):
    """无公告且无事件簇 → 跳过影响分析（warning），不调用 LLM，链路原样。"""
    from app.application.services import events_impact_service as svc

    called = {"n": 0}

    async def _fake_generate(**kwargs):
        called["n"] += 1
        return [], []

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _fake_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    _patch_node_data(monkeypatch, rows=[], clusters=[], rating_changes=[])

    from app.agents.nodes.events import events_node

    result = events_node(_state())
    evt = result["results"].events
    assert evt.impacts == []
    assert any("IMPACT_SKIPPED_NO_FACTS" in w for w in evt.impact_warnings)
    assert called["n"] == 0  # 未调用 LLM
    assert evt.timeline == []
    assert evt.clusters == []
    # 模块状态原样：partial/NO_ANNOUNCEMENT_DATA
    assert result["module_status"]["events"].state == "partial"
    assert result["module_status"]["events"].error_code == "NO_ANNOUNCEMENT_DATA"


def test_node_data_source_unavailable_no_crash(monkeypatch):
    """SQL_BACKEND 非 mysql → 提前返回，impacts/impact_warnings 为空默认。"""
    from app.agents.nodes.events import events_node
    from app.core.config import settings

    monkeypatch.setattr(settings, "SQL_BACKEND", "sqlite")
    result = events_node(_state())
    evt = result["results"].events
    assert evt.impacts == []
    assert evt.impact_warnings == []
    assert evt.timeline == []
    assert evt.clusters == []


# ── 契约：三出口同构 + warning 不丢失 ─────────────────────


def test_chatdata_v1_has_impact_fields():
    """ChatDataV1 字段存在且类型正确。"""
    from app.api.v1.schemas.chat import ChatDataV1

    impact = _impact()
    data = ChatDataV1(
        answer="x",
        trace_id="t",
        impact_conclusions=[impact],
        impact_warnings=["IMPACT_LLM_FAILED: x"],
    )
    assert isinstance(data.impact_conclusions, list)
    assert all(isinstance(i, ImpactConclusion) for i in data.impact_conclusions)
    assert data.impact_conclusions[0].conclusion == "质押上升带来控制权风险"
    assert isinstance(data.impact_warnings, list)
    assert data.impact_warnings == ["IMPACT_LLM_FAILED: x"]


def test_ws_events_payload_has_two_fields():
    """WS turn.completed.events 载荷含 impact_conclusions/impact_warnings。"""
    from app.application.services.ws_turn_runner import _events_payload

    impact = _impact()
    state = {
        "results": ModuleResults(
            events=EventsResult(
                impacts=[impact],
                impact_warnings=["IMPACT_EMPTY: 无结论"],
            )
        ),
    }
    payload = _events_payload(state)
    assert set(payload) == {"impact_conclusions", "impact_warnings"}
    assert payload["impact_warnings"] == ["IMPACT_EMPTY: 无结论"]
    # impact_conclusions 已 model_dump(mode="json") 为 JSON 安全 dict
    assert isinstance(payload["impact_conclusions"][0], dict)
    assert payload["impact_conclusions"][0]["conclusion"] == "质押上升带来控制权风险"
    assert payload["impact_conclusions"][0]["display_tag"] == "推断"


def test_ws_events_payload_empty_when_no_events():
    """events 模块未执行/无结果 → 空列表。"""
    from app.application.services.ws_turn_runner import _events_payload

    assert _events_payload({"results": ModuleResults()}) == {
        "impact_conclusions": [],
        "impact_warnings": [],
    }
    assert _events_payload({}) == {"impact_conclusions": [], "impact_warnings": []}


def test_events_router_exposes_impact_warnings_field():
    """/events 响应含 impact_warnings 字段（默认空，不静默丢失）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/companies/600518.SH/events")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "impact_warnings" in data


def test_three_exits_impact_structure_isomorphic():
    """Chat REST / WS / /events 三出口 ImpactConclusion 结构同构。"""
    from app.api.v1.schemas.chat import ChatDataV1
    from app.api.v1.schemas.events import EventsResponseData
    from app.application.services.ws_turn_runner import _events_payload

    impact = _impact()

    chat = ChatDataV1(answer="x", trace_id="t", impact_conclusions=[impact])
    chat_dumped = chat.model_dump(mode="json")["impact_conclusions"][0]

    ws = _events_payload(
        {"results": ModuleResults(events=EventsResult(impacts=[impact]))}
    )["impact_conclusions"][0]

    rest = EventsResponseData(wind_code="600518.SH", impact_conclusions=[impact])
    rest_dumped = rest.model_dump(mode="json")["impact_conclusions"][0]

    for d in (chat_dumped, ws, rest_dumped):
        assert d["conclusion"] == "质押上升带来控制权风险"
        assert d["impact_type"] == "operation"
        assert d["direction"] == "negative"
        assert d["severity"] == "medium"
        assert d["display_tag"] == "推断"
        assert d["evidence_ids"] == ["ev_ann"]
        assert d["causality_chain"][0]["text"] == "质押比例上升"


# ── generate_answer：舆情影响结论段渲染 ─────────────────────


def test_generate_answer_renders_impact_section(monkeypatch):
    """事件模块有 impacts → 回答追加「舆情影响结论」段（含 display_tag/因果链/证据）。"""
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _NoopProvider(),
    )
    from app.agents.nodes.generate_answer import generate_answer_node

    impact = _impact(statement_type="projection", evidence_ids=("ev_ann",))
    state = _state()
    state["claims"] = []
    state["results"] = ModuleResults(
        events=EventsResult(impacts=[impact], impact_warnings=[])
    )
    fr = generate_answer_node(state)["final_response"]
    assert "舆情影响结论" in fr.answer
    assert "风险推演" in fr.answer  # display_tag
    assert "经营" in fr.answer  # impact_type 中文标签
    assert "质押上升带来控制权风险" in fr.answer
    assert "因果链" in fr.answer
    assert "质押比例上升" in fr.answer
    assert "证据引用" in fr.answer


def test_generate_answer_no_impacts_no_section(monkeypatch):
    """无 impacts → 不渲染该段。"""
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _NoopProvider(),
    )
    from app.agents.nodes.generate_answer import generate_answer_node

    state = _state()
    state["claims"] = []
    state["results"] = ModuleResults(events=EventsResult())
    fr = generate_answer_node(state)["final_response"]
    assert "舆情影响结论" not in fr.answer


class _NoopProvider:
    """透传 provider（隔离真实 LLM）。"""

    provider_name = "noop"

    async def chat(self, messages, **kwargs):
        return messages[-1]["content"]

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self):
        return True
