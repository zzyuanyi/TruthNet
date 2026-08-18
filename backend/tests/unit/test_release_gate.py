"""v3.3.1 §9 批次 E：生产发布闸门与统一总预算口径（8/16 修订）.

反例（§9.5 + 8/16 语义裁决启用）：
- 全局 off 正常启动；
- 全局 suggest 允许启动（8/16 队长拍板：演示/答辩环境启用
  mentionness 非公司判定 + selector LLM 推荐，不自动绑定）；
- 全局 auto 拒绝启动（自动绑定身份仅限离线 runner）；
- selector 两次尝试共享同一 deadline（单次不再被 5s 截断）；
- repair 消耗的是剩余时间而非新 20 秒。
"""

import pytest

from app.core.config import settings


def test_release_gate_off_passes(monkeypatch):
    from app.main import _validate_release_mode

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "off")
    _validate_release_mode()  # 不 raise


def test_release_gate_suggest_passes(monkeypatch):
    """8/16 修订：suggest 允许全局启动（演示/答辩环境）。"""
    from app.main import _validate_release_mode

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "suggest")
    _validate_release_mode()  # 不 raise


def test_release_gate_auto_rejected(monkeypatch):
    from app.main import _validate_release_mode

    monkeypatch.setattr(settings, "ENTITY_SEMANTIC_SELECTION_MODE", "auto")
    with pytest.raises(RuntimeError):
        _validate_release_mode()


def test_selector_repair_shares_single_deadline(monkeypatch):
    """两次尝试共享同一 query 级 deadline：单次调用不再被 5s 默认截断，
    repair 使用剩余时间（§9.4 反例）。"""
    from app.application.models.company_resolution import (
        EntityMention,
        IdentityDecision,
        RoleAssignment,
        SemanticDecision,
    )
    from app.application.services.company_semantic_selector import (
        CompanySemanticSelector,
    )

    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    m = EntityMention(
        mention_id="m1",
        text="平安",
        candidates=[
            {
                "company": {
                    "entity_id": "company_000001.SZ",
                    "wind_code": "000001.SZ",
                    "sec_name": "平安银行",
                    "exchange": "XSHG",
                },
                "match_kind": "exact_name",
                "matched_text": "平安",
                "rank": 0,
            }
        ],
    )
    bad = SemanticDecision(
        relation="single",
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="abstain", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id="m1", role="primary")],
    )
    good = bad.model_copy(
        update={
            "identity_decisions": [
                IdentityDecision(
                    mention_id="m1",
                    action="select",
                    selected_wind_code="000001.SZ",
                )
            ]
        }
    )
    calls = {"n": 0}
    timeouts: list[float] = []

    def fake_llm(messages, schema, timeout=None):
        calls["n"] += 1
        timeouts.append(timeout)
        return good if calls["n"] == 2 else bad

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    selector = CompanySemanticSelector(mode="auto")
    status, _ = selector.decide(user_query="分析平安", mentions=[m])
    assert status == "completed"
    assert calls["n"] == 2
    assert len(timeouts) == 2
    # 第一次调用 ≈ 总预算 20s（不再是 min(5s, remaining) 的 5s 截断）
    assert timeouts[0] > 15
    # repair 使用剩余 deadline（≤ 第一次），不是新 20 秒
    assert timeouts[1] <= timeouts[0]
