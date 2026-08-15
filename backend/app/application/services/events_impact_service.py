"""舆情影响分析共享服务（⑧ B2 第一阶段，2026-08-11）.

REST（/events?include_impacts=true）与 Agent 节点共用本服务。

约束（v3.1 + v3.4 审查落地）：
- LLM 输入只含已有事实（事件簇摘要/公告标题情绪/评级变更/已材料化
  股权边证据 + evidence_ids），输出必须引用输入 evidence_id——
  程序化断言 ⊆ 输入集合，无效单条丢弃；
- 空 evidence 结论丢弃 + warning；impact_type/direction/severity 枚举
  白名单逐条校验——一条非法丢弃该条，不炸整个输出（v3.4）；
- statement_type 由 LLM 输出（observed/inference/projection），
  display_tag（"已发生/推断/风险推演"）由后端确定性渲染；
- 独立超时 + 调用预算（单次调用）；LLM 失败/空结论 → 返回空列表 + warning，
  不影响基础事件响应（不整体 500）；
- 缓存 + singleflight（v3.4）：缓存键含公司 + months + dataset_version +
  graph_version + LLM_BACKEND + prompt/schema 版本 + 输入事实内容 hash；
  并发同键请求共享一次 LLM 调用（防击穿）。
- 股权事实（v3.4）：Neo4j 直接持股边 → make_equity_edge_evidence_id 统一
  ID → 验证 evidence_refs 可回查才送 LLM（不用 fetch_shareholder_records，
  其 source_record_id 无 canonical ID）。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time

from pydantic import BaseModel, Field

from app.api.v1.schemas.events import CausalityStep, ImpactConclusion
from app.core.config import settings

logger = logging.getLogger(__name__)

_TAG_BY_STATEMENT_TYPE = {
    "observed": "已发生",
    "inference": "推断",
    "projection": "风险推演",
}
_VALID_STATEMENT_TYPES = set(_TAG_BY_STATEMENT_TYPE)
# v3.4：枚举白名单——LLM 输出非法值 → 单条丢弃（不炸整个输出）
_VALID_IMPACT_TYPES = {"equity_structure", "operation", "financing", "market"}
_VALID_DIRECTIONS = {"positive", "negative", "neutral"}
_VALID_SEVERITIES = {"low", "medium", "high"}

# ── 缓存 + singleflight（v3.4 + v3.5）──────────────────
_PROMPT_VERSION = "v1"  # 修改 prompt/schema/校验逻辑时递增（prompt+schema 版本合一）
_CACHE_MAX = 128
_CACHE_TTL = 300  # v3.5：成功缓存 TTL 300s（LLM 失败不缓存）
_impact_cache: dict[str, tuple[float, tuple[list[ImpactConclusion], list[str]]]] = {}
_impact_flights: dict[str, asyncio.Task] = {}


def _impact_cache_key(
    *,
    wind_code: str,
    sec_name: str,
    months: int,
    graph_version: str,
    facts_payload: list[dict],
) -> str:
    """缓存键：公司 + 名称 + months + 数据版本 + 图版本 + 模型 + prompt/schema
    版本 + 输入事实 hash（v3.5 补 sec_name；LLM_BACKEND 即模型后端）。"""
    facts_json = json.dumps(facts_payload, sort_keys=True, ensure_ascii=False)
    raw = "|".join(
        [
            wind_code,
            sec_name,
            str(months),
            settings.DATASET_VERSION,
            graph_version or settings.GRAPH_VERSION,
            settings.LLM_BACKEND or "mock",
            _PROMPT_VERSION,
            facts_json,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _get_engine():
    """轻量 engine（只读 evidence_refs 回查用）；与 provenance_service 同款。"""
    from sqlalchemy import create_engine

    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        return create_engine(url, echo=False, pool_pre_ping=True)
    return create_engine(f"sqlite:///{settings.SQLITE_PATH}", echo=False)


class _CausalityStepRaw(BaseModel):
    text: str = Field(..., min_length=1)
    statement_type: str = Field(default="inference")
    evidence_ids: list[str] = Field(default_factory=list)


class _ConclusionRaw(BaseModel):
    conclusion: str = Field(..., min_length=1)
    impact_type: str = Field(default="operation")
    direction: str = Field(default="neutral")
    severity: str = Field(default="low")
    evidence_ids: list[str] = Field(default_factory=list)
    causality_chain: list[_CausalityStepRaw] = Field(default_factory=list)
    statement_type: str = Field(default="inference")


class _ImpactsOutput(BaseModel):
    conclusions: list[_ConclusionRaw] = Field(default_factory=list)


async def generate_impacts(
    *,
    wind_code: str,
    sec_name: str,
    facts: list[dict],
    input_evidence_ids: set[str],
    months: int = 36,
    graph_version: str = "",
) -> tuple[list[ImpactConclusion], list[str]]:
    """生成舆情影响结论。返回 (结论列表, warnings)。

    facts: 既有事实（事件簇/公告/评级/已材料化股权边），每项含 text/evidence_ids。
    LLM 失败或空结论 → ([], [warning])，调用方保持基础事件响应。
    v3.4：缓存 + singleflight（并发同键共享一次 LLM 调用）。
    """
    if settings.LLM_BACKEND in ("", "mock"):
        return (
            [],
            ["IMPACT_LLM_UNAVAILABLE: LLM_BACKEND=mock/空，不生成影响结论"],
        )

    if not facts:
        return ([], ["IMPACT_NO_FACTS: 无可用事件事实，不生成影响结论"])

    facts_payload = [
        {"text": f.get("text", ""), "evidence_ids": f.get("evidence_ids", [])}
        for f in facts
    ]
    key = _impact_cache_key(
        wind_code=wind_code,
        sec_name=sec_name,
        months=months,
        graph_version=graph_version,
        facts_payload=facts_payload,
    )

    # v3.5：TTL 300s——命中但过期则删除重算
    cached = _impact_cache.get(key)
    if cached is not None:
        ts, value = cached
        if time.monotonic() - ts <= _CACHE_TTL:
            return value
        _impact_cache.pop(key, None)

    # singleflight：并发同键复用同一 LLM 调用（防击穿）——
    # 协程只在 await 点切换，先注册 task 再挂起，后到者必命中 flight。
    flight = _impact_flights.get(key)
    if flight is not None and not flight.done():
        return await asyncio.shield(flight)

    task = asyncio.create_task(
        _compute_impacts(
            wind_code=wind_code,
            sec_name=sec_name,
            facts_payload=facts_payload,
            input_evidence_ids=input_evidence_ids,
        )
    )
    _impact_flights[key] = task
    try:
        result = await task
    finally:
        _impact_flights.pop(key, None)
    # v3.5：LLM 失败（IMPACT_LLM_FAILED）不缓存——不缓存失败，避免
    # 短暂故障被后续请求反复命中；空结论（正常返回）可缓存。
    if any(w.startswith("IMPACT_LLM_FAILED") for w in result[1]):
        return result
    if len(_impact_cache) >= _CACHE_MAX:
        _impact_cache.clear()
    _impact_cache[key] = (time.monotonic(), result)
    return result


async def _compute_impacts(
    *,
    wind_code: str,
    sec_name: str,
    facts_payload: list[dict],
    input_evidence_ids: set[str],
) -> tuple[list[ImpactConclusion], list[str]]:
    """LLM 调用 + 程序化校验（v3.4 核心逻辑；generate_impacts 的缓存载体）。"""
    evidence_list = sorted(input_evidence_ids)
    system_prompt = (
        "你是财务舆情分析助手。基于给定事实（公告/事件簇/评级/股权结构）推断对公司的影响。"
        "规则：\n"
        "1. evidence_ids 只能引用输入中出现的 ID，不得编造；\n"
        "2. 没有直接证据的推断必须 statement_type=inference 或 projection，"
        "不得写成已发生事实（observed 仅限事实性陈述）；\n"
        "3. impact_type ∈ {equity_structure, operation, financing, market}；\n"
        "4. direction ∈ {positive, negative, neutral}；severity ∈ {low, medium, high}；\n"
        "5. causality_chain 为步骤数组，每步含 text/statement_type/evidence_ids；\n"
        "6. 每条结论必须引用至少一条输入证据。"
    )
    user_prompt = (
        f"公司：{sec_name}（{wind_code}）\n"
        f"可用证据 ID：{json.dumps(evidence_list, ensure_ascii=False)}\n"
        f"事实：{json.dumps(facts_payload, ensure_ascii=False)}\n"
        "请输出 1-3 条影响结论（结论引用输入证据；不足 1 条可输出空数组）。"
    )

    try:
        from app.infrastructure.llm.factory import (
            create_llm_provider,
        )  # 函数内 import：可测试性

        provider = create_llm_provider()
        result = await asyncio.wait_for(
            provider.structured_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                output_schema=_ImpactsOutput,
            ),
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — 降级：基础事件响应不受影响
        logger.warning("events_impact: LLM 调用失败: %s", exc)
        return ([], [f"IMPACT_LLM_FAILED: {exc}"])

    if not result or not result.conclusions:
        return ([], ["IMPACT_EMPTY: LLM 未返回影响结论"])

    conclusions: list[ImpactConclusion] = []
    dropped: list[str] = []
    for raw in result.conclusions:
        # 1) 证据 ⊆ 输入集合（无效单条丢弃）
        ev_ids = [e for e in raw.evidence_ids if e in input_evidence_ids]
        if len(ev_ids) != len(raw.evidence_ids):
            dropped.append(
                f"{raw.conclusion[:30]}… 引用非输入证据 {len(raw.evidence_ids) - len(ev_ids)} 条，已丢弃"
            )
            continue
        # 2) v3.4：空 evidence 结论丢弃（无支撑的结论不输出）
        if not ev_ids:
            dropped.append(f"{raw.conclusion[:30]}… 未引用任何输入证据，已丢弃")
            continue
        # 3) v3.4：枚举字段逐条校验（一条非法丢弃该条，不炸整体）
        if (
            raw.impact_type not in _VALID_IMPACT_TYPES
            or raw.direction not in _VALID_DIRECTIONS
            or raw.severity not in _VALID_SEVERITIES
        ):
            dropped.append(
                f"{raw.conclusion[:30]}… 枚举字段非法（impact_type/direction/severity），已丢弃"
            )
            continue
        # 4) v3.5：statement_type 非法不再静默改写——丢弃该结论 + warning
        if raw.statement_type not in _VALID_STATEMENT_TYPES:
            dropped.append(
                f"{raw.conclusion[:30]}… statement_type 非法（{raw.statement_type}），已丢弃"
            )
            continue
        steps: list[CausalityStep] = []
        for s in raw.causality_chain:
            # v3.5：非法因果步骤——证据非输入集合或为空 → 丢弃该步骤 + warning
            step_ev = [e for e in s.evidence_ids if e in input_evidence_ids]
            if len(step_ev) != len(s.evidence_ids):
                dropped.append(f"因果步骤[{s.text[:20]}…] 引用非输入证据，已丢弃该步骤")
                continue
            if not step_ev:
                dropped.append(f"因果步骤[{s.text[:20]}…] 无输入证据，已丢弃该步骤")
                continue
            if s.statement_type not in _VALID_STATEMENT_TYPES:
                dropped.append(
                    f"因果步骤[{s.text[:20]}…] statement_type 非法，已丢弃该步骤"
                )
                continue
            steps.append(
                CausalityStep(
                    text=s.text,
                    statement_type=s.statement_type,
                    evidence_ids=step_ev,
                )
            )
        conclusions.append(
            ImpactConclusion(
                conclusion=raw.conclusion,
                impact_type=raw.impact_type,
                direction=raw.direction,
                severity=raw.severity,
                evidence_ids=ev_ids,
                causality_chain=steps,
                statement_type=raw.statement_type,
                display_tag=_TAG_BY_STATEMENT_TYPE[raw.statement_type],
            )
        )
    return conclusions, dropped


def _pick(obj, *keys: str, default=""):
    """按候选键从 dict 或对象取字段（REST schema 对象 / Agent dict 双通道）。

    - dict：依次尝试 keys（键存在且非 None/""）；
    - 对象：依次尝试 getattr；
    - 全缺 → default。
    B2 第二阶段：Agent 节点的事件簇/时间线/评级元素是 dict，字段名与
    REST schema 略有差异（如 institution vs org_name、published_at vs date），
    此处统一双通道兼容，保持 routers/events.py 既有对象调用不变。
    """
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if v not in (None, ""):
                return v
    else:
        for k in keys:
            v = getattr(obj, k, None)
            if v not in (None, ""):
                return v
    return default


def build_impact_facts(
    *,
    event_clusters: list,
    timeline: list,
    rating_changes: list,
) -> tuple[list[dict], set[str]]:
    """从事件数据构造 LLM 输入事实 + 输入证据 ID 集合（供程序校验）。

    事实只含已有数据（摘要/标题/情绪/评级变更），不含推断性文字。
    event_clusters/timeline/rating_changes 元素可为 REST schema 对象或
    Agent 节点产出的 dict（双通道 _pick 兼容）。
    """
    facts: list[dict] = []
    evidence_ids: set[str] = set()
    for c in event_clusters:
        eids = list(_pick(c, "evidence_ids", default=[]) or [])
        evidence_ids.update(eids)
        label = _pick(c, "topic", "cluster_label", default="未分类")
        facts.append(
            {
                "text": f"事件簇[{label}]: {_pick(c, 'summary', default='')}",
                "evidence_ids": eids,
            }
        )
    for t in timeline:
        eids = list(_pick(t, "evidence_ids", default=[]) or [])
        evidence_ids.update(eids)
        facts.append(
            {
                "text": f"公告[{_pick(t, 'date', default='')}] "
                f"{_pick(t, 'title', default='')} "
                f"(情绪:{_pick(t, 'sentiment', default='neutral')})",
                "evidence_ids": eids,
            }
        )
    for r in rating_changes:
        eid = _pick(r, "evidence_id", default="") or ""
        if eid:
            evidence_ids.add(eid)
        facts.append(
            {
                "text": f"评级变更[{_pick(r, 'date', 'published_at', default='')}] "
                f"{_pick(r, 'org_name', 'institution', default='')}: "
                f"{_pick(r, 'prev_rating', 'previous_rating', default='')}→"
                f"{_pick(r, 'new_rating', 'current_rating', default='')} "
                f"({_pick(r, 'change', 'direction', default='maintain')})",
                "evidence_ids": [eid] if eid else [],
            }
        )
    return facts, evidence_ids


async def build_equity_impact_facts(
    wind_code: str,
    graph_version: str = "",
    limit: int = 5,
) -> tuple[list[dict], set[str]]:
    """股权事实：只送已材料化（evidence_refs 可回查）的 Neo4j 直接持股边。

    v3.4：不直接用 fetch_shareholder_records（仅 source_record_id、无
    canonical ID）——改走 Neo4j 边 + build_edge_evidence_map 统一 ID 算法，
    且每条边验证已落库（可回查）才送 LLM；未材料化边保守丢弃。
    Neo4j/MySQL 失败 → 空事实（不阻塞影响分析）。
    """
    gv = graph_version or settings.GRAPH_VERSION
    graph = None
    try:
        from app.application.services.equity_shareholder_service import (
            build_edge_evidence_map,
        )
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        graph = await Neo4jEquityGraph().get_graph(
            wind_code, depth=1, direction="upstream", graph_version=gv
        )
        edges = list(graph.edges)[:limit]
        if not edges:
            return [], set()
        edge_map = build_edge_evidence_map(
            edges=edges, company_code=wind_code, graph_version=gv
        )
    except Exception as exc:  # noqa: BLE001 — 股权事实失败不阻塞影响分析
        logger.warning("build_equity_impact_facts: Neo4j 查询失败: %s", exc)
        return [], set()

    labels = {n.id: (n.label or n.id) for n in (graph.nodes or [])}
    facts: list[dict] = []
    evidence_ids: set[str] = set()
    try:
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            for edge in edges:
                rel_id = (
                    getattr(edge, "relationship_id", "")
                    or getattr(edge, "source_record_id", "")
                    or ""
                )
                eid = edge_map.get(rel_id, "")
                if not eid:
                    continue
                # 验证可回查（只读；未材料化 → 不送 LLM）
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
                    ),
                    {"eid": eid},
                ).scalar()
                if not exists:
                    continue
                pct = getattr(edge, "ownership_pct", None)
                pct_txt = f"{float(pct):.2f}%" if isinstance(pct, (int, float)) else "—"
                period = (
                    getattr(edge, "report_period", "")
                    or getattr(edge, "ann_dt", "")
                    or ""
                )
                src_id = getattr(edge, "source", "") or ""
                tgt_id = getattr(edge, "target", "") or ""
                src = labels.get(src_id, src_id)
                tgt = labels.get(tgt_id, tgt_id)
                facts.append(
                    {
                        "text": f"股权持股[{period}] {src}→{tgt} {pct_txt}",
                        "evidence_ids": [eid],
                    }
                )
                evidence_ids.add(eid)
    except Exception as exc:  # noqa: BLE001 — 回查失败保守丢弃（不送未验证证据）
        logger.warning("build_equity_impact_facts: evidence 回查失败: %s", exc)
        return [], set()
    return facts, evidence_ids
