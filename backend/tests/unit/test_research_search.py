"""研报语义检索（Phase D #10）单元测试.

覆盖：
- 检索工具：mock vector store 命中 → 统一输出结构（content/source/score）
- 降级路径：Chroma 异常/空结果 → 结构化过滤兜底（不报错）
- 兜底失败 → 空列表（绝不抛错）
- sync 包装在事件循环线程内安全（WS 路径）
- 关键词判定 is_research_query
"""

import asyncio

from app.application.services.research_search import (
    is_research_query,
    search_research_insights,
    search_research_insights_sync,
)


class _FakeVectorStore:
    """可编程 vector store mock：正常命中 / 抛异常 / 空结果。"""

    def __init__(self, hits=None, raise_error=False):
        self.hits = hits or []
        self.raise_error = raise_error

    async def search(self, query: str, collection: str, top_k: int = 5) -> list[dict]:
        if self.raise_error:
            raise RuntimeError("Chroma 连接断开")
        return self.hits

    async def add_documents(self, *a, **k):
        return None

    async def check_connection(self) -> bool:
        return not self.raise_error


_SEMANTIC_HITS = [
    {
        "id": "c1",
        "content": "白酒行业 2025 年动销平稳，龙头库存良性，次高端承压。",
        "metadata": {
            "title": "白酒行业 2025 年中期策略",
            "org_name": "中信证券",
            "publish_date": "2025-06-30",
            "report_id": "rp_1001",
        },
        "score": 0.92,
    },
    {
        "id": "c2",
        "content": "行业分化加剧，高端酒确定性占优。",
        "metadata": {
            "title": "食品饮料周报",
            "org_name": "华泰证券",
            "publish_date": "2025-07-01",
            "report_id": "rp_1002",
        },
        "score": 0.85,
    },
]


def test_search_returns_unified_structure():
    """mock 命中 → 统一输出（content/source_title/source_org/source_date/score）。

    #6：c2（食品饮料周报）不含核心主题"白酒"→ 被主题 Gate 过滤。
    """
    results = asyncio.run(
        search_research_insights(
            "白酒行业近期研报观点", vector_store=_FakeVectorStore(hits=_SEMANTIC_HITS)
        )
    )
    assert len(results) == 1  # 只有主题相关的 c1 通过 Gate
    r0 = results[0]
    assert r0["content"] == _SEMANTIC_HITS[0]["content"]
    assert r0["source_title"] == "白酒行业 2025 年中期策略"
    assert r0["source_org"] == "中信证券"
    assert r0["source_date"] == "2025-06-30"
    assert r0["score"] == 0.92
    assert r0["report_id"] == "rp_1001"  # #4：report_id 供可回查 Evidence


def test_default_vector_store_reused(monkeypatch):
    """未显式注入 vector_store 时，默认 ChromaVectorStore 应复用单例。"""
    from app.application.services import research_search as svc
    from app.infrastructure.vector.chroma import vector_store as chroma_mod

    created = []

    class _ReusableVectorStore(_FakeVectorStore):
        def __init__(self):
            created.append(1)
            super().__init__(hits=_SEMANTIC_HITS)

    monkeypatch.setattr(svc, "_VECTOR_STORE", None)
    monkeypatch.setattr(chroma_mod, "ChromaVectorStore", _ReusableVectorStore)

    first = asyncio.run(search_research_insights("白酒行业近期研报观点"))
    second = asyncio.run(search_research_insights("白酒行业近期研报观点"))

    assert len(created) == 1
    assert first and second


def test_relevance_gate_filters_off_topic():
    """#6：全部命中与主题无关 → 不返回跨行业内容（走 SQL 兜底/空）。

    Chroma off-topic 命中不得直接返回（化工内容绝不出现在结果中）；
    SQL 兜底结果（真库）须满足 MUST 语义：content/title/sec_name 含"白酒"。
    """
    off_topic = [
        {
            "id": "x1",
            "content": "化工行业景气度回升，纯碱价格走高。",
            "metadata": {
                "title": "化工行业周报",
                "org_name": "某证券",
                "publish_date": "2025-07-01",
            },
            "score": 0.9,
        },
    ]
    results = asyncio.run(
        search_research_insights(
            "白酒行业近期研报观点", vector_store=_FakeVectorStore(hits=off_topic)
        )
    )
    # 绝不返回 mock 的化工命中（content/title/sec_name/industry 任一不得含"化工"）
    for r in results:
        assert "化工" not in (
            (r.get("content") or "")
            + (r.get("source_title") or "")
            + (r.get("sec_name") or "")
            + (r.get("industry") or "")
        ), f"返回了化工内容: {r}"
    # 主题相关性防护（原始缺陷：白酒检索返回化工/电子研报）：
    # 结果若非空，title/sec_name/industry 不得指向明确无关行业
    # （abstract 全文命中"白酒"的公司研报（如泸州老窖）展示截断后可能
    # 不含"白酒"字——允许；但绝不能出现无关行业公司）
    _UNRELATED_KW = ("化工", "电子", "医药", "银行", "地产", "汽车", "钢铁", "煤炭")
    for r in results:
        meta_text = (
            (r.get("source_title") or "")
            + (r.get("sec_name") or "")
            + (r.get("industry") or "")
        )
        assert not any(
            kw in meta_text for kw in _UNRELATED_KW
        ), f"白酒检索返回无关行业内容: {r}"


def test_search_chroma_down_falls_back(monkeypatch):
    """Chroma 异常 → 结构化过滤兜底（不报错）。"""

    async def _fake_fallback(query, top_k, as_of=""):
        return [
            {
                "content": "兜底结果",
                "source_title": "研报A",
                "source_org": "",
                "source_date": "",
                "score": 0.0,
            }
        ]

    monkeypatch.setattr(
        "app.application.services.research_search._fallback_sql_filter",
        _fake_fallback,
    )
    results = asyncio.run(
        search_research_insights(
            "白酒行业近期研报观点",
            vector_store=_FakeVectorStore(raise_error=True),
        )
    )
    assert len(results) == 1
    assert results[0]["content"] == "兜底结果"


def test_search_empty_result_falls_back(monkeypatch):
    """Chroma 空结果 → 也走结构化过滤兜底。"""

    async def _fake_fallback(query, top_k, as_of=""):
        return []

    monkeypatch.setattr(
        "app.application.services.research_search._fallback_sql_filter",
        _fake_fallback,
    )
    results = asyncio.run(
        search_research_insights(
            "白酒行业近期研报观点", vector_store=_FakeVectorStore(hits=[])
        )
    )
    assert results == []


def test_fallback_failure_returns_empty(monkeypatch):
    """兜底也失败 → 空列表，绝不抛错。"""

    async def _broken_fallback(query, top_k):
        raise RuntimeError("DB 断开")

    monkeypatch.setattr(
        "app.application.services.research_search._fallback_sql_filter",
        _broken_fallback,
    )
    results = asyncio.run(
        search_research_insights(
            "白酒行业", vector_store=_FakeVectorStore(raise_error=True)
        )
    )
    assert results == []


def test_sync_wrapper_safe_inside_event_loop(monkeypatch):
    """WS 路径：事件循环线程内调用 sync 包装不抛 RuntimeError。

    只 mock _run_search_coro——不启动真实 Chroma/BGE 后台任务，
    避免进程退出时 atexit/futures 竞态 traceback（第三轮核查 P2）。
    """

    def _fake_search_coro(query, top_k, as_of=""):
        return [{"content": "x", "source_title": "t", "score": 0.0}]

    monkeypatch.setattr(
        "app.application.services.research_search._run_search_coro",
        _fake_search_coro,
    )

    async def _inside_event_loop():
        return search_research_insights_sync("白酒行业")

    results = asyncio.run(_inside_event_loop())
    assert isinstance(results, list)
    assert results and results[0]["content"] == "x"


def test_is_research_query():
    """关键词判定：研报/行业/评级命中；普通问题不命中。"""
    assert is_research_query("白酒行业近期研报观点")
    assert is_research_query("券商评级如何")
    assert not is_research_query("金牌家居有财务造假风险吗")
    assert not is_research_query("它的应收账款增速为什么异常")


# ── P1-4 回归：语义检索超时 → 立即 SQL 兜底（≤3s，不返回空） ────────


def test_sync_timeout_falls_back_to_sql(monkeypatch):
    """P1-4：语义检索超时（>3s）→ 立即 SQL 兜底（不等 20s、不返回空）。

    曾返回空 + 后台线程继续跑；修复后降级等待 ≈3s。
    """
    import time as _time

    from app.application.services import research_search as rs

    def _slow_semantic(query, top_k, as_of=""):
        _time.sleep(0.1)  # 模拟冷启动模型加载（慢于超时阈值）
        return []

    def _sql_result(query, top_k, as_of=""):
        return [{"content": "sql 兜底结果", "source_title": "t"}]

    monkeypatch.setattr(rs, "_SEARCH_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(rs, "_run_search_coro", _slow_semantic)
    monkeypatch.setattr(rs, "_fallback_sql_filter_sync", _sql_result)

    start = _time.monotonic()
    result = rs.search_research_insights_sync("白酒行业", top_k=5)
    elapsed = _time.monotonic() - start

    assert result and result[0]["content"] == "sql 兜底结果"
    assert elapsed < 2, f"降级应在 3s 内完成，实际 {elapsed:.2f}s"


def test_sync_timeout_sql_failure_returns_empty(monkeypatch):
    """超时后 SQL 兜底也失败 → 返回空（绝不抛异常阻塞主流程）。"""
    import time as _time

    from app.application.services import research_search as rs

    def _slow_semantic(query, top_k):
        _time.sleep(0.1)
        return []

    def _sql_broken(query, top_k):
        raise RuntimeError("sql down")

    monkeypatch.setattr(rs, "_SEARCH_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(rs, "_run_search_coro", _slow_semantic)
    monkeypatch.setattr(rs, "_fallback_sql_filter_sync", _sql_broken)

    result = rs.search_research_insights_sync("白酒行业")
    assert result == []


def test_sync_executor_is_singleton(monkeypatch):
    """executor 为模块级单例（常驻复用，不每次新建线程）."""
    from app.application.services import research_search as rs

    monkeypatch.setattr(rs, "_fallback_sql_filter_sync", lambda q, k: [])
    monkeypatch.setattr(rs, "_run_search_coro", lambda q, k: [])

    first = rs._SYNC_EXECUTOR
    rs.search_research_insights_sync("x")
    assert rs._SYNC_EXECUTOR is first, "executor 应为模块级单例"
