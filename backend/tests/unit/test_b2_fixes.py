"""B2 舆情影响分析 — 批次 A/B/C/D 缺陷修复契约测试（2026-08-15）.

覆盖（fake LLM / mock 路径，禁真实 MySQL、禁真实 LLM 调用）：
- 批次 A：impact_requested 双条件触发收紧（6+6 正反例 + 节点门 + 渲染门 + REST/WS 空）；
- 批次 B：评级-only 路径（generate_impacts 必须被调用 + 评级证据 ID 进输入集合 +
  评级数据不足不伪造）；
- 批次 C：有界执行器 + 有界信号量（IMPACT_BUSY / 并发不无限排队 / 超时 warning /
  后续可执行 / 无 permit/线程泄漏）；
- 批次 D：股权事实失败统一降级（Neo4j 失败 / evidence_refs 回查失败 /
  公告事实仍生成结论 / warning 三出口可见 / 不允许无证据结论）。
"""

import asyncio
import threading
import time

import pytest

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


class _NoopProvider:
    """透传 provider（隔离真实 LLM）。"""

    provider_name = "noop"

    async def chat(self, messages, **kwargs):
        return messages[-1]["content"]

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self):
        return True


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


def _patch_impacts(monkeypatch, impacts=(), warnings=()):
    """把影响服务换成可控 async 实现（禁真实 LLM / Neo4j）。"""
    from app.application.services import events_impact_service as svc

    captured: dict = {"calls": 0, "kwargs": None}

    async def _fake_generate(**kwargs):
        captured["calls"] += 1
        captured["kwargs"] = kwargs
        return list(impacts), list(warnings)

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _fake_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    return captured


def _state(impact_requested: bool = True, modules=("events",)) -> dict:
    return {
        "plan": ExecutionPlan(
            requested_modules=list(modules), impact_requested=impact_requested
        ),
        "company": _company(),
        "runtime": RuntimeState(trace_id="t", turn_id="u"),
    }


# ── 批次 A：impact_requested 双条件触发收紧 ─────────────────


@pytest.mark.parametrize(
    "query,expected",
    [
        # 正例（impact_requested=True）
        ("这些公告会带来什么风险", True),
        ("最近舆情有什么影响", True),
        ("评级下调会造成什么影响", True),
        ("事件对经营有什么影响", True),
        ("立案调查对公司股权结构有什么影响", True),
        ("负面事件对融资的影响", True),
        # 反例（False，只跑 events 基础模块）
        ("康美有造假风险吗", False),
        ("最近有什么公告", False),
        ("最近发生了什么", False),
        ("给我看看康美的事件时间线", False),
        ("这家公司近期新闻", False),
        ("康美药业怎么样", False),
    ],
)
def test_impact_requested_cue_boundary(query, expected):
    """B2 批次 A §二.3：显式 cue 双条件正反例清单（6+6）。"""
    from app.agents.nodes.plan_modules import _detect_impact_requested

    assert _detect_impact_requested(query) is expected


def test_plan_modules_sets_impact_requested_for_explicit_impact():
    """明确询问影响 → plan.impact_requested=True。"""
    from app.agents.nodes.plan_modules import plan_modules_node

    state = {
        "user_query": "这些公告会带来什么风险",
        "company": _company(),
        "comparison_targets": [],
    }
    plan = plan_modules_node(state)["plan"]
    assert plan.impact_requested is True


def test_plan_modules_does_not_set_impact_for_diagnosis():
    """综合诊断（造假/风险但无事件指代）→ plan.impact_requested=False。"""
    from app.agents.nodes.plan_modules import plan_modules_node

    state = {
        "user_query": "康美有造假风险吗",
        "company": _company(),
        "comparison_targets": [],
    }
    plan = plan_modules_node(state)["plan"]
    assert plan.impact_requested is False


def test_finance_only_plan_skips_events_and_b2(monkeypatch):
    """财务问题（plan 只含 finance）→ events 跳过，generate_impacts 不调用。"""
    from app.agents.nodes.events import events_node

    _patch_node_data(monkeypatch, rows=[_ann_row()], clusters=[], rating_changes=[])
    captured = _patch_impacts(monkeypatch)
    result = events_node(_state(modules=("finance",)))
    assert result["results"].events is None
    assert result["module_status"]["events"].state == "skipped"
    assert captured["calls"] == 0


def test_events_without_impact_request_no_b2(monkeypatch):
    """events 请求但 impact_requested=False（综合诊断/宽泛）→ 不调 B2。"""
    from app.agents.nodes.events import events_node

    _patch_node_data(
        monkeypatch,
        rows=[_ann_row()],
        clusters=[_cluster()],
        rating_changes=[_rating()],
    )
    captured = _patch_impacts(monkeypatch)
    result = events_node(_state(impact_requested=False))
    evt = result["results"].events
    assert evt.impacts == []
    assert evt.impact_warnings == []  # 未请求 B2 不追加 warning
    assert captured["calls"] == 0
    assert len(evt.timeline) == 1  # 基础事件链路正常


def test_events_with_impact_request_calls_b2(monkeypatch):
    """明确询问影响（impact_requested=True）→ 调 B2，impacts 写入。"""
    from app.agents.nodes.events import events_node

    _patch_node_data(monkeypatch, rows=[_ann_row()], clusters=[], rating_changes=[])
    captured = _patch_impacts(monkeypatch, impacts=[_impact()], warnings=[])
    result = events_node(_state(impact_requested=True))
    evt = result["results"].events
    assert captured["calls"] == 1
    assert len(evt.impacts) == 1


def test_injected_impacts_not_rendered_without_impact_request(monkeypatch):
    """impacts 被手工注入但 impact_requested=False → 不渲染舆情影响段。"""
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _NoopProvider(),
    )
    from app.agents.nodes.generate_answer import generate_answer_node

    impact = _impact()
    state = _state(impact_requested=False)
    state["claims"] = []
    state["results"] = ModuleResults(events=EventsResult(impacts=[impact]))
    fr = generate_answer_node(state)["final_response"]
    assert "舆情影响结论" not in fr.answer


def test_rest_ws_unrequested_b2_empty_arrays():
    """REST/WS 未请求 B2 → 返回空数组（schema 默认 + WS 空载荷）。"""
    from app.api.v1.schemas.events import EventsResponseData
    from app.application.services.ws_turn_runner import _events_payload

    ws = _events_payload({"results": ModuleResults(events=EventsResult())})
    assert ws == {"impact_conclusions": [], "impact_warnings": []}

    rest = EventsResponseData(wind_code="600518.SH")
    assert rest.impact_conclusions == []
    assert rest.impact_warnings == []


# ── 批次 B：评级-only 路径 ─────────────────────────────────


def test_rating_only_path_calls_generate_impacts(monkeypatch):
    """无公告、无事件簇、有一条评级变化 → generate_impacts 被调用 + 评级证据 ID。"""
    from app.agents.nodes.events import events_node

    _patch_node_data(monkeypatch, rows=[], clusters=[], rating_changes=[_rating()])
    captured = _patch_impacts(monkeypatch)
    result = events_node(_state(impact_requested=True))
    evt = result["results"].events
    assert captured["calls"] == 1
    assert "ev_rating_1" in captured["kwargs"]["input_evidence_ids"]
    assert evt.impacts == []


def test_rating_only_insufficient_evidence_skips_impact(monkeypatch):
    """评级无 evidence_id（数据不足）→ 空结论 + warning，不伪造（不调 LLM）。"""
    from app.agents.nodes.events import events_node

    _patch_node_data(
        monkeypatch, rows=[], clusters=[], rating_changes=[_rating(eid="")]
    )
    captured = _patch_impacts(monkeypatch)
    result = events_node(_state(impact_requested=True))
    evt = result["results"].events
    assert evt.impacts == []
    assert captured["calls"] == 0
    assert any("IMPACT_SKIPPED_NO_FACTS" in w for w in evt.impact_warnings)


# ── 批次 C：超时与并发 ─────────────────────────────────────


def _reset_impact_runtime(events_mod) -> None:
    """重置惰性执行器/信号量（测试隔离）；不阻塞地关闭旧执行器。"""
    ex = events_mod._IMPACT_EXECUTOR
    events_mod._IMPACT_EXECUTOR = None
    events_mod._IMPACT_SEMAPHORE = None
    if ex is not None:
        ex.shutdown(wait=False, cancel_futures=False)


def test_impact_busy_when_inflight_full(monkeypatch):
    """在途数满 → 快速返回 IMPACT_BUSY；释放后后续请求仍可执行。"""
    import app.agents.nodes.events as events_mod
    from app.application.services import events_impact_service as svc
    from app.core.config import settings

    monkeypatch.setattr(settings, "EVENT_IMPACT_MAX_WORKERS", 1)
    monkeypatch.setattr(settings, "EVENT_IMPACT_MAX_INFLIGHT", 1)
    _reset_impact_runtime(events_mod)
    monkeypatch.setattr(events_mod, "_impact_timeout", lambda: 5.0)

    started = threading.Event()
    release = threading.Event()

    async def _blocking_generate(**kwargs):
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return [], []

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _blocking_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)

    company = _company()
    first_outcome: dict = {}

    def _worker():
        first_outcome["r"] = events_mod._run_event_impacts(
            company=company, clusters=[_cluster()], timeline=[], rating_changes=[]
        )

    t = threading.Thread(target=_worker)
    t.start()
    try:
        assert started.wait(timeout=5.0), "第一个任务未在期限内开始"

        # 第二个任务：在途数已满 → 快速返回 IMPACT_BUSY（不排队）
        impacts, warnings = events_mod._run_event_impacts(
            company=company, clusters=[_cluster()], timeline=[], rating_changes=[]
        )
        assert impacts == []
        assert any("IMPACT_BUSY" in w for w in warnings)
    finally:
        release.set()
        t.join(timeout=5.0)
        _reset_impact_runtime(events_mod)

    # 第一个任务正常完成（空结论，无额外 warning）
    assert first_outcome["r"][0] == []
    assert first_outcome["r"][1] == []

    # 后续请求仍可执行（重新注入 fast generate 验证恢复）
    async def _fast_generate(**kwargs):
        return [], ["IMPACT_EMPTY: 无结论"]

    monkeypatch.setattr(svc, "generate_impacts", _fast_generate)
    _reset_impact_runtime(events_mod)
    impacts2, warnings2 = events_mod._run_event_impacts(
        company=company, clusters=[_cluster()], timeline=[], rating_changes=[]
    )
    assert impacts2 == []
    assert any("IMPACT_EMPTY" in w for w in warnings2)
    _reset_impact_runtime(events_mod)


def test_concurrent_tasks_do_not_queue_indefinitely(monkeypatch):
    """两任务并发：均实际进入 generate_impacts，超时返回明确 warning，无 permit 泄漏。"""
    import app.agents.nodes.events as events_mod
    from app.application.services import events_impact_service as svc
    from app.core.config import settings

    monkeypatch.setattr(settings, "EVENT_IMPACT_MAX_WORKERS", 2)
    monkeypatch.setattr(settings, "EVENT_IMPACT_MAX_INFLIGHT", 2)
    _reset_impact_runtime(events_mod)
    monkeypatch.setattr(events_mod, "_impact_timeout", lambda: 0.1)

    lock = threading.Lock()
    started = {"n": 0}
    finished = {"n": 0}

    async def _slow_generate(**kwargs):
        with lock:
            started["n"] += 1
        await asyncio.sleep(0.4)
        with lock:
            finished["n"] += 1
        return [], []

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), []

    monkeypatch.setattr(svc, "generate_impacts", _slow_generate)
    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)

    company = _company()
    outcomes: dict = {}

    def _worker(i):
        outcomes[i] = events_mod._run_event_impacts(
            company=company, clusters=[_cluster()], timeline=[], rating_changes=[]
        )

    try:
        t1 = threading.Thread(target=_worker, args=(0,))
        t2 = threading.Thread(target=_worker, args=(1,))
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        # 第二个任务不因第一个阻塞而无期限排队：两者都进入了 generate_impacts
        assert started["n"] == 2
        for i in (0, 1):
            assert outcomes[i][0] == []
            assert any("IMPACT_TIMEOUT" in w for w in outcomes[i][1])

        # 等待底层协程真正结束（超时后任务仍在 worker 线程内跑完）
        deadline = time.monotonic() + 5.0
        while finished["n"] < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert finished["n"] == 2

        # 无 permit 泄漏：信号量恢复到 in-flight 上限。
        # 注意：release 经 future.add_done_callback 触发，发生在 asyncio.run
        # 完全退出之后，晚于协程内部 finished 自增——存在事件循环清理时间窗，
        # 必须轮询等待恢复，不能立即断言（8/17 CI macos 偶发 flaky 修复）。
        sem = events_mod._impact_semaphore()
        deadline = time.monotonic() + 5.0
        while sem._value < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sem._value == 2

        # 无 worker 线程泄漏：shutdown(wait=True) 后执行器 worker 线程全部退出
        ex = events_mod._IMPACT_EXECUTOR
        ex.shutdown(wait=True, cancel_futures=False)
        assert all(not t.is_alive() for t in ex._threads)
    finally:
        _reset_impact_runtime(events_mod)


# ── 批次 D：统一股权事实失败降级 ───────────────────────────


@pytest.mark.asyncio
async def test_equity_facts_skip_neo4j_when_graph_backend_is_networkx(monkeypatch):
    """Lite/NetworkX 配置不得暗中连接 Neo4j。"""
    from app.application.services import events_impact_service as svc

    monkeypatch.setattr(svc.settings, "GRAPH_BACKEND", "networkx")
    facts, eids, warnings = await svc.build_equity_impact_facts("600518.SH", "gv")
    assert facts == []
    assert eids == set()
    assert warnings == [
        "IMPACT_EQUITY_FACTS_SKIPPED: "
        "GRAPH_BACKEND=networkx，未使用 Neo4j 股权影响事实"
    ]


@pytest.mark.asyncio
async def test_equity_neo4j_failure_returns_warning(monkeypatch):
    """Neo4j 查询失败 → 空事实 + IMPACT_EQUITY_FACTS_FAILED warning。"""
    from app.application.services import events_impact_service as svc
    from app.infrastructure.graph.neo4j import equity_graph as eg_mod

    monkeypatch.setattr(svc.settings, "GRAPH_BACKEND", "neo4j")

    class _FailingGraph:
        async def get_graph(self, *a, **k):
            raise RuntimeError("neo4j down")

    monkeypatch.setattr(eg_mod, "Neo4jEquityGraph", _FailingGraph)

    facts, eids, warnings = await svc.build_equity_impact_facts("600518.SH", "gv")
    assert facts == []
    assert eids == set()
    assert any("IMPACT_EQUITY_FACTS_FAILED" in w and "Neo4j" in w for w in warnings)


@pytest.mark.asyncio
async def test_equity_evidence_refs_failure_returns_warning(monkeypatch):
    """evidence_refs 回查失败 → 空股权事实 + IMPACT_EQUITY_FACTS_FAILED warning。"""
    from app.application.services import events_impact_service as svc
    from app.domain.equity.models import EquityEdge, EquityGraph, EquityNode
    from app.infrastructure.graph.neo4j import equity_graph as eg_mod

    monkeypatch.setattr(svc.settings, "GRAPH_BACKEND", "neo4j")

    edge = EquityEdge(
        source="A",
        target="B",
        ownership_pct=25.0,
        relationship_id="rel_1",
        report_period="2025-12-31",
    )
    graph = EquityGraph(
        company_id="B",
        nodes=[
            EquityNode(id="A", label="股东A", type="person"),
            EquityNode(id="B", label="公司B", type="company"),
        ],
        edges=[edge],
    )

    class _FakeGraph:
        async def get_graph(self, *a, **k):
            return graph

    monkeypatch.setattr(eg_mod, "Neo4jEquityGraph", _FakeGraph)

    def _boom_engine():
        raise RuntimeError("evidence_refs 回查失败")

    monkeypatch.setattr(svc, "_get_engine", _boom_engine)

    facts, eids, warnings = await svc.build_equity_impact_facts("600518.SH", "gv")
    assert facts == []
    assert eids == set()
    assert any("IMPACT_EQUITY_FACTS_FAILED" in w and "回查失败" in w for w in warnings)


def test_announcement_facts_generate_impacts_despite_equity_failure(monkeypatch):
    """股权事实失败（返回 warning）→ 公告事实仍生成影响结论，warning 并入。"""
    from app.agents.nodes.events import events_node
    from app.application.services import events_impact_service as svc

    _patch_node_data(monkeypatch, rows=[_ann_row()], clusters=[], rating_changes=[])

    captured: dict = {"kwargs": None}

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), ["IMPACT_EQUITY_FACTS_FAILED: Neo4j 查询失败: boom"]

    async def _fake_generate(**kwargs):
        captured["kwargs"] = kwargs
        return [_impact(evidence_ids=tuple(kwargs["input_evidence_ids"]))], []

    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    monkeypatch.setattr(svc, "generate_impacts", _fake_generate)

    result = events_node(_state(impact_requested=True))
    evt = result["results"].events
    # 公告事实仍进入 LLM 输入（不因股权失败被阻断）
    texts = [f["text"] for f in captured["kwargs"]["facts"]]
    assert any("关于股东减持的公告" in t for t in texts)
    # 影响结论正常生成
    assert len(evt.impacts) == 1
    # 股权失败 warning 并入 impact_warnings
    assert any("IMPACT_EQUITY_FACTS_FAILED" in w for w in evt.impact_warnings)


def test_equity_warning_visible_three_exits(monkeypatch):
    """IMPACT_EQUITY_FACTS_FAILED 在 Chat / WS / REST 三出口一致可见。"""
    from app.api.v1.schemas.chat import ChatDataV1
    from app.api.v1.schemas.events import EventsResponseData
    from app.application.services.ws_turn_runner import _events_payload

    warning = "IMPACT_EQUITY_FACTS_FAILED: Neo4j 查询失败: boom"
    events_result = EventsResult(impacts=[], impact_warnings=[warning])

    # Chat 出口：ChatDataV1.impact_warnings
    chat = ChatDataV1(answer="x", trace_id="t", impact_warnings=[warning])
    assert chat.impact_warnings == [warning]

    # WS 出口：_events_payload 从 EventsResult.impact_warnings 透出
    ws = _events_payload({"results": ModuleResults(events=events_result)})
    assert ws["impact_warnings"] == [warning]

    # REST 出口：EventsResponseData.impact_warnings 字段承载同一 warning
    rest = EventsResponseData(wind_code="600518.SH", impact_warnings=[warning])
    assert rest.impact_warnings == [warning]


def test_rest_equity_warning_visible(monkeypatch):
    """REST /events include_impacts=true 时股权失败 warning 进入 impact_warnings。"""
    import app.api.v1.routers.events as events_router
    from app.application.services import events_impact_service as svc
    from app.application.services import provenance_service as prov
    from app.core.config import settings

    class _FakeCompany:
        wind_code = "600518.SH"
        sec_name = "康美药业"

    class _FakeResolver:
        async def resolve(self, code):
            return _FakeCompany()

    class _FakeProvenance:
        def create_analysis_run(self, *a, **k):
            return None

        def persist_evidence(self, *a, **k):
            return None

    monkeypatch.setattr(events_router, "CompanyResolver", _FakeResolver)
    monkeypatch.setattr(prov, "ProvenanceService", _FakeProvenance)
    monkeypatch.setattr(settings, "SQL_BACKEND", "mysql")
    monkeypatch.setattr(events_router, "_fetch_event_clusters", lambda *a, **k: [])
    monkeypatch.setattr(
        events_router,
        "_fetch_announcements",
        lambda *a, **k: [
            {
                "object_id": "1",
                "ann_dt": "2026-06-01",
                "n_info_title": "公告标题",
                "n_info_fcode": "010101",
                "sentiment": "negative",
                "source_uri": "http://x",
            }
        ],
    )
    monkeypatch.setattr(events_router, "_fetch_rating_changes", lambda *a, **k: [])

    async def _fake_equity(wind_code, graph_version=""):
        return [], set(), ["IMPACT_EQUITY_FACTS_FAILED: Neo4j 查询失败: boom"]

    async def _fake_generate(**kwargs):
        return [], []

    monkeypatch.setattr(svc, "build_equity_impact_facts", _fake_equity)
    monkeypatch.setattr(svc, "generate_impacts", _fake_generate)

    resp = asyncio.run(
        events_router.get_company_events(
            code="600518.SH", months=36, include_impacts=True
        )
    )
    assert any("IMPACT_EQUITY_FACTS_FAILED" in w for w in resp.data.impact_warnings)
    assert resp.data.impact_conclusions == []


@pytest.mark.asyncio
async def test_no_evidence_conclusion_not_generated(monkeypatch):
    """不允许生成无证据影响结论：空输入证据时结论全部丢弃 + warning。"""
    from app.application.services import events_impact_service as svc
    from app.application.services.events_impact_service import _ImpactsOutput

    class _FakeProvider:
        async def structured_chat(self, messages, output_schema):
            return _ImpactsOutput(
                conclusions=[
                    {
                        "conclusion": "无证据伪造结论",
                        "impact_type": "operation",
                        "direction": "negative",
                        "severity": "high",
                        "evidence_ids": [],  # 无证据
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
        # 模拟"评级数据不足"：只有一条无证据的事实，输入证据集为空
        facts=[{"text": "评级变更[]: →", "evidence_ids": []}],
        input_evidence_ids=set(),
    )
    assert conclusions == []
    assert any("未引用任何输入证据" in w for w in warnings)
