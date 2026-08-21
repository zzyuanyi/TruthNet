"""plan_modules_node 交叉校验标签回归测试 + 混合路由（关键词+LLM 意图识别）。

Bug 修复: need_finance and need_equity → need_equity and need_events
Phase D: 关键词未命中 → LLM 语义识别兜底；失败/全 False → 全模块。
"""

from datetime import date

from pydantic import BaseModel

from app.agents.nodes.plan_modules import (
    _QuerySemanticContext,
    _detect_answer_operation,
    detect_chitchat_intent,
    plan_modules_node,
)
from app.agents.state import CompanyRef


class _FakeIntentProvider:
    """可编程意图识别 provider（structured_chat 返回指定意图）。"""

    provider_name = "fake"

    def __init__(self, intent: dict | None = None, raise_error: bool = False):
        self.intent = intent
        self.raise_error = raise_error
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return ""

    async def chat_stream(self, messages, **kwargs):
        self.calls += 1
        yield ""

    async def structured_chat(self, messages, output_schema: type[BaseModel], **kwargs):
        self.calls += 1
        if self.raise_error:
            raise RuntimeError("LLM 不可用")
        return output_schema(**(self.intent or {}))

    async def check_connection(self) -> bool:
        return True


def _install_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: provider,
    )


def _state(question: str) -> dict:
    return {
        "user_query": question,
        "company": CompanyRef(
            entity_id="ent_test",
            wind_code="000001.SZ",
            sec_name="测试公司",
            exchange="XSHE",
        ),
    }


def _no_company_state(question: str) -> dict:
    return {"user_query": question, "company": None}


def test_finance_equity_only_financial_crosscheck():
    """财务+股东 → finance + equity，仅 financial_vs_cashflow，不出现 equity_vs_events。

    93c4731 引入指标短答后"应收账款"命中 indicator 分支（intent=indicator），
    改用"财务和股东情况"验证 finance+equity 路由。
    """
    result = plan_modules_node(_state("财务和股东情况"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"finance", "equity"}
    assert "financial_vs_cashflow" in plan.cross_checks
    assert "equity_vs_events" not in plan.cross_checks


def test_equity_events_only_equity_crosscheck():
    """股东变动+公告处罚 → equity + events，仅 equity_vs_events。"""
    result = plan_modules_node(_state("股东变动和公告处罚"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"equity", "events"}
    assert "equity_vs_events" in plan.cross_checks
    assert "financial_vs_cashflow" not in plan.cross_checks


def test_diagnosis_all_modules_both_crosschecks():
    """康美有造假风险吗 → 三模块，两个交叉校验都有。"""
    result = plan_modules_node(_state("康美有造假风险吗"))
    plan = result["plan"]
    assert set(plan.requested_modules) == {"finance", "equity", "events"}
    assert "equity_vs_events" in plan.cross_checks
    assert "financial_vs_cashflow" in plan.cross_checks


def test_finance_only_no_crosscheck():
    """利润如何 → 仅 finance，无交叉校验。

    93c4731 引入指标短答后"营业收入"命中 indicator 分支（intent=indicator），
    改用"利润如何"验证 finance-only 路由（同样不触发 indicator 模式）。
    """
    result = plan_modules_node(_state("利润如何"))
    plan = result["plan"]
    assert plan.requested_modules == ["finance"]
    assert plan.cross_checks == []


# ── Phase D: 混合路由（关键词未命中 → LLM 意图识别） ──────


def test_keyword_hit_skips_llm(monkeypatch):
    """关键词命中 → 不调 LLM（provider.calls == 0）。"""
    provider = _FakeIntentProvider()
    _install_provider(monkeypatch, provider)
    plan_modules_node(_state("应收账款情况"))
    assert provider.calls == 0, "关键词命中不应调用 LLM"


def test_llm_intent_finance_only(monkeypatch):
    """无关键词 + LLM 识别 finance → 仅 finance。"""
    provider = _FakeIntentProvider(intent={"finance": True})
    _install_provider(monkeypatch, provider)
    plan = plan_modules_node(_state("公司最近钱收得回来吗"))["plan"]
    assert provider.calls == 1, "无关键词应调用一次 LLM"
    assert plan.requested_modules == ["finance"]


def test_llm_intent_equity_events(monkeypatch):
    """无关键词 + LLM 识别 equity+events → 两模块 + equity_vs_events。"""
    provider = _FakeIntentProvider(intent={"equity": True, "events": True})
    _install_provider(monkeypatch, provider)
    plan = plan_modules_node(_state("他家最近闹得挺大是怎么回事"))["plan"]
    assert set(plan.requested_modules) == {"equity", "events"}
    assert "equity_vs_events" in plan.cross_checks


def test_llm_intent_all_false_falls_back_all(monkeypatch):
    """LLM 全 False → 全模块保守展开（不丢信息）。"""
    provider = _FakeIntentProvider(
        intent={"finance": False, "equity": False, "events": False}
    )
    _install_provider(monkeypatch, provider)
    plan = plan_modules_node(_state("随便聊聊这家公司"))["plan"]
    assert set(plan.requested_modules) == {"finance", "equity", "events"}


def test_llm_failure_falls_back_all(monkeypatch):
    """LLM 抛异常 → 全模块兜底（不阻塞）。"""
    provider = _FakeIntentProvider(raise_error=True)
    _install_provider(monkeypatch, provider)
    plan = plan_modules_node(_state("随便聊聊这家公司"))["plan"]
    assert set(plan.requested_modules) == {"finance", "equity", "events"}


def test_no_company_short_greeting_skips_llm(monkeypatch):
    """明确短问候走快速路径，避免一次无意义的远程 LLM 调用。"""
    provider = _FakeIntentProvider(intent={"intent": "analysis"})
    _install_provider(monkeypatch, provider)

    plan = plan_modules_node(_no_company_state("你好"))["plan"]

    assert plan.intent == "chitchat"
    assert provider.calls == 0


def test_no_company_llm_research_result_is_preserved(monkeypatch):
    """LLM 已判定 research 时不得丢成 None 后再次关键词兜底。"""
    provider = _FakeIntentProvider(intent={"intent": "research"})
    _install_provider(monkeypatch, provider)

    plan = plan_modules_node(_no_company_state("白酒行业最近有什么看法"))["plan"]

    assert plan.intent == "research"
    assert provider.calls == 1


def test_no_company_llm_analysis_becomes_actionable_guide(monkeypatch):
    """需要公司分析但实体缺失时，返回输入公司引导而非查询失败。"""
    provider = _FakeIntentProvider(intent={"intent": "analysis"})
    _install_provider(monkeypatch, provider)

    plan = plan_modules_node(_no_company_state("帮我查查最近的情况"))["plan"]

    assert plan.intent == "guide"
    assert provider.calls == 1


def test_no_company_llm_failure_uses_semantic_fallback(monkeypatch):
    """LLM 失败时，行业请求和无上下文追问仍返回可执行意图。"""
    provider = _FakeIntentProvider(raise_error=True)
    _install_provider(monkeypatch, provider)

    research = plan_modules_node(_no_company_state("白酒行业怎么样"))["plan"]
    follow_up = plan_modules_node(_no_company_state("继续看它的现金流"))["plan"]

    assert research.intent == "research"
    assert follow_up.intent == "guide"


def test_explicit_request_period_overrides_question_period():
    from datetime import date

    from app.agents.state import RequestContext

    state = _state("分析康美药业 2024 年报")
    state["request_context"] = RequestContext(
        as_of=date(2025, 12, 31),
        as_of_kind="report_period",
        requested_period_text="2025",
    )
    plan = plan_modules_node(state)["plan"]
    assert plan.as_of == date(2025, 12, 31)
    assert plan.requested_period_text == "2025"


def test_candidates_produce_disambiguation_plan():
    from app.agents.state import CompanyRef

    state = _no_company_state("分析平安")
    state["company_candidates"] = [
        CompanyRef(
            entity_id="company_000001_SZ",
            wind_code="000001.SZ",
            sec_name="平安银行",
            exchange="XSHE",
        )
    ]
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "company_disambiguation"
    assert plan.requested_modules == []


def test_single_target_comparison_request_routes_relation_clarify():
    """最终续审 §4 A5 / §9.4：comparison_requested=True 但目标 <2 家
    → relation_clarify，不得靠 generate_answer 的 0/1 家 fallback 文案
    掩盖 Resolver 非法状态（单主体 comparison）。"""
    state = _no_company_state("茅台对比一下")
    state["comparison_requested"] = True
    state["comparison_targets"] = [
        CompanyRef(
            entity_id="company_600519_SH",
            wind_code="600519.SH",
            sec_name="贵州茅台",
            exchange="XSHG",
        )
    ]
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "relation_clarify"
    assert plan.requested_modules == []


def test_two_target_comparison_without_dimension_routes_overview():
    """v3.3.3 批次 D → v3.3.4 契约变更（方案 §4.1）：两家不同代码 + 比较词
    但无维度 → overview 轻量概览（原 v3.3.3 行为是 missing_dimension 追问，
    本方案有意变更：无维度不再只追问，改为固定维度概览）。"""
    state = _no_company_state("康美和茅台对比")
    state["comparison_requested"] = True
    state["comparison_targets"] = [
        CompanyRef(
            entity_id="company_600518_SH",
            wind_code="600518.SH",
            sec_name="康美药业",
            exchange="XSHG",
        ),
        CompanyRef(
            entity_id="company_600519_SH",
            wind_code="600519.SH",
            sec_name="贵州茅台",
            exchange="XSHG",
        ),
    ]
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.scope == "cross_company"
    assert plan.comparison.mode == "overview"
    assert plan.comparison.metric_ids == []
    assert plan.comparison.fact_key == ""
    assert plan.comparison.requested_scope == "overview"


def test_detect_indicator_inventory_turnover_question_not_inventories():
    """v3.3.3 批次 A 表征（方案 §2.1 P1）：存货周转情况 → r4_turnover_days。"""
    from app.agents.nodes.plan_modules import detect_indicator

    assert detect_indicator("回到康美，存货周转情况如何") == "r4_turnover_days"
    assert detect_indicator("存货周转天数") == "r4_turnover_days"


def test_detect_indicator_gross_margin_question():
    """v3.3.3 批次 A 表征（方案 §2.3 P1）：毛利率 → r5_gross_margin。"""
    from app.agents.nodes.plan_modules import detect_indicator

    assert detect_indicator("毛利率正常吗") == "r5_gross_margin"


def test_detect_indicator_unsupported_turnover_rate():
    """方案 §4.3：unsupported 精确短语不得被「存货」短词抢占。"""
    from app.agents.nodes.plan_modules import detect_indicator

    assert detect_indicator("存货周转率是多少") == "unsupported"


def test_plan_indicator_intent_for_turnover_question():
    """批次 A 完成标准：存货周转情况问题在有主体时生成 indicator 计划。"""
    state = _state("回到康美，存货周转情况如何")
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.indicator == "r4_turnover_days"


def test_plan_assessment_operation_for_normality_question():
    """收口批次 D（方案 §3.6）：「毛利率正常吗」→ answer_operation=assessment。"""
    state = _state("毛利率正常吗")
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.indicator == "r5_gross_margin"
    assert plan.answer_operation == "assessment"


def test_plan_value_operation_for_plain_question():
    """「毛利率是多少」→ answer_operation=value（不误判 assessment）。"""
    state = _state("毛利率是多少")
    plan = plan_modules_node(state)["plan"]
    assert plan.answer_operation == "value"


def test_same_company_cross_indicator_routes_light_comparison():
    """v3.3.3 批次 C（方案 §2.2/§5.6）：历史指标 + 当前指标 + 比较词
    → light_comparison 计划（ComparisonSpec 恰好两个 metric_id）。"""
    from app.agents.state import ExecutedMetricRef, MemoryContext

    state = _state("和营业收入增速对比呢")
    state["memory_context"] = MemoryContext(
        recent_executed_metrics=[
            ExecutedMetricRef(
                metric_id="accounts_receivable_growth",
                period="20250331",
                unit="percent",
                company_code="000001.SZ",
            )
        ]
    )
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "light_comparison"
    assert plan.requested_modules == []
    assert plan.comparison is not None
    assert plan.comparison.scope == "same_company_cross_indicator"
    assert plan.comparison.mode == "indicator"
    assert plan.comparison.metric_ids == [
        "accounts_receivable_growth",
        "operating_revenue_growth",
    ]
    assert plan.comparison.operation == "difference"


def test_compare_without_history_falls_back_to_single_indicator():
    """批次 C 边界：无历史成功指标 → 单指标短答（不构造比较）。"""
    state = _state("和营业收入增速对比呢")
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.indicator == "operating_revenue_growth"


def test_compare_with_same_history_indicator_not_compared():
    """批次 C 边界：历史指标与当前指标同 ID → 不构造比较。"""
    from app.agents.state import ExecutedMetricRef, MemoryContext

    state = _state("和营业收入增速对比呢")
    state["memory_context"] = MemoryContext(
        recent_executed_metrics=[
            ExecutedMetricRef(
                metric_id="operating_revenue_growth",
                period="20241231",
                unit="percent",
                company_code="000001.SZ",
            )
        ]
    )
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.comparison is None


def test_history_metric_other_company_not_compared():
    """收口批次 B（方案 §3.4）：康美执行指标 → 切换茅台 →
    「和营业收入增速对比呢」不得使用康美的历史指标。"""
    from app.agents.state import ExecutedMetricRef, MemoryContext

    state = _state("和营业收入增速对比呢")
    # 当前公司 = 000001.SZ（_state 默认），历史指标属于另一家公司
    state["memory_context"] = MemoryContext(
        recent_executed_metrics=[
            ExecutedMetricRef(
                metric_id="accounts_receivable_growth",
                period="20250331",
                unit="percent",
                company_code="600518.SH",
            )
        ]
    )
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.comparison is None


def test_history_metric_without_company_not_compared():
    """旧记录无 company_code → 不得用于跨指标比较（保守 fail closed）。"""
    from app.agents.state import ExecutedMetricRef, MemoryContext

    state = _state("和营业收入增速对比呢")
    state["memory_context"] = MemoryContext(
        recent_executed_metrics=[
            ExecutedMetricRef(
                metric_id="accounts_receivable_growth",
                period="20250331",
                unit="percent",
            )
        ]
    )
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "indicator"
    assert plan.comparison is None


def _two_company_state(question: str) -> dict:
    """双公司比较 state：comparison_requested + 两个不同 code。"""
    state = {"user_query": question, "company": None}
    state["comparison_requested"] = True
    state["comparison_targets"] = [
        CompanyRef(
            entity_id="company_600887_SH",
            wind_code="600887.SH",
            sec_name="伊利股份",
            exchange="XSHG",
        ),
        CompanyRef(
            entity_id="company_000895_SZ",
            wind_code="000895.SZ",
            sec_name="双汇发展",
            exchange="XSHE",
        ),
    ]
    return state


def test_cross_company_indicator_question_routes_light_comparison():
    """v3.3.3 批次 D 官方原题：伊利存货周转天数比双汇低多少 →
    cross_company + indicator + less_than（不再统一 comparison_guide）。"""
    plan = plan_modules_node(
        _two_company_state("伊利股份的存货周转天数比双汇发展低多少？")
    )["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.scope == "cross_company"
    assert plan.comparison.mode == "indicator"
    assert plan.comparison.metric_ids == ["r4_turnover_days"]
    assert plan.comparison.operation == "less_than"
    assert plan.comparison.requested_scope == "indicator"


def test_company_research_facts_do_not_fall_into_diagnosis():
    company = CompanyRef(
        entity_id="company_301421_SZ",
        wind_code="301421.SZ",
        sec_name="波长光电",
        exchange="XSHE",
    )
    for question in ("波长光电的首发价格是多少", "波长光电的高管薪酬"):
        plan = plan_modules_node({"user_query": question, "company": company})["plan"]
        assert plan.intent == "company_fact"
        assert plan.fact_key in {"executive_compensation", "ipo_price"}


def test_investment_advice_with_can_buy_wording_is_blocked():
    plan = plan_modules_node(_no_company_state("黄金板块还可以买吗？"))["plan"]
    assert plan.intent == "investment_advice"


def test_industry_stock_list_is_research_not_market_wide_refusal():
    plan = plan_modules_node(_no_company_state("AI医疗板块有哪些个股"))["plan"]
    assert plan.intent == "research"


def test_uncovered_market_metric_does_not_fall_into_diagnosis():
    company = CompanyRef(
        entity_id="company_600570_SH",
        wind_code="600570.SH",
        sec_name="恒生电子",
        exchange="XSHG",
    )
    plan = plan_modules_node(
        {"user_query": "恒生电子今天的主力净买入额是多少", "company": company}
    )["plan"]
    assert plan.intent == "unsupported_indicator"


def test_cross_company_fact_question_routes_company_fact():
    """官方原题：上市日期早几年 → cross_company + company_fact + earlier_than。"""
    plan = plan_modules_node(
        _two_company_state("中国石化的上市日期比中国石油早几年？")
    )["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.scope == "cross_company"
    assert plan.comparison.mode == "company_fact"
    assert plan.comparison.fact_key == "listing_date"
    assert plan.comparison.operation == "earlier_than"
    assert plan.comparison.period_policy == "not_applicable"
    assert plan.comparison.requested_scope == "company_fact"


def test_cross_company_no_dimension_routes_overview():
    """v3.3.4 方案 §4.1：「那茅台呢，对比一下」无维度 → overview 轻量概览。"""
    plan = plan_modules_node(_two_company_state("那茅台呢，对比一下"))["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.scope == "cross_company"
    assert plan.comparison.mode == "overview"
    assert plan.comparison.requested_scope == "overview"


def test_cross_company_risk_dimension_routes_risk_mode():
    """批次 D 诚实路由：双公司风险维度 → mode=risk（对话内暂无执行）。"""
    plan = plan_modules_node(_two_company_state("茅台和康美谁的风险高"))["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.mode == "risk"
    assert plan.comparison.requested_scope == "risk"


def test_cross_company_full_comparison_routes_overview_with_full_scope():
    """v3.3.4 方案 §2.1/§4.1：两家 finalized + 全面比较 → mode=overview +
    requested_scope=full（先基础预览，不再直接跳页面）；「财务与风险」含
    「风险」子串，必须按全面 cue 优先（否则会误判成 risk 模式）。"""
    plan = plan_modules_node(
        _two_company_state("全面对比伊利股份和双汇发展的财务与风险")
    )["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.mode == "overview"
    assert plan.comparison.requested_scope == "full"
    assert plan.comparison.metric_ids == []


def test_cross_company_industry_comparison_routes_overview_with_industry_scope():
    """v3.3.4 方案 §2.1：两家 finalized + 行业对比 → mode=overview +
    requested_scope=industry（对话只出基础财务预览，行业分位由页面承载）。"""
    plan = plan_modules_node(_two_company_state("伊利股份和双汇发展行业对比"))["plan"]
    assert plan.intent == "light_comparison"
    assert plan.comparison.mode == "overview"
    assert plan.comparison.requested_scope == "industry"


def test_full_scope_words_duowei_zhengti_route_full():
    """收口复核审查 P2a：多维/整体与全面一致 → overview +
    requested_scope=full（词表统一自比较语义注册表）。"""
    for q in ("多维对比伊利股份和双汇发展", "整体对比伊利股份和双汇发展"):
        plan = plan_modules_node(_two_company_state(q))["plan"]
        assert plan.intent == "light_comparison", q
        assert plan.comparison.mode == "overview", q
        assert plan.comparison.requested_scope == "full", q


def test_three_company_comparison_routes_guide_without_truncation():
    """v3.3.4 方案 §2.4/§4.1：三家及以上 → comparison_guide，不静默截取前两家
    （结构化保底 next_steps 由 generate_answer 生成）。"""
    state = _two_company_state("康美、茅台、五粮液对比一下")
    state["comparison_targets"] = [
        *state["comparison_targets"],
        CompanyRef(
            entity_id="company_000858_SZ",
            wind_code="000858.SZ",
            sec_name="五粮液",
            exchange="XSHE",
        ),
    ]
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "comparison_guide"
    assert plan.comparison is None


def test_single_company_full_comparison_routes_guide():
    """v3.3.4 方案 §2.1/§7.1-5：只有一家主体 + 全面对比 → comparison_guide
    （不生成预览、不伪造第二主体）。"""
    state = _state("康美药业全面对比")
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "comparison_guide"
    assert plan.comparison is None


def test_industry_comparison_single_company_routes_guide():
    """方案 §8.4：隆基绿能存货周转天数行业对比 → 页面行业基准引导，
    不伪造成双公司比较、不误答单公司指标。"""
    state = _state("隆基绿能存货周转天数行业对比")
    plan = plan_modules_node(state)["plan"]
    assert plan.intent == "comparison_guide"
    assert plan.indicator == ""


def test_explicit_period_and_scope_words_do_not_become_company_mentions():
    """期次/报表口径词不应进入实体解析候选。"""
    from app.application.services.company_mention_extractor import (
        extract_company_mention_result,
    )

    result = extract_company_mention_result("中兴通讯2024财年第1季度销售毛利率是多少")
    assert [item.text for item in result.mentions] == ["中兴通讯"]
    plan = plan_modules_node(
        {
            "user_query": "中兴通讯2024财年第1季度销售毛利率是多少",
            "company": _state("x")["company"],
        }
    )["plan"]
    assert plan.as_of == date(2024, 3, 31)
    assert plan.as_of_kind == "report_period"


def test_high_risk_query_operations_are_not_plain_value():
    company = _state("x")["company"]
    assert (
        plan_modules_node(
            {"user_query": "比亚迪毛利率连续三年下降原因", "company": company}
        )["plan"].answer_operation
        == "causal_trend"
    )
    assert (
        plan_modules_node(
            {"user_query": "贵州茅台现金流会受影响吗", "company": company}
        )["plan"].answer_operation
        == "impact"
    )


def test_industry_average_without_company_uses_benchmark_plan():
    plan = plan_modules_node(
        {"user_query": "家电行业平均毛利率是多少", "company": None}
    )["plan"]
    assert plan.intent == "industry_benchmark"
    assert plan.industry_l1 == "家用电器"
    assert plan.indicator == "r5_gross_margin"


def test_quarter_operations_distinguish_point_yoy_and_mom():
    assert _detect_answer_operation("最新季度毛利率") == "value"
    assert _detect_answer_operation("最新季度单季度净利润看点") == "quarter_single"
    assert _detect_answer_operation("最新季度营业收入同比增长率") == "quarter_yoy"
    assert _detect_answer_operation("最新季度单季度营业收入环比增长率") == "quarter_mom"


def test_turnaround_question_uses_turnaround_operation():
    assert _detect_answer_operation("通威股份2025年净利润能否扭亏为盈") == "turnaround"


def test_directional_event_query_uses_events_only():
    plan = plan_modules_node(
        {
            "user_query": "最近有哪些利好事件",
            "company": _state("x")["company"],
        }
    )["plan"]
    assert plan.requested_modules == ["events"]
    assert plan.event_sentiment == "positive"
    assert not plan.impact_requested


def test_announcement_list_query_uses_events_only():
    plan = plan_modules_node(
        {
            "user_query": "金杯汽车的最新公告有哪些",
            "company": _state("x")["company"],
        }
    )["plan"]
    assert plan.requested_modules == ["events"]
    assert plan.event_list_requested
    assert plan.event_sentiment == "all"


def test_market_wide_announcement_query_does_not_require_fake_company():
    plan = plan_modules_node(
        {
            "user_query": "最近有没有上市公司发布了控股股东股权质押公告",
            "company": None,
        }
    )["plan"]
    assert plan.intent == "research"
    assert plan.event_list_requested


def test_unsupported_indicator_precedes_entity_resolution():
    plan = plan_modules_node(
        {
            "user_query": "贵州茅台最近一个报告期基本每股收益是多少",
            "company": None,
            "entity_resolution_error": "company_not_found",
        }
    )["plan"]
    assert plan.intent == "unsupported_indicator"


def test_market_quote_fields_route_to_anysearch_snapshot():
    cases = (
        ("贵州茅台今天股价", "close"),
        ("恒生电子换手率", "turnover_rate"),
        ("东吴证券总市值", "total_mv"),
        ("恒生电子股息率", "dividend_yield"),
        ("东吴证券今日成交量", "volume"),
        ("平安银行今日是涨还是跌", "pct_chg"),
        ("平安银行的当前市价是多少", "close"),
    )
    for question, field in cases:
        plan = plan_modules_node(_state(question))["plan"]
        assert plan.intent == "market_quote"
        assert plan.market_field == field
        assert plan.requested_modules == []
        assert detect_chitchat_intent(question) is None


def test_market_history_still_routes_but_requires_service_level_history():
    plan = plan_modules_node(_state("中兴通讯的近一月涨跌幅"))["plan"]
    assert plan.intent == "market_quote"
    assert plan.market_field == "pct_chg"


def test_market_decision_questions_use_explicit_boundaries():
    advice = plan_modules_node(_state("上海机电还可以买入吗？"))["plan"]
    execution = plan_modules_node(_state("帮我买入100手贵州茅台"))["plan"]
    clear_position = plan_modules_node(_state("清仓东方财富"))["plan"]
    shares = plan_modules_node(_state("135元买入五粮液100股"))["plan"]
    assert advice.intent == "investment_advice"
    assert execution.intent == "trade_execution"
    assert clear_position.intent == "trade_execution"
    assert shares.intent == "trade_execution"
    assert detect_chitchat_intent("帮我买入100手贵州茅台") is None


def test_generic_buy_recommendation_does_not_inherit_previous_company():
    plan = plan_modules_node(_state("推买入哪些证券股票"))["plan"]
    assert plan.intent == "investment_advice"


def test_generic_research_questions_do_not_fall_back_to_company_guide():
    for question in (
        "推荐一些市场热点资讯",
        "有哪些医疗器械技术正在研发中？",
        "大数据安全领域的技术趋势有哪些？",
    ):
        plan = plan_modules_node({"user_query": question, "company": None})["plan"]
        assert plan.intent == "research"


def test_industry_latest_dynamics_stays_research_without_company():
    plan = plan_modules_node(
        {"user_query": "新能源汽车产业链的最新动态是什么", "company": None}
    )["plan"]

    assert plan.intent == "research"


def test_multi_metric_query_does_not_silently_answer_first_metric():
    plan = plan_modules_node(
        {
            "user_query": "东方电子2023年总股本、营业收入、净资产、收盘价、eps",
            "company": _state("x")["company"],
        }
    )["plan"]
    assert plan.intent == "multi_metric"


def test_company_research_and_latest_dynamics_do_not_use_generic_risk_answer():
    research = plan_modules_node(_state("哈药股份的机构评级有哪些变化"))["plan"]
    dynamics = plan_modules_node(_state("双良节能最新的市场动态是什么"))["plan"]
    assert research.intent == "research"
    assert research.requested_modules == []
    assert dynamics.intent == "simple_query"
    assert dynamics.requested_modules == ["events"]
    assert dynamics.event_list_requested


def test_unsupported_market_analytics_do_not_start_diagnosis():
    for question in (
        "300669今日主力资金是否净流入",
        "中锐股份压力位在哪里",
        "恒大高新量价关系是否显示主力意图",
    ):
        plan = plan_modules_node(_state(question))["plan"]
        assert plan.intent == "unsupported_indicator", question
        assert plan.requested_modules == []


def test_market_wide_question_is_unsupported_before_fake_company_resolution():
    plan = plan_modules_node(
        {
            "user_query": "今天有哪些股票表现较好？",
            "company": None,
            "entity_resolution_error": "company_not_found",
        }
    )["plan"]
    assert plan.intent == "unsupported"


def test_market_field_without_company_is_explicitly_unsupported():
    plan = plan_modules_node({"user_query": "近一月涨跌幅", "company": None})["plan"]

    assert plan.intent == "unsupported"


def test_account_and_trading_rules_are_unsupported_before_entity_error():
    for question in (
        "如何查询国债逆回购的成交记录",
        "多个账户是否可同时开通创业板权限",
        "如何查询信用账户的手续费",
    ):
        plan = plan_modules_node(
            {
                "user_query": question,
                "company": None,
                "entity_resolution_error": "company_not_found",
            }
        )["plan"]
        assert plan.intent == "unsupported", question


def test_market_decision_boundary_precedes_missing_entity():
    plan = plan_modules_node(
        {
            "user_query": "基金etf515000能不能买",
            "company": None,
            "entity_resolution_error": "company_not_found",
        }
    )["plan"]
    assert plan.intent == "investment_advice"


def test_reverse_order_trade_details_use_trade_boundary():
    plan = plan_modules_node(
        {
            "user_query": "135元 300股 000858 卖出",
            "company": _state("x")["company"],
        }
    )["plan"]
    assert plan.intent == "trade_execution"


def test_cleared_position_history_query_is_not_trade_execution():
    plan = plan_modules_node(
        {
            "user_query": "如何查询已清仓股票",
            "company": None,
            "entity_resolution_error": "company_not_found",
        }
    )["plan"]
    assert plan.intent == "unsupported"


def test_continuous_loss_question_uses_net_profit_trend_count():
    plan = plan_modules_node(_state("通威股份连续亏损了几年"))["plan"]
    assert plan.intent == "indicator"
    assert plan.indicator == "net_profit"
    assert plan.answer_operation == "loss_years"


def test_company_research_advantage_routes_to_research():
    plan = plan_modules_node(_state("惠泰医疗在冠脉通路领域的核心优势是什么"))["plan"]
    assert plan.intent == "research"
    assert plan.requested_modules == []


def test_company_fact_boundaries_use_fact_or_research_routes():
    assert (
        plan_modules_node(_state("中国重工是退市了？"))["plan"].intent == "company_fact"
    )
    assert (
        plan_modules_node(_state("新光制药属于哪个细分板块"))["plan"].intent
        == "company_fact"
    )
    assert (
        plan_modules_node(_state("海能达最新的财务报告有哪些？"))["plan"].intent
        == "research"
    )


def test_market_price_prediction_does_not_start_financial_diagnosis():
    for question in ("看看中铁装配会反转吗", "云鼎科技目前走势分析"):
        plan = plan_modules_node(_state(question))["plan"]
        assert plan.intent == "causal_query"
        assert plan.requested_modules == []


def test_company_external_price_impact_is_honest_causal_boundary():
    plan = plan_modules_node(_state("多晶硅价格上涨9%对通威股份业绩的影响"))["plan"]
    assert plan.intent == "causal_query"
    assert plan.requested_modules == []


def test_query_semantic_context_is_single_source_for_boundary_features():
    context = _QuerySemanticContext.from_query("多晶硅价格上涨9%对通威股份业绩的影响")
    assert context.answer_operation == "impact"
    assert context.is_causal_boundary
    assert not context.is_multi_metric
    assert context.market_field is None


def test_volume_price_rise_is_explicitly_unsupported_indicator():
    plan = plan_modules_node(_state("天龙股份属于量价齐升吗"))["plan"]
    assert plan.intent == "unsupported_indicator"


def test_external_market_field_is_explicitly_unsupported():
    plan = plan_modules_node(_state("外盘"))["plan"]
    assert plan.intent == "unsupported_indicator"


def test_account_and_unsupported_analysis_boundaries_do_not_diagnose():
    cases = (
        "如何查询预留手机号码",
        "如何设置个股行情页面",
        "比亚迪研发投入占比多少？",
        "中工国际K线在60日均线附近吗",
    )
    for question in cases:
        plan = plan_modules_node(_state(question))["plan"]
        assert plan.intent in {"unsupported", "unsupported_indicator"}, question
