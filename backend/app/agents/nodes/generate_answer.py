"""GenerateAnswer — V12 §7.2. 生成最终回答。

Bug fix: 将 evidence 同步到 FinalResponse，避免证据丢失。
"""

from app.agents.state import AgentState, FinalResponse


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])

    if company is None:
        return {
            "final_response": FinalResponse(
                answer="未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。",
                risk_level="unknown",
                claims=[],
                evidence=[],
            )
        }

    triggered = [c for c in claims if c.severity == "red"]
    verified = [
        c for c in claims if getattr(c, "verification_status", "") == "verified"
    ]
    partial = [c for c in claims if getattr(c, "verification_status", "") == "partial"]
    unsupported = [
        c for c in claims if getattr(c, "verification_status", "") == "unsupported"
    ]

    answer_parts = [
        f"{company.sec_name}（{company.wind_code}）综合分析完成。",
        f"共检测到 {len(triggered)} 项高风险信号，",
        f"{len(verified)} 项已核实，{len(partial)} 项部分核实。",
    ]

    if unsupported:
        answer_parts.append(f" {len(unsupported)} 项因证据不足未予确认。")

    answer = "".join(answer_parts)
    if triggered:
        answer += " 详情请查看企业画像页。"

    # 动态 follow-ups（基于实际触发的规则）
    follow_ups = []
    if any(c.rule_id == "R1" for c in claims):
        follow_ups.append("查看应收账款近8季度趋势")
    if any(c.rule_id == "R2" for c in claims):
        follow_ups.append("查看经营现金流与净利润对比")
    if any(c.claim_type == "equity" for c in claims):
        follow_ups.append("查看实控人控制的其他上市公司")
    if any(c.claim_type == "event" for c in claims):
        follow_ups.append("查看公司事件时间线")
    if not follow_ups:
        follow_ups = ["查看企业画像详情"]

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level="red" if triggered else "unknown",
            claims=claims,
            evidence=evidence,
            follow_ups=follow_ups,
        )
    }
