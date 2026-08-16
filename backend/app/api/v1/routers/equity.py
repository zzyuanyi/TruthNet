"""股权穿透路由 — V12 §11 + Phase C 真实图谱 + Phase D #12 链路载荷.

GET /api/v1/companies/{code}/equity

Full profile 流程：
  code → CompanyResolver（MySQL 真实画像）→ Neo4jEquityGraph（真实边/路径）。
  Neo4j 不可用时返回 partial=true + NEO4J_UNAVAILABLE + 空图，绝不降级 NetworkX 冒充。
Lite profile 使用 NetworkX（明确降级适配器）。
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.equity import (
    EquityChainDTO,
    EquityEdgeDTO,
    EquityNodeDTO,
    EquityPathDTO,
    EquityResponseData,
    TargetCompanyDTO,
)
from app.application.services.company_resolver import CompanyResolver
from app.application.services.equity_chain_service import build_equity_chains
from app.application.services.equity_shareholder_service import (
    build_edge_evidence_map,
    fetch_shareholder_records,
    materialize_equity_evidence,
)
from app.core.config import settings
from app.domain.equity.models import EquityGraph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["equity"])


def _graph_to_dtos(
    graph: EquityGraph,
) -> tuple[list[EquityNodeDTO], list[EquityEdgeDTO], list[EquityPathDTO]]:
    """将域模型转为 DTO（ownership_pct 统一 0-100）。"""
    nodes = [
        EquityNodeDTO(
            id=n.id,
            entity_id=n.entity_id or n.id,
            name=n.label,
            entity_type=n.type,
            wind_code=n.wind_code,
            mock=n.mock,
            source_system=n.source_system,
        )
        for n in graph.nodes
    ]
    edges = [
        EquityEdgeDTO(
            id=e.relationship_id or "",
            source=e.source,
            target=e.target,
            relation_type=e.relation,
            ownership_pct=e.effective_ownership_pct(),
            relationship_id=e.relationship_id,
            source_record_id=e.source_record_id,
            report_period=e.report_period,
            ann_dt=e.ann_dt,
            is_latest=e.is_latest,
            mock=e.mock,
            source_system=e.source_system,
        )
        for e in graph.edges
    ]
    paths = []
    for i, chain in enumerate(graph.control_chains):
        paths.append(
            EquityPathDTO(
                path_id=f"path_{i:03d}",
                node_ids=chain.path,
                edge_ids=chain.edge_ids,
                depth=chain.depth,
                final_control_pct=chain.effective_control_pct(),
                path_type=chain.path_type,
                source_system=chain.source_system,
            )
        )
    return nodes, edges, paths


@router.get(
    "/companies/{code}/equity",
    response_model=V12Response[EquityResponseData],
)
async def get_company_equity(
    code: str = Path(..., description="公司代码，如 600518 或 600518.SH"),
    depth: int = Query(default=5, ge=1, le=10, description="穿透深度"),
    as_of: str | None = Query(default=None, description="数据截止日期 (YYYY-MM-DD)"),
    include_related: bool = Query(default=True, description="是否包含关联方"),
):
    """股权穿透 — 目标公司来自 MySQL，图来自 Neo4j/NetworkX."""
    trace_id = str(uuid.uuid4())

    # 8.09 审查：适配器边界规范化 as_of（YYYY-MM-DD / YYYYQn → YYYYMMDD），
    # 无法解析返回 422（不得静默返回空图）；Agent/报告与 REST 统一八位期次。
    from app.domain.finance.period import normalize_period

    norm_as_of = normalize_period(as_of) if as_of else None
    if as_of and norm_as_of is None:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_AS_OF: {as_of!r}（支持 YYYYMMDD / YYYY-MM-DD / YYYYQn）",
        )

    # 1. MySQL 解析公司（真实 entity_id/wind_code/sec_name）
    resolver = CompanyResolver()
    company = await resolver.resolve(code)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {code}")

    warning_items: list[WarningItem] = []
    data_warnings: list[str] = []
    partial = False

    # 2. 获取图数据
    use_neo4j = settings.GRAPH_BACKEND == "neo4j"
    graph: EquityGraph | None = None

    if use_neo4j:
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        adapter = Neo4jEquityGraph()
        if await adapter.check_connection():
            graph = await adapter.get_graph(
                company.wind_code,
                depth=depth,
                as_of=norm_as_of,
                graph_version=settings.GRAPH_VERSION,
            )
        else:
            # Neo4j 不可用：返回 partial + 空图，绝不降级 NetworkX 冒充
            msg = "Neo4j 不可用，本次股权查询返回空图（不降级 NetworkX）。"
            warning_items.append(
                WarningItem(
                    code="NEO4J_UNAVAILABLE",
                    message=msg,
                    module="equity",
                    recoverable=True,
                )
            )
            data_warnings.append(msg)
            partial = True
            graph = EquityGraph(
                company_id=company.entity_id,
                source_system="neo4j",
                graph_version=settings.GRAPH_VERSION,
                dataset_version=settings.DATASET_VERSION,
            )
    else:
        # Lite profile：明确使用 NetworkX 降级适配器
        from app.infrastructure.graph.networkx.equity_graph import (
            NetworkXEquityGraph,
        )

        adapter = NetworkXEquityGraph()
        graph = await adapter.get_graph(company.wind_code, depth=depth)
        warning_items.append(
            WarningItem(
                code="NETWORKX_LITE",
                message="Lite profile 使用 NetworkX 降级适配器。",
                module="equity",
                recoverable=True,
            )
        )
        data_warnings.append("lite networkx")

    try:
        nodes, edges, paths = _graph_to_dtos(graph)
    except Exception as exc:  # noqa: BLE001
        msg = f"图结果转换异常: {exc}"
        warning_items.append(
            WarningItem(
                code="GRAPH_DTO_ERROR",
                message=msg,
                module="equity",
                recoverable=False,
            )
        )
        data_warnings.append(msg)
        partial = True
        nodes, edges, paths = [], [], []

    # 上市公司节点显示名：Neo4j 的 canonical_name 为证券代码，统一替换为公司简称
    code_name_map: dict[str, str] = {}
    _code_nodes = [
        n
        for n in nodes
        if n.wind_code and re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", n.wind_code)
    ]
    if _code_nodes:
        try:
            from sqlalchemy import text

            from app.domain.finance._fetch import _get_engine

            _codes = sorted({n.wind_code for n in _code_nodes})
            _ph = ",".join([f":c{i}" for i in range(len(_codes))])
            _params = {f"c{i}": c for i, c in enumerate(_codes)}
            with _get_engine().connect() as _conn:
                _rows = _conn.execute(
                    text(
                        "SELECT wind_code, sec_name FROM companies "
                        f"WHERE wind_code IN ({_ph})"
                    ),
                    _params,
                ).fetchall()
            code_name_map = {str(r[0]): str(r[1]) for r in _rows if r[1]}
        except Exception:  # noqa: BLE001 — 名称替换失败不阻断图展示
            logger.warning("equity: 公司名映射失败，回退证券代码", exc_info=True)
        for _n in _code_nodes:
            if code_name_map.get(_n.wind_code):
                _n.name = code_name_map[_n.wind_code]

    # Phase D #12: 正式链路载荷（证据/风险标签/合并说明）
    # canonical evidence_id 映射 + 幂等落库：REST 画像返回的 evidence_ids
    # 可立即经 GET /evidence/{id} 回查（与 Agent 落库同一算法）
    equity_chains: list[EquityChainDTO] = []
    chain_warnings: list[str] = []
    try:
        graph_version = getattr(graph, "graph_version", "") or settings.GRAPH_VERSION
        # 证据标题用名映射（节点 ID → 显示名）：代码样式 label 用公司简称替换
        evidence_name_map: dict[str, str] = {}
        for n in graph.nodes:
            label = n.label or ""
            if label and re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", label):
                label = code_name_map.get(label) or n.wind_code or label
            evidence_name_map[n.id] = label
        try:
            _materialized, _conflicts = materialize_equity_evidence(
                edges=graph.edges,
                company_code=company.wind_code,
                graph_version=graph_version,
                trace_id=trace_id,
                node_name_map=evidence_name_map,
            )
        except Exception as exc:  # noqa: BLE001 — 证据落库失败不阻断链路
            logger.warning("equity: 证据落库失败: %s", exc, exc_info=True)
        node_name_map: dict[str, str] = {}
        for n in graph.nodes:
            label = n.label or ""
            if label and re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", label):
                label = code_name_map.get(label) or n.wind_code or label
            node_name_map[n.id] = label
        edge_evidence_map = build_edge_evidence_map(
            edges=graph.edges,
            company_code=company.wind_code,
            graph_version=graph_version,
        )
        chain_models, chain_warnings = build_equity_chains(
            company_code=company.wind_code,
            chains=graph.control_chains,
            node_name_map=node_name_map,
            graph_edges=graph.edges,
            # 8.09 审查：股东记录与图快照同期次（曾不传 as_of 导致链路
            # 与历史时点图不一致）
            top_shareholder_records=fetch_shareholder_records(
                company.wind_code, as_of=norm_as_of
            ),
            edge_evidence_map=edge_evidence_map,
            as_of=norm_as_of or "",
            source_system=getattr(graph, "source_system", "") or "unknown",
            merge_groups=[],
        )
        equity_chains = [EquityChainDTO(**c.to_dict()) for c in chain_models]
        if True:  # node risk guard
            # 缺口 #31：节点风险标签统一消费 canonical 链路风险等级，
            # 不再由前端按持股比例阈值自判（红/橙/黄优先级取高）。
            _risk_rank = {"red": 5, "orange": 4, "yellow": 3, "blue": 2, "green": 1}
            _node_risk: dict[str, str] = {}
            for _chain in equity_chains:
                if not _chain.node_ids or not _chain.risk_level:
                    continue
                if _chain.risk_level not in _risk_rank:
                    continue
                for _nid in _chain.node_ids:
                    _old = _node_risk.get(_nid)
                    if not _old or _risk_rank[_chain.risk_level] > _risk_rank.get(
                        _old, 0
                    ):
                        _node_risk[_nid] = _chain.risk_level
            for _node in nodes:
                if _node.id in _node_risk:
                    _node.risk_level = _node_risk[_node.id]
        data_warnings.extend(chain_warnings)
    except Exception as exc:  # noqa: BLE001 — 链路载荷失败不影响基础图
        logger.warning("equity_chains 构建失败: %s", exc, exc_info=True)
        data_warnings.append(f"股权链路载荷构建失败: {exc}")

    # 8.09 审查：路径截断时如实标记 partial + PATH_LIMIT_REACHED
    truncated = bool(getattr(graph, "truncated", False))
    if truncated:
        partial = True
        msg = "股权路径超过 200 条限制被截断，返回的是深链优先的前 200 条，非精确全集。"
        warning_items.append(
            WarningItem(
                code="PATH_LIMIT_REACHED",
                message=msg,
                module="equity",
                recoverable=False,
            )
        )
        data_warnings.append(msg)

    return V12Response(
        data=EquityResponseData(
            target=TargetCompanyDTO(
                entity_id=company.entity_id,
                wind_code=company.wind_code,
                name=company.sec_name,
            ),
            nodes=nodes,
            edges=edges,
            paths=paths,
            equity_chains=equity_chains,
            as_of=norm_as_of or as_of,
            graph_version=getattr(graph, "graph_version", "") or settings.GRAPH_VERSION,
            source_system=getattr(graph, "source_system", "") or "unknown",
            partial=partial,
            warnings=data_warnings,
            requested_depth=getattr(graph, "requested_depth", 0),
            max_observed_hops=getattr(graph, "max_observed_hops", 0),
            truncated=truncated,
            coverage_note=getattr(graph, "coverage_note", "") or "",
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=warning_items,
    )
