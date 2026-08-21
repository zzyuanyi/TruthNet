"""远期记忆提炼单元测试 — Phase D #15.

覆盖:
- 摘要结构（memory-v1）完整
- 有来源轮次 / 保留 Evidence
- 不把 LLM 新信息写入事实（确定性抽取）
- 限长
- 幂等（同来源提炼结果稳定）
- 失败不阻塞（损坏摘要回退 None）
- 注入区分远期摘要/近期轮次/当前问题
- 策略开关 none/recent_only/summary_plus_recent
"""

from app.application.services.memory_distillation import (
    MemorySummary,
    build_summary_for_turns,
    load_context_with_memory,
)
from app.application.services.response_meta_utils import effective_active_code


# ── 最终续审 §7 D1：effective active code 语义 ───────────────


def test_effective_active_code_new_data_explicit_empty():
    """新数据显式写了空 active subject → 返回空（跳过本轮继续回溯），
    不得回退陈旧的顶层 company_code。"""
    assert effective_active_code({"active_company_code": ""}, "600518.SH") == ""


def test_effective_active_code_old_data_no_field():
    """旧数据无 active_company_code 字段 → 回退顶层 company_code。"""
    assert effective_active_code({}, "600518.SH") == "600518.SH"


def test_effective_active_code_prefers_active():
    """comparison/reference 轮：active 与顶层 code 不同时取 active。"""
    assert (
        effective_active_code({"active_company_code": "600519.SH"}, "600518.SH")
        == "600519.SH"
    )


def _turns(n: int = 5):
    return [
        {
            "turn_id": f"turn_{i}",
            "turn_index": i + 1,
            "question": f"第{i+1}轮：康美药业(600518.SH)有造假风险吗"
            if i == 0
            else f"第{i+1}轮：它的应收情况如何",
            "answer": "综合风险等级为 orange；触发 R1、R2；需关注",
            "evidence_ids": [f"ev_{i}_1", f"ev_{i}_2"],
        }
        for i in range(n)
    ]


def test_summary_structure_complete():
    """摘要含 version/text/covered_until/source_turn_ids/evidence_ids/...。"""
    s = build_summary_for_turns(_turns())
    d = s.to_dict()
    for field in (
        "version",
        "text",
        "covered_until_turn_index",
        "source_turn_ids",
        "evidence_ids",
        "company_codes",
        "key_facts",
        "limitations",
        "updated_at",
    ):
        assert field in d
    assert d["version"] == "memory-v1"


def test_summary_version_uses_settings(monkeypatch):
    """MEMORY_SUMMARY_VERSION 改动后新建摘要同步使用配置值。"""
    from app.application.services import memory_distillation as md

    monkeypatch.setattr(md.settings, "MEMORY_SUMMARY_VERSION", "memory-v2-test")
    assert MemorySummary().version == "memory-v2-test"
    summary = MemorySummary.from_dict({"text": "旧摘要"})
    assert summary is not None
    assert summary.version == "memory-v2-test"


def test_summary_has_source_turns_and_evidence():
    """有来源轮次；保留 Evidence。"""
    s = build_summary_for_turns(_turns(5))
    assert len(s.source_turn_ids) == 5
    assert s.source_turn_ids[0] == "turn_0"
    assert "ev_0_1" in s.evidence_ids
    assert s.covered_until_turn_index == 5


def test_summary_deterministic():
    """幂等：同来源提炼结果稳定。"""
    a = build_summary_for_turns(_turns(3))
    b = build_summary_for_turns(_turns(3))
    assert a.to_dict() == b.to_dict()


def test_summary_no_llm_fabrication():
    """不把 LLM 新信息写入事实：key_facts 仅来自历史回答文本。"""
    turns = [
        {
            "turn_id": "t1",
            "turn_index": 1,
            "question": "康美药业有造假风险吗",
            "answer": "综合风险等级为 orange",
            "evidence_ids": ["ev_1"],
        }
    ]
    s = build_summary_for_turns(turns)
    assert "orange" in " ".join(s.key_facts) or "风险等级 orange" in s.text
    # 不应出现回答中不存在的内容
    assert not any("虚构" in f for f in s.key_facts)


def test_key_facts_negated_rules_not_recorded():
    """8/19 修复：否定语境（未/不/无触发）中的 R 规则不得记为触发。

    反例：答案「R1、R2 未触发」此前被 re.findall 抽成「触发 R1」「触发 R2」，
    远期摘要出现事实反转。修复后分句级否定过滤，否定句中的 R 全部跳过。
    """
    from app.application.services.memory_distillation import _extract_key_facts

    # 全部未触发 → 一条"触发 R"都不应出现
    rows = [
        {
            "question": "R1 是否触发",
            "answer": "R1、R2 未触发，风险等级为 green，需关注",
        }
    ]
    facts = _extract_key_facts(rows)
    assert not any(
        f.startswith("触发 R") for f in facts
    ), f"未触发被误记为触发: {facts}"
    assert "风险等级 green" in facts

    # 混合：R1 未触发、R3 触发 → 只记 R3
    rows2 = [
        {
            "question": "规则触发情况",
            "answer": "R1 未触发，但 R3 触发，风险等级为 orange",
        }
    ]
    facts2 = _extract_key_facts(rows2)
    assert "触发 R1" not in facts2
    assert "触发 R3" in facts2

    # 正向语境保持：无否定词时正常记录
    rows3 = [{"question": "规则触发情况", "answer": "触发 R1、R2，风险等级为 red"}]
    facts3 = _extract_key_facts(rows3)
    assert "触发 R1" in facts3
    assert "触发 R2" in facts3


def test_key_facts_discovery_words():
    """8/19 修复：『未发现 R1』等措辞同样不得记为触发。"""
    from app.application.services.memory_distillation import _extract_key_facts

    rows = [
        {
            "question": "是否有规则触发",
            "answer": "未发现 R4、R5 触发信号，风险等级为 yellow",
        }
    ]
    facts = _extract_key_facts(rows)
    assert not any(
        f.startswith("触发 R") for f in facts
    ), f"未发现被误记为触发: {facts}"


def test_summary_truncated():
    """限长：超长摘要被截断。"""
    turns = _turns(30)
    turns = [
        dict(t, answer="风险等级为 orange 且触发 R1 R2 R3 R4 R5 R6 R7，" * 20)
        for t in turns
    ]
    s = build_summary_for_turns(turns, max_chars=200)
    assert len(s.text) <= 200


def test_broken_summary_returns_none():
    """摘要损坏（结构非法）→ from_dict 返回 None（回退近期轮次）。"""
    assert MemorySummary.from_dict(None) is None
    assert MemorySummary.from_dict("not a dict") is None
    assert MemorySummary.from_dict({"version": "memory-v1"}) is not None  # 缺字段容错


def test_round_trip_dict():
    """to_dict → from_dict 往返无损。"""
    s = build_summary_for_turns(_turns(2))
    s2 = MemorySummary.from_dict(s.to_dict())
    assert s2 is not None
    assert s2.to_dict() == s.to_dict()


def test_load_context_with_memory_strategies():
    """策略开关：none / recent_only / summary_plus_recent。"""
    ctx = load_context_with_memory("ses_none")
    assert ctx["strategy"] in ("none", "recent_only", "summary_plus_recent")
    # 无此会话数据时策略仍返回结构
    assert "recent" in ctx and "summary" in ctx
