"""股权穿透路由 — V12 §11 + Phase C 真实图谱 + Phase D #12 链路载荷.

GET /api/v1/companies/{code}/equity

Full profile 流程：
  code → CompanyResolver（MySQL 真实画像）→ Neo4jEquityGraph（真实边/路径）。
  Neo4j 不可用时返回 partial=true + NEO4J_UNAVAILABLE + 空图，绝不降级 NetworkX 冒充。
Lite profile 使用 NetworkX（明确降级适配器）。
"""

import logging
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
from app.core.config import settings
from app.domain.equity.models import EquityGraph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["equity"])


def _fetch_shareholder_records(wind_code: str) -> list[dict]:
    """读取 MySQL top_shareholders 最新记录（供链路证据回查与比例比对）。"""
    try:
        from app.domain.finance._fetch import _get_engine
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT s_holder_name, s_holder_pct, report_period, "
                        "source_record_id FROM top_shareholders "
                        "WHERE wind_code = :c ORDER BY report_period DESC LIMIT 20"
                    ),
                    {"c": wind_code},
                )
                .mappings()
                .fetchall()
            )
        return [
            {
                "holder_name": r["s_holder_name"],
                "pct": r["s_holder_pct"],
                "report_period": str(r["report_period"] or ""),
                "source_record_id": r["source_record_id"],
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001 — 股东记录读取失败不影响链路基础数据
        logger.warning("equity: top_shareholders 读取失败", exc_info=True)
        return []


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

    # Phase D #12: 正式链路载荷（证据/风险标签/合并说明）
    equity_chains: list[EquityChainDTO] = []
    chain_warnings: list[str] = []
    try:
        node_name_map = {n.id: n.label for n in graph.nodes}
        chain_models, chain_warnings = build_equity_chains(
            company_code=company.wind_code,
            chains=graph.control_chains,
            node_name_map=node_name_map,
            graph_edges=graph.edges,
            top_shareholder_records=_fetch_shareholder_records(company.wind_code),
            as_of=as_of or "",
            source_system=getattr(graph, "source_system", "") or "unknown",
            merge_groups=[],
        )
        equity_chains = [EquityChainDTO(**c.to_dict()) for c in chain_models]
        data_warnings.extend(chain_warnings)
    except Exception as exc:  # noqa: BLE001 — 链路载荷失败不影响基础图
        logger.warning("equity_chains 构建失败: %s", exc, exc_info=True)
        data_warnings.append(f"股权链路载荷构建失败: {exc}")

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
