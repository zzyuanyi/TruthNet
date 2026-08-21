"""方案 v3.1 §7 关键测试 — 步骤 8（resolve_entity_node 委托新架构）.

对应审查测试项：
- 唯一精确命中自动锁定；唯一启发式命中按策略处理（经节点派生旧字段）；
- 新实体解析失败或 LLM 失败时不得沿用历史公司（防串到节点层）；
- 身份确认前 relation 不可执行（reference）→ 不派生 comparison；
- 新旧对照：legacy 与 v9 节点对同一输入派生一致（并行迁移期）。
"""

import json

from sqlalchemy import create_engine, text

from app.agents.nodes.resolve_entity import resolve_entity_node
from app.agents.state import AgentState, MemoryContext, RequestContext, RuntimeState

_TABLE = (
    "CREATE TABLE companies ("
    "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
    "industry_l1 TEXT, aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
    "is_latest INTEGER)"
)


def _make_state(query: str, memory: MemoryContext | None = None) -> AgentState:
    return {
        "user_query": query,
        "memory_context": memory,
        "runtime": RuntimeState(trace_id="t", session_id="s"),
    }


def _mysql_repo(rows: list[tuple]):
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
    from app.infrastructure.persistence.mysql.company_repository import (
        MySQLCompanyRepository,
    )

    mrepo = MySQLCompanyRepository()
    mrepo._engine = engine
    return mrepo


# ── 确定性正例（lite profile，CI 可用）───────────────────────


def test_exact_name_single():
    r = resolve_entity_node(_make_state("康美药业的财务风险"))
    assert r["company"] is not None
    assert r["company"].sec_name == "康美药业"
    assert r["company_candidates"] == []
    assert not r["comparison_requested"]


def test_query_code_single():
    r = resolve_entity_node(_make_state("600519.SH 的营收"))
    assert r["company"].wind_code == "600519.SH"


def test_reverse_contains_unique_locked():
    """'茅台营收' → 贵州茅台（safe_reverse_contains 锁定）。"""
    r = resolve_entity_node(_make_state("茅台营收"))
    assert r["company"] is not None
    assert r["company"].sec_name == "贵州茅台"


# ── 历史延续与防串（节点层）─────────────────────────────────


def test_anaphora_continues_history():
    mc = MemoryContext(
        resolved_entity_name="康美药业",
        resolved_company_code="600518.SH",
        is_anaphora=True,
    )
    r = resolve_entity_node(_make_state("它的应收账款增速", mc))
    assert r["company"].sec_name == "康美药业"


def test_unresolved_new_entity_not_inherited(monkeypatch):
    """历史康美 + '台泥的营收'（lite 无台泥）→ 防串：不沿用康美，报未识别。"""
    import app.agents.nodes.resolve_entity as rn
    from app.infrastructure.persistence.sqlite.company_repository import (
        SQLiteCompanyRepository,
    )

    monkeypatch.setattr(rn, "get_company_repository", lambda: SQLiteCompanyRepository())
    mc = MemoryContext(
        resolved_entity_name=None,
        resolved_company_code="600518.SH",
        is_anaphora=False,
        previous_companies=["康美药业"],
    )
    r = resolve_entity_node(_make_state("台泥的营收", mc))
    assert r["company"] is None
    assert r["entity_resolution_error"] == "company_not_found"
    assert r["unresolved_fragments"] == ["台泥"]


def test_explicit_code_highest_priority():
    state = _make_state(
        "分析贵州茅台", MemoryContext(resolved_company_code="600518.SH")
    )
    state["request_context"] = RequestContext(company_code="600518.SH")
    r = resolve_entity_node(state)
    assert r["company"].sec_name == "康美药业"


def test_generic_technology_topic_does_not_become_company(monkeypatch):
    import app.application.services.exact_company_spotter as spotter

    monkeypatch.setattr(spotter, "spot_exact_company_spans", lambda _query: [])
    result = resolve_entity_node(_make_state("固态电池技术的最新研发动态有哪些"))

    assert result["company"] is None
    assert result["company_candidates"] == []
    assert result["entity_resolution_result"].reason_code == "industry_context"


def test_chitchat_and_market_without_company_skip_entity_lookup():
    chitchat = resolve_entity_node(_make_state("你会什么"))
    market = resolve_entity_node(_make_state("近一月涨跌幅"))

    assert chitchat["entity_resolution_result"].reason_code == "chitchat"
    assert market["entity_resolution_result"].reason_code == "company_not_found"


def test_market_query_with_exact_company_still_resolves_entity():
    result = resolve_entity_node(_make_state("贵州茅台近期走势如何"))

    assert result["company"] is not None, result[
        "entity_resolution_result"
    ].model_dump()
    assert result["company"].wind_code == "600519.SH"


def test_market_query_with_explicit_code_still_resolves_entity():
    result = resolve_entity_node(_make_state("600519.SH 近一周涨跌幅"))

    assert result["company"] is not None, result[
        "entity_resolution_result"
    ].model_dump()
    assert result["company"].wind_code == "600519.SH"


def test_bare_market_followup_uses_current_company():
    memory = MemoryContext(current_company_code="600519.SH")
    result = resolve_entity_node(_make_state("换手率", memory))

    assert result["company"] is not None, result[
        "entity_resolution_result"
    ].model_dump()
    assert result["company"].wind_code == "600519.SH"


# ── 多 mention 与确认（MySQL 内存表）────────────────────────


def test_comparison_derives_targets(monkeypatch):
    import app.agents.nodes.resolve_entity as rn

    repo = _mysql_repo(
        [
            ("c1", "600519.SH", "贵州茅台", None),
            ("c2", "603077.SH", "和邦生物", None),
        ]
    )
    monkeypatch.setattr(rn, "get_company_repository", lambda: repo)
    r = resolve_entity_node(_make_state("茅台和和邦对比"))
    assert r["comparison_requested"] is True
    assert {c.sec_name for c in r["comparison_targets"]} == {"贵州茅台", "和邦生物"}
    assert r["company"] is None


def test_multi_mention_single_unconfirmed_flat_candidates(monkeypatch):
    """'平安和茅台对比'：恰好 1 个未确认 mention（平安）→ 旧扁平候选
    输出该 mention 候选（P0-5）；茅台已锁定。

    最终续审 §4 A4：部分绑定不得作为可执行 comparison 离开 → 降级
    ambiguous，comparison_requested 不再置 True（确认重跑后恢复）。
    """
    import app.agents.nodes.resolve_entity as rn

    repo = _mysql_repo(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
            ("c3", "600519.SH", "贵州茅台", None),
        ]
    )
    monkeypatch.setattr(rn, "get_company_repository", lambda: repo)
    r = resolve_entity_node(_make_state("平安和茅台对比"))
    assert r["company"] is None
    assert {c.wind_code for c in r["company_candidates"]} == {
        "000001.SZ",
        "601318.SH",
    }  # 仅平安的候选（不混入茅台）
    assert r["comparison_requested"] is False  # A4 降级 ambiguous


def test_relation_reference_not_comparison(monkeypatch):
    """ "分析康美提到茅台的公告" → relation=reference，不派生 comparison。"""
    import app.agents.nodes.resolve_entity as rn

    repo = _mysql_repo(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    monkeypatch.setattr(rn, "get_company_repository", lambda: repo)
    r = resolve_entity_node(_make_state("分析康美提到茅台的公告"))
    result = r["entity_resolution_result"]
    assert result.intent == "reference"
    assert r["company"] is None
    assert r["comparison_requested"] is False  # 不进入 comparison_guide


# ── 对照测试（步骤 8 完成使命；legacy 已于步骤 11 删除）───────
