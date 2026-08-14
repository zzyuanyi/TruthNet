"""v3.3.1 §8 批次 D：grouped alternatives 权威 DTO 与 REST/WS additive 契约.

反例（§8.3）：
- 两个 parent 的 alternative ID/parent 归属不冲突；
- pending 保留完整 grouped alternatives；
- segmentation ambiguity 不产生空 candidates 卡片（改发 clarification）；
- REST additive 字段可序列化；
- 旧单 mention company_candidates 契约不变（见 test_ws_turn_runner /
  test_api_v1_full_contract 存量用例）。

注：复合分段唯一方案会被 resolver 直接采用（无歧义不保留方案）；
多方案歧义场景按 DTO 构造验证传输链（alternative_id 生成规则
`alt_{parent_id}_{pos}_{connector}` 由 resolver._segment_compound 保证）。
"""

import json

from app.api.v1.schemas.chat import ChatDataV1
from app.application.models.company_resolution import (
    EntityMention,
    EntityResolutionIssue,
    EntityResolutionResult,
    SegmentationAlternative,
    make_mention_id,
)
from app.application.services.ws_turn_runner import (
    _build_entity_pending,
    _segmentation_clarification_required,
)


def _sub(text: str, start: int, end: int, code: str, name: str) -> EntityMention:
    return EntityMention(
        mention_id=make_mention_id(start, end, text),
        text=text,
        start=start,
        end=end,
        status="auto_selected",
        selected_wind_code=code,
        role="primary",
        candidates=[
            {
                "company": {
                    "entity_id": f"company_{code}",
                    "wind_code": code,
                    "sec_name": name,
                    "exchange": "XSHG",
                },
                "match_kind": "exact_name",
                "matched_text": text,
                "rank": 0,
            }
        ],
    )


def _ambiguous_result() -> EntityResolutionResult:
    """两个分段歧义父，每个父两个方案（子 mention ID 互不相同）。"""
    p1 = EntityMention(
        mention_id=make_mention_id(0, 7, "平安和茅台和协和"),
        text="平安和茅台和协和",
        start=0,
        end=7,
        status="needs_refinement",
        truncated=True,
    )
    p2 = EntityMention(
        mention_id=make_mention_id(8, 15, "康美和中兴和宁德"),
        text="康美和中兴和宁德",
        start=8,
        end=15,
        status="needs_refinement",
        truncated=True,
    )
    alts = [
        SegmentationAlternative(
            parent_mention_id=p1.mention_id,
            alternative_id=f"alt_{p1.mention_id}_2_和",
            mentions=[
                _sub("平安", 0, 2, "000001.SZ", "平安银行"),
                _sub("茅台", 3, 5, "600519.SH", "贵州茅台"),
            ],
        ),
        SegmentationAlternative(
            parent_mention_id=p1.mention_id,
            alternative_id=f"alt_{p1.mention_id}_5_和",
            mentions=[
                _sub("平安", 0, 2, "000001.SZ", "平安银行"),
                _sub("协和", 6, 8, "603077.SH", "协和电子"),
            ],
        ),
        SegmentationAlternative(
            parent_mention_id=p2.mention_id,
            alternative_id=f"alt_{p2.mention_id}_2_和",
            mentions=[
                _sub("康美", 8, 10, "600518.SH", "康美药业"),
                _sub("中兴", 11, 13, "000063.SZ", "中兴通讯"),
            ],
        ),
        SegmentationAlternative(
            parent_mention_id=p2.mention_id,
            alternative_id=f"alt_{p2.mention_id}_5_和",
            mentions=[
                _sub("中兴", 11, 13, "000063.SZ", "中兴通讯"),
                _sub("宁德", 14, 16, "300750.SZ", "宁德时代"),
            ],
        ),
    ]
    return EntityResolutionResult(
        intent="ambiguous",
        mentions=[p1, p2],
        unresolved_mentions=[p1.text, p2.text],
        segmentation_alternatives=alts,
        resolution_issues=[
            EntityResolutionIssue(
                code="segmentation_ambiguous",
                mention_ids=[p1.mention_id, p2.mention_id],
            )
        ],
    )


def test_two_parent_alternatives_no_id_conflict():
    """两个 parent 的 alternative ID/parent 归属不冲突（§8.3 反例 1）。"""
    r = _ambiguous_result()
    alts = r.segmentation_alternatives
    parents = {a.parent_mention_id for a in alts}
    assert len(parents) == 2
    assert len({a.alternative_id for a in alts}) == 4  # ID 互不相同
    for a in alts:
        assert a.alternative_id.startswith(f"alt_{a.parent_mention_id}_")
    for p in parents:
        assert sum(1 for a in alts if a.parent_mention_id == p) == 2


def test_pending_preserves_grouped_alternatives():
    """pending 保留完整 grouped alternatives（§8.3 反例 2）。"""
    from app.application.services.ws_session_manager import ActiveTurn

    r = _ambiguous_result()
    turn = ActiveTurn(turn_id="t1", session_id="s1", question="q")
    pending = _build_entity_pending(turn, r)
    assert len(pending["segmentation_alternatives"]) == 4
    assert {a["parent_mention_id"] for a in pending["segmentation_alternatives"]} == {
        a.parent_mention_id for a in r.segmentation_alternatives
    }


def test_pending_single_alternative_id_derived_when_exactly_one():
    """恰好一个 parent 有权威选择时派生兼容单值；多 parent 不派生。"""
    from app.application.services.ws_session_manager import ActiveTurn

    from app.application.models.company_resolution import EntityMention

    r = EntityResolutionResult(
        intent="ambiguous",
        mentions=[
            EntityMention(mention_id="p1", text="平安和茅台", status="needs_refinement")
        ],
        selected_alternative_ids={"p1": "alt_p1_0_和"},
    )
    turn = ActiveTurn(turn_id="t1", session_id="s1", question="q")
    pending = _build_entity_pending(turn, r)
    assert pending["selected_alternative_id"] == "alt_p1_0_和"
    # 多 parent：不派生单值（None）
    r2 = r.model_copy(update={"selected_alternative_ids": {"p1": "a1", "p2": "a2"}})
    pending2 = _build_entity_pending(turn, r2)
    assert pending2["selected_alternative_id"] is None


def test_segmentation_ambiguity_requires_clarification_not_candidates():
    """segmentation ambiguity 判定：澄清事件而非空 candidates 卡片（§8.3 反例 3）。"""
    r = _ambiguous_result()
    assert _segmentation_clarification_required(r) is True
    # 普通歧义（有候选确认）不触发 clarification
    plain = EntityResolutionResult(intent="single")
    assert _segmentation_clarification_required(plain) is False
    # 无 alternatives 但带 segmentation_ambiguous issue 也触发
    issue_only = EntityResolutionResult(
        intent="ambiguous",
        resolution_issues=[
            EntityResolutionIssue(code="segmentation_ambiguous", mention_ids=["p1"])
        ],
    )
    assert _segmentation_clarification_required(issue_only) is True


def test_rest_additive_fields_serializable():
    """REST additive 字段可序列化（§8.3 反例 4）。"""
    r = _ambiguous_result()
    data = ChatDataV1(
        answer="ok",
        trace_id="t",
        segmentation_alternatives=[a.model_dump() for a in r.segmentation_alternatives],
        entity_resolution_issues=[i.model_dump() for i in r.resolution_issues],
    )
    dumped = json.loads(data.model_dump_json())
    assert len(dumped["segmentation_alternatives"]) == 4
    assert len(dumped["entity_resolution_issues"]) >= 1
    # 旧字段仍在（契约不删）
    assert "company_candidates" in dumped
    assert "needs_confirmation" in dumped
