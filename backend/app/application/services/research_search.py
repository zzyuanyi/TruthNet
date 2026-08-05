"""研报/公告语义检索工具 — Phase D #10.

基于 VectorStorePort.search（Chroma 集合 research_report_chunks，203,058 chunks）
封装检索；Chroma 不可用或空结果 → research_reports 表结构化关键词过滤兜底
（V12 §10.10），绝不报错阻塞主流程。

graph 节点是同步 def，通过 search_research_insights_sync 调用（独立线程
asyncio.run，REST/WS 双路径安全，与 llm_sync 同模式）。
"""

import asyncio
import concurrent.futures
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_report_chunks"
_SEARCH_KEYWORDS = ("研报", "观点", "行业", "机构", "分析师", "评级", "近期")


def _semantic_to_insight(hit: dict) -> dict:
    """Chroma 命中 → 统一输出结构（content/source/score）。"""
    meta = hit.get("metadata") or {}
    return {
        "content": (hit.get("content") or "")[:300],
        "source_title": meta.get("title", ""),
        "source_org": meta.get("org_name", ""),
        "source_date": str(meta.get("publish_date", "") or ""),
        "score": round(float(hit.get("score", 0.0)), 3),
    }


_STOP_WORDS = frozenset(
    {"什么", "如何", "为什么", "怎么样", "是否", "多少", "哪些", "最近"}
)


def _split_keywords(query: str) -> list[str]:
    """问题 → 过滤关键词（去停用词 + 2-gram 切分）。

    整段连续汉字（如"白酒行业"）直接 LIKE 匹配不到标题，拆出 2-gram
    （白酒/酒行/行业）提高召回；按出现顺序去重返回。
    """
    import re

    tokens = re.findall(r"[一-鿿]{2,}|[A-Za-z]{2,}", query)
    kws: list[str] = []
    for t in tokens:
        if t in _STOP_WORDS or t in kws:
            continue
        kws.append(t)
        if len(t) >= 4:
            for i in range(len(t) - 1):
                gram = t[i : i + 2]
                if gram not in _STOP_WORDS and gram not in kws:
                    kws.append(gram)
    return kws


async def search_research_insights(
    query: str, top_k: int = 5, vector_store=None
) -> list[dict]:
    """语义检索研报观点；Chroma 断开/空结果 → 结构化过滤兜底（不报错）。

    Args:
        query: 用户问题（如"白酒行业近期研报观点"）。
        top_k: 返回条数。
        vector_store: 可注入 mock（测试用）；None 用真实 ChromaVectorStore。
    """
    try:
        if vector_store is None:
            from app.infrastructure.vector.chroma.vector_store import (
                ChromaVectorStore,
            )

            vector_store = ChromaVectorStore()
        hits = await vector_store.search(query, collection=COLLECTION_NAME, top_k=top_k)
    except Exception:  # noqa: BLE001 — Chroma 任何异常走兜底
        logger.warning(
            "research_search: Chroma 检索异常，走结构化过滤兜底", exc_info=True
        )
        hits = []

    if hits:
        return [_semantic_to_insight(h) for h in hits]
    try:
        return await _fallback_sql_filter(query, top_k)
    except Exception:  # noqa: BLE001 — 兜底异常也返回空，绝不报错
        logger.warning("research_search: 兜底检索异常，返回空", exc_info=True)
        return []


def _fallback_sql_filter_sync(query: str, top_k: int) -> list[dict]:
    """结构化过滤兜底（V12 §10.10）同步核心：research_reports 关键词 LIKE。

    同步实现供 async 入口（to_thread）与同步超时降级共用。
    """
    keywords = _split_keywords(query)
    if not keywords:
        return []
    try:
        from sqlalchemy import text

        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        rows = []
        with engine.connect() as conn:
            for kw in keywords:
                if len(rows) >= top_k:
                    break
                rs = conn.execute(
                    text(
                        "SELECT title, abstract, org_name, sec_name, publish_date "
                        "FROM research_reports "
                        "WHERE is_latest = 1 AND (title LIKE :kw OR abstract LIKE :kw) "
                        "ORDER BY publish_date DESC LIMIT :lim"
                    ),
                    {"kw": f"%{kw}%", "lim": top_k - len(rows)},
                )
                for r in rs:
                    rows.append(
                        {
                            "content": (r.abstract or "")[:300]
                            or (r.title or "")[:300],
                            "source_title": r.title or "",
                            "source_org": r.org_name or "",
                            "source_date": str(r.publish_date or ""),
                            "score": 0.0,
                        }
                    )
        return rows
    except Exception:  # noqa: BLE001 — 兜底失败也返回空，绝不报错
        logger.warning("research_search: 结构化过滤兜底失败，返回空", exc_info=True)
        return []


async def _fallback_sql_filter(query: str, top_k: int) -> list[dict]:
    """结构化过滤兜底 async 入口（同步 SQL 经 to_thread，不阻塞事件循环）。"""
    return await asyncio.to_thread(_fallback_sql_filter_sync, query, top_k)


def _run_search_coro(query: str, top_k: int) -> list[dict]:
    """线程内执行 async 检索；解释器关闭竞态（RuntimeError）不污染 stderr。"""
    try:
        return asyncio.run(search_research_insights(query, top_k=top_k))
    except RuntimeError:
        logger.warning("research_search: 解释器关闭竞态，返回空")
        return []


# 语义检索降级超时（Phase D "每级 3s 内完成"）：超过即走 SQL 兜底
_SEARCH_TIMEOUT_SECONDS = 3.0
# 单例 executor：常驻复用，不每次新建线程（消除线程残留/排队竞态）
_SYNC_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def search_research_insights_sync(query: str, top_k: int = 5) -> list[dict]:
    """同步包装（graph 节点调用）：单例 executor 提交，超时降级 SQL 兜底。

    REST（asyncio.to_thread）与 WS（事件循环线程内同步 invoke）双路径安全。
    超时后立即执行 SQL 兜底（不再 20s 后返回空）；排队任务可被 cancel。
    """
    future = _SYNC_EXECUTOR.submit(_run_search_coro, query, top_k)
    try:
        return future.result(timeout=_SEARCH_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        # 取消排队/未完成任务（正在运行的模型加载无法强停，由预热脚本解决）；
        # 立即 SQL 兜底——降级等待 ≈3s
        future.cancel()
        logger.warning(
            "research_search: 语义检索超时（>%ss），降级 SQL 兜底",
            _SEARCH_TIMEOUT_SECONDS,
        )
        try:
            return _fallback_sql_filter_sync(query, top_k)
        except Exception:  # noqa: BLE001 — SQL 兜底异常也返回空
            logger.warning("research_search: SQL 兜底失败，返回空", exc_info=True)
            return []
    except Exception:  # noqa: BLE001
        logger.warning("research_search: 检索异常，返回空", exc_info=True)
        return []


def is_research_query(query: str) -> bool:
    """是否研报类问题（可选调用判定）。"""
    return any(kw in query for kw in _SEARCH_KEYWORDS)


def report_insights_enabled() -> bool:
    """配置开关（V12 预留）：VECTOR_BACKEND 启用时允许语义检索。"""
    return settings.VECTOR_BACKEND in ("chroma", "chromadb")
