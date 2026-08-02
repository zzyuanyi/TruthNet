"""ValidateEvidenceAndSchema — V12 §7.2 + Phase C 任务 16.

内存验证增强：
  - claim_id 唯一检查；
  - evidence_id 唯一 + 同 ID 不同内容判冲突；
  - source_record_id 非空；
  - source_type 合法；
  - Claim 引用不存在时 partial/unsupported；
  - 返回稳定 ProvenanceValidationReport。
"""

from app.agents.state import AgentState, EvidenceRef
from app.domain.provenance.models import ProvenanceValidationReport

# 合法 evidence source_type（与 evidence_refs 注释 + 各模块产出对齐）
_VALID_SOURCE_TYPES = {
    "financial_statement",
    "ownership_record",
    "news_article",
    "regulation",
    "announcement",
    "neo4j_relationship",
    "event_cluster",
}


def _evidence_content_key(ev: EvidenceRef) -> str:
    """Evidence 内容指纹（同 ID 冲突判定）。"""
    return "|".join(
        [
            ev.source_type or "",
            ev.source_record_id or "",
            ev.field_path or "",
            ev.period or "",
            ev.value or "",
        ]
    )


def validate_evidence_node(state: AgentState) -> dict:
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])

    issues: list[str] = []
    evidence_ids: set[str] = set()
    duplicate_claim_ids: list[str] = []
    duplicate_evidence_ids: list[str] = []
    conflicting_ids: list[str] = []
    dangling_evidence_ids: list[str] = []
    evidence_content: dict[str, str] = {}
    seen_evidence_ids: set[str] = set()

    # ── evidence 唯一性 / 内容一致性 / 字段完整性 ─────────
    for ev in evidence:
        eid = ev.evidence_id
        if not eid:
            continue
        if eid in seen_evidence_ids:
            duplicate_evidence_ids.append(eid)
            # 同 ID 不同内容 → 冲突
            if evidence_content.get(eid) != _evidence_content_key(ev):
                conflicting_ids.append(eid)
        else:
            seen_evidence_ids.add(eid)
            evidence_content[eid] = _evidence_content_key(ev)
        evidence_ids.add(eid)
        if not ev.source_record_id:
            issues.append(f"{eid}: source_record_id 为空")
        if ev.source_type not in _VALID_SOURCE_TYPES:
            issues.append(f"{eid}: source_type 非法 {ev.source_type!r}")

    # ── claim 唯一性 / 引用完整性 ─────────────────────────
    seen_claim_ids: set[str] = set()
    for claim in claims:
        if claim.claim_id in seen_claim_ids:
            duplicate_claim_ids.append(claim.claim_id)
        seen_claim_ids.add(claim.claim_id)

        if not claim.evidence_ids:
            claim.verification_status = "unsupported"
            claim.limitations.append("缺少证据引用")
            issues.append(f"{claim.claim_id}: 无 evidence_ids 引用")
            continue

        missing = [eid for eid in claim.evidence_ids if eid not in evidence_ids]
        if missing:
            claim.verification_status = "partial"
            claim.limitations.append(f"缺失证据: {', '.join(missing)}")
            dangling_evidence_ids.extend(missing)
            issues.append(f"{claim.claim_id}: 引用了不存在的证据 {missing}")
        else:
            claim.verification_status = "verified"

    runtime = state.get("runtime")
    if runtime and issues:
        if hasattr(runtime, "warnings"):
            for issue in issues:
                if issue not in runtime.warnings:
                    runtime.warnings.append(issue)

    report = ProvenanceValidationReport(
        claim_count=len(claims),
        evidence_count=len(evidence),
        link_count=sum(len(c.evidence_ids) for c in claims),
        dangling_evidence_ids=sorted(set(dangling_evidence_ids)),
        duplicate_claim_ids=sorted(set(duplicate_claim_ids)),
        duplicate_evidence_ids=sorted(set(duplicate_evidence_ids)),
        conflicting_ids=sorted(set(conflicting_ids)),
        status="ok" if not issues else "issues",
    )

    # 写入 state 供持久化使用
    state["provenance_report"] = report

    # claims 已由 build_claims 写入 state，本节点仅原地修改 verification_status；
    # 返回空增量（a + [] = a），避免拼接 reducer 下 claims 翻倍。
    return {
        "claims": [],
        "runtime": runtime,
        "provenance_report": report,
    }
