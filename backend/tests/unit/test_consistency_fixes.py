"""13 项审查问题修复的单元测试 — 外部核查清单回归.

覆盖：
  #1 R7 简化/完整文案与 limitation
  #2 Claim severity 与规则引擎一致（非法值回退 unknown）
  #3 绿色控制链不计风险 / 非首条高风险链被识别 / 同链只生成一条
  #8 叶子风险计数（排除综合 risk Claim 与绿色链）
  #10 R7 动态追问（按 core_profit_available）
  #5 期次解析（parse_query_period）
  #6 搜索主题 Gate（意图词不参与匹配）
  #12 数值格式化（禁止长浮点）
  #13 supporting_evidence_ids（排除综合 risk）
"""

from datetime import date

from app.agents.nodes.build_claims import build_claims_node
from app.agents.nodes.generate_answer import (
    _build_follow_ups,
    _format_number_value,
    _leaf_risk_claims,
    _select_answer_mode,
)
from app.agents.nodes.plan_modules import parse_query_period
from app.agents.state import (
    AgentState,
    Claim,
    CompanyRef,
    EquityResult,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
    RuntimeState,
)
from app.application.services.research_search import _split_keywords
from app.domain.evidence.models import supporting_evidence_ids


def _company() -> CompanyRef:
    return CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
    )


def _ev(evidence_id: str, **kw) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type=kw.get("source_type", "financial_statement"),
        source_record_id=kw.get("source_record_id") or f"src_{evidence_id}",
        field_path=kw.get("field_path", "test_field"),
    )


def _state(
    results: ModuleResults | None = None,
    claims: list | None = None,
    user_query: str = "分析康美药业",
) -> AgentState:
    return {
        "user_query": user_query,
        "company": _company(),
        "results": results,
        "claims": claims or [],
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


# ── #1 R7 文案：简化/完整模式 ───────────────────────────────


def _r7_state(core_profit_available: bool) -> AgentState:
    explanation = (
        "扣非净利润与归母净利润显著背离"
        if core_profit_available
        else "净利润增速与现金流/营收增速背离"
    )
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R7": "triggered"},
            rule_details={
                "R7": {
                    "evidence_ids": ["ev_r7_1"],
                    "severity": "red",
                    "explanation": explanation,
                    "quality": {
                        "core_profit_available": core_profit_available,
                        "simplified_mode": not core_profit_available,
                    },
                }
            },
            evidence=[_ev("ev_r7_1", field_path="net_profit")],
        )
    )
    return _state(results)


def test_r7_simplified_mode_uses_divergence_text():
    """#1：简化模式（无扣非字段）→ 文案不含扣非、追加 limitation。"""
    result = build_claims_node(_r7_state(core_profit_available=False))
    r7 = next(c for c in result["claims"] if c.claim_type == "financial")
    assert "净利润增速与现金流/营收增速背离" in r7.text
    assert "扣非净利润" not in r7.text
    assert "扣非净利润字段不可用，采用简化判断" in r7.limitations


def test_r7_full_mode_mentions_deducted_profit():
    """#1：扣非字段可用 → 使用完整 explanation，无简化 limitation。"""
    result = build_claims_node(_r7_state(core_profit_available=True))
    r7 = next(c for c in result["claims"] if c.claim_type == "financial")
    assert "扣非净利润与归母净利润显著背离" in r7.text
    assert "采用简化判断" not in "".join(r7.limitations)


# ── #2 Claim severity 与引擎一致 ────────────────────────────


def test_severity_from_engine():
    """#2：Claim severity 使用引擎值（R4/R5/R6 不再统一 orange）。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R4": "triggered"},
            rule_details={
                "R4": {
                    "evidence_ids": ["ev_r4_1"],
                    "severity": "yellow",
                    "explanation": "存货增速与营收增速背离",
                }
            },
            evidence=[_ev("ev_r4_1", field_path="inventories")],
        )
    )
    result = build_claims_node(_state(results))
    r4 = next(c for c in result["claims"] if c.claim_type == "financial")
    assert r4.severity == "yellow"


def test_severity_invalid_falls_back_unknown():
    """#2：引擎 severity 非法/缺失 → unknown（不猜测）。"""
    results = ModuleResults(
        finance=FinanceResult(
            rule_statuses={"R1": "triggered"},
            rule_details={
                "R1": {
                    "evidence_ids": ["ev_r1_1"],
                    "severity": "critical",  # 非法等级
                    "explanation": "测试",
                }
            },
            evidence=[_ev("ev_r1_1")],
        )
    )
    result = build_claims_node(_state(results))
    r1 = next(c for c in result["claims"] if c.claim_type == "financial")
    assert r1.severity == "unknown"


# ── #3 股权 Claim：chain_details 分级 ───────────────────────


def _chain_results(*chain_details: dict) -> ModuleResults:
    return ModuleResults(
        equity=EquityResult(
            chains=[{"path": ["A"], "total_stake": 0.1}],
            evidence=[_ev("ev_eq_a", source_type="neo4j_relationship")],
            chain_details=list(chain_details),
        )
    )


def _chain(
    chain_id: str,
    risk_level: str,
    final_control_pct: float,
    evidence_ids: list[str],
    path_type: str = "ownership",
) -> dict:
    return {
        "chain_id": chain_id,
        "path_names": ["股东", "中间", "目标"],
        "depth": 3,
        "final_control_pct": final_control_pct,
        # 8.09 四轮审查：默认 ownership（持股关系）；control 仅在有明确
        # 控制证据时使用
        "path_type": path_type,
        "evidence_ids": evidence_ids,
        "risk_label": "normal" if risk_level == "green" else "concentrated_control",
        "risk_level": risk_level,
        "risk_reasons": [],
    }


def test_green_chain_claim_is_green():
    """#3：普通绿色控制链 → severity=green 事实 Claim（不计风险）。"""
    results = _chain_results(
        _chain("c1", "green", 30.0, ["ev_eq_a"]),
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1
    assert equity[0].severity == "green"
    # 8.09 四轮审查：默认 ownership 链路 → 持股关系展示，不称"控制关系"
    assert "持股关系事实展示" in equity[0].limitations[0]
    assert "不构成控制关系" in equity[0].limitations[0]
    assert "股权链穿透" in equity[0].text
    assert "最终持股" in equity[0].text


def test_control_chain_claim_keeps_control_wording():
    """8.09 四轮审查：仅 path_type=control（明确控制证据）使用"控制链/
    最终控制/事实性控制关系"。"""
    results = _chain_results(
        _chain("c1", "green", 60.0, ["ev_eq_a"], path_type="control"),
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1
    assert "控制链穿透" in equity[0].text
    assert "最终控制 60.0%" in equity[0].text
    assert "事实性控制关系展示" in equity[0].limitations[0]


def test_fallback_chain_claim_uses_ownership_wording():
    """8.09 五轮审查：chain_details 缺失的降级 Claim 统一走 _chain_claim_text()
    ownership 措辞（曾硬编码"控制链穿透/最终控制"，与 ownership 语义冲突）。"""
    results = ModuleResults(
        equity=EquityResult(
            chains=[
                {
                    "path": ["A", "B"],
                    "path_names": ["股东A", "康美药业"],
                    "total_stake": 0.1,
                }
            ],
            evidence=[_ev("ev_eq_a", source_type="neo4j_relationship")],
            chain_details=[],
        )
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1
    assert equity[0].severity == "unknown"  # 降级载荷不默认 red
    assert "股权链穿透" in equity[0].text
    assert "最终持股 10.0%" in equity[0].text  # total_stake 0.1 → 10% 兜底
    assert "控制链穿透" not in equity[0].text
    assert "最终控制" not in equity[0].text


def test_high_risk_chain_not_first_is_detected():
    """#3：非首条高风险链仍被识别（按风险等级选择，不只 chains[0]）。"""
    results = _chain_results(
        _chain("c1", "green", 95.0, ["ev_eq_a"]),  # 比例最大但无风险
        _chain("c2", "orange", 30.0, ["ev_eq_a"]),  # 高风险链
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    severities = {c.severity for c in equity}
    assert "orange" in severities  # 高风险链必被识别
    assert "green" in severities  # 主控制链事实保留


def test_same_chain_claim_dedup():
    """#3：主链与最高风险链为同一条 → 只生成一条 Claim。"""
    results = _chain_results(
        _chain("c1", "orange", 80.0, ["ev_eq_a"]),
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1


def test_chain_without_canonical_evidence_skipped():
    """#3：无 canonical evidence_ids 的链不得标记 verified（不生成 Claim）。"""
    results = ModuleResults(
        equity=EquityResult(
            chains=[{"path": ["A"], "total_stake": 0.1}],
            evidence=[_ev("ev_other", source_type="neo4j_relationship")],
            chain_details=[_chain("c1", "red", 60.0, ["ev_missing"])],
        )
    )
    result = build_claims_node(_state(results))
    assert all(c.claim_type != "equity" for c in result["claims"])


def test_all_green_chains_only_main_claim():
    """P2-3：全绿链时不选择"最高风险链"（避免两条绿色 Claim 重复）。"""
    results = _chain_results(
        _chain("c1", "green", 90.0, ["ev_eq_a"]),
        _chain("c2", "green", 30.0, ["ev_eq_a"]),
    )
    result = build_claims_node(_state(results))
    equity = [c for c in result["claims"] if c.claim_type == "equity"]
    assert len(equity) == 1  # 只输出主控制链一条
    assert equity[0].severity == "green"
    # 主控制链 = 最终控制比例最大者
    assert "90.0%" in equity[0].text


def test_research_claim_id_distinct_per_report():
    """P2-2：同标题不同 report_id → Claim ID 不同（不冲突）。"""
    from app.agents.nodes.generate_answer import _research_evidence_and_claims

    insights = [
        {
            "report_id": "rp_a1",
            "source_title": "白酒行业 2025 年中期策略",
            "source_org": "中信证券",
            "content": "动销平稳。",
            "source_date": "2025-06-30",
        },
        {
            "report_id": "rp_a2",  # 同标题、不同报告 ID
            "source_title": "白酒行业 2025 年中期策略",
            "source_org": "中信证券",
            "content": "龙头库存良性。",
            "source_date": "2025-07-01",
        },
        {
            # 无 report_id → 不可回查，不生成且不进入可渲染结果
            "source_title": "无 ID 研报",
            "source_org": "某机构",
            "content": "x",
        },
    ]
    evidence, claims, valid = _research_evidence_and_claims(
        insights, company_code="", turn_id="t", trace_id="tr"
    )
    assert len(claims) == 2
    assert len(valid) == 2  # 无 report_id 的第三条被排除
    assert claims[0].claim_id != claims[1].claim_id
    assert claims[0].evidence_ids != claims[1].evidence_ids


# ── #8 叶子风险计数 ─────────────────────────────────────────


def _claim(
    claim_type: str, severity: str, evidence_ids: list[str] | None = None
) -> Claim:
    return Claim(
        claim_id=f"clm_{claim_type}_{severity}",
        text="t",
        claim_type=claim_type,
        severity=severity,
        evidence_ids=evidence_ids or [],
    )


def test_leaf_risk_claims_excludes_risk_and_green():
    """#8：综合 risk Claim 与绿色链不参与风险计数。"""
    claims = [
        _claim("risk", "red"),  # 综合风险汇总（不计）
        _claim("equity", "green"),  # 绿色控制链（不计）
        _claim("financial", "red"),  # 叶子信号（计）
        _claim("cross_validation", "orange"),  # 叶子信号（计）
        _claim("event", "unknown"),  # unknown（不计）
    ]
    leaf = _leaf_risk_claims(claims)
    assert len(leaf) == 2


def test_supporting_evidence_excludes_risk_claim():
    """#13：supporting_evidence_ids 排除综合 risk Claim 引用。"""
    claims = [
        _claim("risk", "red", ["ev_risk_a"]),
        _claim("financial", "red", ["ev_fin_a", "ev_fin_b"]),
        _claim("research", "unknown", ["ev_report_a"]),
    ]
    ids = supporting_evidence_ids(claims)
    assert ids == ["ev_fin_a", "ev_fin_b", "ev_report_a"]
    assert "ev_risk_a" not in ids


# ── #10 R7 动态追问 ─────────────────────────────────────────


def _followup_state(core_profit_available: bool, triggered: bool = True) -> AgentState:
    status = "triggered" if triggered else "not_triggered"
    return {
        "user_query": "测试",
        "company": _company(),
        "plan": None,
        "module_status": {},
        "results": ModuleResults(
            finance=FinanceResult(
                rule_statuses={"R7": status},
                rule_details={
                    "R7": {
                        "evidence_ids": ["ev_r7_1"],
                        "quality": {"core_profit_available": core_profit_available},
                    }
                },
                evidence=[],
            )
        ),
        "claims": [
            Claim(
                claim_id="clm_r7",
                text="R7 触发",
                claim_type="financial",
                severity="red",
                rule_id="R7",
                evidence_ids=["ev_r7_1"],
            )
        ]
        if triggered
        else [],
        "runtime": RuntimeState(trace_id="t"),
    }


def test_r7_followup_simplified_when_core_profit_missing():
    """#10：扣非字段不可用 → 推荐简化对比追问。"""
    follow_ups = _build_follow_ups(_followup_state(core_profit_available=False))
    assert "查看净利润、营收与经营现金流增速对比" in follow_ups
    assert "扣非净利润与归母净利润对比" not in follow_ups


def test_r7_followup_full_when_core_profit_available():
    """#10：扣非字段可用 → 推荐扣非对比追问。"""
    follow_ups = _build_follow_ups(_followup_state(core_profit_available=True))
    assert "查看扣非净利润与归母净利润对比" in follow_ups


# ── #5 期次解析 ─────────────────────────────────────────────


def test_parse_query_period_annual():
    assert parse_query_period("分析康美药业2025年报") == (
        date(2025, 12, 31),
        "report_period",
        "2025年报",
    )
    assert parse_query_period("2025年数据") == (
        date(2025, 12, 31),
        "report_period",
        "2025年数据",
    )


def test_parse_query_period_quarters():
    assert parse_query_period("康美2025Q1怎么样") == (
        date(2025, 3, 31),
        "report_period",
        "2025Q1",
    )
    assert parse_query_period("2025年三季报") == (
        date(2025, 9, 30),
        "report_period",
        "2025年三季报",
    )
    assert parse_query_period("2025半年报") == (
        date(2025, 6, 30),
        "report_period",
        "2025半年报",
    )


def test_parse_query_period_date():
    assert parse_query_period("截至2025-09-30") == (
        date(2025, 9, 30),
        "as_of",
        "截至2025-09-30",
    )
    assert parse_query_period("2025年9月30日") == (
        date(2025, 9, 30),
        "as_of",
        "2025年9月30日",
    )


def test_parse_query_period_none():
    assert parse_query_period("康美药业财务健康吗") == (None, "", "")


def test_parse_query_period_relative_and_yearless_quarter():
    assert parse_query_period("康美药业今年上半年营收", today=date(2026, 8, 20)) == (
        date(2026, 6, 30),
        "report_period",
        "今年上半年",
    )
    assert parse_query_period("康美药业三季度变化", today=date(2026, 8, 20)) == (
        date(2025, 9, 30),
        "report_period",
        "三季度",
    )


# ── #6 搜索主题 Gate ────────────────────────────────────────


def test_split_keywords_theme_vs_intent():
    """#6：意图词不参与匹配；核心主题词正确提取。"""
    core, intent = _split_keywords("白酒行业近期研报观点")
    assert "行业" not in core and "近期" not in core
    assert "研报" not in core and "观点" not in core
    assert "白酒" in core  # 核心主题
    assert "行业" in intent or "研报" in intent


def test_split_keywords_removes_question_suffix():
    """口语化行业问题必须留下可检索主题，不能把问句尾词并入 MUST。"""
    from app.application.services.research_search import _split_keywords

    core, intent = _split_keywords("白酒行业怎么样")

    assert core == ["白酒"]
    assert "行业" in intent


def test_split_keywords_company_name_kept():
    """#6：公司名不拆意图词，完整保留为核心词。"""
    core, _ = _split_keywords("康美药业财务分析")
    assert "康美药业" in core


# ── #12 数值格式化 ──────────────────────────────────────────


def test_format_number_no_long_float():
    """#12：百分比 1 位小数；通用数值紧凑，禁止 15 位浮点。"""
    assert _format_number_value(149.6000000001, "percent") == "149.6"
    assert _format_number_value(166.234, "percentage_point") == "166.2"
    assert _format_number_value(0.30100000000000004, "") == "0.301"
    assert _format_number_value(3.0, "") == "3"
    assert _format_number_value(True, "") == "是"


# ── #11 AnswerMode ──────────────────────────────────────────


def test_answer_mode_fraud():
    """#11：造假问题 → fraud_diagnosis 模式。"""
    mode = _select_answer_mode(_state(user_query="康美药业造假了吗"), [], False, False)
    assert mode == "fraud_diagnosis"


def test_answer_mode_equity_only():
    """#11：纯股权查询 → equity 模式。"""
    claims = [_claim("equity", "green", ["ev_eq_a"])]
    mode = _select_answer_mode(_state(claims=claims), claims, False, False)
    assert mode == "equity"


# ── 闲聊/引导意图（同学反馈"你好"答非所问） ────────────────


def test_detect_chitchat_intent():
    """寒暄识别：纯寒暄 → chitchat；想用无实体 → guide；正常查询 → None。"""
    from app.agents.nodes.plan_modules import detect_chitchat_intent

    assert detect_chitchat_intent("你好") == "chitchat"
    assert detect_chitchat_intent("你好呀") == "chitchat"
    assert detect_chitchat_intent("hello") == "chitchat"
    assert detect_chitchat_intent("hi there!") == "chitchat"
    assert detect_chitchat_intent("which stock") is None
    assert detect_chitchat_intent("你是谁") == "chitchat"
    assert detect_chitchat_intent("你能帮我做什么") == "chitchat"
    assert detect_chitchat_intent("有什么功能") == "chitchat"
    assert detect_chitchat_intent("") == "chitchat"  # 空问题按寒暄
    assert detect_chitchat_intent("帮我看看股票") == "guide"
    assert detect_chitchat_intent("怎么用") == "guide"
    assert detect_chitchat_intent("我该怎么开始") == "guide"
    assert detect_chitchat_intent("今天天气怎么样") == "unsupported"
    assert detect_chitchat_intent("分析康美药业") is None
    assert detect_chitchat_intent("康美药业造假了吗") is None
    assert detect_chitchat_intent("你好，帮我分析康美药业") is None
    assert detect_chitchat_intent("谢谢，继续分析它的现金流") is None


def test_generate_answer_chitchat_guides():
    """ "你好"（无公司）→ 欢迎引导语，而非"未找到匹配公司"。"""
    from app.agents.nodes.generate_answer import generate_answer_node
    from app.agents.state import ExecutionPlan

    state = _state(user_query="你好")
    state["company"] = None  # 无公司路径（chitchat 分支前提）
    state["plan"] = ExecutionPlan(intent="chitchat", requested_modules=[])
    result = generate_answer_node(state)
    fr = result["final_response"]
    assert "织网鉴真" in fr.answer
    assert "请输入上市公司名称或股票代码" in fr.answer
    assert "未能在数据覆盖范围内找到匹配的公司" not in fr.answer


def test_generate_answer_guide_prompts():
    """ "帮我看看股票"（无公司）→ 引导提供公司名/代码。"""
    from app.agents.nodes.generate_answer import generate_answer_node
    from app.agents.state import ExecutionPlan

    state = _state(user_query="帮我看看股票")
    state["company"] = None
    state["plan"] = ExecutionPlan(intent="guide", requested_modules=[])
    result = generate_answer_node(state)
    answer = result["final_response"].answer
    assert "不直接推荐股票" in answer
    assert "请提供公司名称或股票代码" in answer


def test_generate_answer_chitchat_subtypes():
    """感谢/告别不重复整段产品介绍，范围外问题明确说明能力边界。"""
    from app.agents.nodes.generate_answer import generate_answer_node
    from app.agents.state import ExecutionPlan

    for query, intent, expected in (
        ("谢谢", "chitchat", "不客气"),
        ("再见", "chitchat", "再见"),
        ("今天天气怎么样", "unsupported", "超出了织网鉴真的服务范围"),
    ):
        state = _state(user_query=query)
        state["company"] = None
        state["plan"] = ExecutionPlan(intent=intent, requested_modules=[])
        answer = generate_answer_node(state)["final_response"].answer
        assert expected in answer
        assert "未能在数据覆盖范围内找到匹配的公司" not in answer


def test_generate_answer_guide_subtypes():
    """能力询问与失去上下文的追问应给出各自可执行的引导。"""
    from app.agents.nodes.generate_answer import generate_answer_node
    from app.agents.state import ExecutionPlan

    for query, expected in (
        ("你能帮我做什么", "财务勾稽"),
        ("继续看它的现金流", "没有找到可延续的公司上下文"),
    ):
        state = _state(user_query=query)
        state["company"] = None
        state["plan"] = ExecutionPlan(intent="guide", requested_modules=[])
        answer = generate_answer_node(state)["final_response"].answer
        assert expected in answer
        assert "未能在数据覆盖范围内找到匹配的公司" not in answer


# ── R8/R9/R13 回归：混合问候、公司事实、多公司比较 ─────────────


def test_mixed_greeting_not_chitchat():
    """R8：问候+公司混合输入不被闲聊吞掉（fullmatch 后不命中问候词）。"""
    from app.agents.nodes.plan_modules import detect_chitchat_intent

    assert detect_chitchat_intent("你好，康美药业怎么样") is None
    assert detect_chitchat_intent("在吗，看看金牌家居") is None
    assert detect_chitchat_intent("你好，帮我分析康美药业") is None
    assert detect_chitchat_intent("谢谢，继续看它的现金流") is None
    # unsupported 先于闲聊：含"你好"的天气问题归 unsupported
    assert detect_chitchat_intent("你好，今天天气怎么样") == "unsupported"
    # 纯寒暄变体仍识别（词表不缩窄）
    assert detect_chitchat_intent("你好呀") == "chitchat"
    assert detect_chitchat_intent("早上好") == "chitchat"
    assert detect_chitchat_intent("哈喽") == "chitchat"
    assert detect_chitchat_intent("你能帮我做什么") == "chitchat"


def test_detect_company_fact_exact_templates():
    """R9：公司事实只命中明确模板，裸"行业/股本"不误路由。"""
    from app.agents.nodes.plan_modules import detect_company_fact

    assert detect_company_fact("康美药业属于什么行业") == "industry"
    assert detect_company_fact("金牌家居的所属行业") == "industry"
    assert detect_company_fact("康美药业在哪个交易所上市") == "exchange"
    assert detect_company_fact("康美药业上市日期") == "listing_date"
    assert detect_company_fact("金牌家居的企业类型") == "comp_type"
    assert detect_company_fact("康美药业主营业务") == "business"
    assert detect_company_fact("康美药业总股本是多少") == "total_shares"
    # 不误路由：行业研报 / 股本变化
    assert detect_company_fact("白酒行业近期研报观点") is None
    assert detect_company_fact("康美药业股本变化风险") is None


def test_plan_company_fact_skips_modules(monkeypatch):
    """R9：公司已解析 + fact 模板 → company_fact plan，requested_modules=[]。"""
    from app.agents.nodes import plan_modules as pm
    from app.agents.state import CompanyRef

    state = {
        "user_query": "康美药业属于什么行业",
        "company": CompanyRef(
            entity_id="e",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
            industry_l1="医药生物",
        ),
        "request_context": None,
    }
    result = pm.plan_modules_node(state)
    plan = result["plan"]
    assert plan.intent == "company_fact"
    assert plan.requested_modules == []
    assert plan.fact_key == "industry"


def test_answer_company_fact_honest_and_traceable():
    """R11：事实回答——已覆盖字段给值，未覆盖字段诚实声明 + registry Evidence。"""
    from app.agents.nodes.generate_answer import _answer_company_fact
    from app.agents.state import CompanyRef, RuntimeState

    state = {
        "company": CompanyRef(
            entity_id="e",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
            industry_l1="医药生物",
        ),
        "runtime": RuntimeState(turn_id="t1", trace_id="tr1", session_id="s1"),
    }
    # 行业有数据
    out = _answer_company_fact(state, "industry")
    assert "医药生物" in out["final_response"].answer
    assert out["final_response"].evidence[0].source_type == "company_registry"
    assert out["final_response"].evidence[0].source_record_id == "600518.SH"
    assert out["final_response"].evidence[0].evidence_id.startswith("ev_cr_")
    # 总股本无结构化数据 → 诚实"未覆盖"，不推算
    out2 = _answer_company_fact(state, "total_shares")
    assert "未覆盖" in out2["final_response"].answer
    assert out2["final_response"].claims == []


def test_comparison_guide_detection(monkeypatch):
    """R13 平移：多公司比较检测（Resolver._detect_comparison）。"""
    from app.application.services.company_entity_resolver import _detect_comparison

    assert _detect_comparison("中芯国际和台积电的差距", ["中芯国际"])
    assert _detect_comparison("康美药业对比金牌家居", ["康美药业", "金牌家居"])
    assert not _detect_comparison("分析康美药业", ["康美药业"])
    assert not _detect_comparison("康美药业有风险吗", ["康美药业"])


def test_company_type_labels():
    """P1-2：中文标签 1=非金融、2=银行、3=保险、4=证券（3/4 不写反）。"""
    from app.domain.company.models import company_type_label_from_code

    assert company_type_label_from_code(1) == "非金融企业"
    assert company_type_label_from_code(2) == "银行"
    assert company_type_label_from_code(3) == "保险"
    assert company_type_label_from_code(4) == "证券"
    assert company_type_label_from_code(None) is None
    assert company_type_label_from_code(99) is None
    # 分类函数保持英文（Gate 用），不受展示标签影响
    from app.domain.company.models import company_type_from_code

    assert company_type_from_code(3) == "financial"
    assert company_type_from_code(4) == "financial"


def test_comparison_guide_detection_zero_hits():
    """P2-2 平移：强比较词 + 0 家候选（库外公司）→ 判比较（引导）。"""
    from app.application.services.company_entity_resolver import _detect_comparison

    assert _detect_comparison("甲公司和乙公司的差距", [])
    # 排除词语境不判比较
    assert not _detect_comparison("白酒行业比较", [])


def test_fact_value_persist_shape():
    """P2-1：事实回答顶层返回 claims/evidence（persist_turn 只读顶层）。"""
    from app.agents.nodes.generate_answer import _answer_company_fact
    from app.agents.state import CompanyRef, RuntimeState

    state = {
        "company": CompanyRef(
            entity_id="e",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
            industry_l1="医药生物",
        ),
        "runtime": RuntimeState(turn_id="t1", trace_id="tr1", session_id="s1"),
    }
    out = _answer_company_fact(state, "industry")
    assert len(out["claims"]) == 1
    assert len(out["evidence"]) == 1
    assert out["claims"][0].claim_type == "company_fact"
    assert out["claims"][0].verification_status == "verified"
    # 无值分支：三者全空，不生成虚假 Evidence
    out2 = _answer_company_fact(state, "total_shares")
    assert out2["claims"] == []
    assert out2["evidence"] == []
