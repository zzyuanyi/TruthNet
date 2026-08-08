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
    """应收账款+股东 → finance + equity，仅 financial_vs_cashflow，不出现 equity_vs_events。"""
    result = plan_modules_node(_state("应收账款和股东情况"))
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
    """营业收入如何 → 仅 finance，无交叉校验。"""
    result = plan_modules_node(_state("营业收入如何"))
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
