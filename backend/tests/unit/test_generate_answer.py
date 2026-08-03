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


# ── Phase C: 母公司口径措辞 ────────────────────────────────


def _finance_state(rule_statuses, warnings=None, claims=None, company=None):
    """构造 finance 已执行的 state。"""
    fin = FinanceResult(
        rule_statuses=rule_statuses,
        warnings=warnings or [],
        evidence=[],
    )
    return _make_state(
        company=company or _company(),
        claims=claims or [],
        results=ModuleResults(finance=fin),
    )


def test_no_risk_finance_executed_parent_scope_wording():
    """Finance 执行且无风险 → 明确"母公司报表及当前数据覆盖范围"。"""
    claims = [_claim("c1", "financial", "green", None)]
    state = _finance_state(rule_statuses={"R1": "not_triggered"}, claims=claims)
    fr = generate_answer_node(state)["final_response"]
    assert "在母公司报表及当前数据覆盖范围内，未发现明显异常信号。" in fr.answer


def test_risk_finance_executed_parent_scope_wording():
    """Finance 执行且有风险 → 结论带"基于母公司报表及当前数据覆盖"。"""
    claims = [_claim("c1", "financial", "red", "R1")]
    state = _finance_state(rule_statuses={"R1": "triggered"}, claims=claims)
    fr = generate_answer_node(state)["final_response"]
    assert "基于母公司报表及当前数据覆盖" in fr.answer
    assert "共检测到 1 项风险信号" in fr.answer


def test_pure_equity_no_parent_scope_forced():
    """纯股权查询（finance 未执行）→ 不强行插入母公司口径说明。"""
    claims = [_claim("c1", "equity", "red", None)]
    state = _make_state(company=_company(), claims=claims)
    fr = generate_answer_node(state)["final_response"]
    assert "母公司报表" not in fr.answer
    assert "共检测到 1 项风险信号" in fr.answer


def test_unknown_company_type_no_false_no_risk():
    """公司类型未知 → 不得输出"未发现风险"，明确数据不足。"""
    state = _finance_state(
        rule_statuses={f"R{i}": "insufficient_data" for i in range(1, 8)},
        warnings=["公司类型缺失，无法判断是否适用非金融财务规则，规则未执行"],
    )
    fr = generate_answer_node(state)["final_response"]
    assert "公司类型信息缺失" in fr.answer
    assert "无法确认是否存在财务风险" in fr.answer
    assert "未发现明显异常信号" not in fr.answer


def test_forbidden_phrases_absent():
    """禁止出现"集团整体没有风险 / 未发现任何风险 / 公司不存在财务风险"。"""
    claims = [_claim("c1", "financial", "green", None)]
    state = _finance_state(rule_statuses={"R1": "not_triggered"}, claims=claims)
    answer = generate_answer_node(state)["final_response"].answer
    for forbidden in ("集团整体没有风险", "未发现任何风险", "公司不存在财务风险"):
        assert forbidden not in answer


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


# ── 规则明细（rule_details 展开） ──────────────────────────


def _rule_state(rule_details, rule_statuses=None, claims=None):
    """构造带 rule_details 的 state（finance 已执行）。"""
    fin = FinanceResult(
        rule_statuses=rule_statuses or {rid: "triggered" for rid in rule_details},
        rule_details=rule_details,
    )
    return _make_state(
        company=_company(),
        claims=claims or [_claim("c1", "financial", "red", "R1")],
        results=ModuleResults(finance=fin),
    )


def test_rule_details_only_triggered():
    """只展示 triggered 规则：R2 not_triggered 不出现在明细。"""
    rule_details = {
        "R1": {
            "rule_name": "应收-营收背离",
            "severity": "red",
            "current": {
                "acct_rcv_growth": {"value": 149.6, "unit": "percent"},
            },
        },
        "R2": {
            "rule_name": "现金流-利润背离",
            "severity": "orange",
            "current": {
                "cf_to_profit_ratio": {"value": -21.6, "unit": "ratio"},
            },
        },
    }
    state = _rule_state(
        rule_details,
        rule_statuses={"R1": "triggered", "R2": "not_triggered"},
    )
    answer = generate_answer_node(state)["final_response"].answer
    assert "R1 应收-营收背离（高风险）" in answer
    assert "现金流-利润背离" not in answer


def test_rule_details_units():
    """百分比 / pp / 季度 / 天数单位正确，bool 指标用是/否。"""
    rule_details = {
        "R1": {
            "rule_name": "应收-营收背离",
            "severity": "red",
            "current": {
                "acct_rcv_growth": {"value": 149.6, "unit": "percent"},
                "growth_gap": {"value": 166.2, "unit": "percentage_point"},
                "consec_neg_cf": {"value": 2, "unit": "quarters"},
                "inventory_turnover_days": {"value": 20, "unit": "days"},
                "oth_rcv_large": {"value": True, "unit": ""},
            },
        },
    }
    answer = generate_answer_node(_rule_state(rule_details))["final_response"].answer
    assert "应收账款增速 149.6%" in answer
    assert "增速差距 166.2pp" in answer
    assert "连续负现金流季度 2个季度" in answer
    assert "存货周转天数 20天" in answer
    assert "存在大额其他应收款：是" in answer


def test_rule_details_none_value_skipped():
    """空值指标不输出（不得出现 None%）。"""
    rule_details = {
        "R1": {
            "rule_name": "应收-营收背离",
            "severity": "red",
            "current": {
                "acct_rcv_growth": {"value": None, "unit": "percent"},
                "oper_rev_growth": {"value": -16.6, "unit": "percent"},
            },
        },
    }
    answer = generate_answer_node(_rule_state(rule_details))["final_response"].answer
    assert "None" not in answer
    assert "营业收入增速 -16.6%" in answer


def test_rule_details_no_metrics_no_section():
    """无 rule_details 数据 → 不追加"触发规则明细"；
    空 current → 仍展示规则名+等级（指标部分省略）。"""
    # 空 current：规则名+等级保留，指标部分省略
    state_empty_current = _rule_state(
        {"R1": {"rule_name": "应收-营收背离", "severity": "red", "current": {}}}
    )
    answer_empty = generate_answer_node(state_empty_current)["final_response"].answer
    assert "触发规则明细：R1 应收-营收背离（高风险）。" in answer_empty

    # 无 rule_details：完全不追加明细段
    state_no_details = _make_state(
        company=_company(), claims=[_claim("c1", "financial", "red", "R1")]
    )
    assert (
        "触发规则明细"
        not in generate_answer_node(state_no_details)["final_response"].answer
    )


# ── FinalResponse 字段透传 ─────────────────────────────────


def test_claims_and_evidence_passthrough():
    """claims/evidence 原样透传到 FinalResponse。"""
    claims = [_claim("c1", "financial", "red", "R1")]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert result.claims == claims
    assert result.evidence == []
