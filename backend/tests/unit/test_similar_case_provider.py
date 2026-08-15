"""相似指标案例 Provider + Schema 单元测试 — 任务①.

覆盖（SQLite 合成数据，不访问 MySQL/网络）：
- Schema 四态序列化 + FinanceRuleItem 含 similar_cases；
- Provider：同行业优先 / 自排除 / limit=5 / 距离排序 / sources[] 覆盖全部
  涉及表且 row_id 可回查 / metric_value=None→empty / 无样本→empty /
  引擎异常→error / 非法 rule_id→not_supported。
"""

import pytest
from sqlalchemy import create_engine, text

from app.api.v1.schemas.finance import (
    FinanceRuleItem,
    SimilarCase,
    SimilarCaseSource,
    SimilarCasesResult,
)
from app.application.services.similar_case_provider import (
    RealSimilarCaseProvider,
    extract_metric_value,
)

STATEMENT = "408006000"


class _ExplodingEngine:
    """connect() 即抛错的引擎，用于验证 Provider 异常降级为 error。"""

    def connect(self):
        raise RuntimeError("engine boom")


@pytest.fixture
def provider_engine(tmp_path):
    """临时 SQLite 库（companies + 三张报表，含行级定位字段）。"""
    db_path = tmp_path / "similar.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE companies (wind_code TEXT PRIMARY KEY, sec_name TEXT, "
                "comp_type_code INTEGER, industry_l1 TEXT, is_latest INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE balance_sheet (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "source_record_id TEXT, wind_code TEXT, report_period TEXT, "
                "statement_type TEXT, acct_rcv REAL, oth_rcv REAL, inventories REAL, "
                "monetary_cap REAL, tot_assets REAL, st_borrow REAL, lt_borrow REAL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE income_statement (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "source_record_id TEXT, wind_code TEXT, report_period TEXT, "
                "statement_type TEXT, oper_rev REAL, less_oper_cost REAL, "
                "net_profit_excl_min_int_inc REAL, net_profit_after_ded_nr_lp REAL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE cash_flow (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "source_record_id TEXT, wind_code TEXT, report_period TEXT, "
                "statement_type TEXT, net_cash_flows_oper_act REAL)"
            )
        )
    yield engine
    engine.dispose()


def _insert(engine, table, values):
    cols = list(values.keys())
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {table} ({', '.join(cols)}) "
                f"VALUES ({', '.join(':' + c for c in cols)})"
            ),
            values,
        )


def _insert_company(
    engine, code, name=None, comp_type=1, industry="医药生物", is_latest=1
):
    _insert(
        engine,
        "companies",
        {
            "wind_code": code,
            "sec_name": name or code,
            "comp_type_code": comp_type,
            "industry_l1": industry,
            "is_latest": is_latest,
        },
    )


def _insert_bs(engine, code, period, **fields):
    row = {
        "source_record_id": fields.pop("source_record_id", f"bs:{code}:{period}"),
        "wind_code": code,
        "report_period": period,
        "statement_type": STATEMENT,
        "acct_rcv": None,
        "oth_rcv": None,
        "inventories": None,
        "monetary_cap": None,
        "tot_assets": None,
        "st_borrow": None,
        "lt_borrow": None,
    }
    row.update(fields)
    _insert(engine, "balance_sheet", row)


def _insert_is(engine, code, period, **fields):
    row = {
        "source_record_id": fields.pop("source_record_id", f"is:{code}:{period}"),
        "wind_code": code,
        "report_period": period,
        "statement_type": STATEMENT,
        "oper_rev": None,
        "less_oper_cost": None,
        "net_profit_excl_min_int_inc": None,
        "net_profit_after_ded_nr_lp": None,
    }
    row.update(fields)
    _insert(engine, "income_statement", row)


def _insert_cf(engine, code, period, **fields):
    row = {
        "source_record_id": fields.pop("source_record_id", f"cf:{code}:{period}"),
        "wind_code": code,
        "report_period": period,
        "statement_type": STATEMENT,
        "net_cash_flows_oper_act": None,
    }
    row.update(fields)
    _insert(engine, "cash_flow", row)


def _seed_r1_peer(engine, code, gap, industry="医药生物"):
    """按目标 gap（pp）播种一个 R1 同行公司（or_yoy=0，ar_yoy=gap/100）。

    数值须 ≥1 万元，否则 yoy_growth 的 1 万元分母保护会返回 None。
    """
    _insert_company(engine, code, industry=industry)
    ar_prev = 100_000_000.0
    ar_cur = ar_prev * (1 + gap / 100)
    _insert_bs(
        engine, code, "20250331", acct_rcv=ar_prev, source_record_id=f"bs:{code}:prev"
    )
    _insert_bs(
        engine, code, "20260331", acct_rcv=ar_cur, source_record_id=f"bs:{code}:cur"
    )
    _insert_is(
        engine,
        code,
        "20250331",
        oper_rev=200_000_000.0,
        source_record_id=f"is:{code}:prev",
    )
    _insert_is(
        engine,
        code,
        "20260331",
        oper_rev=200_000_000.0,
        source_record_id=f"is:{code}:cur",
    )


def _seed_r4_peer(engine, code, gap, industry="医药生物"):
    """按目标 gap（pp）播种一个 R4 同行公司（or_yoy=0，inv_yoy=gap/100）。

    R4 growth_gap = 存货增速 - 营收增速；存货去年同期 ≥1 万元避免分母保护。
    """
    _insert_company(engine, code, industry=industry)
    inv_prev = 100_000_000.0
    inv_cur = inv_prev * (1 + gap / 100)
    _insert_bs(
        engine,
        code,
        "20250331",
        inventories=inv_prev,
        source_record_id=f"bs:{code}:prev",
    )
    _insert_bs(
        engine, code, "20260331", inventories=inv_cur, source_record_id=f"bs:{code}:cur"
    )
    _insert_is(
        engine,
        code,
        "20250331",
        oper_rev=200_000_000.0,
        source_record_id=f"is:{code}:prev",
    )
    _insert_is(
        engine,
        code,
        "20260331",
        oper_rev=200_000_000.0,
        source_record_id=f"is:{code}:cur",
    )


def _fetch_source_row(engine, source):
    """按 source 的 row_id 回查真实行（字段值 + 期间 + 口径 + 公司）。"""
    table = source.source_table
    field = source.fields[0]
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    f"SELECT wind_code, report_period, statement_type, "
                    f"{field} AS value FROM {table} WHERE id = :rid"
                ),
                {"rid": source.row_id},
            )
            .mappings()
            .one()
        )
    return row


# ══════════════════════════════════════════════════════════
# Schema 序列化
# ══════════════════════════════════════════════════════════


def test_schema_four_states_roundtrip():
    ok = SimilarCasesResult(
        status="ok",
        cases=[
            SimilarCase(
                company_code="920992.BJ",
                company_name="中科美菱",
                industry="医药生物",
                period="20260331",
                metric={"gap": 13.32},
                distance=0.003,
            )
        ],
    )
    empty = SimilarCasesResult(status="empty", reason="暂无相似案例")
    error = SimilarCasesResult(status="error", reason="数据库连接失败")
    not_supported = SimilarCasesResult(status="not_supported", reason="规则 R8 不支持")

    for obj in (ok, empty, error, not_supported):
        dumped = obj.model_dump(mode="json")
        restored = SimilarCasesResult.model_validate(dumped)
        assert restored.status == obj.status
        assert restored.reason == obj.reason
        assert restored.cases == obj.cases


def test_schema_source_and_finance_rule_item():
    src = SimilarCaseSource(
        source_table="balance_sheet",
        row_id=7,
        source_record_id="bs:600000.SH:20260331",
        wind_code="600000.SH",
        report_period="20260331",
        fields=["acct_rcv"],
    )
    assert src.report_statement_type == "408006000"
    assert src.model_dump(mode="json")["row_id"] == 7

    item = FinanceRuleItem(
        rule_id="R1",
        status="triggered",
        similar_cases=SimilarCasesResult(status="empty", reason="暂无相似案例"),
    )
    assert item.similar_cases is not None
    assert item.similar_cases.status == "empty"
    dumped = item.model_dump(mode="json")
    assert dumped["similar_cases"]["status"] == "empty"
    # 未传入时默认 None
    assert FinanceRuleItem(rule_id="R2").similar_cases is None


def test_schema_source_period_role():
    current = SimilarCaseSource(
        source_table="balance_sheet",
        wind_code="600000.SH",
        report_period="20260331",
    )
    assert current.period_role == "current"
    prior = SimilarCaseSource(
        source_table="balance_sheet",
        wind_code="600000.SH",
        report_period="20250331",
        period_role="prior",
    )
    assert prior.period_role == "prior"
    assert prior.model_dump(mode="json")["period_role"] == "prior"


def test_extract_metric_value():
    current = {
        "gap": {"value": 12.0, "unit": "percentage_point"},
        "other": {"value": 1, "unit": "x"},
    }
    assert extract_metric_value("R1", current) == {"gap": 12.0}
    assert extract_metric_value("R1", {}) is None
    assert extract_metric_value("R1", {"gap": {"value": None}}) is None
    assert extract_metric_value("R1", {"gap": {"unit": "%"}}) is None
    assert extract_metric_value("R8", current) is None


# ══════════════════════════════════════════════════════════
# Provider 状态映射
# ══════════════════════════════════════════════════════════


def test_provider_not_supported_unknown_rule(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    result = p.find("R8", "600000.SH", {"x": 1.0}, "医药生物", "20260331")
    assert result.status == "not_supported"


def test_provider_empty_when_metric_missing(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _insert_company(provider_engine, "600000.SH")
    result = p.find("R1", "600000.SH", None, "医药生物", "20260331")
    assert result.status == "empty"
    assert result.cases == []
    assert "暂无相似案例" in result.reason


def test_provider_empty_when_no_samples(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _insert_company(provider_engine, "600000.SH")
    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "empty"
    assert result.cases == []


def test_provider_error_on_engine_failure():
    p = RealSimilarCaseProvider(engine=_ExplodingEngine())
    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "error"
    assert result.cases == []
    assert result.reason


# ══════════════════════════════════════════════════════════
# Provider 检索核心（R1：跨表 + YoY）
# ══════════════════════════════════════════════════════════


def test_provider_r1_distance_sorted_and_self_excluded(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    # 目标公司自身（gap 12）不应出现在结果中
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    for code, gap in [
        ("P05", 5.0),
        ("P10", 10.0),
        ("P15", 15.0),
        ("P20", 20.0),
        ("P25", 25.0),
    ]:
        _seed_r1_peer(provider_engine, code, gap)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    codes = [c.company_code for c in result.cases]
    assert "600000.SH" not in codes  # 自排除
    # 距离升序（单指标 |gap-12|）：P10(2) < P15(3) < P05(7) < P20(8) < P25(13)
    assert codes == ["P10", "P15", "P05", "P20", "P25"]
    assert [c.distance for c in result.cases] == sorted(
        c.distance for c in result.cases
    )


def test_provider_r1_same_industry_only_when_enough(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    for code, gap in [
        ("P10", 10.0),
        ("P15", 15.0),
        ("P05", 5.0),
        ("P20", 20.0),
        ("P25", 25.0),
    ]:
        _seed_r1_peer(provider_engine, code, gap)
    # 跨行业更接近（gap 11）也不应进入结果：同行业样本 ≥ limit 只取同行业
    _seed_r1_peer(provider_engine, "CROSS11", 11.0, industry="计算机")

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    assert all(c.industry == "医药生物" for c in result.cases)
    assert "CROSS11" not in [c.company_code for c in result.cases]


def test_provider_r1_cross_industry_fill_same_first(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    # 仅 2 家同行（< limit），需跨行业补足，且同行排前
    _seed_r1_peer(provider_engine, "P10", 10.0)
    _seed_r1_peer(provider_engine, "P15", 15.0)
    # 跨行业更接近
    _seed_r1_peer(provider_engine, "CROSS12", 12.0, industry="计算机")
    _seed_r1_peer(provider_engine, "CROSS11", 11.0, industry="计算机")

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    codes = [c.company_code for c in result.cases]
    # 同行排前：P10/P15 在前，跨行业补足在后
    assert codes[:2] == ["P10", "P15"]
    assert set(codes) == {"P10", "P15", "CROSS11", "CROSS12"}


def test_provider_limit_5(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    for i in range(7):
        _seed_r1_peer(provider_engine, f"P{i:02d}", 5.0 + i * 2.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331", limit=5)
    assert result.status == "ok"
    assert len(result.cases) == 5


def test_provider_r1_sources_cover_all_tables_and_row_backtrace(provider_engine):
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    case = result.cases[0]
    assert case.company_code == "P10"
    # R1 跨表 × YoY：balance_sheet + income_statement × current + prior = 4 条
    assert len(case.sources) == 4
    roles = {(s.source_table, s.period_role) for s in case.sources}
    assert roles == {
        ("balance_sheet", "current"),
        ("balance_sheet", "prior"),
        ("income_statement", "current"),
        ("income_statement", "prior"),
    }
    for s in case.sources:
        assert s.fields == (
            ["acct_rcv"] if s.source_table == "balance_sheet" else ["oper_rev"]
        )
        assert s.report_period == (
            "20260331" if s.period_role == "current" else "20250331"
        )

    # row_id 可回查：用 row_id 查回真实行，且 wind_code/report_period/口径一致
    bs_cur = next(
        s
        for s in case.sources
        if s.source_table == "balance_sheet" and s.period_role == "current"
    )
    assert bs_cur.row_id is not None
    assert bs_cur.report_period == "20260331"
    assert bs_cur.report_statement_type == "408006000"
    with provider_engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT wind_code, report_period, statement_type, acct_rcv "
                    "FROM balance_sheet WHERE id = :rid"
                ),
                {"rid": bs_cur.row_id},
            )
            .mappings()
            .one()
        )
    assert row["wind_code"] == "P10"
    assert row["report_period"] == "20260331"
    assert row["statement_type"] == "408006000"
    assert row["acct_rcv"] == pytest.approx(110_000_000.0)

    # 证据采用原始行回查模式（evidence_ids 为空，sources 可回查）
    assert case.evidence_ids == []
    assert case.statement_type == "observed"
    assert case.report_statement_type == "408006000"


def test_provider_r1_sources_recompute_metric(provider_engine):
    """用 R1 sources[]（current+prior 回查真实值）重算 gap，须与案例 metric 一致。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    case = result.cases[0]
    assert case.company_code == "P10"

    def val(table, role):
        source = next(
            s for s in case.sources if s.source_table == table and s.period_role == role
        )
        row = _fetch_source_row(provider_engine, source)
        # 每个 source 都能按其 row_id 回查到对应行（期间/公司/口径一致）
        assert row["wind_code"] == case.company_code
        assert row["report_period"] == source.report_period
        assert row["statement_type"] == "408006000"
        return row["value"]

    ar_cur = val("balance_sheet", "current")
    ar_prev = val("balance_sheet", "prior")
    or_cur = val("income_statement", "current")
    or_prev = val("income_statement", "prior")
    ar_yoy = (ar_cur - ar_prev) / abs(ar_prev)
    or_yoy = (or_cur - or_prev) / abs(or_prev)
    gap = (ar_yoy - or_yoy) * 100
    assert gap == pytest.approx(case.metric["gap"], rel=1e-6)
    # 播种口径：or_yoy=0，gap 即应收增速
    assert gap == pytest.approx(10.0, rel=1e-6)


def test_provider_r4_sources_recompute_metric(provider_engine):
    """用 R4 sources[]（current+prior 回查真实值）重算 growth_gap，与案例一致。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r4_peer(provider_engine, "600000.SH", 12.0)
    _seed_r4_peer(provider_engine, "P10", 10.0)

    result = p.find("R4", "600000.SH", {"growth_gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    case = result.cases[0]
    assert case.company_code == "P10"
    assert len(case.sources) == 4

    def val(table, role):
        source = next(
            s for s in case.sources if s.source_table == table and s.period_role == role
        )
        row = _fetch_source_row(provider_engine, source)
        assert row["report_period"] == source.report_period
        assert row["statement_type"] == "408006000"
        return row["value"]

    inv_cur = val("balance_sheet", "current")
    inv_prev = val("balance_sheet", "prior")
    or_cur = val("income_statement", "current")
    or_prev = val("income_statement", "prior")
    inv_yoy = (inv_cur - inv_prev) / abs(inv_prev)
    or_yoy = (or_cur - or_prev) / abs(or_prev)
    growth_gap = (inv_yoy - or_yoy) * 100
    assert growth_gap == pytest.approx(case.metric["growth_gap"], rel=1e-6)
    assert growth_gap == pytest.approx(10.0, rel=1e-6)


def test_provider_r1_missing_prior_excluded_no_forged_source(provider_engine):
    """缺去年同期数据的公司被排除；存续案例的去年行填真实期间，不伪造。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)
    # 只有当前期行，无 20250331 行
    _insert_company(provider_engine, "P_NO_PRIOR")
    _insert_bs(provider_engine, "P_NO_PRIOR", "20260331", acct_rcv=110_000_000.0)
    _insert_is(provider_engine, "P_NO_PRIOR", "20260331", oper_rev=200_000_000.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    codes = [c.company_code for c in result.cases]
    assert "P_NO_PRIOR" not in codes  # 缺去年同期 → 排除
    assert "P10" in codes
    case = next(c for c in result.cases if c.company_code == "P10")
    prior_periods = {s.report_period for s in case.sources if s.period_role == "prior"}
    assert prior_periods == {"20250331"}  # 去年行填真实期间，不填当前期


def test_provider_r1_missing_prior_all_empty(provider_engine):
    """唯一候选缺去年同期时，返回 empty，绝不伪造去年行。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _insert_company(provider_engine, "P_NO_PRIOR")
    _insert_bs(provider_engine, "P_NO_PRIOR", "20260331", acct_rcv=110_000_000.0)
    _insert_is(provider_engine, "P_NO_PRIOR", "20260331", oper_rev=200_000_000.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "empty"
    assert result.cases == []


# ══════════════════════════════════════════════════════════
# 批次 G：候选公司只取最新快照（is_latest=1）
# ══════════════════════════════════════════════════════════


def test_provider_excludes_stale_company_snapshot(provider_engine):
    """is_latest=0 的公司即便有完整当前期+去年同期行，也不能成为候选。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)
    _seed_r1_peer(provider_engine, "P_STALE", 8.0)  # 距离最近但为旧快照
    with provider_engine.begin() as conn:
        conn.execute(
            text("UPDATE companies SET is_latest = 0 WHERE wind_code = :wc"),
            {"wc": "P_STALE"},
        )

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    codes = [c.company_code for c in result.cases]
    assert "P_STALE" not in codes
    assert codes == ["P10"]


def test_provider_includes_latest_company_snapshot(provider_engine):
    """is_latest=1 的公司可成为候选。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    assert [c.company_code for c in result.cases] == ["P10"]


def test_provider_self_exclusion_still_applies(provider_engine):
    """目标公司即便 is_latest=1 也仍自排除。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    assert "600000.SH" not in [c.company_code for c in result.cases]


def test_provider_financial_company_not_participating(provider_engine):
    """comp_type_code != 1 的金融企业不参与候选（即便 is_latest=1）。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _seed_r1_peer(provider_engine, "600000.SH", 12.0)
    _seed_r1_peer(provider_engine, "P10", 10.0)
    _seed_r1_peer(provider_engine, "BANK", 8.0)  # 数据完整但为金融企业
    with provider_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE companies SET comp_type_code = 2, industry_l1 = '银行' "
                "WHERE wind_code = :wc"
            ),
            {"wc": "BANK"},
        )

    result = p.find("R1", "600000.SH", {"gap": 12.0}, "医药生物", "20260331")
    assert result.status == "ok"
    assert "BANK" not in [c.company_code for c in result.cases]


def test_provider_r3_single_table_multi_metric(provider_engine):
    """R3 单表 + 多指标欧氏距离。"""
    p = RealSimilarCaseProvider(engine=provider_engine)
    _insert_company(provider_engine, "600000.SH")
    _insert_company(provider_engine, "B1")
    _insert_company(provider_engine, "B2")
    _insert_bs(
        provider_engine,
        "B1",
        "20260331",
        monetary_cap=30.0,
        st_borrow=20.0,
        lt_borrow=5.0,
        tot_assets=100.0,
    )
    _insert_bs(
        provider_engine,
        "B2",
        "20260331",
        monetary_cap=50.0,
        st_borrow=40.0,
        lt_borrow=10.0,
        tot_assets=100.0,
    )

    result = p.find(
        "R3",
        "600000.SH",
        {"cash_to_assets": 30.0, "debt_to_assets": 25.0},
        "医药生物",
        "20260331",
    )
    assert result.status == "ok"
    assert result.cases
    first = result.cases[0]
    assert set(first.metric.keys()) == {"cash_to_assets", "debt_to_assets"}
    # R3 单表：仅 balance_sheet 一条 source，字段含全部参与计算列
    assert len(first.sources) == 1
    assert first.sources[0].source_table == "balance_sheet"
    assert set(first.sources[0].fields) == {
        "monetary_cap",
        "st_borrow",
        "lt_borrow",
        "tot_assets",
    }
    # B1 (30%,25%) 与目标完全相同 → 距离 0 排最前
    assert first.company_code == "B1"
    assert first.distance == pytest.approx(0.0)


class TestDecimalCoercion:
    """真机回归：MySQL DECIMAL 列以 decimal.Decimal 返回，未经归一化会抛
    ``unsupported operand type(s) for *: 'decimal.Decimal' and 'float'``。
    _to_float + _field/_prev_field 边界归一化必须保证 _compute_metric 全程 float。
    """

    def test_to_float_coerces_decimal(self):
        from decimal import Decimal

        from app.application.services.similar_case_provider import _to_float

        assert _to_float(Decimal("12.5")) == 12.5
        assert _to_float(None) is None
        assert _to_float("abc") is None

    def test_compute_metric_survives_decimal_raw_values(self):
        from decimal import Decimal

        from app.application.services.similar_case_provider import (
            _RawRow,
            _compute_metric,
        )

        def row(period: str, **values) -> _RawRow:
            return _RawRow(
                row_id=1,
                source_record_id=None,
                wind_code="600000.SH",
                report_period=period,
                values=values,
            )

        cur_rows = {
            "balance_sheet": {
                "600000.SH": row(
                    "20260331",
                    acct_rcv=Decimal("120000000"),
                    oth_rcv=Decimal("5000000"),
                    inventories=Decimal("80000000"),
                    monetary_cap=Decimal("30000000"),
                    tot_assets=Decimal("100000000"),
                    st_borrow=Decimal("20000000"),
                    lt_borrow=Decimal("10000000"),
                )
            },
            "income_statement": {
                "600000.SH": row(
                    "20260331",
                    oper_rev=Decimal("200000000"),
                    less_oper_cost=Decimal("150000000"),
                    net_profit_excl_min_int_inc=Decimal("40000000"),
                    net_profit_after_ded_nr_lp=Decimal("30000000"),
                )
            },
            "cash_flow": {
                "600000.SH": row(
                    "20260331", net_cash_flows_oper_act=Decimal("20000000")
                )
            },
        }
        prev_rows = {
            "balance_sheet": {
                "600000.SH": row("20250331", acct_rcv=Decimal("100000000"))
            },
            "income_statement": {
                "600000.SH": row("20250331", oper_rev=Decimal("180000000"))
            },
        }
        m1 = _compute_metric("R1", cur_rows, prev_rows, "600000.SH")
        assert isinstance(m1["gap"], float)  # Decimal * float 不再抛 TypeError
        m5 = _compute_metric("R5", cur_rows, prev_rows, "600000.SH")
        assert isinstance(m5["gross_margin"], float)
        m7 = _compute_metric("R7", cur_rows, prev_rows, "600000.SH")
        assert isinstance(m7["core_profit_ratio"], float)
