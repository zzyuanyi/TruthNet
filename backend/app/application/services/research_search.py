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
import re
import threading
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_report_chunks"
_SEARCH_KEYWORDS = ("研报", "观点", "行业", "机构", "分析师", "评级", "近期")
_VECTOR_STORE = None
_VECTOR_STORE_LOCK = threading.Lock()


def _default_vector_store():
    """进程级 ChromaVectorStore 单例，避免每次请求重建 Chroma client。"""
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        with _VECTOR_STORE_LOCK:
            if _VECTOR_STORE is None:
                from app.infrastructure.vector.chroma.vector_store import (
                    ChromaVectorStore,
                )

                _VECTOR_STORE = ChromaVectorStore()
    return _VECTOR_STORE


def _semantic_to_insight(hit: dict) -> dict:
    """Chroma 命中 → 统一输出结构（content/source/score）。

    #4：补充 report_id/wind_code/sec_name/source_uri，供生成可回查 Evidence。
    """
    meta = hit.get("metadata") or {}
    return {
        "content": (hit.get("content") or "")[:300],
        "source_title": meta.get("title", ""),
        "source_org": meta.get("org_name", ""),
        "source_date": str(meta.get("publish_date", "") or ""),
        "report_id": str(meta.get("report_id", "") or ""),
        "wind_code": str(meta.get("wind_code", "") or ""),
        "sec_name": str(meta.get("sec_name", "") or ""),
        "source_uri": str(meta.get("source_uri", "") or ""),
        "score": round(float(hit.get("score", 0.0)), 3),
    }


_STOP_WORDS = frozenset(
    {
        "什么情况",
        "怎么样",
        "怎么看",
        "为什么",
        "什么",
        "如何",
        "是否",
        "多少",
        "哪些",
        "最近",
        "情况",
        "表现",
    }
)

# 意图词（#6）：只标记"这是研报类问题"，不参与 OR 匹配——
# "行业/近期/研报/观点"等泛词会拉入大量无关研报（如"白酒行业"误配化工/电子）；
# "财务/分析/公司"也是非主题词，剥离后留下核心实体（如"康美药业财务分析"→"康美药业"）
_INTENT_WORDS = frozenset(
    {
        "行业",
        "近期",
        "研报",
        "观点",
        "机构",
        "分析师",
        "评级",
        "最新",
        "解读",
        "展望",
        "报告",
        "推荐",
        "财务",
        "分析",
        "公司",
    }
)


def _split_keywords(query: str) -> tuple[list[str], list[str]]:
    """问题 → (核心主题词, 命中意图词)。

    核心主题词：整段连续汉字去掉意图词后剩余的主题内容（如
    "白酒行业" → 核心"白酒"）；2-gram 仅在主题词 ≥4 字时切分作为
    扩展召回（OR 辅助），完整主题串作为 MUST 词（#6）。
    意图词只标记意图，绝不参与 LIKE OR 匹配。

    Returns:
        core_keywords: 参与匹配的核心主题词（可为空）
        intent_words: 命中的意图词（仅标记意图）
    """
    import re

    tokens = re.findall(r"[一-鿿]{2,}|[A-Za-z]{2,}", query)
    core: list[str] = []
    intent: list[str] = []
    for t in tokens:
        if t in _INTENT_WORDS:
            if t not in intent:
                intent.append(t)
            continue
        # 连续汉字去掉意图词后剩余部分（按词长降序替换，避免"行业"吞"银行"）
        rest = t
        for w in sorted(_INTENT_WORDS, key=len, reverse=True):
            if w in rest:
                rest = rest.replace(w, "")
                if w not in intent:
                    intent.append(w)
        # 去掉问句尾词，避免“白酒行业怎么样”形成不存在的 MUST 词
        # “白酒怎么样”，导致真实白酒研报被 SQL 相关性 Gate 全部拒绝。
        for w in sorted(_STOP_WORDS, key=len, reverse=True):
            rest = rest.replace(w, "")
        rest = rest.strip()
        if len(rest) >= 2:
            core.append(rest)
            if len(rest) >= 4:
                for i in range(len(rest) - 1):
                    gram = rest[i : i + 2]
                    if gram not in _STOP_WORDS and gram not in core:
                        core.append(gram)
    # 去重保序
    seen: set[str] = set()
    core_dedup: list[str] = []
    for k in core:
        if k not in seen:
            seen.add(k)
            core_dedup.append(k)
    return core_dedup, intent


# Chroma 相关度下限（低于视为不相关，走 SQL 兜底；#6）
_MIN_RELEVANCE_SCORE = 0.15


def _topic_anchor(query: str) -> str:
    """提取研报问题的主题锚点，避免用任意二元词放行无关结果。"""
    text = re.sub(r"[？?。！!，,]", "", query or "").strip()
    for marker in ("的生产工艺", "的主要应用领域", "的应用领域"):
        if marker in text:
            return text.split(marker, 1)[0].strip("的")
    match = re.search(
        r"(?:近期|目前|当前|最近)?(.{2,16}?)(?:行业|领域|板块|产业链)", text
    )
    if match:
        return match.group(1).strip("的")
    if "技术" in text:
        prefix = text.split("技术", 1)[0]
        prefix = re.sub(r"^(?:近期|目前|当前|最近|有哪些)", "", prefix)
        return prefix.strip("的")
    return ""


def _hit_text(hit: dict) -> str:
    meta = hit.get("metadata") or {}
    return "".join(
        str(value or "")
        for value in (
            hit.get("content"),
            hit.get("source_title"),
            hit.get("sec_name"),
            hit.get("industry"),
            meta.get("title"),
            meta.get("sec_name"),
            meta.get("industry_l1"),
        )
    )


def _pass_relevance_gate(hit: dict, core_keywords: list[str], query: str = "") -> bool:
    """核心主题 Gate（#6）：至少一个核心主题词出现在命中内容/标题中。

    语义检索可能返回语义相近但主题无关的研报（如"白酒"配到"电子"），
    核心主题词必须可字面命中才放行。
    """
    if not core_keywords:
        return False
    text = _hit_text(hit)
    anchor = _topic_anchor(query)
    if anchor:
        return anchor in text
    return any(kw in text for kw in core_keywords)


_TECH_OBJECT_CUES = (
    "人工智能",
    "AI",
    "机器人",
    "影像",
    "内窥",
    "微创",
    "介入",
    "植入",
    "手术",
    "监护",
    "麻醉",
    "传感",
    "算法",
    "数字化",
    "3D",
    "基因",
    "质谱",
    "分子",
    "康复",
    "激光",
    "超声",
)


def _pass_answer_type_gate(hit: dict, query: str) -> bool:
    """命中内容必须能回答问题类型；不满足时宁可返回数据不足。"""
    text = _hit_text(hit)
    sentences = [s for s in re.split(r"[。；;\n]", text) if s]
    anchor = _topic_anchor(query)
    if "高管薪酬" in query:
        return any(
            (not anchor or anchor in sentence)
            and any(cue in sentence for cue in ("高管", "薪酬", "董事长薪酬", "董监高"))
            for sentence in sentences
        )
    if any(cue in query for cue in ("首发价格", "首发价", "发行价格", "发行价")):
        return any(
            (not anchor or anchor in sentence)
            and any(
                cue in sentence for cue in ("首发价格", "首发价", "发行价格", "发行价")
            )
            for sentence in sentences
        )
    if "产业链" in query:
        if not anchor or anchor in {"热门", "相关"}:
            return False
        return any(
            (not anchor or anchor in sentence) and "产业链" in sentence
            for sentence in sentences
        )
    if "市场规模" in query or "市场空间" in query or "市场容量" in query:
        return any(
            (not anchor or anchor in sentence)
            and any(
                cue in sentence
                for cue in ("市场规模", "市场空间", "市场容量", "行业规模")
            )
            for sentence in sentences
        )
    if "生产工艺" in query:
        return bool(anchor) and any(
            anchor in sentence
            and any(
                cue in sentence
                for cue in ("生产工艺", "制备工艺", "生产流程", "制备流程")
            )
            for sentence in sentences
        )
    if "应用领域" in query:
        return bool(anchor) and any(
            anchor in sentence
            and any(
                cue in sentence for cue in ("应用领域", "应用于", "用于", "应用场景")
            )
            for sentence in sentences
        )
    if "挑战" in query:
        return any(
            (not anchor or anchor in sentence)
            and any(
                cue in sentence
                for cue in (
                    "挑战",
                    "风险",
                    "压力",
                    "瓶颈",
                    "集采",
                    "降价",
                    "监管",
                    "竞争加剧",
                )
            )
            for sentence in sentences
        )
    if "整体表现" in query:
        return any(
            (not anchor or anchor in sentence)
            and "行业" in sentence
            and any(
                cue in sentence
                for cue in ("增长", "下降", "回升", "承压", "景气", "增速", "表现")
            )
            for sentence in sentences
        )
    if any(cue in query for cue in ("技术", "研发", "创新")):
        progress_cues = ("技术", "研发", "在研", "开发", "创新", "临床", "试验", "迭代")
        return any(
            (not anchor or anchor in sentence)
            and any(cue in sentence for cue in progress_cues)
            and any(cue in sentence for cue in _TECH_OBJECT_CUES)
            for sentence in sentences
        )
    return True


def _dedup_report_ids(hits: list[dict]) -> list[dict]:
    """按 report_id 去重（report_id 为空时按 source_title），保持顺序。"""
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        key = h.get("report_id") or h.get("source_title") or ""
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def _pass_date_gate(hit: dict, as_of: str) -> bool:
    """研报日期 Gate（P1-3）：publish_date 不得晚于 as_of（YYYYMMDD）。

    兼容 "2025-06-30"（varchar 常见格式）与 "20250630" 两种写法。
    """
    if not as_of:
        return True
    date_str = str((hit.get("metadata") or {}).get("publish_date", "") or "")
    norm = date_str.replace("-", "").replace("/", "").strip()
    if not norm:
        return True  # 无日期不排除（SQL 路径另有严格过滤）
    return norm <= as_of


async def search_research_insights(
    query: str, top_k: int = 5, vector_store=None, as_of: str = ""
) -> list[dict]:
    """语义检索研报观点；Chroma 断开/空结果/不相关 → 结构化过滤兜底（不报错）。

    #6 相关性：Chroma 命中须过主题 Gate（核心主题词字面命中）+ 最低相关度，
    未通过不返回，改走 SQL 兜底；两路都无相关内容 → 诚实返回空。
    #5 期次：as_of（YYYYMMDD）存在时，Chroma/SQL 均只返回 publish_date <= as_of。

    Args:
        query: 用户问题（如"白酒行业近期研报观点"）。
        top_k: 返回条数。
        vector_store: 可注入 mock（测试用）；None 用真实 ChromaVectorStore。
        as_of: 信息截止日（YYYYMMDD）；空表示不限。
    """
    core_keywords, _intent = _split_keywords(query)
    try:
        if vector_store is None:
            vector_store = _default_vector_store()
        hits = await vector_store.search(query, collection=COLLECTION_NAME, top_k=top_k)
    except Exception:  # noqa: BLE001 — Chroma 任何异常走兜底
        logger.warning(
            "research_search: Chroma 检索异常，走结构化过滤兜底", exc_info=True
        )
        hits = []

    if hits:
        filtered = [
            h
            for h in hits
            if float(h.get("score", 0.0)) >= _MIN_RELEVANCE_SCORE
            and _pass_relevance_gate(h, core_keywords, query)
            and _pass_answer_type_gate(h, query)
            and _pass_date_gate(h, as_of)
        ]
        if filtered:
            return _dedup_report_ids([_semantic_to_insight(h) for h in filtered])
        logger.warning("research_search: Chroma 命中未过主题/日期 Gate，走 SQL 兜底")
    try:
        return await _fallback_sql_filter(query, top_k, as_of=as_of)
    except Exception:  # noqa: BLE001 — 兜底异常也返回空，绝不报错
        logger.warning("research_search: 兜底检索异常，返回空", exc_info=True)
        return []


def _fallback_sql_filter_sync(query: str, top_k: int, as_of: str = "") -> list[dict]:
    """结构化过滤兜底（V12 §10.10）同步核心：research_reports 关键词 LIKE。

    同步实现供 async 入口（to_thread）与同步超时降级共用。

    #6 相关性修正：
      - 意图词（行业/近期/研报/观点…）不参与匹配；
      - 核心主题词完整串必须命中（title/abstract/sec_name/industry_l1 之一，
        AND 语义），2-gram 仅作 OR 扩展召回——杜绝"白酒"检索混入化工/电子；
      - 纯意图查询（无核心主题）→ 诚实返回空，不用泛词补足。
    #4：输出补 report_id/wind_code/sec_name/source_uri 供可回查 Evidence。
    #5 期次：as_of（YYYYMMDD）存在时只取 publish_date <= as_of。
    """
    core_keywords, _intent = _split_keywords(query)
    if not core_keywords:
        return []
    # 主题锚点优先；不能再以任意 2-gram（如“块链”）代替完整主题。
    must_kw = _topic_anchor(query) or max(core_keywords, key=len)
    try:
        from sqlalchemy import text

        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        rows = []
        with engine.connect() as conn:
            # 单次查询：MUST（核心主题，AND）+ OR 扩展（2-gram 辅助召回）
            # 注意：真表字段是 industry_l1（非 industry）
            must_cond = (
                "(title LIKE :must OR abstract LIKE :must OR sec_name LIKE :must "
                "OR industry_l1 LIKE :must)"
            )
            params: dict = {"must": f"%{must_kw}%", "lim": top_k}
            date_cond = ""
            if as_of:
                # publish_date 为 varchar 日期（YYYY-MM-DD），归一化后比较
                date_cond = " AND REPLACE(publish_date, '-', '') <= :asof "
                params["asof"] = as_of
            rs = conn.execute(
                text(
                    f"SELECT report_id, wind_code, title, abstract, org_name, sec_name, "
                    f"publish_date, source_uri, industry_l1 "
                    f"FROM research_reports "
                    f"WHERE is_latest = 1 AND {must_cond}{date_cond}"
                    f"ORDER BY publish_date DESC LIMIT :lim"
                ),
                params,
            )
            for r in rs:
                rows.append(
                    {
                        "content": (r.abstract or "")[:300] or (r.title or "")[:300],
                        "source_title": r.title or "",
                        "source_org": r.org_name or "",
                        "source_date": str(r.publish_date or ""),
                        "report_id": str(r.report_id or ""),
                        "wind_code": str(r.wind_code or ""),
                        "sec_name": r.sec_name or "",
                        "source_uri": r.source_uri or "",
                        # 行业映射命中（industry_l1）也属主题相关——随结果返回
                        "industry": r.industry_l1 or "",
                        "score": 0.0,
                    }
                )
        return [row for row in rows if _pass_answer_type_gate(row, query)]
    except Exception:  # noqa: BLE001 — 兜底失败也返回空，绝不报错
        logger.warning("research_search: 结构化过滤兜底失败，返回空", exc_info=True)
        return []


async def _fallback_sql_filter(query: str, top_k: int, as_of: str = "") -> list[dict]:
    """结构化过滤兜底 async 入口（同步 SQL 经 to_thread，不阻塞事件循环）。"""
    return await asyncio.to_thread(_fallback_sql_filter_sync, query, top_k, as_of)


def _run_search_coro(query: str, top_k: int, as_of: str = "") -> list[dict]:
    """线程内执行 async 检索；解释器关闭竞态（RuntimeError）不污染 stderr。"""
    try:
        return asyncio.run(search_research_insights(query, top_k=top_k, as_of=as_of))
    except RuntimeError:
        logger.warning("research_search: 解释器关闭竞态，返回空")
        return []


# 语义检索降级超时（Phase D "每级 3s 内完成"）：超过即走 SQL 兜底
_SEARCH_TIMEOUT_SECONDS = 3.0
# 单例 executor：常驻复用，不每次新建线程（消除线程残留/排队竞态）
_SYNC_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def search_research_insights_sync(
    query: str, top_k: int = 5, as_of: str = ""
) -> list[dict]:
    """同步包装（graph 节点调用）：单例 executor 提交，超时降级 SQL 兜底。

    REST（asyncio.to_thread）与 WS（事件循环线程内同步 invoke）双路径安全。
    超时后立即执行 SQL 兜底（不再 20s 后返回空）；排队任务可被 cancel。
    #5 期次：as_of（YYYYMMDD）贯通 Chroma/SQL 两路。

    性能埋点（Phase D #7）：Chroma 查询耗时 / SQL fallback 耗时 / 总耗时 /
    是否 fallback / 是否 timeout / 结果数。
    """

    t0 = time.perf_counter()
    future = _SYNC_EXECUTOR.submit(_run_search_coro, query, top_k, as_of)
    timed_out = False
    total_ms = 0.0
    chroma_ms = 0.0
    fallback_ms = 0.0
    try:
        result = future.result(timeout=_SEARCH_TIMEOUT_SECONDS)
        total_ms = (time.perf_counter() - t0) * 1000
        chroma_ms = total_ms  # 成功路径 = Chroma 查询耗时
        _record_search_metrics(
            total_ms=total_ms,
            chroma_ms=chroma_ms,
            fallback_ms=0.0,
            result_count=len(result),
            degraded=False,
            timed_out=False,
        )
        return result
    except concurrent.futures.TimeoutError:
        # 取消排队/未完成任务（正在运行的模型加载无法强停，由预热脚本解决）；
        # 立即 SQL 兜底——降级等待 ≈3s
        future.cancel()
        logger.warning(
            "research_search: 语义检索超时（>%ss），降级 SQL 兜底",
            _SEARCH_TIMEOUT_SECONDS,
        )
        timed_out = True
        tf = time.perf_counter()
        try:
            result = _fallback_sql_filter_sync(query, top_k, as_of=as_of)
            total_ms = (time.perf_counter() - t0) * 1000
            fallback_ms = (time.perf_counter() - tf) * 1000
            _record_search_metrics(
                total_ms=total_ms,
                chroma_ms=_SEARCH_TIMEOUT_SECONDS * 1000,
                fallback_ms=fallback_ms,
                result_count=len(result),
                degraded=True,
                timed_out=True,
            )
            return result
        except Exception:  # noqa: BLE001 — SQL 兜底异常也返回空
            logger.warning("research_search: SQL 兜底失败，返回空", exc_info=True)
            _record_search_metrics(
                total_ms=(time.perf_counter() - t0) * 1000,
                chroma_ms=_SEARCH_TIMEOUT_SECONDS * 1000,
                fallback_ms=0.0,
                result_count=0,
                degraded=True,
                timed_out=True,
            )
            return []
    except Exception:  # noqa: BLE001
        logger.warning("research_search: 检索异常，返回空", exc_info=True)
        total_ms = (time.perf_counter() - t0) * 1000
        _record_search_metrics(
            total_ms=total_ms,
            chroma_ms=total_ms,
            fallback_ms=0.0,
            result_count=0,
            degraded=True,
            timed_out=timed_out,
        )
        return []


def _record_search_metrics(
    *,
    total_ms: float,
    chroma_ms: float,
    fallback_ms: float,
    result_count: int,
    degraded: bool,
    timed_out: bool,
) -> None:
    """搜索性能埋点（结构化指标，不含用户问题）。"""
    try:
        from app.infrastructure.observability.timing import metrics_collector

        metrics_collector.record(
            "search.total_ms",
            total_ms,
            degraded=degraded,
            timeout=timed_out,
            result_count=result_count,
        )
        metrics_collector.record(
            "search.chroma_ms",
            chroma_ms,
            degraded=degraded,
            timeout=timed_out,
            result_count=result_count,
        )
        if fallback_ms:
            metrics_collector.record(
                "search.fallback_ms",
                fallback_ms,
                degraded=True,
                timeout=timed_out,
                result_count=result_count,
            )
    except Exception:  # noqa: BLE001 — 埋点失败不影响主流程
        logger.warning("research_search: 性能埋点失败", exc_info=True)


def is_research_query(query: str) -> bool:
    """是否研报类问题（可选调用判定）。"""
    return any(kw in query for kw in _SEARCH_KEYWORDS)


def report_insights_enabled() -> bool:
    """配置开关（V12 预留）：VECTOR_BACKEND 启用时允许语义检索。"""
    return settings.VECTOR_BACKEND in ("chroma", "chromadb")
