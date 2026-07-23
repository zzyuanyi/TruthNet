"""股权穿透路由 — V12 §11.

GET /api/v1/companies/{code}/equity
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

router = APIRouter(tags=["equity"])


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
    """股权穿透 — 返回目标公司向上穿透的股东、控制链和持股比例.

    支持 lite (NetworkX) 和 full (Neo4j) Profile。
    """
    trace_id = str(uuid.uuid4())

    # 规范化公司代码
    from app.infrastructure.graph.normalizer import extract_wind_code_suffix

    code_6, suffix = extract_wind_code_suffix(code)
    resolved_code = code_6 if code_6 else code

    # 检查公司是否存在（使用 companies 路由的 mock 数据）
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    company = next(
        (c for c in _MOCK_COMPANIES if c["code"] == resolved_code),
        None,
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {code}")

    warning_items: list[WarningItem] = []
    data_warnings: list[str] = []
    partial = False

    # 获取 Graph Adapter（依赖注入简化版）
    from app.core.config import settings

    try:
        if settings.GRAPH_BACKEND == "neo4j":
            from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

            adapter = Neo4jEquityGraph()
            if await adapter.check_connection():
                graph = await adapter.get_graph(resolved_code, depth=depth)
            else:
                # 降级到 NetworkX
                msg = "Neo4j 不可用，降级到 NetworkX"
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
                from app.infrastructure.graph.networkx.equity_graph import (
                    NetworkXEquityGraph,
                )

                adapter = NetworkXEquityGraph()
                graph = await adapter.get_graph(resolved_code, depth=depth)
        else:
            from app.infrastructure.graph.networkx.equity_graph import (
                NetworkXEquityGraph,
            )

            adapter = NetworkXEquityGraph()
            graph = await adapter.get_graph(resolved_code, depth=depth)
    except Exception as exc:
        msg = f"图查询异常: {exc}"
        warning_items.append(
            WarningItem(
                code="GRAPH_QUERY_ERROR",
                message=msg,
                module="equity",
                recoverable=False,
            )
        )
        data_warnings.append(msg)
        partial = True
        graph = None

    # 构建响应
    nodes: list[EquityNodeDTO] = []
    edges: list[EquityEdgeDTO] = []
    paths: list[EquityPathDTO] = []

    if graph:
        for n in graph.nodes:
            nodes.append(
                EquityNodeDTO(
                    id=n.id,
                    entity_id=n.id,
                    name=n.label,
                    entity_type=n.type,
                    mock=False,
                )
            )
        for e in graph.edges:
            edges.append(
                EquityEdgeDTO(
                    source=e.source,
                    target=e.target,
                    relation_type=e.relation,
                    ownership_pct=(
                        e.stake_ratio * 100 if e.stake_ratio is not None else None
                    ),
                )
            )
        for i, chain in enumerate(graph.control_chains):
            paths.append(
                EquityPathDTO(
                    path_id=f"path_{i:03d}",
                    node_ids=chain.path,
                    edge_ids=[],
                    depth=chain.depth,
                    final_control_pct=chain.total_stake,
                    path_type="control",
                )
            )

    return V12Response(
        data=EquityResponseData(
            target=TargetCompanyDTO(
                entity_id=f"company_{resolved_code}",
                wind_code=f"{resolved_code}{suffix or ''}",
                name=company.get("short_name") or company.get("name", resolved_code),
            ),
            nodes=nodes,
            edges=edges,
            paths=paths,
            as_of=as_of,
            graph_version="equity-mock-v12",
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
