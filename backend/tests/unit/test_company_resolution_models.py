"""方案 v3.1 §7 关键测试 — 步骤 2（DTO、状态不变量、relation 映射、纯函数）.

对应审查测试项：
- 清洗时间/请求词后 start/end 仍切回原文正确片段（纯函数层：ID/指纹稳定性）
- locked mention 身份不可改，但 role 必须被校验（模型不变量）
- 身份全部确认但 relation 未解析时不重跑（PendingEntityResolution.can_resume）
- 唯一精确命中自动锁定，唯一启发式命中按策略处理（resolution_source 派生）
"""

from app.application.models.company_resolution import (
    EXECUTABLE_RELATIONS,
    EntityMention,
    EntityResolutionOverride,
    PendingEntityResolution,
    SemanticDecision,
    is_executable_relation,
    make_mention_id,
    make_query_fingerprint,
    resolution_source_from_match_kind,
    validate_relation_roles,
)
from app.agents.state import CompanyRef


def _ref(code: str = "600000.SH", name: str = "某公司") -> CompanyRef:
    return CompanyRef(
        entity_id=f"company_{code}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
    )


def _mention(
    mention_id: str,
    text: str = "平安",
    start: int = 0,
    end: int = 2,
    status: str = "needs_confirmation",
    selected: str | None = None,
    role: str | None = None,
) -> EntityMention:
    return EntityMention(
        mention_id=mention_id,
        text=text,
        start=start,
        end=end,
        status=status,
        selected_wind_code=selected,
        role=role,
    )


# ── mention_id / fingerprint 稳定性（P1-4）───────────────────


def test_mention_id_stable_and_deterministic():
    """同一 (start, end, text) 恒生成同一 ID；不同 span 不同 ID。"""
    a1 = make_mention_id(0, 2, "平安")
    a2 = make_mention_id(0, 2, "平安")
    b = make_mention_id(4, 6, "茅台")
    assert a1 == a2
    assert a1 != b
    # 稳定格式 m_{start}_{end}_{hash8}
    assert a1.startswith("m_0_2_")
    assert len(a1.rsplit("_", 1)[-1]) == 8


def test_mention_id_does_not_contain_raw_text():
    """ID 不直接包含完整用户文本（P1-4）。"""
    mid = make_mention_id(0, 2, "平安")
    assert "平安" not in mid


def test_query_fingerprint_fixed_algorithm():
    """原始问题 UTF-8 SHA256，同一问题恒一致。"""
    assert make_query_fingerprint("茅台和和邦对比") == make_query_fingerprint(
        "茅台和和邦对比"
    )
    assert make_query_fingerprint("茅台和和邦对比") != make_query_fingerprint(
        "和邦和茅台对比"
    )


# ── relation 映射（P0-3）─────────────────────────────────────


def test_executable_relations_only_four():
    """仅 single/continuation/switch/comparison 可生成自动重跑 override。"""
    assert EXECUTABLE_RELATIONS == {"single", "continuation", "switch", "comparison"}
    for r in ("single", "continuation", "switch", "comparison"):
        assert is_executable_relation(r)
    for r in ("reference", "sequence", "ambiguous", "no_company"):
        assert not is_executable_relation(r)
    assert not is_executable_relation(None)


# ── relation/role 一致性校验（P1-1）──────────────────────────


def test_relation_role_single_requires_one_primary():
    km = _mention("m1", selected="600518.SH", role="primary", status="user_confirmed")
    assert validate_relation_roles("single", [km])
    other = _mention("m2", selected="600519.SH", role="primary")
    assert not validate_relation_roles("single", [km, other])  # 两个 primary


def test_relation_role_comparison_two_distinct_codes():
    a = _mention("m1", selected="000001.SZ", role="primary")
    b = _mention("m2", selected="600519.SH", role="comparison_peer")
    assert validate_relation_roles("comparison", [a, b])
    assert not validate_relation_roles("comparison", [a])  # 只有一家


def test_relation_role_reference_needs_referenced():
    primary = _mention("m1", selected="600518.SH", role="primary")
    ref = _mention("m2", selected="600519.SH", role="referenced")
    assert validate_relation_roles("reference", [primary, ref])
    assert not validate_relation_roles("reference", [primary])


def test_relation_role_no_company_selects_nothing():
    assert validate_relation_roles("no_company", [])
    sel = _mention("m1", selected="600518.SH", role="primary")
    assert not validate_relation_roles("no_company", [sel])


def test_relation_role_ambiguous_never_executable():
    a = _mention("m1", selected="000001.SZ", role="primary")
    b = _mention("m2", selected="600519.SH", role="comparison_peer")
    assert not validate_relation_roles("ambiguous", [a, b])


# ── resolution_source 派生（P1-2）────────────────────────────


def test_resolution_source_from_match_kind():
    assert resolution_source_from_match_kind("exact_code") == "code"
    assert resolution_source_from_match_kind("exact_name") == "exact_name"
    assert resolution_source_from_match_kind("exact_legal_name") == "exact_legal_name"
    assert resolution_source_from_match_kind("exact_alias") == "exact_alias"
    assert resolution_source_from_match_kind("reverse_contains") == "substring"
    assert resolution_source_from_match_kind("prefix") == "substring"
    assert resolution_source_from_match_kind("contains") == "substring"


# ── pending 状态不变量（P0-1/P0-3/P1-3）──────────────────────


def test_remaining_only_needs_confirmation():
    """唯一候选已锁定（auto_selected）不进 remaining（P0-1）。"""
    locked = _mention("m1", text="茅台", status="auto_selected", selected="600519.SH")
    need = _mention("m2", text="平安")
    pending = PendingEntityResolution(
        origin_turn_id="t1",
        question="茅台和平安对比",
        query_fingerprint="fp",
        mentions={"m1": locked, "m2": need},
    )
    assert pending.remaining_mention_ids == ["m2"]


def test_only_needs_confirmation_is_confirmable():
    assert _mention("m1").is_confirmable
    assert not _mention("m1", status="auto_selected").is_confirmable
    assert not _mention("m1", status="needs_refinement").is_confirmable
    assert not _mention("m1", status="not_found").is_confirmable
    assert not _mention("m1", status="user_confirmed").is_confirmable


def test_can_resume_requires_relation_resolved_and_executable():
    """身份全确认但 relation 未解析时不重跑（P0-3）。"""
    selected = _mention("m1", status="user_confirmed", selected="600519.SH")
    # 身份已确认但 relation_status 未 resolved → 不重跑
    pending = PendingEntityResolution(
        origin_turn_id="t1",
        question="平安和茅台对比",
        query_fingerprint="fp",
        mentions={"m1": selected},
        relation="comparison",
        relation_status="needs_clarification",
    )
    assert pending.all_identities_selected
    assert not pending.can_resume
    # relation_status resolved 但 relation 不可执行（reference）→ 不重跑
    pending2 = PendingEntityResolution(
        origin_turn_id="t1",
        question="分析康美提到茅台的公告",
        query_fingerprint="fp",
        mentions={"m1": selected},
        relation="reference",
        relation_status="resolved",
    )
    assert not pending2.can_resume
    # 全部满足 → 可重跑
    pending3 = PendingEntityResolution(
        origin_turn_id="t1",
        question="平安和茅台对比",
        query_fingerprint="fp",
        mentions={"m1": selected},
        relation="comparison",
        relation_status="resolved",
    )
    assert pending3.can_resume


# ── SemanticDecision 默认 abstain（P0-4/v3 §5）────────────────


def test_semantic_decision_defaults_abstain():
    """输出模型默认 abstain，不能默认选第一家。"""
    decision = SemanticDecision()
    assert decision.relation == "ambiguous"
    assert decision.identity_decisions == []
    assert decision.role_assignments == []


def test_override_carries_relation_and_role():
    """override 保留 relation/role（P0-3），不能只剩 wind_code。"""
    override = EntityResolutionOverride(
        query_fingerprint="fp",
        relation="comparison",
        decisions=[
            {
                "mention_id": "m_0_2_x",
                "text": "平安",
                "start": 0,
                "end": 2,
                "wind_code": "000001.SZ",
                "role": "primary",
            },
            {
                "mention_id": "m_4_6_y",
                "text": "茅台",
                "start": 4,
                "end": 6,
                "wind_code": "600519.SH",
                "role": "comparison_peer",
            },
        ],
    )
    assert override.relation == "comparison"
    assert [d.role for d in override.decisions] == ["primary", "comparison_peer"]
