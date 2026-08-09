"""股权链路创新闭环服务 — Phase D #12.

为股权控制链补充正式链路载荷：
  - evidence_ids：真实证据（Neo4j relationship_id / top_shareholders 来源记录）；
  - risk_label → risk_level 规范映射（复用单一映射函数，不各写一套）；
  - risk_reasons：可解释风险原因（链路层级过深/控制比例集中/多层中间实体/
    来源覆盖不足/比例不一致）；
  - merge_explanation：一致行动人合并说明（仅依据可解释、可回查的键合并）。

约束：
  - 不根据名称相似或常识擅自合并一致行动人；
  - 无可验证一致行动关系 → 返回未合并结果 + 明确 warning；
  - evidence_ids 必须来自真实记录，不得用 mock/随机 UUID。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# 单一映射函数：risk_label → canonical risk_level（全仓库唯一来源）
# 复用仓库既有等级口径：red/orange/yellow/green/unknown
_RISK_LABEL_TO_LEVEL: dict[str, str] = {
    "deep_chain": "yellow",  # 链路层级过深
    "concentrated_control": "orange",  # 最终控制比例集中
    "multi_layer_entity": "yellow",  # 多层中间实体
    "insufficient_source": "yellow",  # 来源覆盖不足
    "ownership_mismatch": "orange",  # 比例不一致（与 CV-NUM-02 呼应）
    "concerted_action": "orange",  # 一致行动关系
    "normal": "green",
}


def map_risk_level(risk_label: str | None) -> str:
    """risk_label → canonical risk_level（单一映射，禁止各处各写）。"""
    if not risk_label:
        return "green"
    return _RISK_LABEL_TO_LEVEL.get(risk_label, "yellow")


def default_risk_reasons(risk_label: str) -> list[str]:
    """风险标签 → 可解释风险原因（默认映射；调用方可追加具体依据）。"""
    _REASONS: dict[str, list[str]] = {
        "deep_chain": ["链路层级过深，实际控制关系难以穿透核实"],
        # 8.09 四轮审查：措辞中性化——ownership 路径是持股关系，比例集中
        # 只能说"持股集中"，不得断言"控制权集中"
        "concentrated_control": ["最终控制/持股比例集中，高度集中于少数主体"],
        "multi_layer_entity": ["存在多层中间实体，关联方识别成本高"],
        "insufficient_source": ["股权数据来源覆盖不足，链路完整性待核验"],
        "ownership_mismatch": ["不同来源持股比例存在偏差，需复核"],
        "concerted_action": ["存在一致行动关系，控制权需合并计算"],
        "normal": [],
    }
    return _REASONS.get(risk_label, [])


@dataclass
class EquityChainDTO:
    """正式股权链路载荷（Phase D #12，与 V12 paths 兼容扩展）。"""

    chain_id: str
    node_ids: list[str] = field(default_factory=list)
    path_names: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    depth: int = 0
    final_control_pct: float | None = None
    # 8.09 四轮审查：透传底层 path_type（ownership/control）——十大股东
    # 链路默认 ownership（持股关系），只有明确控制证据才标记 control；
    # 下游（Claim/回答/PDF）按 path_type 选择措辞，不得一律称"控制"。
    path_type: str = "ownership"
    evidence_ids: list[str] = field(default_factory=list)
    risk_label: str = "normal"
    risk_level: str = "green"
    risk_reasons: list[str] = field(default_factory=list)
    merge_explanation: str = ""
    merged_entity_ids: list[str] = field(default_factory=list)
    merge_key: str = ""
    merge_basis: str = ""
    source_system: str = "unknown"
    as_of: str = ""

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "node_ids": self.node_ids,
            "path_names": self.path_names,
            "edge_ids": self.edge_ids,
            "depth": self.depth,
            "final_control_pct": self.final_control_pct,
            "path_type": self.path_type,
            "evidence_ids": self.evidence_ids,
            "risk_label": self.risk_label,
            "risk_level": self.risk_level,
            "risk_reasons": self.risk_reasons,
            "merge_explanation": self.merge_explanation,
            "merged_entity_ids": self.merged_entity_ids,
            "merge_key": self.merge_key,
            "merge_basis": self.merge_basis,
            "source_system": self.source_system,
            "as_of": self.as_of,
        }


def _chain_evidence_ids(
    edge_ids: list[str],
    node_ids: list[str],
    graph_edges: list,
    top_shareholder_records: list[dict],
    edge_evidence_map: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """收集链路证据 ID——仅 canonical ev_* 可回查 ID（去重）。

    优先级：
      1. edge_evidence_map 将 relationship_id 转 canonical evidence_id
         （与 Agent 落库一致，可经 GET /evidence/{id} 回查）；
      2. graph_edges 自带 canonical evidence_id（兼容已带该字段的模型）。

    top_shareholder_records 仅用于比例比对，不再注入 evidence_ids
    （裸 source_record_id 无法通过 GET /evidence/{id} 回查）。

    Returns:
        (eids, unmatched_edge_ids)：无法映射为 canonical 的边由调用方转 warning。
    """
    eids: list[str] = []
    seen: set[str] = set()
    unmatched: list[str] = []
    edge_evidence_map = edge_evidence_map or {}

    # 1. 边 relationship_id → canonical evidence_id（优先）
    for eid in edge_ids:
        if not eid:
            continue
        canonical = edge_evidence_map.get(eid)
        if canonical and canonical not in seen:
            seen.add(canonical)
            eids.append(canonical)
        else:
            unmatched.append(eid)

    # 2. 图边自带 canonical evidence（兼容 Pydantic 模型与 dict）
    for edge in graph_edges:
        if isinstance(edge, dict):
            ev = edge.get("evidence_id")
        else:
            ev = getattr(edge, "evidence_id", None)
        if ev and ev.startswith("ev_") and ev not in seen:
            seen.add(ev)
            eids.append(ev)

    return eids[:20], unmatched  # 限制长度，避免超长载荷


def _derive_risk_label(
    *,
    depth: int,
    final_control_pct: float | None,
    node_ids: list[str],
    evidence_ids: list[str],
    source_system: str,
    ownership_mismatch: bool = False,
    path_type: str = "ownership",
) -> tuple[str, list[str]]:
    """依据可解释因素推导风险标签与原因。

    8.09 四轮审查：措辞随 path_type 区分——ownership 路径是持股关系，
    比例集中只能说"持股比例集中"，不得断言"控制权集中"（除非存在明确
    控制证据标记为 control）。
    """
    reasons: list[str] = []
    control_term = "最终控制" if path_type == "control" else "最终持股"
    # 8.09 五轮审查：深链原因措辞随 path_type——ownership 是持股关系，
    # 只能说"持股关系难以穿透核实"
    rel_term = "控制关系" if path_type == "control" else "持股关系"

    if depth >= 6:
        reasons.append(f"链路层级过深（depth≥6），实际{rel_term}难以穿透核实")
    if final_control_pct is not None and final_control_pct >= 50:
        reasons.append(f"{control_term}比例 {final_control_pct:.1f}% 集中（≥50%）")
    if len(node_ids) >= 8:
        reasons.append(f"链路包含 {len(node_ids)} 个节点，多层中间实体结构")
    if source_system != "neo4j":
        reasons.append(f"数据来源为 {source_system}，覆盖完整度待核验")
    if not evidence_ids:
        reasons.append("链路缺少可回查证据，来源覆盖不足")
    if ownership_mismatch:
        reasons.append("不同来源持股比例存在偏差，需复核")

    if ownership_mismatch:
        label = "ownership_mismatch"
    elif final_control_pct is not None and final_control_pct >= 50:
        label = "concentrated_control"
    elif depth >= 6:
        label = "deep_chain"
    elif len(node_ids) >= 8:
        label = "multi_layer_entity"
    elif not evidence_ids:
        label = "insufficient_source"
    else:
        label = "normal"

    return label, reasons


def build_equity_chains(
    *,
    company_code: str,
    chains: list[Any],
    node_name_map: dict[str, str],
    graph_edges: list[Any] | None = None,
    top_shareholder_records: list[dict] | None = None,
    edge_evidence_map: dict[str, str] | None = None,
    as_of: str = "",
    source_system: str = "unknown",
    merge_groups: list[dict] | None = None,
) -> tuple[list[EquityChainDTO], list[str]]:
    """将领域控制链升级为正式链路 DTO。

    Args:
        edge_evidence_map: {relationship_id: canonical evidence_id}，由调用方按
            equity_shareholder_service.make_equity_edge_evidence_id 构建（与 Agent
            落库一致）；缺省时无法映射的边从 evidence_ids 丢弃并输出 warning。

    Returns:
        (chains_dto, warnings)：warnings 包含合并/证据相关的审慎提示。
    """
    warnings: list[str] = []
    graph_edges = graph_edges or []
    top_shareholder_records = top_shareholder_records or []
    merge_groups = merge_groups or []
    merge_explanation = ""

    # 一致行动人合并：仅依据可回查键（图中明确的一致行动关系 / 配置 group key）
    if merge_groups:
        merged_ids = [g.get("entity_id") for g in merge_groups if g.get("entity_id")]
        merge_key = merge_groups[0].get("merge_key", "") if merge_groups else ""
        merge_basis = merge_groups[0].get("merge_basis", "") if merge_groups else ""
        merge_explanation = (
            f"按可回查键 '{merge_key}' 合并一致行动人（依据：{merge_basis}），"
            f"合并实体：{len(merged_ids)} 个"
        )
    elif any(
        (c.get("concerted_action") if isinstance(c, dict) else False) for c in chains
    ):
        merge_explanation = "图中存在明确一致行动关系标记，已按可回查键合并"
    else:
        warnings.append("缺少可验证一致行动关系，未进行一致行动人合并")

    # ownership mismatch 检测：链上边比例与最终控制比例一致性（由调用方传入标记）
    out: list[EquityChainDTO] = []
    for i, chain in enumerate(chains):
        if isinstance(chain, dict):
            node_ids = chain.get("path") or chain.get("node_ids") or []
            edge_ids = chain.get("edge_ids") or []
            depth = int(chain.get("depth") or 0)
            final_pct = chain.get("final_control_pct") or chain.get(
                "effective_control_pct"
            )
            path_names = chain.get("path_names") or [
                node_name_map.get(n, n) for n in node_ids
            ]
            # 8.09 四轮审查：透传底层 path_type（默认 ownership——持股关系，
            # 不得默认为 control）
            chain_path_type = str(chain.get("path_type") or "ownership")
        else:
            node_ids = list(chain.path)
            edge_ids = list(chain.edge_ids)
            depth = int(chain.depth)
            final_pct = chain.effective_control_pct()
            path_names = [node_name_map.get(n, n) for n in node_ids]
            chain_path_type = str(getattr(chain, "path_type", None) or "ownership")

        evidence_ids, unmatched = _chain_evidence_ids(
            edge_ids=edge_ids,
            node_ids=node_ids,
            graph_edges=graph_edges,
            top_shareholder_records=top_shareholder_records,
            edge_evidence_map=edge_evidence_map,
        )
        if unmatched:
            warnings.append(
                f"链路 chain_{company_code}_{i:03d} 有 {len(unmatched)} 条边"
                "无法映射为可回查证据 ID，已从 evidence_ids 丢弃"
            )

        # 比例一致性：MySQL 股东表 vs Neo4j 边（按链路顶层股东名称匹配后比较）
        ownership_mismatch = False
        if path_names and top_shareholder_records:
            top_holder_name = path_names[0]
            for rec in top_shareholder_records:
                rec_name = rec.get("holder_name") or ""
                rec_pct = rec.get("pct")
                if not rec_name or rec_pct is None:
                    continue
                # 名称匹配（含归一化宽松匹配）才比较——避免任意股东比例误判
                if rec_name == top_holder_name or (
                    rec_name
                    and top_holder_name
                    and (rec_name in top_holder_name or top_holder_name in rec_name)
                ):
                    if (
                        abs(
                            float(rec_pct)
                            - (float(final_pct) if final_pct is not None else 0.0)
                        )
                        > settings.CV_NUM_02_OWNERSHIP_TOLERANCE
                    ):
                        ownership_mismatch = True
                        break

        risk_label, risk_reasons = _derive_risk_label(
            depth=depth,
            final_control_pct=float(final_pct) if final_pct is not None else None,
            node_ids=node_ids,
            evidence_ids=evidence_ids,
            source_system=source_system,
            ownership_mismatch=ownership_mismatch,
            path_type=chain_path_type,
        )

        out.append(
            EquityChainDTO(
                chain_id=f"chain_{company_code}_{i:03d}",
                node_ids=node_ids,
                path_names=path_names,
                edge_ids=edge_ids,
                depth=depth,
                final_control_pct=float(final_pct) if final_pct is not None else None,
                path_type=chain_path_type,
                evidence_ids=evidence_ids,
                risk_label=risk_label,
                risk_level=map_risk_level(risk_label),
                risk_reasons=risk_reasons,
                merge_explanation=merge_explanation,
                merged_entity_ids=(
                    [g.get("entity_id") for g in merge_groups if g.get("entity_id")]
                    if merge_groups
                    else []
                ),
                merge_key=merge_groups[0].get("merge_key", "") if merge_groups else "",
                merge_basis=merge_groups[0].get("merge_basis", "")
                if merge_groups
                else "",
                source_system=source_system,
                as_of=as_of,
            )
        )

    return out, warnings
