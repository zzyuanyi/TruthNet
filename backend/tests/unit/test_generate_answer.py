"""GenerateAnswer 节点单元测试 — V12 §7.2/§2.6 + Phase D #13.

覆盖：四层回答结构、risk_level 分级、追问生成（规则/缺失数据/缺失模块）、
company None、FinalResponse 字段透传、LLM 问答润色（Phase D #13）。
"""

import pytest

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


class _PassthroughProvider:
    """透传 provider：返回用户原文（等效不润色，供现有测试隔离真实 LLM）。"""

    provider_name = "test"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        return messages[-1]["content"]

    async def chat_stream(self, messages, **kwargs):
        yield await self.chat(messages, **kwargs)

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """所有 generate_answer 测试禁用真实 LLM：润色透传原文。

    Phase D #13 润色在节点内 create_llm_provider()，本地 deepseek key
    会导致每个测试真调 LLM。统一 patch 为透传 provider，
    润色专项测试再各自覆盖。
    """
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _PassthroughProvider(),
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
    """纯股权查询（finance 未执行）→ 不强行插入母公司口径说明。

    #11：equity 模式开场（"股权穿透分析完成"），非"综合分析完成"。
    """
    claims = [_claim("c1", "equity", "red", None)]
    state = _make_state(company=_company(), claims=claims)
    fr = generate_answer_node(state)["final_response"]
    assert "母公司报表" not in fr.answer
    assert "股权穿透分析完成" in fr.answer
    assert "发现 1 项股权风险信号" in fr.answer


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


def test_follow_up_adds_available_industry_percentile():
    claims = [_claim("c1", "financial", "orange", "R1")]
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered"},
            industry_benchmark={
                "industry_l1": "医药生物",
                "percentiles": {"r1_gap": 87.5},
            },
        )
    )
    follow_ups = generate_answer_node(
        _make_state(company=_company(), claims=claims, results=results)
    )["final_response"].follow_ups
    assert "查看应收-营收背离幅度的行业分位对比" in follow_ups


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


# ── Phase D #13: LLM 问答润色 ─────────────────────────────


class _FakeLLM:
    """可编程 fake provider：注入润色文本 / 抛异常 / 改关键信息。"""

    provider_name = "fake"
    result: str = ""
    raise_error: bool = False

    def __init__(self, result: str = "", raise_error: bool = False):
        self.result = result
        self.raise_error = raise_error

    async def chat(self, messages: list[dict], **kwargs) -> str:
        if self.raise_error:
            raise RuntimeError("LLM 服务不可用")
        return self.result or messages[-1]["content"]

    async def chat_stream(self, messages, **kwargs):
        yield await self.chat(messages, **kwargs)

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self) -> bool:
        return True


def _polish_state(monkeypatch, provider):
    """构造带触发规则明细 + 解读段（含【】标记）的 state，注入指定 LLM provider。

    #7：润色默认关闭——专项测试显式开启 ANSWER_POLISH_ENABLED。
    """
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: provider,
    )
    monkeypatch.setattr("app.core.config.settings.ANSWER_POLISH_ENABLED", True)
    rule_details = {
        "R1": {
            "rule_name": "应收-营收背离",
            "severity": "red",
            "explanation": "应收账款增速与营业收入增速存在显著背离",
            "current": {
                "acct_rcv_growth": {"value": 149.6, "unit": "percent"},
                "growth_gap": {"value": 166.2, "unit": "percentage_point"},
            },
        },
    }
    fin = FinanceResult(
        rule_statuses={"R1": "triggered"},
        rule_details=rule_details,
        interpretation="",
    )
    return _make_state(
        company=_company(),
        claims=[_claim("c1", "financial", "red", "R1")],
        results=ModuleResults(finance=fin),
    )


def test_polish_applies_when_key_facts_kept(monkeypatch):
    """LLM 返回流畅润色文本（关键信息一致、标记保留）→ 采用润色文本。"""
    polished = (
        "金牌家居（600518.SH）的综合分析已经完成。"
        "我们检测到 1 项风险信号。"
        "触发规则明细：R1 应收-营收背离（高风险）：应收账款增速 149.6%、"
        "增速差距 166.2pp。"
        "【预警点】应收异常。【数据对比】应收账款增速 149.6%。"
        "【可能模式】当前规则组合未匹配预定义模式，需进一步验证。"
        "【限制说明】分析基于母公司报表及当前数据覆盖范围，结果仅供参考。"
        "【重要说明】规则信号不等同于造假事实认定，需结合审计和监管文件核验，"
        "不构成投资建议。"  # 模板全部标记必须保留
    )
    state = _polish_state(monkeypatch, _FakeLLM(result=polished))
    answer = generate_answer_node(state)["final_response"].answer
    assert "综合分析已经完成" in answer  # 润色文本生效
    assert "R1 应收-营收背离（高风险）" in answer
    assert "149.6%" in answer


def test_polish_fallback_when_key_facts_changed(monkeypatch):
    """LLM 改动规则 ID/数值 → 回退模板原文。"""
    tampered = "分析完成，检测到 R2 触发（中风险），增速 50%。"  # R1→R2、149.6→50
    state = _polish_state(monkeypatch, _FakeLLM(result=tampered))
    answer = generate_answer_node(state)["final_response"].answer
    # 回退模板：保留原始 R1 / 149.6% / 166.2pp
    assert "R1 应收-营收背离（高风险）" in answer
    assert "149.6%" in answer
    assert "166.2pp" in answer
    assert "增速差距 50%" not in answer


def test_polish_fallback_when_llm_fails(monkeypatch):
    """LLM 抛异常 → 原样回退模板。"""
    state = _polish_state(monkeypatch, _FakeLLM(raise_error=True))
    answer = generate_answer_node(state)["final_response"].answer
    assert "R1 应收-营收背离（高风险）" in answer
    assert "149.6%" in answer
    assert "共检测到 1 项风险信号" in answer


def test_polish_rejects_deleted_markers(monkeypatch):
    """P1 回归：润色删除【】段落标记 → 回退模板。

    #7 后模板标记为【预警点】【数据对比】（pattern_matches 为空无
    【可能模式】）——回退后确定性标记必须齐全，且无标记的 LLM 文本不生效。
    """
    stripped = (
        "金牌家居综合分析完成，检测到1项风险信号。"
        "预警点：应收异常。可能模式：收入虚增。"  # 【】全删
    )
    state = _polish_state(monkeypatch, _FakeLLM(result=stripped))
    answer = generate_answer_node(state)["final_response"].answer
    assert "【预警点】" in answer, "标记被删应回退模板"
    assert "【数据对比】" in answer
    assert "预警点：应收异常" not in answer  # LLM 无标记文本未生效


def test_polish_skipped_for_company_none(monkeypatch):
    """公司未识别 → 不调 LLM，直接返回提示语。"""
    called = {"n": 0}

    class _CountingProvider(_FakeLLM):
        async def chat(self, messages, **kwargs):
            called["n"] += 1
            return "不应出现"

    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _CountingProvider(),
    )
    result = generate_answer_node(_make_state(company=None))
    assert "未能在数据覆盖范围内找到匹配的公司" in result["final_response"].answer
    assert called["n"] == 0, "company None 时不应调用 LLM"


# ── FinalResponse 字段透传 ─────────────────────────────────


def test_claims_and_evidence_passthrough():
    """claims/evidence 原样透传到 FinalResponse。"""
    claims = [_claim("c1", "financial", "red", "R1")]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))[
        "final_response"
    ]
    assert result.claims == claims
    assert result.evidence == []
