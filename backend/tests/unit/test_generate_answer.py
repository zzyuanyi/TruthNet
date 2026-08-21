"""GenerateAnswer 节点单元测试 — V12 §7.2/§2.6 + Phase D #13.

覆盖：四层回答结构、risk_level 分级、追问生成（规则/缺失数据/缺失模块）、
company None、FinalResponse 字段透传、LLM 问答润色（Phase D #13）。
"""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.nodes.generate_answer import generate_answer_node
from app.agents.state import (
    AgentState,
    Claim,
    CompanyRef,
    ExecutionPlan,
    EventsResult,
    FinanceResult,
    ModuleResults,
    ModuleStatus,
    RuntimeState,
)
from app.application.ports.web_search_provider import SearchResult
from app.application.services.market_quote_service import MarketQuoteResult


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


def test_positive_event_query_does_not_render_negative_summary():
    events = EventsResult(
        timeline=[
            {"date": "2026-01-01", "title": "监管处罚", "sentiment": "negative"},
            {"date": "2026-02-01", "title": "回购公告", "sentiment": "positive"},
        ]
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("东吴证券", "601555.SH"),
                plan=ExecutionPlan(
                    intent="simple_query",
                    requested_modules=["events"],
                    event_sentiment="positive",
                ),
                results=ModuleResults(events=events),
            ),
            "user_query": "最近有哪些利好事件",
        }
    )
    answer = result["final_response"].answer
    assert "回购公告" in answer
    assert "监管处罚" not in answer


def test_announcement_list_query_renders_all_events():
    events = EventsResult(
        timeline=[
            {
                "date": "2026-02-01",
                "title": "回购公告",
                "category": "股份回购",
                "sentiment": "positive",
                "evidence_ids": ["ev_ann_1"],
            },
            {
                "date": "2026-01-01",
                "title": "监管处罚",
                "category": "监管处罚",
                "sentiment": "negative",
                "evidence_ids": ["ev_ann_2"],
            },
        ]
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("金杯汽车", "600609.SH"),
                plan=ExecutionPlan(
                    intent="simple_query",
                    requested_modules=["events"],
                    event_list_requested=True,
                ),
                results=ModuleResults(events=events),
            ),
            "user_query": "金杯汽车的最新公告有哪些",
        }
    )
    answer = result["final_response"].answer
    assert "回购公告" in answer
    assert "监管处罚" in answer
    assert "ev_ann_1" in answer
    assert answer.index("回购公告") < answer.index("监管处罚")


def test_latest_announcement_states_dataset_coverage():
    """旧数据集不能被包装成当前最新公告，也不能虚构正文。"""
    events = EventsResult(
        timeline=[
            {
                "date": "2025-01-09",
                "title": "行政处罚决定书公告",
                "sentiment": "negative",
                "evidence_ids": ["ev_ann_old"],
            }
        ]
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("东吴证券", "601555.SH"),
                plan=ExecutionPlan(
                    intent="simple_query",
                    requested_modules=["events"],
                    event_list_requested=True,
                ),
                results=ModuleResults(events=events),
            ),
            "user_query": "东吴证券的最新公告内容？",
        }
    )

    answer = result["final_response"].answer
    assert "数据集内最新可回查" in answer
    assert "截至 2025-01-09" in answer
    assert "不能把上述记录表述为当前市场的最新公告" in answer
    assert "未取回公告正文" in answer


def test_market_wide_announcement_query_explains_scope():
    result = generate_answer_node(
        {
            **_make_state(
                company=None,
                plan=ExecutionPlan(intent="research", event_list_requested=True),
            ),
            "user_query": "最近有没有上市公司发布了控股股东股权质押公告",
        }
    )
    answer = result["final_response"].answer
    assert "需要先指定上市公司或股票代码" in answer
    assert "不能据此确认所有上市公司的股权质押公告" in answer


def test_unresolved_market_question_does_not_ask_for_fake_company():
    result = generate_answer_node(
        {
            **_make_state(company=None),
            "user_query": "黄金板块还可以买吗",
            "entity_resolution_error": "company_not_found",
            "unresolved_fragments": ["黄金板块还可以买"],
        }
    )
    assert "只支持可识别的单只 A 股行情快照" in result["final_response"].answer
    assert "请提供完整名称" not in result["final_response"].answer


def test_no_company_investment_advice_uses_boundary_answer():
    result = generate_answer_node(
        {
            **_make_state(company=None),
            "user_query": "黄金板块还可以买吗？",
            "plan": ExecutionPlan(intent="investment_advice"),
        }
    )
    answer = result["final_response"].answer
    assert "不提供是否买入或卖出的投资建议" in answer
    assert "请提供完整公司名称" not in answer


def test_market_quote_answer_has_exact_field_date_and_evidence(monkeypatch):
    hit = SearchResult(
        title="600519.SH 20260820 日线行情",
        url="https://example.test/600519",
        snippet="trade_date=20260820 close=1291.5 amount=3280474.226",
        source="anysearch",
    )
    monkeypatch.setattr(
        "app.application.services.market_quote_service.query_market_quote",
        lambda **kwargs: MarketQuoteResult(
            status="ok",
            field="close",
            value=Decimal("1291.5"),
            raw_value="1291.5",
            trade_date="2026-08-20",
            hit=hit,
        ),
    )
    state = {
        **_make_state(
            company=_company("贵州茅台", "600519.SH"),
            plan=ExecutionPlan(intent="market_quote", market_field="close"),
        ),
        "user_query": "贵州茅台今天股价",
    }

    result = generate_answer_node(state)

    assert "2026-08-20" in result["final_response"].answer
    assert "收盘价为1,291.50元" in result["final_response"].answer
    assert result["evidence"][0].field_path == "market_quote.close"
    assert result["evidence"][0].value == "1291.5"
    assert result["claims"][0].evidence_ids == [result["evidence"][0].evidence_id]


def test_market_quote_missing_field_is_honest(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.market_quote_service.query_market_quote",
        lambda **kwargs: MarketQuoteResult(
            status="field_missing",
            field="volume",
            trade_date="2026-08-20",
            hit=SearchResult(snippet="amount=3280474.226", source="anysearch"),
        ),
    )
    state = {
        **_make_state(
            company=_company("东吴证券", "601555.SH"),
            plan=ExecutionPlan(intent="market_quote", market_field="volume"),
        ),
        "user_query": "东吴证券今日成交量",
    }

    result = generate_answer_node(state)

    assert "未返回成交量字段" in result["final_response"].answer
    assert result["evidence"] == []
    assert "成交额" not in result["final_response"].answer


def test_investment_advice_and_trade_execution_are_not_guessed():
    advice = generate_answer_node(
        {
            **_make_state(
                company=_company("上海机电", "600835.SH"),
                plan=ExecutionPlan(intent="investment_advice"),
            ),
            "user_query": "上海机电还可以买入吗？",
        }
    )["final_response"].answer
    execution = generate_answer_node(
        {
            **_make_state(
                company=_company("贵州茅台", "600519.SH"),
                plan=ExecutionPlan(intent="trade_execution"),
            ),
            "user_query": "帮我买入100手贵州茅台",
        }
    )["final_response"].answer
    assert "不提供是否买入或卖出的投资建议" in advice
    assert "不能代为买卖证券" in execution


def test_turnaround_question_explains_result(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_metric",
        lambda *args, **kwargs: type(
            "Result",
            (),
            {
                "status": "ok",
                "value": -1_776_000_000.0,
                "unit": "CNY",
                "period": "20251231",
                "observations": [],
                "label": "净利润",
            },
        )(),
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("通威股份", "600438.SH"),
                plan=ExecutionPlan(intent="indicator", indicator="net_profit"),
            ),
            "user_query": "通威股份2025年净利润能否扭亏为盈",
        }
    )
    answer = result["final_response"].answer
    assert "尚未扭亏为盈" in answer
    assert "17.76亿元" in answer


def test_receivable_impact_verifies_growth_before_risk_reasoning(monkeypatch):
    from app.application.services.indicator_query_service import IndicatorQueryResult

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_metric",
        lambda *args, **kwargs: IndicatorQueryResult(
            status="ok",
            indicator="accounts_receivable",
            label="应收账款余额",
            period="20251231",
            value=130.0,
            unit="CNY",
        ),
    )
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator_trend",
        lambda *args, **kwargs: [
            IndicatorQueryResult(
                status="ok",
                indicator="accounts_receivable",
                label="应收账款余额",
                period="20241231",
                value=100.0,
                unit="CNY",
            ),
            IndicatorQueryResult(
                status="ok",
                indicator="accounts_receivable",
                label="应收账款余额",
                period="20251231",
                value=130.0,
                unit="CNY",
            ),
        ],
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("贵州茅台", "600519.SH"),
                plan=ExecutionPlan(
                    intent="indicator",
                    indicator="accounts_receivable",
                    answer_operation="impact",
                ),
            ),
            "user_query": "贵州茅台应收账款激增有何风险？",
        }
    )
    answer = result["final_response"].answer
    assert "同比增长 30.00%" in answer
    assert "[推断]" in answer
    assert "坏账减值风险" in answer


def test_multi_metric_query_returns_available_items(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_metric",
        lambda *args, **kwargs: type(
            "Result",
            (),
            {
                "status": "ok",
                "value": 123_000_000.0,
                "unit": "CNY",
                "period": "20231231",
                "observations": [],
            },
        )(),
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company(),
                plan=ExecutionPlan(intent="multi_metric", as_of=date(2023, 12, 31)),
            ),
            "user_query": "康美药业2023年总股本、营业收入、净资产、收盘价、eps",
        }
    )
    answer = result["final_response"].answer
    assert "| 指标 | 数值 | 数据期与口径 |" in answer
    assert "| 总股本 | 暂无数据 | 当前数据范围未覆盖 |" in answer
    assert "营业收入" in answer
    assert "| 净资产 | 1.23亿元 | 2023-12-31，母公司口径 |" in answer


def test_research_list_questions_are_formatted_as_company_list():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "医疗器械行业的主要竞争者有哪些",
        [
            {"sec_name": "鱼跃医疗", "content": "片段"},
            {"sec_name": "海尔生物", "content": "片段"},
        ],
    )
    assert answer == "相关研报涉及的公司包括：鱼跃医疗、海尔生物。"


def test_research_technology_question_filters_marketing_noise():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "医疗器械行业正在研发哪些技术",
        [
            {
                "source_title": "医疗器械行业报告",
                "source_org": "测试机构",
                "content": "行业正在研发AI影像辅助诊断技术。营销渠道持续拓展，报告给出目标价。",
            }
        ],
    )
    assert "AI影像辅助诊断技术" in answer
    assert "营销渠道" not in answer
    assert "目标价" not in answer


def test_research_industry_question_marks_limited_sample():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "医疗器械行业整体表现如何",
        [
            {
                "source_title": "行业报告",
                "content": "市场规模保持增长。营销渠道改善。",
            }
        ],
    )
    assert "市场规模保持增长" in answer
    assert "营销渠道" not in answer
    assert "不能代表全行业全部公司" in answer


def test_research_emerging_company_questions_are_formatted_as_company_list():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "医疗器械行业有哪些新兴公司值得关注",
        [
            {"sec_name": "鱼跃医疗", "content": ""},
            {"sec_name": "海尔生物", "content": ""},
        ],
    )
    assert answer == "相关研报涉及的公司包括：鱼跃医疗、海尔生物。"


def test_research_sector_company_questions_are_formatted_as_company_list():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "化学制药板块有哪些公司",
        [
            {"sec_name": "司太立", "content": "片段"},
            {"sec_name": "华海药业", "content": "片段"},
        ],
    )
    assert answer == "相关研报涉及的公司包括：司太立、华海药业。"


def test_research_company_list_includes_source_table_when_available():
    from app.agents.nodes.generate_answer import _format_research_insights

    answer = _format_research_insights(
        "医疗器械行业的主要竞争者有哪些",
        [
            {
                "sec_name": "鱼跃医疗",
                "source_title": "医疗器械行业报告",
                "report_id": "rp_1",
                "content": "家用医疗设备覆盖较广",
            }
        ],
    )
    assert "相关研报涉及的公司包括：鱼跃医疗。" in answer
    assert "| 公司 | 研报依据 | 摘要 |" in answer


def test_company_research_returns_source_table_without_generic_risk(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.research_search.report_insights_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.application.services.research_search.search_research_insights_sync",
        lambda *args, **kwargs: [
            {
                "report_id": "rp_1",
                "source_date": "2026-08-18",
                "source_org": "测试证券",
                "source_title": "公司评级更新",
                "content": "盈利预测维持稳定，评级由增持调整为中性。",
            }
        ],
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("哈药股份", "600664.SH"),
                plan=ExecutionPlan(intent="research"),
            ),
            "user_query": "哈药股份的机构评级有哪些变化",
        }
    )
    answer = result["final_response"].answer
    assert "| 日期 | 机构 / 研报 | 核心观点 |" in answer
    assert "公司评级更新" in answer
    assert "综合分析完成" not in answer
    assert len(result["evidence"]) == 1


def test_continuous_loss_answer_counts_latest_negative_years_and_uses_table(
    monkeypatch,
):
    from app.application.services.indicator_query_service import IndicatorQueryResult

    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator_trend",
        lambda *args, **kwargs: [
            IndicatorQueryResult(
                status="ok",
                indicator="net_profit",
                label="净利润",
                period="20231231",
                value=2.0,
                unit="CNY",
            ),
            IndicatorQueryResult(
                status="ok",
                indicator="net_profit",
                label="净利润",
                period="20241231",
                value=-1.0,
                unit="CNY",
            ),
            IndicatorQueryResult(
                status="ok",
                indicator="net_profit",
                label="净利润",
                period="20251231",
                value=-2.0,
                unit="CNY",
            ),
        ],
    )
    result = generate_answer_node(
        {
            **_make_state(
                company=_company("通威股份", "600438.SH"),
                plan=ExecutionPlan(
                    intent="indicator",
                    indicator="net_profit",
                    answer_operation="loss_years",
                ),
            ),
            "user_query": "通威股份连续亏损了几年",
        }
    )
    answer = result["final_response"].answer
    assert "| 年度 | 净利润 |" in answer
    assert "连续亏损 2 年" in answer


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
    # 新契约：股权维度输出控制链细节（控制人/路径/持股），不只计数
    assert "股权维度：" in fr.answer
    assert "事件维度存在 1 项信号" in fr.answer

    # ④ 追问：equity/event claim 触发对应追问
    assert "查看实控人控制的其他上市公司" in fr.follow_ups
    assert "查看公司事件时间线" in fr.follow_ups


def test_company_analysis_includes_brief_summary():
    """公司综合提问 → 附带轻量简要分析，不缺席。"""
    claims = [
        _claim("c1", "financial", "red", "R1"),
        _claim("c2", "equity", "orange", None),
        _claim("c3", "event", "yellow", None),
    ]
    state = _make_state(
        company=_company("金牌家居", "603180.SH"),
        claims=claims,
        plan=ExecutionPlan(intent="analysis"),
    )
    answer = generate_answer_node(state)["final_response"].answer
    assert "【简要分析】金牌家居整体判断" in answer
    assert "财务信号 1 项" in answer
    assert "股权信号 1 项" in answer
    assert "事件信号 1 项" in answer


def test_no_risk_signal_conclusion():
    """无风险信号 claim → "未发现明显异常" + green。"""
    claims = [_claim("c1", "financial", "green", None)]
    result = generate_answer_node(_make_state(company=_company(), claims=claims))
    fr = result["final_response"]
    assert "未发现明显异常信号" in fr.answer
    assert fr.risk_level == "green"


def test_module_failure_no_signal_conclusion_is_degraded():
    """模块失败且无 claim 时，头行不得 fail-open 为未发现异常。"""
    plan = ExecutionPlan(requested_modules=["finance"])
    module_status = {
        "finance": ModuleStatus(state="failed", error_code="DB_ERROR", recoverable=True)
    }
    result = generate_answer_node(
        _make_state(company=_company(), plan=plan, module_status=module_status)
    )
    fr = result["final_response"]
    assert "本轮分析未完整完成" in fr.answer
    assert "财务模块失败" in fr.answer
    assert "无法确认是否存在明显异常信号" in fr.answer
    assert "未发现明显异常信号" not in fr.answer


def test_report_period_without_financial_claims_discloses_scope_limit():
    plan = ExecutionPlan(
        intent="diagnose",
        requested_modules=["finance", "equity", "events"],
        as_of=date(2025, 9, 30),
        as_of_kind="report_period",
        requested_period_text="三季报",
    )
    state = _make_state(
        company=_company("东吴证券", "601555.SH"),
        plan=plan,
        claims=[_claim("event-1", "event", "red", None)],
        results=ModuleResults(
            finance=FinanceResult(rule_statuses={"R1": "not_applicable"})
        ),
    )
    answer = generate_answer_node(state)["final_response"].answer
    assert "未提取到三季报可核验的财务指标" in answer
    assert "不能替代该报告期的财务分析" in answer


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
    assert "| 指标 | 数值 | 单位 |" in answer
    assert "| 应收账款增速 | 149.6% | % |" in answer
    assert "| 增速差距 | 166.2pp | pp |" in answer
    assert "| 连续负现金流季度 | 2个季度 | 个季度 |" in answer
    assert "| 存货周转天数 | 20天 | 天 |" in answer
    assert "| 存在大额其他应收款 | 是 | 暂无 |" in answer


def test_rule_details_single_metric_keeps_short_text():
    rule_details = {
        "R1": {
            "rule_name": "应收-营收背离",
            "severity": "red",
            "current": {
                "acct_rcv_growth": {"value": 149.6, "unit": "percent"},
            },
        },
    }
    answer = generate_answer_node(_rule_state(rule_details))["final_response"].answer
    assert "【数据对比】应收账款增速 149.6%。" in answer
    assert "| 指标 | 数值 | 单位 |" not in answer


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


def test_unsupported_plan_with_company_does_not_fail_open_to_normal():
    state = _make_state(
        company=_company("华旺科技", "605377.SH"),
        plan=ExecutionPlan(intent="unsupported"),
    )
    answer = generate_answer_node(state)["final_response"].answer
    assert "超出了织网鉴真的服务范围" in answer
    assert "未发现明显异常信号" not in answer


def test_explicit_consolidated_scope_is_rejected():
    state = _make_state(company=_company())
    state["user_query"] = "请按合并口径分析康美药业财务风险"
    result = generate_answer_node(state)
    answer = result["final_response"].answer
    assert "不能切换为合并口径" in answer
    assert result["final_response"].claims == []


def test_multi_year_indicator_does_not_fall_back_to_latest(monkeypatch):
    from app.application.services.indicator_query_service import IndicatorQueryResult

    from app.agents.nodes.generate_answer import _answer_indicator

    state = _make_state(
        company=_company(),
        plan=ExecutionPlan(intent="indicator", indicator="operating_revenue"),
    )
    state["user_query"] = "最近三年营收变化"
    # 8/20 CI 修复：本测试此前依赖真实 DB（本地 mysql 有数据、CI sqlite 空）
    # 导致 query_indicator_trend 返回空 → 误走"年度序列不足"分支。
    # 显式 mock 三年序列，使断言与数据库环境无关。
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_indicator_trend",
        lambda *args, **kwargs: [
            IndicatorQueryResult(
                status="ok",
                indicator="operating_revenue",
                label="营业收入",
                period="20231231",
                value=100.0,
                unit="CNY",
            ),
            IndicatorQueryResult(
                status="ok",
                indicator="operating_revenue",
                label="营业收入",
                period="20241231",
                value=120.0,
                unit="CNY",
            ),
            IndicatorQueryResult(
                status="ok",
                indicator="operating_revenue",
                label="营业收入",
                period="20251231",
                value=150.0,
                unit="CNY",
            ),
        ],
    )
    monkeypatch.setattr(
        "app.application.services.indicator_query_service.query_metric",
        lambda *a, **k: pytest.fail("多年趋势不得查询并冒充最新单期"),
    )
    result = _answer_indicator(state, "operating_revenue")
    answer = result["final_response"].answer
    assert "年度序列" in answer
    assert "2023年" in answer and "2025年" in answer


# ── 2026-08-12 批 1.5：实体解析失败/候选截断文案 ─────────────


def test_entity_resolution_error_message():
    """疑似公司未识别 → 明确文案（非通用引导）。"""
    state = _make_state(company=None)
    state["entity_resolution_error"] = "company_not_found"
    state["unresolved_fragments"] = ["台积电"]
    result = generate_answer_node(state)
    answer = result["final_response"].answer
    assert "台积电" in answer
    assert "未能识别" in answer


def test_candidates_truncated_message():
    """候选过多截断 → 明确文案。"""
    state = _make_state(company=None)
    state["candidates_truncated"] = True
    result = generate_answer_node(state)
    assert "候选公司过多" in result["final_response"].answer


# ── v3.3.3 批次 C：轻量比较渲染（方案 §8.2）──────────────────


def _light_compare_state():
    from app.agents.state import ComparisonSpec

    return {
        "company": _company(),
        "plan": ExecutionPlan(
            intent="light_comparison",
            comparison=ComparisonSpec(
                scope="same_company_cross_indicator",
                mode="indicator",
                metric_ids=[
                    "accounts_receivable_growth",
                    "operating_revenue_growth",
                ],
                operation="difference",
            ),
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }


def test_answer_light_comparison_ok(monkeypatch):
    """批次 C：ok 结果渲染结论 + indicator_comparison claim + 证据。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.application.services.light_comparison_service import (
        ComparisonValue,
        LightComparisonResult,
    )

    conclusion = (
        "应收账款同比增速（12.50%）比营业收入同比增速（8.00%）"
        "高 4.50个百分点（共同期间 20250331，母公司口径）"
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_same_company_indicators",
        lambda *a, **k: LightComparisonResult(
            status="ok",
            scope="same_company_cross_indicator",
            operation="difference",
            participants=[
                ComparisonValue(
                    company_code="600518.SH",
                    sec_name="康美药业",
                    metric_id="accounts_receivable_growth",
                    metric_label="应收账款同比增速",
                    period="20250331",
                    value=12.5,
                    unit="percent",
                ),
                ComparisonValue(
                    company_code="600518.SH",
                    sec_name="康美药业",
                    metric_id="operating_revenue_growth",
                    metric_label="营业收入同比增速",
                    period="20250331",
                    value=8.0,
                    unit="percent",
                ),
            ],
            period="20250331",
            conclusion=conclusion,
        ),
    )
    out = _answer_light_comparison(_light_compare_state())
    assert "高 4.50个百分点" in out["final_response"].answer
    assert out["claims"][0].claim_type == "indicator_comparison"
    assert out["claims"][0].verification_status == "verified"
    assert out["executed_metrics"] == [
        {
            "metric_id": "accounts_receivable_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
            "company_code": "600518.SH",
        },
        {
            "metric_id": "operating_revenue_growth",
            "period": "20250331",
            "unit": "percent",
            "status": "ok",
            "company_code": "600518.SH",
        },
    ]


def test_answer_light_comparison_partial_no_winner(monkeypatch):
    """方案 §4.6：partial 只列可得一侧，不输出高低结论。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.application.services.light_comparison_service import (
        LightComparisonResult,
    )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_same_company_indicators",
        lambda *a, **k: LightComparisonResult(
            status="partial",
            scope="same_company_cross_indicator",
            operation="difference",
            warnings=["一侧指标数据不可用，仅列可得一侧，不比较高低"],
        ),
    )
    out = _answer_light_comparison(_light_compare_state())
    answer = out["final_response"].answer
    assert "无法比较高低" in answer
    assert out["claims"] == []
    assert out["executed_metrics"] == []  # 非 ok 轮不产出执行记录


def test_answer_light_comparison_unit_mismatch_clarifies(monkeypatch):
    """方案 §4.5：单位不兼容 → 澄清文案，不硬算。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.application.services.light_comparison_service import (
        LightComparisonResult,
    )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_same_company_indicators",
        lambda *a, **k: LightComparisonResult(
            status="unsupported",
            scope="same_company_cross_indicator",
            operation="difference",
            warnings=["单位不兼容（CNY vs percent），不得直接相减"],
        ),
    )
    out = _answer_light_comparison(_light_compare_state())
    assert "单位不兼容" in out["final_response"].answer
    assert out["claims"] == []


def test_answer_light_comparison_insufficient_data_no_conclusion(monkeypatch):
    """方案 §4.4：无共同期间 → 诚实说明，不输出数值结论。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.application.services.light_comparison_service import (
        LightComparisonResult,
    )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_same_company_indicators",
        lambda *a, **k: LightComparisonResult(
            status="insufficient_data",
            scope="same_company_cross_indicator",
            operation="difference",
            warnings=["无共同期间，不得跨期相减"],
        ),
    )
    out = _answer_light_comparison(_light_compare_state())
    answer = out["final_response"].answer
    assert "无共同期间" in answer
    assert "无法完成" in answer
    assert out["claims"] == []


# ── v3.3.3 批次 D：跨公司轻量比较渲染（方案 §8.3）────────────────


def _cross_compare_state():
    from app.agents.state import ComparisonSpec

    return {
        "company": _company("伊利股份", "600887.SH"),
        "comparison_targets": [
            _company("伊利股份", "600887.SH"),
            _company("双汇发展", "000895.SZ"),
        ],
        "plan": ExecutionPlan(
            intent="light_comparison",
            comparison=ComparisonSpec(
                scope="cross_company",
                mode="indicator",
                metric_ids=["r4_turnover_days"],
                operation="less_than",
            ),
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }


def test_answer_cross_company_indicator_ok(monkeypatch):
    """官方原题渲染：双方原始值 + 共同期间 + 程序差值。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.application.services.light_comparison_service import (
        ComparisonValue,
        LightComparisonResult,
    )

    conclusion = (
        "伊利股份（600887.SH）存货周转天数为100.00天；"
        "双汇发展（000895.SZ）为110.00天。"
        "存货周转天数：伊利股份比双汇发展低 10.00天"
        "（共同期间 20241231，母公司口径）"
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_cross_company_indicators",
        lambda *a, **k: LightComparisonResult(
            status="ok",
            scope="cross_company",
            operation="less_than",
            participants=[
                ComparisonValue(
                    company_code="600887.SH",
                    sec_name="伊利股份",
                    metric_id="r4_turnover_days",
                    metric_label="存货周转天数",
                    period="20241231",
                    value=100.0,
                    unit="days",
                ),
                ComparisonValue(
                    company_code="000895.SZ",
                    sec_name="双汇发展",
                    metric_id="r4_turnover_days",
                    metric_label="存货周转天数",
                    period="20241231",
                    value=110.0,
                    unit="days",
                ),
            ],
            period="20241231",
            conclusion=conclusion,
        ),
    )
    out = _answer_light_comparison(_cross_compare_state())
    answer = out["final_response"].answer
    assert "低 10.00天" in answer
    assert out["claims"][0].claim_type == "indicator_comparison"
    assert out["executed_metrics"] == [
        {
            "metric_id": "r4_turnover_days",
            "period": "20241231",
            "unit": "days",
            "status": "ok",
            "company_code": "600887.SH",
        },
        {
            "metric_id": "r4_turnover_days",
            "period": "20241231",
            "unit": "days",
            "status": "ok",
            "company_code": "000895.SZ",
        },
    ]


def test_answer_cross_company_missing_dimension(monkeypatch):
    """「那茅台呢，对比一下」→ 追问维度，不启动数值查询。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.agents.state import ComparisonSpec

    state = _cross_compare_state()
    state["plan"] = ExecutionPlan(
        intent="light_comparison",
        comparison=ComparisonSpec(scope="cross_company", mode="missing_dimension"),
    )
    out = _answer_light_comparison(state)
    assert "请指定要比较的维度" in out["final_response"].answer
    assert out["claims"] == []


def test_answer_cross_company_risk_page_guide():
    """批次 D 诚实路由：风险维度 → 页面引导文案。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.agents.state import ComparisonSpec

    state = _cross_compare_state()
    state["plan"] = ExecutionPlan(
        intent="light_comparison",
        comparison=ComparisonSpec(scope="cross_company", mode="risk"),
    )
    out = _answer_light_comparison(state)
    assert "跨公司对比" in out["final_response"].answer
    assert out["claims"] == []


def test_answer_cross_company_fact_listing_date(monkeypatch):
    """官方原题渲染：上市日期早晚（年差由服务计算）。"""
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.agents.state import ComparisonSpec
    from app.application.services.light_comparison_service import (
        LightComparisonResult,
    )

    conclusion = (
        "中国石化（600028.SH）上市日期为2001-08-08；"
        "中国石油（601857.SH）为2007-11-05。中国石化比中国石油早约 6.3 年上市。"
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_cross_company_facts",
        lambda *a, **k: LightComparisonResult(
            status="ok",
            scope="cross_company",
            operation="earlier_than",
            conclusion=conclusion,
        ),
    )
    state = {
        "company": _company("中国石化", "600028.SH"),
        "comparison_targets": [
            CompanyRefWithDate("中国石化", "600028.SH", "2001-08-08"),
            CompanyRefWithDate("中国石油", "601857.SH", "2007-11-05"),
        ],
        "plan": ExecutionPlan(
            intent="light_comparison",
            comparison=ComparisonSpec(
                scope="cross_company",
                mode="company_fact",
                fact_key="listing_date",
                operation="earlier_than",
                period_policy="not_applicable",
            ),
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_light_comparison(state)
    answer = out["final_response"].answer
    assert "早约 6.3 年" in answer
    assert out["claims"][0].claim_type == "company_fact_comparison"
    assert len(out["evidence"]) == 2


def test_cross_company_fact_uses_web_fill_for_missing_dates(monkeypatch):
    from app.agents.nodes.generate_answer import _answer_light_comparison
    from app.agents.state import ComparisonSpec, EvidenceRef

    dates = {"600028.SH": "2001-08-08", "601857.SH": "2007-11-05"}
    calls: list[str] = []

    def fake_fill(**kwargs):
        code = kwargs["wind_code"]
        calls.append(code)
        value = dates[code]
        return value, EvidenceRef(
            evidence_id=f"ev_web_{code}",
            source_type="web_search",
            source_record_id=f"https://example.test/{code}",
            field_path="listing_date",
            value=value,
            company_code=code,
            module="company_fact",
        )

    monkeypatch.setattr(
        "app.agents.nodes._answer_comparison._web_search_fill_company_fact", fake_fill
    )
    state = {
        "company": _company("中国石化", "600028.SH"),
        "comparison_targets": [
            CompanyRefWithDate("中国石化", "600028.SH", ""),
            CompanyRefWithDate("中国石油", "601857.SH", ""),
        ],
        "plan": ExecutionPlan(
            intent="light_comparison",
            comparison=ComparisonSpec(
                scope="cross_company",
                mode="company_fact",
                fact_key="listing_date",
                operation="earlier_than",
                period_policy="not_applicable",
            ),
        ),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_light_comparison(state)
    assert calls == ["600028.SH", "601857.SH"]
    assert "早约" in out["final_response"].answer
    assert {e.source_type for e in out["evidence"]} == {"web_search"}


def CompanyRefWithDate(name: str, code: str, listing: str) -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code.replace('.', '_')}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
        listing_date=listing,
    )


# ── v3.3.4 Preview First：三家及以上保底（方案 §2.4/§6.1）────────────────


def _guide_state(query: str, codes_names: list[tuple[str, str]]) -> dict:
    return {
        "user_query": query,
        "company": None,
        "comparison_targets": [_company(name, code) for code, name in codes_names],
        "plan": ExecutionPlan(intent="comparison_guide"),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }


def test_answer_comparison_guide_three_companies_choose_pair():
    """方案 §2.4/§7.1-22：三家 finalized + 页面不支持多主体 →
    choose_comparison_pair（全部去重代码），不查询、不截断、overview_rows 空。"""
    from app.agents.nodes.generate_answer import _answer_comparison_guide

    state = _guide_state(
        "康美、茅台、五粮液对比一下",
        [("600518.SH", "康美药业"), ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液")],
    )
    out = _answer_comparison_guide(state)
    payload = out["light_comparison"]
    assert payload["comparison_mode"] == ""
    assert payload["overview_rows"] == []
    assert payload["requested_scope"] == "overview"
    assert payload["next_steps"][0]["kind"] == "choose_comparison_pair"
    assert payload["next_steps"][0]["participant_codes"] == [
        "600518.SH",
        "600519.SH",
        "000858.SZ",
    ]
    assert "尚未执行数值比较" in out["final_response"].answer
    assert out["final_response"].claims == []


def test_answer_comparison_guide_multi_page_enabled_open_multi(monkeypatch):
    """方案 §2.4/§7.1-21：页面支持多主体 → open_multi_company_comparison。"""
    from app.agents.nodes.generate_answer import _answer_comparison_guide
    from app.core.config import settings

    monkeypatch.setattr(settings, "COMPARISON_MULTI_PAGE_ENABLED", True)
    state = _guide_state(
        "全面对比康美、茅台和五粮液",
        [("600518.SH", "康美药业"), ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液")],
    )
    out = _answer_comparison_guide(state)
    payload = out["light_comparison"]
    assert payload["requested_scope"] == "full"
    assert payload["next_steps"][0]["kind"] == "open_multi_company_comparison"
    assert len(payload["next_steps"][0]["participant_codes"]) == 3
    assert "尚未执行数值比较" in out["final_response"].answer


def test_answer_comparison_guide_over_five_requires_narrowing():
    """方案 §2.4/§7.1-23：超过上限 5 家 → next_steps 为空、纯文案缩小范围，
    不传入部分主体、不默认选择、不查询。"""
    from app.agents.nodes.generate_answer import _answer_comparison_guide

    state = _guide_state(
        "这六家公司对比一下",
        [
            ("600518.SH", "康美药业"),
            ("600519.SH", "贵州茅台"),
            ("000858.SZ", "五粮液"),
            ("600887.SH", "伊利股份"),
            ("000895.SZ", "双汇发展"),
            ("601857.SH", "中国石油"),
        ],
    )
    out = _answer_comparison_guide(state)
    payload = out["light_comparison"]
    assert payload["next_steps"] == []
    assert payload["overview_rows"] == []
    answer = out["final_response"].answer
    assert "超过一次对比的上限 5 家" in answer
    assert "未执行任何指标查询" in answer


def test_answer_comparison_guide_single_company_full_no_preview():
    """方案 §2.1/§7.1-5：只有一家主体 + 全面对比 → 澄清文案，不生成伪造
    预览、不携带错误主体的跳转参数。"""
    from app.agents.nodes.generate_answer import _answer_comparison_guide

    state = {
        "user_query": "康美药业全面对比",
        "company": _company("康美药业", "600518.SH"),
        "comparison_targets": [],
        "plan": ExecutionPlan(intent="comparison_guide"),
        "runtime": RuntimeState(turn_id="turn-1", trace_id="trace-1"),
    }
    out = _answer_comparison_guide(state)
    assert "light_comparison" not in out
    assert "只有一家公司" in out["final_response"].answer
