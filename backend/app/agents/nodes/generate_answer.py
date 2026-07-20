"""GenerateAnswer — V12 §7.2. Mock: return fixed text."""

from app.agents.state import AgentState, FinalResponse


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])

    if company is None:
        return {
            "final_response": FinalResponse(
                answer="未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。",
                risk_level="unknown",
            )
        }

    triggered = [c for c in claims if c.severity == "red"]
    answer = (
        f"{company.sec_name}（{company.wind_code}）综合分析完成。"
        f"共检测到 {len(triggered)} 项高风险信号。"
    )
    if triggered:
        answer += " 详情请查看企业画像页。"

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level="red" if triggered else "unknown",
            claims=claims,
            follow_ups=[
                "查看应收账款近8季度趋势",
                "查看实控人控制的其他上市公司",
                "对比同行业应收增速分位",
            ],
        )
    }
