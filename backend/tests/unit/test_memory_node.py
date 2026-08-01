"""Memory 节点单元测试 — V12 §7.6.

覆盖：指代消解、实体提取、多轮上下文注入。
"""

import pytest
from app.agents.state import AgentState, CompanyRef, MemoryContext, RuntimeState

# ── 辅助 ────────────────────────────────────────────────────


def _make_state(
    query: str,
    messages: list | None = None,
    company: CompanyRef | None = None,
) -> AgentState:
    """构造 AgentState 用于测试。"""
    state: AgentState = {
        "user_query": query,
        "messages": messages or [],
        "company": company,
        "runtime": RuntimeState(
            request_id="test",
            trace_id="test_trace",
            session_id="test_session",
        ),
    }
    return state


def _msg(role: str, content: str) -> dict:
    """构造模拟消息。"""
    return {"role": role, "content": content}


# ── 指代检测 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query,expected",
    [
        ("它最近财务怎么样", True),
        ("它的应收账款增速如何", True),
        ("这家公司有风险吗", True),
        ("那家的股权结构呢", True),
        ("该公司近三年营收如何", True),
        ("上次那家公司现金流呢", True),
        ("刚才查的那家", True),
        ("之前那个指标", True),
        ("康美药业有风险吗", False),
        ("查询贵州茅台财务报表", False),
        ("帮我分析一下宁德时代", False),
        ("", False),
    ],
)
def test_anaphora_detection(query: str, expected: bool):
    """测试指代词检测。"""
    from app.agents.nodes.memory import _contains_anaphora

    assert _contains_anaphora(query) == expected


@pytest.mark.parametrize(
    "query,expected_type",
    [
        ("它最近怎么样", "explicit"),
        ("它的应收账款", "explicit"),
        ("这家公司有风险吗", "vague"),
        ("该公司近况", "vague"),
        ("上次那家公司", "back_reference"),
        ("刚才查的那家", "back_reference"),
        ("之前提到的那只股票", "back_reference"),
        ("康美药业有风险吗", "none"),
    ],
)
def test_anaphora_type(query: str, expected_type: str):
    """测试指代类型分类。"""
    from app.agents.nodes.memory import _extract_anaphora_type

    assert _extract_anaphora_type(query) == expected_type


# ── 公司名提取 ──────────────────────────────────────────────


def test_extract_companies_from_text():
    """从文本中提取公司名称。"""
    from app.agents.nodes.memory import _extract_companies_from_text

    text = "康美药业财务报表显示异常，和贵州茅台对比差距明显"
    companies = _extract_companies_from_text(text)
    assert "康美药业" in companies
    assert "贵州茅台" in companies


def test_extract_companies_dedup():
    """重复公司名去重保持首次出现顺序。"""
    from app.agents.nodes.memory import _extract_companies_from_text

    text = "康美药业和康美药业以及宁德时代，还有康美药业"
    companies = _extract_companies_from_text(text)
    assert companies == ["康美药业", "宁德时代"]


# ── 指标提取 ────────────────────────────────────────────────


def test_extract_indicators():
    """从文本中提取财务指标。"""
    from app.agents.nodes.memory import _extract_indicators_from_text

    text = "看看营收、净利润和经营现金流的情况"
    indicators = _extract_indicators_from_text(text)
    assert "营收" in indicators
    assert "净利润" in indicators
    assert "经营现金流" in indicators


# ── Lite 消解 ───────────────────────────────────────────────


def test_resolve_lite_no_anaphora():
    """无指代词时直接返回空消解。"""
    from app.agents.nodes.memory import _resolve_lite

    ctx = _resolve_lite("康美药业有风险吗", [], "康美药业")
    assert ctx.is_anaphora is False
    assert ctx.resolved_entity_name is None


def test_resolve_lite_with_anaphora_and_history():
    """含指代词且有历史消息时消解成功。"""
    from app.agents.nodes.memory import _resolve_lite

    messages = [
        _msg("user", "康美药业有风险吗"),
        _msg("assistant", "康美药业财务存在以下风险信号..."),
    ]
    ctx = _resolve_lite("它的应收账款怎么样", messages, None)

    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "康美药业"
    assert "康美药业" in ctx.previous_companies


def test_resolve_lite_with_anaphora_no_history_but_current():
    """含指代词但无历史消息时使用当前 company。"""
    from app.agents.nodes.memory import _resolve_lite

    ctx = _resolve_lite("它的应收账款怎么样", [], "康美药业")

    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "康美药业"


def test_resolve_lite_back_reference():
    """追问指代"上次那家"正确消解。"""
    from app.agents.nodes.memory import _resolve_lite

    messages = [
        _msg("user", "帮我分析一下贵州茅台"),
        _msg("assistant", "贵州茅台财务状况健康..."),
        _msg("user", "它的营收增长如何"),
        _msg("assistant", "贵州茅台营收增长稳定..."),
    ]
    ctx = _resolve_lite("上次那家公司的现金流呢", messages, None)

    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "贵州茅台"


def test_resolve_lite_multiple_companies():
    """多公司对话中取最近的实体。"""
    from app.agents.nodes.memory import _resolve_lite

    messages = [
        _msg("user", "对比康美药业和贵州茅台"),
        _msg("assistant", "两家公司对比如下..."),
        _msg("user", "宁德时代的营收属于什么行业"),
        _msg("assistant", "宁德时代属于电池行业..."),
    ]
    ctx = _resolve_lite("这家公司的股权结构呢", messages, None)

    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "宁德时代"  # 最近提到的


def test_resolve_lite_indicators_tracking():
    """历史中提及的指标被正确追踪。"""
    from app.agents.nodes.memory import _resolve_lite

    messages = [
        _msg("user", "康美药业营收和净利润增速如何"),
        _msg("assistant", "该公司的毛利率在下降..."),
        _msg("user", "应收账款和现金流呢"),
    ]
    ctx = _resolve_lite("这些指标的趋势", messages, None)

    assert "营收" in ctx.referenced_indicators or len(ctx.referenced_indicators) > 0


# ── 上下文消息构建 ──────────────────────────────────────────


def test_build_context_message_full():
    """完整上下文消息构建。"""
    from app.agents.nodes.memory import _build_context_message

    ctx = MemoryContext(
        resolved_entity_name="康美药业",
        is_anaphora=True,
        previous_companies=["康美药业"],
        referenced_indicators=["营收", "应收账款", "经营现金流"],
    )
    msg = _build_context_message(ctx)
    assert msg is not None
    assert "康美药业" in msg
    assert "营收" in msg


def test_build_context_message_empty():
    """空上下文不生成消息。"""
    from app.agents.nodes.memory import _build_context_message

    ctx = MemoryContext()
    msg = _build_context_message(ctx)
    assert msg is None


# ── 集成: memory_node ───────────────────────────────────────


def test_memory_node_no_anaphora():
    """memory_node 对普通查询返回上下文但无指代消解。"""
    from app.agents.nodes.memory import memory_node

    state = _make_state("康美药业有风险吗", [])
    result = memory_node(state)

    assert "memory_context" in result
    ctx = result["memory_context"]
    assert isinstance(ctx, MemoryContext)
    assert ctx.is_anaphora is False
    assert ctx.resolved_entity_name is None


def test_memory_node_with_anaphora():
    """memory_node 对含指代查询注入上下文消息。"""
    from app.agents.nodes.memory import memory_node

    messages = [
        _msg("user", "康美药业有风险吗"),
        _msg("assistant", "康美药业财务风险分析结果..."),
    ]
    state = _make_state("它的应收账款怎么样", messages)
    result = memory_node(state)

    assert "memory_context" in result
    ctx = result["memory_context"]
    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "康美药业"

    # 应注入上下文消息
    msgs = result.get("messages", [])
    assert len(msgs) > 0
    assert any("康美药业" in str(m.get("content", "")) for m in msgs)


def test_memory_node_with_current_company():
    """含指代词 + state.company 已设置的场景。"""
    from app.agents.nodes.memory import memory_node

    company = CompanyRef(
        entity_id="company_600519_SH",
        wind_code="600519.SH",
        sec_name="贵州茅台",
        exchange="XSHG",
    )
    state = _make_state("它的近况如何", [], company=company)
    result = memory_node(state)

    ctx = result["memory_context"]
    assert ctx.resolved_entity_name == "贵州茅台"


# ── 10 轮对话指代测试 ───────────────────────────────────────


def test_ten_turns_anaphora():
    """10 轮对话 + 指代消解正确性。"""
    from app.agents.nodes.memory import memory_node

    turns = [
        ("康美药业有风险吗", "康美药业财务存在以下高风险信号..."),
        ("它的应收账款增速如何", "康美药业应收账款增速47.2%与营收增速背离..."),
        ("那现金流和利润呢", "经营现金流为负，与净利润背离..."),
        ("这家公司的股权结构", "康美药业实控人为..."),
        ("上次提到的存货指标呢", "存货增速与营收存在异常..."),
        ("它还有其他风险吗", "还检测到存贷双高信号..."),
        ("该公司的现金流风险怎么样", "投资活动现金流持续为负..."),
        ("那关联方有什么异常吗", "其他应收款占比过高..."),
        ("之前分析的结论是什么", "综合风险为红色预警..."),
        ("这个结论可靠吗", "当前3项已核实，1项部分核实..."),
    ]

    messages: list[dict] = []
    for q, a in turns[:-1]:  # 前 9 轮作为历史
        messages.append(_msg("user", q))
        messages.append(_msg("assistant", a))

    # 第 10 轮：含指代"这个"
    last_q = turns[-1][0]
    state = _make_state(last_q, messages)
    result = memory_node(state)

    ctx = result["memory_context"]
    assert ctx.is_anaphora is True
    assert ctx.resolved_entity_name == "康美药业"  # 10 轮始终是康美
    assert len(ctx.previous_companies) > 0


def test_ten_turns_entity_switch():
    """10 轮对话中途切换公司时正确追踪。"""
    from app.agents.nodes.memory import memory_node

    turns = [
        ("康美药业有风险吗", "康美药业存在财务风险..."),
        ("贵州茅台呢", "贵州茅台财务状况健康..."),  # 切换
    ]

    messages = [
        _msg("user", q) if i % 2 == 0 else _msg("assistant", a)
        for i, (q, a) in enumerate(turns)
    ]

    state = _make_state("它的营收怎么样", messages)
    result = memory_node(state)

    ctx = result["memory_context"]
    # 最近提到的是贵州茅台
    assert ctx.resolved_entity_name == "贵州茅台"
