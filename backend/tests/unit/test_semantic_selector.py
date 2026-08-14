"""方案 v3.1 §7 关键测试 — 步骤 7（CompanySemanticSelector 受约束 LLM）.

对应审查测试项：
- mock/off 模式零次 LLM 调用；suggest 不自动绑定；auto 仅接受 allowlist
  内合法结果（P0-4/v3 §5）；
- 库外 wind_code、错 mention_id、role 缺失、越界 alternative_id → invalid；
- locked mention 身份不可改，但 role 必须被校验（P1-1）；
- LLM 超时/异常 → 确定性降级，不串历史主体；
- 高置信场景 LLM 调用次数为 0；只有歧义场景调用一次。
"""

import json

from sqlalchemy import create_engine, text

from app.application.models.company_resolution import (
    EntityMention,
    IdentityDecision,
    RoleAssignment,
    SegmentationAlternative,
    SemanticDecision,
)
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.application.services.company_semantic_selector import (
    CompanySemanticSelector,
    validate_semantic_decision,
)
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)
from app.core.config import settings

_TABLE = (
    "CREATE TABLE companies ("
    "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
    "industry_l1 TEXT, aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
    "is_latest INTEGER)"
)


def _lookup(rows: list[tuple]):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(_TABLE))
        for r in rows:
            conn.execute(
                text(
                    "INSERT INTO companies VALUES "
                    "(:eid, :code, :name, 'XSHG', NULL, :aliases, NULL, '1', 1)"
                ),
                {"eid": r[0], "code": r[1], "name": r[2], "aliases": r[3]},
            )
    repo = MySQLCompanyRepository()
    repo._engine = engine
    return repo


def _mention(
    mention_id: str, text: str, codes: list[str], status: str = "needs_confirmation"
) -> EntityMention:
    candidates = []
    for code in codes:
        candidates.append(
            {
                "company": {
                    "entity_id": f"company_{code}",
                    "wind_code": code,
                    "sec_name": f"公司{code}",
                    "exchange": "XSHG",
                },
                "match_kind": "exact_name",
                "matched_text": text,
                "rank": 0,
            }
        )
    return EntityMention(
        mention_id=mention_id,
        text=text,
        start=0,
        end=len(text),
        candidates=candidates,
        status=status,
    )


# ── mock/off 显式禁用（P0-4/v3 §5）───────────────────────────


def test_mock_backend_disabled_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    calls: list = []

    def fake_structured(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_structured)
    selector = CompanySemanticSelector(mode="auto")
    status, decision = selector.decide(
        user_query="分析平安",
        mentions=[_mention("m1", "平安", ["000001.SZ", "601318.SH"])],
    )
    assert status == "disabled"
    assert decision is None
    assert calls == [], "mock 环境必须零次 LLM 调用"


def test_off_mode_disabled_zero_calls(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake_structured(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_structured)
    selector = CompanySemanticSelector(mode="off")
    status, _ = selector.decide(
        user_query="分析平安", mentions=[_mention("m1", "平安", ["000001.SZ"])]
    )
    assert status == "disabled"
    assert calls == []


# ── 程序校验（P1-1）─────────────────────────────────────────


def _decision(**kw) -> SemanticDecision:
    defaults = dict(
        relation="single",
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id="m1", role="primary")],
    )
    defaults.update(kw)
    return SemanticDecision(**defaults)


def test_valid_decision_completed():
    mention = _mention("m1", "平安", ["000001.SZ", "601318.SH"])
    ok, reason = validate_semantic_decision(_decision(), [mention], None)
    assert ok, reason


def test_out_of_allowlist_code_invalid():
    mention = _mention("m1", "平安", ["000001.SZ", "601318.SH"])
    d = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="600519.SH"
            )
        ]
    )
    ok, reason = validate_semantic_decision(d, [mention], None)
    assert not ok
    assert "库外" in reason


def test_unknown_mention_id_invalid():
    mention = _mention("m1", "平安", ["000001.SZ"])
    d = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m_unknown", action="select", selected_wind_code="000001.SZ"
            )
        ]
    )
    ok, reason = validate_semantic_decision(d, [mention], None)
    assert not ok
    assert "未知 mention_id" in reason


def test_role_missing_invalid():
    """adopted（已绑定）mention 缺 role → invalid。"""
    mention = _mention("m1", "平安", ["000001.SZ"], status="auto_selected")
    mention.selected_wind_code = "000001.SZ"
    d = _decision(
        identity_decisions=[],  # locked 不接受 identity
        role_assignments=[],  # 缺 role
    )
    ok, reason = validate_semantic_decision(d, [mention], None)
    assert not ok
    assert "role 缺失" in reason


def test_locked_identity_ignored_not_invalid():
    """v3.3 批次 C：locked mention 出现在 identity decisions →
    整体 invalid（不再静默忽略，与"任何非法输出整体 invalid"一致）。"""
    mention = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    mention.selected_wind_code = "600519.SH"
    d = _decision(
        relation="single",
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="600000.SH"
            )
        ],  # locked 改写 → invalid（库外值同样被该规则拦截）
        role_assignments=[RoleAssignment(mention_id="m1", role="primary")],
    )
    ok, reason = validate_semantic_decision(d, [mention], None)
    assert not ok
    assert "locked" in reason


def test_alternative_out_of_range_invalid():
    """v3.3 批次 C：alternative 属于错误/越界方案 → invalid（按父分组）。"""
    from app.application.models.company_resolution import SegmentationDecision

    sub = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    sub.selected_wind_code = "600519.SH"
    alt = SegmentationAlternative(
        parent_mention_id="p1", alternative_id="alt_2", mentions=[sub]
    )
    d = _decision(
        role_assignments=[],
        identity_decisions=[],
        segmentation_decisions=[
            SegmentationDecision(
                parent_mention_id="p1", action="select", alternative_id="alt_99"
            )
        ],
    )
    parent = _mention("p1", "茅台和协和", [], status="needs_confirmation")
    ok, reason = validate_semantic_decision(d, [parent], [alt])
    assert not ok
    assert "越界" in reason


def test_alternative_required_when_ambiguous():
    """v3.3 批次 C：有分段歧义但无 segmentation_decisions → invalid。"""

    sub = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    sub.selected_wind_code = "600519.SH"
    alt = SegmentationAlternative(
        parent_mention_id="p1", alternative_id="alt_2", mentions=[sub]
    )
    d = _decision(
        role_assignments=[],
        identity_decisions=[],
        segmentation_decisions=[],
    )
    parent = _mention("p1", "茅台和协和", [], status="needs_confirmation")
    ok, reason = validate_semantic_decision(d, [parent], [alt])
    assert not ok
    assert "无 segmentation_decisions" in reason


def test_relation_role_inconsistency_invalid():
    """comparison 只绑定一家 → 不一致（需至少两个不同 wind_code）。"""
    m1 = _mention("m1", "平安", ["000001.SZ"], status="auto_selected")
    m1.selected_wind_code = "000001.SZ"
    m2 = _mention("m2", "茅台", ["600519.SH"], status="auto_selected")
    m2.selected_wind_code = "600519.SH"
    # 两家绑定 → comparison 合法（primary 由服务端按原文顺序派生，P1-1）
    d = _decision(
        relation="comparison",
        identity_decisions=[],
        role_assignments=[
            RoleAssignment(mention_id="m1", role="primary"),
            RoleAssignment(mention_id="m2", role="comparison_peer"),
        ],
    )
    ok, reason = validate_semantic_decision(d, [m1, m2], None)
    assert ok, reason
    # 只绑定一家 → comparison 不一致
    m3 = _mention("m3", "茅台", ["600519.SH"], status="auto_selected")
    m3.selected_wind_code = "600519.SH"
    d2 = _decision(
        relation="comparison",
        identity_decisions=[],
        role_assignments=[RoleAssignment(mention_id="m3", role="primary")],
    )
    ok2, reason2 = validate_semantic_decision(d2, [m3], None)
    assert not ok2
    assert "两个不同 code" in reason2


# ── 超时/异常降级 ───────────────────────────────────────────


def test_timeout_returns_timeout_status(monkeypatch):
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", lambda *a, **kw: None)
    selector = CompanySemanticSelector(mode="auto")
    status, decision = selector.decide(
        user_query="分析平安", mentions=[_mention("m1", "平安", ["000001.SZ"])]
    )
    assert status == "timeout"
    assert decision is None


# ── Resolver 集成：调用时机与 suggest/auto ───────────────────


def _selector_with_fake(fake_decision, mode="auto", calls=None):
    """构造 Resolver 集成用 selector（fake LLM 返回固定 decision）。"""
    selector = CompanySemanticSelector(mode=mode)
    if calls is not None:

        def _fake(messages, schema, timeout=None):
            calls.append(messages)
            return fake_decision

        selector._fake = _fake
    return selector


def test_high_confidence_zero_llm_calls(monkeypatch):
    """高置信场景（唯一锁定）→ LLM 调用次数为 0。"""
    calls: list = []
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    def fake_structured(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_structured)
    lookup = _lookup([("c1", "600519.SH", "贵州茅台", None)])
    resolver = CompanyEntityResolver(
        lookup, selector=CompanySemanticSelector(mode="auto")
    )
    r = resolver.resolve("茅台营收")
    assert r.selected_companies[0].sec_name == "贵州茅台"
    assert calls == [], "高置信场景必须零次 LLM 调用"


def _pingan_lookup_with_mention_id():
    """返回 (lookup, mention_id)——先无 selector 解析一次拿真实 mention_id。"""
    lookup = _lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
        ]
    )
    r0 = CompanyEntityResolver(lookup).resolve("分析平安")
    return lookup, r0.mentions[0].mention_id


def test_ambiguity_triggers_one_call_suggest_not_bind(monkeypatch):
    """歧义场景调用一次；suggest 记录选择但不绑定。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    lookup, mid = _pingan_lookup_with_mention_id()
    decision = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id=mid, action="select", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id=mid, role="primary")],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    resolver = CompanyEntityResolver(
        lookup, selector=CompanySemanticSelector(mode="suggest")
    )
    r = resolver.resolve("分析平安")
    assert r.selector_status == "completed"
    assert r.mentions[0].status == "needs_confirmation"  # suggest 不绑定
    assert r.mentions[0].selected_wind_code is None
    assert r.mentions[0].role == "primary"  # role 已应用


def test_auto_binds_allowlist_choice(monkeypatch):
    """auto 模式：LLM 选择在候选集内 → 绑定为 llm_selected。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    lookup, mid = _pingan_lookup_with_mention_id()
    decision = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id=mid, action="select", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id=mid, role="primary")],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    resolver = CompanyEntityResolver(
        lookup, selector=CompanySemanticSelector(mode="auto")
    )
    r = resolver.resolve("分析平安")
    assert r.selector_status == "completed"
    assert r.mentions[0].status == "llm_selected"
    assert r.mentions[0].selected_wind_code == "000001.SZ"
    assert r.mentions[0].resolution_source == "llm"
    assert r.selected_companies[0].wind_code == "000001.SZ"


def test_relation_ambiguity_triggers_selector(monkeypatch):
    """ "分析康美提到茅台的公告"：两家唯一但关系不明 → 调 LLM 判 reference。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    lookup = _lookup(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    r0 = CompanyEntityResolver(lookup).resolve("分析康美提到茅台的公告")
    ids = {m.text: m.mention_id for m in r0.mentions}
    decision = SemanticDecision(
        relation="reference",
        identity_decisions=[],
        role_assignments=[
            RoleAssignment(mention_id=ids["康美"], role="primary"),
            RoleAssignment(mention_id=ids["茅台"], role="referenced"),
        ],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    resolver = CompanyEntityResolver(
        lookup, selector=CompanySemanticSelector(mode="auto")
    )
    r = resolver.resolve("分析康美提到茅台的公告")
    assert r.intent == "reference"  # 不降级为 comparison
    roles = {m.text: m.role for m in r.mentions}
    assert roles["康美"] == "primary"
    assert roles["茅台"] == "referenced"


# ── v3.3 批次 C（10.2）：verifier 新不变量与 repair ─────────────


def test_duplicate_identity_decision_invalid():
    m = _mention("m1", "平安", ["000001.SZ"])
    d = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="000001.SZ"
            ),
            IdentityDecision(mention_id="m1", action="abstain"),
        ],
    )
    ok, reason = validate_semantic_decision(d, [m], None)
    assert not ok
    assert "重复 identity" in reason


def test_missing_identity_decision_invalid():
    m = _mention("m1", "平安", ["000001.SZ"])
    d = _decision(identity_decisions=[])
    ok, reason = validate_semantic_decision(d, [m], None)
    assert not ok
    assert "缺 identity" in reason


def test_abstain_with_code_invalid():
    m = _mention("m1", "平安", ["000001.SZ"])
    d = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="abstain", selected_wind_code="000001.SZ"
            )
        ],
    )
    ok, reason = validate_semantic_decision(d, [m], None)
    assert not ok
    assert "abstain" in reason


def test_truncated_mention_select_invalid():
    m = _mention("m1", "平安", ["000001.SZ"])
    m.truncated = True
    d = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="000001.SZ"
            )
        ],
    )
    ok, reason = validate_semantic_decision(d, [m], None)
    assert not ok
    assert "truncated" in reason


def test_repair_retries_once_and_completes(monkeypatch):
    """第一次 verifier invalid → repair 再调一次 → completed，恰好两次。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    m = _mention("m1", "平安", ["000001.SZ"])
    bad = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="abstain", selected_wind_code="000001.SZ"
            )
        ],
    )
    good = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="000001.SZ"
            )
        ],
    )
    calls = {"n": 0}

    def fake_llm(messages, schema, timeout=None):
        calls["n"] += 1
        return good if calls["n"] == 2 else bad

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_llm)
    selector = CompanySemanticSelector(mode="auto")
    status, decision = selector.decide(user_query="分析平安", mentions=[m])
    assert status == "completed"
    assert decision == good
    assert calls["n"] == 2
    assert selector.last_attempts == 2
    assert selector.last_validation_error == ""


def test_repair_still_invalid_returns_invalid(monkeypatch):
    """两次均 invalid → selector_status=invalid，不部分应用。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    m = _mention("m1", "平安", ["000001.SZ"])
    bad = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="abstain", selected_wind_code="000001.SZ"
            )
        ],
    )
    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", lambda *a, **kw: bad)
    selector = CompanySemanticSelector(mode="auto")
    status, decision = selector.decide(user_query="分析平安", mentions=[m])
    assert status == "invalid"
    assert decision is None
    assert selector.last_attempts == 2
    assert selector.last_validation_error


# ── v3.3.1 §6：verifier 纯化与 abstain 闭环（§6.6 反例）─────────


def _seg_parent(parent_id: str = "p1") -> EntityMention:
    """分段歧义父：无候选 needs_confirmation（_finalize_span P0-4 产物）。"""
    return _mention(parent_id, "茅台和协和", [], status="needs_confirmation")


def _seg_alt(parent_id: str, alt_id: str, subs: list[EntityMention]):
    return SegmentationAlternative(
        parent_mention_id=parent_id, alternative_id=alt_id, mentions=subs
    )


def _select_alt(
    parent_id: str, alt_id: str, sub: EntityMention, code: str
) -> SemanticDecision:
    """合法整体：select 分段方案 + 子身份 select + 子 role primary。"""
    from app.application.models.company_resolution import SegmentationDecision

    return _decision(
        relation="single",
        segmentation_decisions=[
            SegmentationDecision(
                parent_mention_id=parent_id, action="select", alternative_id=alt_id
            )
        ],
        identity_decisions=[
            IdentityDecision(
                mention_id=sub.mention_id, action="select", selected_wind_code=code
            )
        ],
        role_assignments=[RoleAssignment(mention_id=sub.mention_id, role="primary")],
    )


def test_verifier_snapshot_does_not_mutate_inputs():
    """valid：快照物化结果，但输入 alternative 子 mention 与父零修改。"""
    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    validated, reason = validate_semantic_decision(
        _select_alt("p1", "alt_1", sub, "000001.SZ"), [parent], [alt]
    )
    assert validated is not None, reason
    assert alt.mentions[0].selected_wind_code is None  # 未被模拟赋值污染
    assert alt.mentions[0].role is None
    assert parent.status == "needs_confirmation"
    snap = {m.mention_id: m for m in validated.adopted_mentions}
    assert "p1" not in snap  # 被替换父已删除
    assert snap["m1"].selected_wind_code == "000001.SZ"
    assert snap["m1"].role == "primary"


def test_verifier_invalid_leaves_inputs_untouched():
    """invalid（role 缺失）：输入 alternative 子 mention 仍为原值。"""
    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    d = _select_alt("p1", "alt_1", sub, "000001.SZ").model_copy(
        update={"role_assignments": []}
    )
    validated, reason = validate_semantic_decision(d, [parent], [alt])
    assert validated is None
    assert "role 缺失" in reason
    assert alt.mentions[0].selected_wind_code is None
    assert alt.mentions[0].role is None


def test_selected_alt_parent_id_must_not_be_referenced():
    """identity/role 引用已删除父 ID → invalid（§6.6 反例 2）。"""
    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    d = _select_alt("p1", "alt_1", sub, "000001.SZ").model_copy(
        update={
            "identity_decisions": [
                IdentityDecision(
                    mention_id="p1", action="select", selected_wind_code="000001.SZ"
                )
            ]
        }
    )
    validated, reason = validate_semantic_decision(d, [parent], [alt])
    assert validated is None
    assert "未知 mention_id" in reason


def test_child_mention_id_conflict_invalid():
    """子 mention ID 与既有 adopted ID 冲突 → invalid（§6.6 反例 3）。"""
    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    other = _mention("m1", "另一家公司", ["600519.SH"])
    validated, reason = validate_semantic_decision(
        _select_alt("p1", "alt_1", sub, "000001.SZ"), [parent, other], [alt]
    )
    assert validated is None
    assert "冲突" in reason


def test_segmentation_abstain_valid_without_identity_role():
    """segmentation abstain 合法：不要求父 identity/role（§6.6 反例 4）。"""
    from app.application.models.company_resolution import SegmentationDecision

    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    d = _decision(
        relation="ambiguous",
        identity_decisions=[],
        role_assignments=[],
        segmentation_decisions=[
            SegmentationDecision(parent_mention_id="p1", action="abstain")
        ],
    )
    validated, reason = validate_semantic_decision(d, [parent], [alt])
    assert validated is not None, reason
    assert validated.unresolved_parent_ids == ("p1",)
    assert {m.mention_id for m in validated.adopted_mentions} == {"p1"}


def test_segmentation_abstain_requires_ambiguous_relation():
    """segmentation abstain + relation 非 ambiguous → invalid（§6.6 反例 5）。"""
    from app.application.models.company_resolution import SegmentationDecision

    sub = _mention("m1", "平安", ["000001.SZ"])
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    d = _decision(
        relation="single",
        identity_decisions=[],
        role_assignments=[],
        segmentation_decisions=[
            SegmentationDecision(parent_mention_id="p1", action="abstain")
        ],
    )
    validated, reason = validate_semantic_decision(d, [parent], [alt])
    assert validated is None


def test_locked_plus_abstain_ambiguous_valid():
    """locked 茅台 + 平安 abstain 合法，不改写茅台（§6.6 反例 6）。"""
    locked = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    locked.selected_wind_code = "600519.SH"
    pending = _mention("m2", "平安", ["000001.SZ"])
    d = _decision(
        relation="ambiguous",
        identity_decisions=[IdentityDecision(mention_id="m2", action="abstain")],
        role_assignments=[
            RoleAssignment(mention_id="m1", role="primary"),
            # abstain 的普通 mention（非分段父）仍须 role 覆盖（§6.2
            # 只豁免 segmentation abstain 父）
            RoleAssignment(mention_id="m2", role="referenced"),
        ],
    )
    validated, reason = validate_semantic_decision(d, [locked, pending], None)
    assert validated is not None, reason
    snap = {m.mention_id: m for m in validated.adopted_mentions}
    assert snap["m1"].selected_wind_code == "600519.SH"
    assert snap["m2"].selected_wind_code is None


def test_no_company_with_locked_invalid():
    """no_company + locked mention → invalid（§6.6 反例 7）。"""
    locked = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    locked.selected_wind_code = "600519.SH"
    d = _decision(
        relation="no_company",
        identity_decisions=[],
        role_assignments=[RoleAssignment(mention_id="m1", role="primary")],
    )
    validated, reason = validate_semantic_decision(d, [locked], None)
    assert validated is None
    assert "no_company" in reason


def test_sequence_valid_but_not_executable():
    """sequence 合法通过 verifier，但保持不可执行（§6.6 反例 8）。"""
    from app.application.models.company_resolution import is_executable_relation

    m1 = _mention("m1", "康美", ["600518.SH"], status="auto_selected")
    m1.selected_wind_code = "600518.SH"
    m2 = _mention("m2", "茅台", ["600519.SH"], status="auto_selected")
    m2.selected_wind_code = "600519.SH"
    d = _decision(
        relation="sequence",
        identity_decisions=[],
        role_assignments=[
            RoleAssignment(mention_id="m1", role="primary"),
            RoleAssignment(mention_id="m2", role="referenced"),
        ],
    )
    validated, reason = validate_semantic_decision(d, [m1, m2], None)
    assert validated is not None, reason
    assert not is_executable_relation("sequence")


def test_prompt_contains_alternative_sub_candidates():
    """prompt 明确包含 alternative 子候选 code/match_kind（§6.6 反例 9）。"""
    from app.application.services.company_semantic_selector import _build_messages

    sub = _mention("m1", "茅台", ["600519.SH"], status="auto_selected")
    alt = _seg_alt("p1", "alt_1", [sub])
    parent = _seg_parent("p1")
    msgs = _build_messages("茅台和协和的营收", [parent], [alt], "", "")
    user = msgs[1]["content"]
    assert "parent=p1 alt_1" in user
    assert "m1" in user
    assert "600519.SH" in user
    assert "kind:exact_name" in user


def test_repair_keeps_original_candidates():
    """repair 第二次消息仍包含完整候选（§6.6 反例 10）。"""
    from app.application.services.company_semantic_selector import (
        _build_messages,
        _repair_messages,
    )

    m = _mention("m1", "平安", ["000001.SZ", "601318.SH"])
    msgs = _build_messages("分析平安", [m], None, "", "single")
    bad = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id="m1", action="select", selected_wind_code="600519.SH"
            )
        ]
    )
    repaired = _repair_messages(msgs, bad, "库外 wind_code", "single")
    assert len(repaired) == 4
    assert repaired[1] == msgs[1]  # 原始 user payload（全部候选）保留
    assert "601318.SH" in repaired[1]["content"]
    assert repaired[2]["role"] == "assistant"
    assert "600519.SH" in repaired[2]["content"]  # 上一轮 invalid 输出
    assert "库外 wind_code" in repaired[3]["content"]


def test_auto_apply_no_extra_repository_queries(monkeypatch):
    """auto 应用不产生额外 Repository 查询（§6.6 反例 11）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    class _Counting:
        def __init__(self, repo):
            self._repo = repo
            self.calls: list[str] = []

        def lookup_mention(self, text):
            self.calls.append(text)
            return self._repo.lookup_mention(text)

    repo = _lookup(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
        ]
    )
    counting = _Counting(repo)
    r0 = CompanyEntityResolver(counting).resolve("分析平安")
    baseline = len(counting.calls)
    mid = r0.mentions[0].mention_id
    decision = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id=mid, action="select", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id=mid, role="primary")],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    counting.calls = []
    resolver = CompanyEntityResolver(
        counting, selector=CompanySemanticSelector(mode="auto")
    )
    r = resolver.resolve("分析平安")
    assert r.mentions[0].status == "llm_selected"
    assert len(counting.calls) == baseline  # 无 selector 时同查询次数


def test_suggest_authoritative_result_unchanged_except_audit(monkeypatch):
    """suggest 前后权威结果深比较一致，仅 audit 字段变化（§6.6 反例 12）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    lookup, mid = _pingan_lookup_with_mention_id()
    r0 = CompanyEntityResolver(lookup).resolve("分析平安")
    decision = _decision(
        identity_decisions=[
            IdentityDecision(
                mention_id=mid, action="select", selected_wind_code="000001.SZ"
            )
        ],
        role_assignments=[RoleAssignment(mention_id=mid, role="primary")],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: decision
    )
    resolver = CompanyEntityResolver(
        lookup, selector=CompanySemanticSelector(mode="suggest")
    )
    r = resolver.resolve("分析平安")
    assert r.selector_status == "completed"
    assert r.semantic_suggestion is not None
    # mentions 逐字段深比较一致（身份/状态/角色均未被 suggest 改写）
    for m0, m1 in zip(r0.mentions, r.mentions):
        assert m0.model_dump() == m1.model_dump()
    assert r.intent == r0.intent
    assert r.needs_confirmation == r0.needs_confirmation
