"""ValidateEvidenceAndSchema — V12 §7.2. 验证 Claim 的 evidence 引用完整性。

Bug fix:
  - 不仅检查 evidence_ids 非空，还验证每个 ID 真实存在
  - 缺证据的 Claim 降级为 unsupported
  - 将问题写入 warnings
"""

from app.agents.state import AgentState


def validate_evidence_node(state: AgentState) -> dict:
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])

    # 建立 evidence ID 索引
    evidence_ids: set[str] = set()
    for ev in evidence:
        if hasattr(ev, "evidence_id"):
            evidence_ids.add(ev.evidence_id)

    issues: list[str] = []

    for claim in claims:
        if not claim.evidence_ids:
            # 无 evidence 引用 → 降级
            claim.verification_status = "unsupported"
            claim.limitations.append("缺少证据引用")
            issues.append(f"{claim.claim_id}: 无 evidence_ids 引用")
        else:
            # 检查每个 evidence_id 是否存在
            missing = [eid for eid in claim.evidence_ids if eid not in evidence_ids]
            if missing:
                claim.verification_status = "partial"
                claim.limitations.append(f"缺失证据: {', '.join(missing)}")
                issues.append(f"{claim.claim_id}: 引用了不存在的证据 {missing}")
            else:
                claim.verification_status = "verified"

    runtime = state.get("runtime")
    if runtime and issues and hasattr(runtime, "warnings"):
        runtime.warnings.extend(issues)

    # claims 已由 build_claims 写入 state，本节点仅原地修改 verification_status；
    # 返回空增量（a + [] = a），避免拼接 reducer 下 claims 翻倍。
    return {
        "claims": [],
        "runtime": runtime,
    }
