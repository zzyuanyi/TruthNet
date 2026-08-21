"""启动预热 — 真流式首块优化（2️⃣）.

冷启动 4s+ 主要来自首次 invoke 的 graph 编译/线程池与 MySQL/Neo4j/Chroma
首连——提前到 lifespan 完成，readyz 在预热完成后才返回 ready，
避免首请求承担冷启动延迟。

独立模块（不 import main）：health readyz 与 main lifespan 共用，无循环依赖。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PREWARM_COMPLETE = False


def prewarm_runtime() -> None:
    """预热真实运行路径：graph 编译 + 存储连接建立。

    预热失败不抛错（由调用方降级处理）；成功才置 _PREWARM_COMPLETE。
    """
    global _PREWARM_COMPLETE

    # 1. graph 预编译（首次编译含 import 副作用 + LangGraph 初始化）
    from app.agents.graph import create_agent_graph

    create_agent_graph().compile()

    # 2. MySQL engine 首次连接 + 一次轻量查询（预热连接池与 SQL 编译）
    from sqlalchemy import text

    from app.domain.finance._fetch import _get_engine

    with _get_engine().connect() as conn:
        conn.execute(text("SELECT 1")).scalar()

    # 3. Neo4j driver 预热（连接池建立；Lite profile 跳过）
    from app.core.config import settings

    if settings.GRAPH_BACKEND == "neo4j":
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        adapter = Neo4jEquityGraph()
        adapter._check_connection_sync()

    # 4. Chroma client 预热（client 初始化；不可用不阻塞）
    try:
        from app.infrastructure.vector.chroma.vector_store import ChromaVectorStore

        ChromaVectorStore()._get_client()
    except Exception:  # noqa: BLE001 — Chroma 不可用时首请求自行降级
        logger.warning("启动预热: Chroma client 初始化失败（降级）", exc_info=True)

    _PREWARM_COMPLETE = True


def is_prewarmed() -> bool:
    """readyz 门控：预热完成才返回 ready。"""
    return _PREWARM_COMPLETE
