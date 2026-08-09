"""Equity — V12 §8.6. 股权穿透节点（真实 Neo4j / Lite NetworkX）。

Full profile: MySQL 公司 → Neo4jEquityGraph 真实图，产出真实 relationship_id 证据。
Lite profile: NetworkX（明确降级适配器）。
不再硬编码"马兴田→康美实业"Mock 链，不再产出固定 ev_eq_01。
"""

from __future__ import annotations

import logging
import time

from app.agents.state import (
    AgentState,
    EvidenceRef,
    EquityResult,
    ModuleResults,
    ModuleStatus,
)
from app.core.config import settings
from app.domain.provenance.id_factory import NS_EQUITY, make_evidence_id

logger = logging.getLogger(__name__)


def _evidence_for_edge(
    *,
    edge: dict,
    company_code: str,
    trace_id: str,
    turn_id: str,
    graph_version: str,
) -> EvidenceRef:
    """为一条股权边生成确定性 EvidenceRef（绑定真实 relationship_id）。"""
    rel_id = edge.get("relationship_id") or edge.get("source_record_id") or ""
    period = edge.get("report_period") or edge.get("ann_dt") or ""
    pct = edge.get("ownership_pct")
    evidence_id = make_evidence_id(
        source_namespace=NS_EQUITY,
        source_type="neo4j_relationship",
        source_record_id=rel_id,
        field_path="ownership_pct",
        period=period,
        dataset_version=graph_version,
        company_code=company_code,
    )
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type="neo4j_relationship",
        source_record_id=rel_id,
        source_table="neo4j:OWNS",
        field_path="ownership_pct",
        period=period,
        value=(f"{pct:.2f}" if isinstance(pct, (int, float)) else str(pct or "")),
        source_title=(
            f"{edge.get('source_name', '')}→{edge.get('target_name', '')} "
            f"持股 {pct}"
        ),
        module="equity",
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=company_code,
        statement_scope="ownership_record",
        dataset_version=graph_version,
    )


def _build_chain_details(
    *,
    chains: list[dict],
    graph_edges: list,
    company_code: str,
    as_of: str,
    source_system: str,
    node_name_map: dict[str, str] | None = None,
    edge_evidence_map: dict[str, str] | None = None,
    top_shareholder_records: list[dict] | None = None,
) -> list[dict]:
    """Phase D #12: 通过 equity_chain_service 构建正式链路载荷。"""
    try:
        from app.application.services.equity_chain_service import build_equity_chains

        # chains 是 dict（path/edge_ids 等），转成可消费结构
        dto_list, _warnings = build_equity_chains(
            company_code=company_code,
            chains=chains,
            node_name_map=node_name_map or {},
            graph_edges=graph_edges,
            top_shareholder_records=top_shareholder_records or [],
            edge_evidence_map=edge_evidence_map or {},
            as_of=as_of,
            source_system=source_system,
            merge_groups=[],
        )
        return [d.to_dict() for d in dto_list]
    except Exception:  # noqa: BLE001 — 链路载荷失败不影响主流程
        logger.warning("equity: chain_details 构建失败，跳过", exc_info=True)
        return []


def _latest_shareholders(records: list[dict]) -> list[dict]:
    """将 top_shareholders 记录规范为最新报告期的回答 DTO。"""

    def normalize_period(value) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())[:8]

    periods = [normalize_period(item.get("report_period")) for item in records]
    latest_period = max((period for period in periods if period), default="")
    if not latest_period:
        return []
    shareholders: list[dict] = []
    for item in records:
        if normalize_period(item.get("report_period")) != latest_period:
            continue
        pct = item.get("pct")
        shareholders.append(
            {
                "holder_name": str(item.get("holder_name") or ""),
                "ownership_pct": float(pct) if pct is not None else None,
                "report_period": latest_period,
                "source_record_id": str(item.get("source_record_id") or ""),
            }
        )
    by_name: dict[str, dict] = {}
    for item in shareholders:
        name = item["holder_name"]
        existing = by_name.get(name)
        if existing is None or (item.get("ownership_pct") or 0.0) > (
            existing.get("ownership_pct") or 0.0
        ):
            by_name[name] = item
    shareholders = list(by_name.values())
    shareholders.sort(key=lambda item: item.get("ownership_pct") or 0.0, reverse=True)
    return shareholders[:10]


def equity_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    plan = state.get("plan")
    company = state.get("company")
    runtime = state.get("runtime")

    # 未选中 → no-op
    if plan is not None and "equity" not in plan.requested_modules:
        return {
            "module_status": {"equity": ModuleStatus(state="skipped")},
            "results": ModuleResults(equity=None),
        }

    if company is None:
        return {
            "module_status": {"equity": ModuleStatus(state="skipped")},
            "results": ModuleResults(equity=None),
        }

    company_code = company.wind_code or company.entity_id
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""

    # #5 期次传播：Neo4j 图按截止期过滤（Lite NetworkX 为静态图，不支持 as_of）
    as_of = ""
    if plan is not None and plan.as_of:
        as_of = plan.as_of.strftime("%Y%m%d")

    from app.application.services.equity_shareholder_service import (
        fetch_shareholder_records,
    )

    shareholder_records = fetch_shareholder_records(company_code, as_of=as_of or None)
    shareholders = _latest_shareholders(shareholder_records)

    if settings.GRAPH_BACKEND == "neo4j":
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        adapter = Neo4jEquityGraph()
        if not adapter._check_connection_sync():
            return {
                "module_status": {
                    "equity": ModuleStatus(
                        state="partial",
                        error_code="NEO4J_UNAVAILABLE",
                        recoverable=True,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                },
                "results": ModuleResults(
                    equity=EquityResult(
                        graph={}, chains=[], evidence=[], shareholders=shareholders
                    )
                ),
            }

        try:
            graph = adapter._get_graph_sync(company_code, depth=5, as_of=as_of or None)
        except Exception:  # noqa: BLE001
            logger.exception("股权查询失败: %s", company_code)
            return {
                "module_status": {
                    "equity": ModuleStatus(
                        state="partial",
                        error_code="EQUITY_QUERY_ERROR",
                        recoverable=True,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                },
                "results": ModuleResults(
                    equity=EquityResult(
                        graph={}, chains=[], evidence=[], shareholders=shareholders
                    )
                ),
            }

        graph_version = graph.graph_version or settings.GRAPH_VERSION

        # 构建图数据（含名称映射）
        node_name = {n.id: n.label for n in graph.nodes}
        graph_data = {
            "source": "neo4j",
            "graph_version": graph_version,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.label,
                    "entity_id": n.entity_id or n.id,
                    "type": n.type,
                    "wind_code": n.wind_code,
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "relationship_id": e.relationship_id,
                    "source": e.source,
                    "source_name": node_name.get(e.source, e.source),
                    "target": e.target,
                    "target_name": node_name.get(e.target, e.target),
                    "relation_type": e.relation,
                    "ownership_pct": e.effective_ownership_pct(),
                    "report_period": e.report_period,
                    "ann_dt": e.ann_dt,
                    "source_record_id": e.source_record_id,
                }
                for e in graph.edges
            ],
        }

        chains = []
        for chain in graph.control_chains:
            chains.append(
                {
                    "path": chain.path,
                    "path_names": [node_name.get(nid, nid) for nid in chain.path],
                    "total_stake": chain.total_stake,
                    "depth": chain.depth,
                    "edge_ids": chain.edge_ids,
                    "final_control_pct": chain.effective_control_pct(),
                    "source": "neo4j",
                }
            )

        # 证据：每条真实边一条 EvidenceRef（去重按 relationship_id）
        evidence = []
        seen = set()
        edge_evidence_map: dict[str, str] = {}
        for e in graph.edges:
            edge_dict = {
                "relationship_id": e.relationship_id,
                "source_record_id": e.source_record_id,
                "source_name": node_name.get(e.source, e.source),
                "target_name": node_name.get(e.target, e.target),
                "report_period": e.report_period,
                "ann_dt": e.ann_dt,
                "ownership_pct": e.effective_ownership_pct(),
            }
            rid = e.relationship_id or e.source_record_id
            if rid in seen:
                continue
            seen.add(rid)
            ev_ref = _evidence_for_edge(
                edge=edge_dict,
                company_code=company_code,
                trace_id=trace_id,
                turn_id=turn_id,
                graph_version=graph_version,
            )
            evidence.append(ev_ref)
            edge_evidence_map[rid] = ev_ref.evidence_id

        # Phase D #12: 正式链路载荷（Agent/WS 与 REST 一致；
        # canonical evidence_id 映射 + 真实股东记录驱动 mismatch 检测）
        chain_details = _build_chain_details(
            chains=chains,
            graph_edges=list(graph.edges),
            company_code=company_code,
            as_of=as_of,
            source_system="neo4j",
            node_name_map=node_name,
            edge_evidence_map=edge_evidence_map,
            top_shareholder_records=shareholder_records,
        )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "module_status": {
                "equity": ModuleStatus(state="success", duration_ms=elapsed_ms)
            },
            "results": ModuleResults(
                equity=EquityResult(
                    graph=graph_data,
                    chains=chains,
                    evidence=evidence,
                    chain_details=chain_details,
                    shareholders=shareholders,
                )
            ),
        }

    # Lite profile：NetworkX 明确降级
    from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph

    adapter = NetworkXEquityGraph()
    graph = adapter._get_graph_sync(company_code, depth=5)
    node_name = {n.id: n.label for n in graph.nodes}
    graph_data = {
        "source": "networkx",
        "nodes": [
            {
                "id": n.id,
                "name": n.label,
                "entity_id": n.entity_id or n.id,
                "type": n.type,
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "relationship_id": e.relationship_id,
                "source": e.source,
                "source_name": node_name.get(e.source, e.source),
                "target": e.target,
                "target_name": node_name.get(e.target, e.target),
                "relation_type": e.relation,
                "ownership_pct": e.effective_ownership_pct(),
            }
            for e in graph.edges
        ],
    }
    chains = [
        {
            "path": chain.path,
            "path_names": [node_name.get(nid, nid) for nid in chain.path],
            "total_stake": chain.total_stake,
            "depth": chain.depth,
            "edge_ids": chain.edge_ids,
            "final_control_pct": chain.effective_control_pct(),
            "source": "networkx",
        }
        for chain in graph.control_chains
    ]
    evidence = []
    seen = set()
    edge_evidence_map: dict[str, str] = {}
    for e in graph.edges:
        rid = e.relationship_id
        if rid in seen:
            continue
        seen.add(rid)
        ev_ref = _evidence_for_edge(
            edge={
                "relationship_id": rid,
                "source_name": node_name.get(e.source, e.source),
                "target_name": node_name.get(e.target, e.target),
                "report_period": None,
                "ann_dt": None,
                "ownership_pct": e.effective_ownership_pct(),
            },
            company_code=company_code,
            trace_id=trace_id,
            turn_id=turn_id,
            graph_version="networkx-lite",
        )
        evidence.append(ev_ref)
        edge_evidence_map[rid] = ev_ref.evidence_id

    # Phase D #12: 正式链路载荷（Lite 同样产出，source=networkx）
    chain_details = _build_chain_details(
        chains=chains,
        graph_edges=list(graph.edges),
        company_code=company_code,
        as_of=as_of,
        source_system="networkx",
        node_name_map=node_name,
        edge_evidence_map=edge_evidence_map,
        top_shareholder_records=shareholder_records,
    )

    return {
        "module_status": {"equity": ModuleStatus(state="success", duration_ms=200)},
        "results": ModuleResults(
            equity=EquityResult(
                graph=graph_data,
                chains=chains,
                evidence=evidence,
                chain_details=chain_details,
                shareholders=shareholders,
            )
        ),
    }
