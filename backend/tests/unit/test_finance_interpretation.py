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


@pytest.mark.parametrize("pct", ["1%", "2%", "4%", "6%", "7%"])
def test_interpretation_rejects_rule_id_digit_collision(monkeypatch, pct):
    """P1 回归：规则 ID 数字（R1→1）不得作为合法数值，编造 1%/2%/… 必须拒绝。

    来源仅含 R1 + 149.6 时，若提取前不移除 R\d+，编造的 1% 会因
    R1 贡献数字 1 而通过溯源校验。
    """
    from app.agents.nodes.finance import _validate_interpretation

    source = '{"R1": {"rule_name": "应收-营收背离", "current": {"acct_rcv_growth": {"value": 149.6}}}}'
    fabricated = (
        f"【预警点】应收异常。\n【数据对比】增速 {pct}。\n"
        "【可能模式】收入虚增。\n【限制说明】无。"
    )
    assert not _validate_interpretation(fabricated, source), f"编造 {pct} 应被拒绝"


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


def test_fallback_creation_failure_keeps_primary(monkeypatch):
    """P2 回归：备用 Provider 构造失败时，不得丢弃已创建的主 Provider."""
    from app.agents.llm_sync import _get_providers
    from app.core.config import settings

    class _Primary:
        provider_name = "primary"
        _client = None

    primary = _Primary()
    calls = []

    def _fake_create(backend=None):
        calls.append(backend)
        if backend == "qwen":
            raise RuntimeError("fallback init failed")
        return primary

    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    monkeypatch.setattr(settings, "LLM_FALLBACK_BACKEND", "qwen")
    monkeypatch.setattr(
        "app.infrastructure.llm.factory.create_llm_provider",
        _fake_create,
    )

    actual_primary, actual_fallback = _get_providers()

    assert actual_primary is primary
    assert actual_fallback is None
    assert calls == [None, "qwen"]


def test_run_llm_chat_timeout_cancels_task_and_closes_client(monkeypatch):
    """P2 回归：超时后底层 asyncio task 被真正取消，客户端关闭，备用不调用."""
    import threading
    import time

    from app.agents.llm_sync import run_llm_chat

    cancelled = threading.Event()
    closed = threading.Event()
    fallback_called = threading.Event()

    class _Client:
        async def close(self):
            closed.set()

    class _SlowPrimary:
        provider_name = "primary"
        _client = _Client()

        async def chat(self, messages):
            try:
                await asyncio.sleep(30)
                return "late result"
            except asyncio.CancelledError:
                cancelled.set()
                raise

    class _Fallback:
        provider_name = "fallback"
        _client = None

        async def chat(self, messages):
            fallback_called.set()
            return "fallback result"

    monkeypatch.setattr(
        "app.agents.llm_sync._get_providers",
        lambda: (_SlowPrimary(), _Fallback()),
    )

    started = time.monotonic()
    result = run_llm_chat([], timeout=0.1)
    elapsed = time.monotonic() - started

    assert result == ""
    assert elapsed < 2
    assert cancelled.wait(2), "底层 asyncio task 未收到取消"
    assert closed.wait(2), "取消后 Provider 客户端未关闭"
    assert not fallback_called.is_set(), "总超时后不应继续调用备用 Provider"


def test_structured_none_switches_to_fallback():
    """P2-1 回归：主 provider 结构化返回 None（失败语义）→ 切换备用。"""
    from pydantic import BaseModel

    from app.agents.llm_sync import _call_with_fallback

    class _Schema(BaseModel):
        finance: bool = False

    class _PrimaryNone:
        provider_name = "primary"
        calls = 0

        async def structured_chat(self, messages, schema, **kwargs):
            self.calls += 1
            return None  # 失败语义（base provider 降级后返回 None）

    class _FallbackOk:
        provider_name = "fallback"
        calls = 0

        async def structured_chat(self, messages, schema, **kwargs):
            self.calls += 1
            return schema(finance=True)

    primary, fallback = _PrimaryNone(), _FallbackOk()
    result = asyncio.run(
        _call_with_fallback(primary, fallback, lambda p: p.structured_chat([], _Schema))
    )
    assert fallback.calls == 1, "主返回 None 应切换备用"
    assert result.finance is True
