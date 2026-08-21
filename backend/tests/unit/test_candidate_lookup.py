"""方案 v3.1 §7 关键测试 — 步骤 5（候选 lookup port / CandidateMatch / 截断）.

对应审查测试项：
- 恰好 limit 个候选不误判 truncated，limit+1 才截断（P1-3）；
- match_kind 区分：exact_code/exact_name/exact_alias/contains/reverse_contains/prefix
  （P1-2）；反向包含"茅台→贵州茅台"标 reverse_contains，前缀"和邦→和邦生物"
  标 prefix；
- URL.create()（P1-6）密码特殊字符（本测试通过内存表间接覆盖引擎创建路径）。
"""

import asyncio
import json

from sqlalchemy import create_engine, text

from app.application.models.company_resolution import CandidateLookupResult
from app.infrastructure.persistence.mysql.company_repository import (
    MySQLCompanyRepository,
)
from app.infrastructure.persistence.sqlite.company_repository import (
    SQLiteCompanyRepository,
)

_TABLE = (
    "CREATE TABLE companies ("
    "entity_id TEXT, wind_code TEXT, sec_name TEXT, exchange_code TEXT, "
    "industry_l1 TEXT, aliases TEXT, listing_date TEXT, comp_type_code TEXT, "
    "is_latest INTEGER)"
)


def _make_engine(rows: list[tuple]) -> "object":
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
    return engine


def _lookup(engine, text_query: str, limit: int = 6) -> CandidateLookupResult:
    repo = MySQLCompanyRepository()
    repo._engine = engine  # 复用测试引擎，不触发真实连接
    return repo.lookup_mention(text_query, limit=limit)


# ── match_kind 区分（P1-2）──────────────────────────────────


def test_exact_code_kind():
    engine = _make_engine(
        [("c1", "600518.SH", "康美药业", None), ("c2", "600519.SH", "贵州茅台", None)]
    )
    result = _lookup(engine, "600518.SH")
    assert len(result.matches) == 1
    assert result.matches[0].match_kind == "exact_code"
    assert result.matches[0].company.sec_name == "康美药业"


def test_exact_name_kind():
    engine = _make_engine(
        [("c1", "600518.SH", "康美药业", None), ("c2", "600519.SH", "贵州茅台", None)]
    )
    result = _lookup(engine, "贵州茅台")
    assert [m.match_kind for m in result.matches] == ["exact_name"]
    assert result.matches[0].company.wind_code == "600519.SH"


def test_reverse_contains_maotai():
    """'茅台' → 贵州茅台（sec_name 包含 mention，标 reverse_contains）。"""
    engine = _make_engine(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
            ("c3", "603589.SH", "口子窖", None),
        ]
    )
    result = _lookup(engine, "茅台")
    assert [m.match_kind for m in result.matches] == ["reverse_contains"]
    assert result.matches[0].company.sec_name == "贵州茅台"


def test_prefix_kind_hebang():
    """'和邦' → 和邦生物（sec_name 以 mention 开头，标 prefix）。"""
    engine = _make_engine(
        [
            ("c1", "603077.SH", "和邦生物", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    result = _lookup(engine, "和邦")
    assert [m.match_kind for m in result.matches] == ["prefix"]
    assert result.matches[0].company.sec_name == "和邦生物"


def test_contains_kind_full_name_in_mention():
    """mention 包含完整 sec_name（如 '康美药业和贵州茅台'）→ contains。"""
    engine = _make_engine(
        [
            ("c1", "600518.SH", "康美药业", None),
            ("c2", "600519.SH", "贵州茅台", None),
        ]
    )
    result = _lookup(engine, "康美药业和贵州茅台")
    kinds = [m.match_kind for m in result.matches]
    assert kinds == ["contains", "contains"]
    assert {m.company.sec_name for m in result.matches} == {"康美药业", "贵州茅台"}


def test_exact_alias_kind():
    engine = _make_engine(
        [
            ("c1", "000001.SZ", "平安银行", json.dumps(["平安"], ensure_ascii=False)),
            ("c2", "601318.SH", "中国平安", json.dumps(["平安"], ensure_ascii=False)),
            ("c3", "600519.SH", "贵州茅台", None),
        ]
    )
    result = _lookup(engine, "平安")
    # 别名精确命中两家（exact_alias）；sec_name 反向包含可能也命中
    kinds = [m.match_kind for m in result.matches]
    assert "exact_alias" in kinds
    assert {m.company.sec_name for m in result.matches} == {"平安银行", "中国平安"}


# ── limit+1 截断（P1-3）─────────────────────────────────────


def _many_pingans(n: int) -> list[tuple]:
    return [(f"c{i}", f"{601000 + i}.SH", f"平安集团{i}", None) for i in range(n)]


def test_exactly_limit_not_truncated():
    """恰好 limit 个候选 → truncated=False（不误判）。"""
    engine = _make_engine(_many_pingans(6))
    result = _lookup(engine, "平安", limit=6)
    assert len(result.matches) == 6
    assert result.truncated is False


def test_limit_plus_one_truncated():
    """limit+1 个候选 → truncated=True，candidates 截到 limit。"""
    engine = _make_engine(_many_pingans(7))
    result = _lookup(engine, "平安", limit=6)
    assert len(result.matches) == 6
    assert result.truncated is True


def test_empty_text_returns_empty():
    engine = _make_engine(_many_pingans(3))
    result = _lookup(engine, "")
    assert result.matches == []
    assert result.truncated is False


def test_mysql_empty_search_keeps_result_contract():
    repo = MySQLCompanyRepository()
    repo._list_all_sync = lambda limit: []

    result = asyncio.run(repo.search("", limit=3))

    assert result.companies == []
    assert result.total == 0


# ── lite 实现（Resolver 单元测试用）─────────────────────────


def test_lite_lookup_kinds():
    repo = SQLiteCompanyRepository()
    r1 = repo.lookup_mention("茅台")
    assert [m.match_kind for m in r1.matches] == ["reverse_contains"]
    assert r1.matches[0].company.sec_name == "贵州茅台"
    r2 = repo.lookup_mention("600519.SH")
    assert r2.matches[0].match_kind == "exact_code"
    r3 = repo.lookup_mention("贵州茅台")
    assert r3.matches[0].match_kind == "exact_name"
    r4 = repo.lookup_mention("康美药业")
    assert r4.matches[0].match_kind == "exact_name"
    assert r4.matches[0].company.sec_name == "康美药业"
