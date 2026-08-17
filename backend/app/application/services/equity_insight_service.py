"""股权穿透深挖服务 — Phase E 会2（8/16 会议整改第②条）.

职责：在已有确定性链路（equity_chain_service 的 risk_reasons/merge_explanation）
之上，新增两类「说明了什么」的隐含关系检测与解读：

1. cross_holding（交叉/环形持股）：有向持股图中长度 ≥2 的有向环
   （A→B→A 相互持股；A→B→C→A 环形持股）。
2. implicit_chain（隐含间接持股）：目标公司 2 跳及以上间接持股路径
   （X→…→T 中 X 通过若干中间实体间接持有 T），补充「链条每多一层，
   实际受益关系越难穿透」的解读。

约束（对齐会2 铁律：解读有数据依据、可回查）：
- 只输出基于真实图结构的检测结果，evidence_ids 来自边 relationship_id
  经 edge_evidence_map 映射的 canonical 证据（可经 GET /evidence/{id} 回查）；
- 措辞区分 path_type（持股关系 vs 明确控制证据），不得一律断言"控制"；
- 无检测结果返回空列表，不编造解读；
- 纯确定性逻辑，零 LLM、零外部依赖。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 交叉/环形持股 → 提醒级（治理观察项，非中高危欺诈信号；与
# equity_chain_service 的 concentrated_control=yellow 口径一致）
_CROSS_HOLDING_LEVEL: str = "yellow"
# 隐含持股链 3 层及以上 → 提醒级；2 层 → 正常（观察项）
_IMPLICIT_DEEP_LEVEL: str = "yellow"
_IMPLICIT_NORMAL_LEVEL: str = "green"

_MAX_CYCLE_DEPTH = 6
_MAX_INSIGHTS = 12


class EquityInsight(BaseModel):
    """单条隐含关系解读（结构化 + 可回查证据）。"""

    insight_id: str = Field(..., description="洞察 ID")
    insight_type: Literal["cross_holding", "implicit_chain"] = Field(
        ..., description="洞察类型"
    )
    title: str = Field(..., description="标题")
    detail: str = Field(..., description="解读文案（有数据依据）")
    entity_ids: list[str] = Field(default_factory=list, description="涉及节点 ID")
    entity_names: list[str] = Field(default_factory=list, description="涉及节点名称")
    path: list[str] = Field(default_factory=list, description="节点路径（名称）")
    edge_ids: list[str] = Field(default_factory=list, description="边 relationship_id")
    evidence_ids: list[str] = Field(
        default_factory=list, description="可回查 canonical 证据 ID"
    )
    risk_level: str = Field(default="green", description="风险等级")


def _node_name(node_id: str, node_name_map: dict[str, str]) -> str:
    return node_name_map.get(node_id, node_id)


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    """环的旋转等价去重：取以最小节点开头的旋转序列。"""
    if not cycle:
        return ()
    min_idx = min(range(len(cycle)), key=lambda i: (cycle[i], i))
    rotated = cycle[min_idx:] + cycle[:min_idx]
    return tuple(rotated)


def _find_cycles(
    adj: dict[str, list[Any]],
    start: str,
    max_depth: int,
) -> list[list[str]]:
    """从 start 出发的简单有向环（长度 2..max_depth，不含自环）。"""
    found: list[list[str]] = []
    path: list[str] = [start]
    on_path = {start}

    def _dfs(u: str, depth: int) -> None:
        for edge in adj.get(u, []):
            tgt = edge.target
            if tgt == start and len(path) >= 2:
                found.append(list(path))
            elif tgt not in on_path and depth < max_depth:
                path.append(tgt)
                on_path.add(tgt)
                _dfs(tgt, depth + 1)
                path.pop()
                on_path.remove(tgt)

    _dfs(start, 1)
    return found


def _cycle_edges(cycle: list[str], adj: dict[str, list[Any]]) -> list[Any]:
    """环路径上每条边（A→B→C→A：A→B、B→C、C→A）。"""
    edges: list[Any] = []
    n = len(cycle)
    for i in range(n):
        src = cycle[i]
        tgt = cycle[(i + 1) % n]
        for edge in adj.get(src, []):
            if edge.target == tgt:
                edges.append(edge)
                break
    return edges


def _cross_holding_insight(
    cycle: list[str],
    adj: dict[str, list[Any]],
    node_name_map: dict[str, str],
    edge_evidence_map: dict[str, str],
    company_code: str,
    idx: int,
) -> EquityInsight:
    names = [_node_name(n, node_name_map) for n in cycle]
    edges = _cycle_edges(cycle, adj)
    rel_ids = [e.relationship_id for e in edges if e.relationship_id]
    evidence_ids: list[str] = []
    for rid in rel_ids:
        canonical = edge_evidence_map.get(rid)
        if canonical and canonical not in evidence_ids:
            evidence_ids.append(canonical)

    arrow = "→".join(names + [names[0]])
    if len(cycle) == 2:
        title = "交叉持股关系"
        detail = (
            f"{names[0]} 与 {names[1]} 存在交叉持股（{arrow}），"
            "双方利益深度绑定，需关注一致行动可能性与治理透明度。"
        )
    else:
        title = "环形持股结构"
        detail = (
            f"{names[0]}、{names[1]} 等 {len(cycle)} 方形成环形持股（{arrow}），"
            "股权关系盘根错节，实际控制人识别与穿透核验成本高。"
        )
    return EquityInsight(
        insight_id=f"eqi_{company_code}_{idx:03d}",
        insight_type="cross_holding",
        title=title,
        detail=detail,
        entity_ids=list(cycle),
        entity_names=names,
        path=names,
        edge_ids=rel_ids,
        evidence_ids=evidence_ids,
        risk_level=_CROSS_HOLDING_LEVEL,
    )


def _implicit_chain_insight(
    chain: Any,
    node_name_map: dict[str, str],
    edge_evidence_map: dict[str, str],
    company_code: str,
    target_name: str,
    idx: int,
) -> EquityInsight:
    if isinstance(chain, dict):
        node_ids = chain.get("path") or chain.get("node_ids") or []
        edge_ids = chain.get("edge_ids") or []
        final_pct = chain.get("final_control_pct")
        if final_pct is None:
            final_pct = chain.get("effective_control_pct")
        path_type = str(chain.get("path_type") or "ownership")
    else:
        node_ids = list(chain.path)
        edge_ids = list(chain.edge_ids)
        final_pct = chain.effective_control_pct()
        path_type = str(getattr(chain, "path_type", None) or "ownership")

    depth = max(0, len(edge_ids))
    if depth < 2:
        return None  # 非隐含（直接持股）不产出

    names = [_node_name(n, node_name_map) for n in node_ids]
    evidence_ids: list[str] = []
    for rid in edge_ids:
        canonical = edge_evidence_map.get(rid)
        if canonical and canonical not in evidence_ids:
            evidence_ids.append(canonical)

    # 比例缺失或为 0（图数据未算持股乘积）时不展示「累计 0.00%」
    pct_text = ""
    if final_pct is not None and float(final_pct) > 0:
        pct_text = f"（累计 {float(final_pct):.2f}%）"
    rel_term = "控制" if path_type == "control" else "持股"
    top = names[0] if names else "上游主体"
    middle = names[1:-1] or []
    target = target_name or (names[-1] if names else "目标公司")
    if middle:
        structure = f"通过 {('、'.join(middle))} 等 {len(middle)} 层中间实体"
    else:
        structure = f"通过 {names[1] if len(names) > 1 else '中间实体'} 等 1 层中间实体"

    title = f"{top} 间接{rel_term} {target}"
    detail = (
        f"{top}{structure}间接{rel_term}{target}{pct_text}，"
        f"链条深度 {depth} 层（{('→'.join(names))}），每多一层中间实体，"
        "实际受益关系越难穿透核验。"
    )
    return EquityInsight(
        insight_id=f"eqi_{company_code}_{idx:03d}",
        insight_type="implicit_chain",
        title=title,
        detail=detail,
        entity_ids=node_ids,
        entity_names=names,
        path=names,
        edge_ids=list(edge_ids),
        evidence_ids=evidence_ids,
        risk_level=(_IMPLICIT_DEEP_LEVEL if depth >= 3 else _IMPLICIT_NORMAL_LEVEL),
    )


def build_equity_insights(
    *,
    graph: Any,
    node_name_map: dict[str, str],
    edge_evidence_map: dict[str, str],
    company_code: str,
    target_name: str = "",
) -> list[EquityInsight]:
    """构建隐含关系解读列表（会2）。

    Args:
        graph: EquityGraph（nodes/edges/control_chains）。
        node_name_map: 节点 ID → 显示名（含代码节点替换公司简称）。
        edge_evidence_map: {relationship_id: canonical evidence_id}。
        company_code: 目标公司代码（insight_id 前缀）。
        target_name: 目标公司显示名。

    Returns:
        list[EquityInsight]：交叉持股 + 隐含持股链解读；无结果返回空。
    """
    if graph is None:
        return []
    edges = list(getattr(graph, "edges", None) or [])
    if not edges:
        return []
    max_depth = int(getattr(graph, "requested_depth", 0) or 5)
    max_depth = max(2, min(max_depth, _MAX_CYCLE_DEPTH))

    adj: dict[str, list[Any]] = defaultdict(list)
    for edge in edges:
        src = edge.source
        if src:
            adj[src].append(edge)

    insights: list[EquityInsight] = []

    # 1. 交叉/环形持股（有向环，去重）
    seen_cycles: set[tuple[str, ...]] = set()
    for start in sorted(adj):
        for cycle in _find_cycles(adj, start, max_depth):
            canonical = _canonical_cycle(cycle)
            if canonical in seen_cycles:
                continue
            seen_cycles.add(canonical)
            insights.append(
                _cross_holding_insight(
                    list(canonical),
                    adj,
                    node_name_map,
                    edge_evidence_map,
                    company_code,
                    len(insights),
                )
            )
            if len(insights) >= _MAX_INSIGHTS:
                return insights

    # 2. 隐含持股链解读（复用已有 control_chains 的多跳路径）
    chains = list(getattr(graph, "control_chains", None) or [])
    for chain in chains:
        insight = _implicit_chain_insight(
            chain,
            node_name_map,
            edge_evidence_map,
            company_code,
            target_name,
            len(insights),
        )
        if insight is not None:
            insights.append(insight)
            if len(insights) >= _MAX_INSIGHTS:
                break

    return insights
