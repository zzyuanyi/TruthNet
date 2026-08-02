"""股权穿透路由 — V12 §11 + Phase C 真实图谱.

GET /api/v1/companies/{code}/equity

Full profile 流程：
  code → CompanyResolver（MySQL 真实画像）→ Neo4jEquityGraph（真实边/路径）。
  Neo4j 不可用时返回 partial=true + NEO4J_UNAVAILABLE + 空图，绝不降级 NetworkX 冒充。
Lite profile 使用 NetworkX（明确降级适配器）。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.equity import (
    EquityEdgeDTO,
    EquityNodeDTO,
    EquityPathDTO,
    EquityResponseData,
    TargetCompanyDTO,
)
from app.application.services.company_resolver import CompanyResolver
from app.core.config import settings
from app.domain.equity.models import EquityGraph

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
            graph = await adapter.get_graph(company.wind_code, depth=depth, as_of=as_of)
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
            as_of=as_of,
            graph_version=getattr(graph, "graph_version", "") or settings.GRAPH_VERSION,
            source_system=getattr(graph, "source_system", "") or "unknown",
            partial=partial,
            warnings=data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=warning_items,
    )
