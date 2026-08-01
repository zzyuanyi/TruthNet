"""GenerateAnswer 节点单元测试 — V12 §7.2/§2.6.

覆盖：四层回答结构、risk_level 分级、追问生成（规则/缺失数据/缺失模块）、
company None、FinalResponse 字段透传。
"""

from app.agents.nodes.generate_answer import generate_answer_node
from app.agents.state import (
    AgentState,
    Claim,
    CompanyRef,
    ExecutionPlan,
    FinanceResult,
    ModuleResults,
    ModuleStatus,
    RuntimeState,
)


def _company(name: str = "康美药业", code: str = "600518.SH") -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code.replace('.', '_')}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
    )


def _claim(
    claim_id: str,
    claim_type: str = "financial",
    severity: str = "red",
    rule_id: str | None = "R1",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=f"{claim_id} 结论",
        claim_type=claim_type,
        severity=severity,
        rule_id=rule_id,
        evidence_ids=["ev_01"],
    )


def _make_state(
    company: CompanyRef | None = None,
    claims: list | None = None,
    plan: ExecutionPlan | None = None,
    module_status: dict | None = None,
    results: ModuleResults | None = None,
) -> AgentState:
    return {
        "user_query": "测试",
        "company": company,
        "claims": claims or [],
        "evidence": [],
        "plan": plan,
        "module_status": module_status or {},
        "results": results or ModuleResults(),
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


# ── company None ────────────────────────────────────────────


def test_company_none():
    """公司未识别 → 提示语 + unknown。"""
    result = generate_answer_node(_make_state(company=None))
    fr = result["final_response"]
    assert "未能在数据覆盖范围内找到匹配的公司" in fr.answer
    assert fr.risk_level == "unknown"
    assert fr.claims == []
    assert fr.evidence == []


# ── 四层回答结构 ────────────────────────────────────────────


def test_four_layer_structure():
    """有 claims → 结论 + 三类信号摘要 + 追问。"""
    claims = [
        _claim("c1", "financial", "red", "R1"),
        _claim("c2", "financial", "orange", "R2"),
        _claim("c3", "equity", "red", None),
        _claim("c4", "event", "orange", None),
    ]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))
    fr = result["final_response"]

    # ① 一句话结论
    assert "康美药业（600518.SH）综合分析完成" in fr.answer
    assert "共检测到 4 项风险信号" in fr.answer

    # ② 三类核心信号摘要
    assert "财务维度检测到 2 项规则信号（R1、R2）" in fr.answer
    assert "股权维度发现 1 条控制链" in fr.answer
    assert "事件维度存在 1 项信号" in fr.answer

    # ④ 追问：equity/event claim 触发对应追问
    assert "查看实控人控制的其他上市公司" in fr.follow_ups
    assert "查看公司事件时间线" in fr.follow_ups


def test_no_risk_signal_conclusion():
    """无风险信号 claim → "未发现明显异常" + green。"""
    claims = [_claim("c1", "financial", "green", None)]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))
    fr = result["final_response"]
    assert "未发现明显异常信号" in fr.answer
    assert fr.risk_level == "green"


# ── risk_level 分级 ─────────────────────────────────────────


def test_risk_level_red():
    """存在 red claim → red。"""
    claims = [_claim("c1", "financial", "orange"), _claim("c2", "financial", "red")]
    fr = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert fr.risk_level == "red"


def test_risk_level_orange():
    """最高 orange → orange。"""
    claims = [_claim("c1", "financial", "orange")]
    fr = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert fr.risk_level == "orange"


def test_risk_level_unknown_when_no_claims():
    """无 claims → unknown。"""
    fr = generate_answer_node(_make_state(company=_company(), claims=[]))[
        "final_response"
    ]
    assert fr.risk_level == "unknown"


# ── 追问生成 ────────────────────────────────────────────────


def test_follow_up_rule_triggered():
    """R1 触发 → 应收账款趋势追问。"""
    claims = [_claim("c1", "financial", "red", "R1")]
    fr = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert "查看应收账款近 8 季度趋势" in fr.follow_ups


def test_follow_up_insufficient_data():
    """R5 insufficient_data → 费用明细追问（缺失数据维度）。"""
    results = ModuleResults(
        finance=FinanceResult(rule_statuses={"R5": "insufficient_data"})
    )
    fr = generate_answer_node(_make_state(company=_company(), results=results))[
        "final_response"
    ]
    assert "查看费用明细数据" in fr.follow_ups


def test_follow_up_missing_module():
    """plan 请求 events 但 skipped → 事件时间线追问（缺失模块维度）。"""
    plan = ExecutionPlan(requested_modules=["finance", "events"])
    module_status = {"events": ModuleStatus(state="skipped")}
    fr = generate_answer_node(
        _make_state(company=_company(), plan=plan, module_status=module_status)
    )["final_response"]
    assert "查看公司事件时间线" in fr.follow_ups


def test_follow_up_partial_module():
    """plan 请求 events 但 partial → 事件时间线追问（P2-1 回归）。"""
    plan = ExecutionPlan(requested_modules=["finance", "events"])
    module_status = {"events": ModuleStatus(state="partial")}
    fr = generate_answer_node(
        _make_state(company=_company(), plan=plan, module_status=module_status)
    )["final_response"]
    assert "查看公司事件时间线" in fr.follow_ups


def test_follow_up_dedup():
    """同一追问多条件触发 → 只出现一次。"""
    claims = [_claim("c4", "event", "orange", None)]
    plan = ExecutionPlan(requested_modules=["events"])
    module_status = {"events": ModuleStatus(state="skipped")}
    fr = generate_answer_node(
        _make_state(
            company=_company(),
            claims=claims,
            plan=plan,
            module_status=module_status,
        )
    )["final_response"]
    assert fr.follow_ups.count("查看公司事件时间线") == 1


def test_follow_up_fallback():
    """无任何触发 → 兜底追问。"""
    fr = generate_answer_node(_make_state(company=_company()))["final_response"]
    assert fr.follow_ups == ["查看企业画像详情"]


# ── FinalResponse 字段透传 ─────────────────────────────────


def test_claims_and_evidence_passthrough():
    """claims/evidence 原样透传到 FinalResponse。"""
    claims = [_claim("c1", "financial", "red", "R1")]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert result.claims == claims
    assert result.evidence == []
