"""Finance LLM 解读（Phase D #12）单元测试.

覆盖：
- 固定四段解读结构（预警点/数据对比/可能模式/限制说明）
- 数值必须可追溯到 rule_details 原文
- LLM 失败/超时 → 回退规则 explanation
- 无 triggered 规则 → 不产出解读
- run_llm_chat 在事件循环线程内调用不抛 RuntimeError（WS 路径）
"""

import asyncio

import pytest

from app.agents.nodes.finance import _build_llm_interpretation

_RULE_DETAILS = {
    "R1": {
        "rule_name": "应收-营收背离",
        "explanation": "应收账款增速 149.6% 显著高于营业收入增速 -16.6%，差距 166.2pp",
        "severity": "red",
        "current": {
            "acct_rcv_growth": {"value": 149.6, "unit": "percent"},
            "oper_rev_growth": {"value": -16.6, "unit": "percent"},
            "growth_gap": {"value": 166.2, "unit": "percentage_point"},
        },
    },
    "R2": {
        "rule_name": "现金流-利润背离",
        "explanation": "现金流/利润比 -21.6，连续负现金流 2 个季度",
        "severity": "orange",
        "current": {
            "cf_to_profit_ratio": {"value": -21.6, "unit": "ratio"},
            "consec_neg_cf": {"value": 2, "unit": "quarters"},
        },
    },
}

_FOUR_PART_OUTPUT = (
    "【预警点】应收账款增速 149.6% 显著高于营收增速 -16.6%，现金流承压。\n"
    "【数据对比】增速差距 166.2pp，现金流/利润比 -21.6。\n"
    "【可能模式】收入虚增型特征，需进一步验证。\n"
    "【限制说明】基于母公司报表口径，不覆盖合并层面。"
)


class _FakeProvider:
    provider_name = "fake"

    def __init__(self, result: str = "", raise_error: bool = False):
        self.result = result
        self.raise_error = raise_error

    async def chat(self, messages: list[dict], **kwargs) -> str:
        if self.raise_error:
            raise RuntimeError("LLM 不可用")
        return self.result or ""

    async def chat_stream(self, messages, **kwargs):
        yield await self.chat(messages, **kwargs)

    async def structured_chat(self, messages, output_schema, **kwargs):
        return output_schema()

    async def check_connection(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    """默认注入返回空串的 fake provider（避免真调 DeepSeek）。"""

    def _install(provider):
        monkeypatch.setattr(
            "app.infrastructure.llm.factory.create_llm_provider",
            lambda backend=None: provider,
        )

    _install(_FakeProvider())
    return _install


def _rule_statuses(*triggered: str) -> dict[str, str]:
    return {
        rid: "triggered" if rid in triggered else "not_triggered"
        for rid in _RULE_DETAILS
    }


def test_interpretation_four_parts(monkeypatch):
    """LLM 返回四段解读 → 原样采用。"""
    statuses = _rule_statuses("R1", "R2")
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(result=_FOUR_PART_OUTPUT),
    )
    text = _build_llm_interpretation(_RULE_DETAILS, statuses)
    for part in ("【预警点】", "【数据对比】", "【可能模式】", "【限制说明】"):
        assert part in text


def test_interpretation_numbers_traceable_to_rule_details(monkeypatch):
    """解读段数值均可追溯 rule_details 原文。"""
    statuses = _rule_statuses("R1", "R2")
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(result=_FOUR_PART_OUTPUT),
    )
    text = _build_llm_interpretation(_RULE_DETAILS, statuses)
    for value in ("149.6%", "-16.6%", "166.2pp", "-21.6"):
        assert value in text, f"解读缺失原文数值 {value}"


def test_interpretation_llm_failure_falls_back_to_explanation(monkeypatch):
    """LLM 抛异常 → 回退规则 explanation 串（不伪造、不丢失信息）。"""
    statuses = _rule_statuses("R1", "R2")
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(raise_error=True),
    )
    text = _build_llm_interpretation(_RULE_DETAILS, statuses)
    assert text.startswith("【预警点】")
    assert "应收账款增速 149.6%" in text
    assert "现金流/利润比 -21.6" in text


def test_interpretation_empty_when_no_triggered(monkeypatch):
    """无 triggered 规则 → 不产出解读。"""
    statuses = _rule_statuses()
    text = _build_llm_interpretation(_RULE_DETAILS, statuses)
    assert text == ""


def test_interpretation_rejects_missing_markers(monkeypatch):
    """P1 验收：缺四段标记的 LLM 输出 → 拒绝，回退 explanation。"""
    bad = "预警点：应收异常。数据对比：增速差大。可能模式：收入虚增。限制说明：无。"  # 无【】
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(result=bad),
    )
    text = _build_llm_interpretation(_RULE_DETAILS, _rule_statuses("R1"))
    assert text.startswith("【预警点】")
    assert "应收账款增速 149.6%" in text  # 回退 explanation 原文


def test_interpretation_rejects_fabricated_numbers(monkeypatch):
    """P1 验收：新增编造数值（999%）→ 拒绝，回退 explanation。"""
    fabricated = (
        "【预警点】应收异常。\n【数据对比】增速差距 999%。\n"
        "【可能模式】收入虚增。\n【限制说明】无。"
    )
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(result=fabricated),
    )
    text = _build_llm_interpretation(_RULE_DETAILS, _rule_statuses("R1"))
    assert text.startswith("【预警点】")
    assert "999%" not in text  # 编造数值未进入输出
    assert "149.6%" in text  # 回退 explanation 含原文数值


def test_run_llm_chat_safe_inside_event_loop(monkeypatch):
    """WS 路径：事件循环线程内调用 run_llm_chat 不抛 RuntimeError。"""
    from app.agents.llm_sync import run_llm_chat

    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        lambda backend=None: _FakeProvider(result="ok"),
    )

    async def _inside_event_loop():
        # 模拟 WS：在事件循环线程内同步调用（直接 asyncio.run 会崩的场景）
        return run_llm_chat([{"role": "user", "content": "hi"}])

    text = asyncio.run(_inside_event_loop())
    assert text == "ok"


def test_run_llm_chat_timeout_fallback():
    """LLM 超时（>3s）→ 返回空串，调用方回退。"""
    import time

    from app.agents.llm_sync import run_llm_chat

    class _SlowProvider(_FakeProvider):
        async def chat(self, messages, **kwargs):
            await asyncio.sleep(30)
            return "太慢"

    # 直接注入需要 patch；此处手动替换 factory 属性
    from app.infrastructure.llm import factory as llm_factory

    original = llm_factory.create_llm_provider
    llm_factory.create_llm_provider = lambda backend=None: _SlowProvider()
    try:
        start = time.monotonic()
        text = run_llm_chat([{"role": "user", "content": "hi"}], timeout=1.0)
        elapsed = time.monotonic() - start
    finally:
        llm_factory.create_llm_provider = original
    assert text == ""
    assert elapsed < 5, "超时应在 1s 附近返回（线程不阻塞调用方）"
