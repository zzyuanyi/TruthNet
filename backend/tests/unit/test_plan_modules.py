"""plan_modules_node 交叉校验标签回归测试 + 混合路由（关键词+LLM 意图识别）。

Bug 修复: need_finance and need_equity → need_equity and need_events
Phase D: 关键词未命中 → LLM 语义识别兜底；失败/全 False → 全模块。
"""

from pydantic import BaseModel

from app.agents.nodes.plan_modules import plan_modules_node
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
