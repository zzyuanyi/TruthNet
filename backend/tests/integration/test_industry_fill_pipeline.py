"""行业补全链路 SQLite 集成测试（档案 v1.1 §10.2）。

覆盖：dry-run 零写入、apply 只补缺失、事务回滚、幂等、
>51 候选不截断（无隐式 50）、nan 占位值清洗、研报确定性补全、
门禁 fail-closed 拒绝 apply（缺记录）、非法行业值降级 UNMAPPED 零写入。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from backend.app.application.services.industry_fill.constants import QueryStatus
from backend.app.application.services.industry_fill.db import (
    apply_industry_fill,
    current_database,
    fetch_coverage_stats,
)
from backend.app.application.services.industry_fill.provider import ProviderResult
from backend.app.application.services.industry_fill.service import (
    RunConfig,
    run_pipeline,
)

DDL = """
CREATE TABLE companies (
  wind_code VARCHAR(32) PRIMARY KEY,
  sec_name VARCHAR(128) NOT NULL,
  industry_l1 VARCHAR(64),
  industry_l2 VARCHAR(64),
  sw_indu_code VARCHAR(32),
  industry_source VARCHAR(64),
  industry_as_of VARCHAR(10)
);
CREATE TABLE research_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  wind_code VARCHAR(32),
  sec_name VARCHAR(128),
  industry_l1 VARCHAR(64),
  sw_indu_code VARCHAR(32)
);
"""


class FakeProvider:
    name = "fake"

    def __init__(self, script: dict[str, ProviderResult]):
        self.script = script
        self.queried: list[str] = []

    def probe(self) -> dict:
        return {}

    def query_many(
        self,
        codes,
        *,
        retry_empty=False,
        cached=None,
        max_retries=3,
        backoff_seconds=1.0,
        on_progress=None,
        on_result=None,
        concurrency=4,
    ):
        out = []
        for code in codes:
            if code in (cached or {}):
                res = cached[code]
            else:
                self.queried.append(code)
                res = self.script.get(
                    code,
                    ProviderResult(
                        wind_code=code,
                        security_number=code.split(".")[0],
                        query_status=QueryStatus.EMPTY,
                    ),
                )
            out.append(res)
            if on_result is not None:
                on_result(res)
        return out


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for statement in DDL.split(";"):
            if statement.strip():
                conn.exec_driver_sql(statement)
    yield eng
    eng.dispose()


class OmittingProvider(FakeProvider):
    """省略指定代码的 staging 记录，模拟缺记录触发门禁失败（档案 §9 门禁 2）。"""

    def __init__(self, script: dict[str, ProviderResult], omit: set[str]):
        super().__init__(script)
        self.omit = omit

    def query_many(
        self,
        codes,
        *,
        retry_empty=False,
        cached=None,
        max_retries=3,
        backoff_seconds=1.0,
        on_progress=None,
        on_result=None,
        concurrency=4,
    ):
        out = []
        for code in codes:
            if code in self.omit:
                continue  # 不回调、不落盘：该代码缺 staging 记录
            res = self.script.get(
                code,
                ProviderResult(
                    wind_code=code,
                    security_number=code.split(".")[0],
                    query_status=QueryStatus.EMPTY,
                ),
            )
            out.append(res)
            if on_result is not None:
                on_result(res)
        return out


def _seed(
    engine, codes: list[str], with_industry: bool = False, source: str | None = None
):
    with engine.begin() as conn:
        for code in codes:
            conn.execute(
                text(
                    "INSERT INTO companies (wind_code, sec_name, industry_l1, "
                    "industry_source, industry_as_of) VALUES (:c, :n, :l1, :src, :asof)"
                ),
                {
                    "c": code,
                    "n": f"公司{code}",
                    "l1": "食品饮料" if with_industry else None,
                    "src": source
                    if source is not None
                    else ("research_report" if with_industry else "nan"),
                    "asof": "2026-08-14" if with_industry else "2026-08-01",
                },
            )


def _config(engine, provider, **overrides) -> RunConfig:
    base = dict(
        database=":memory:",
        provider=provider,
        mapping_version="sw-l2-to-l1-v1",
        dataset_version="official-2026-07-12",
        provider_version="fake-1.0",
        cache_dir=None,
        run_id="testrun",
        skip_benchmark_rebuild=True,
        mapping_csv_path=Path("data/processed/industry_mapping.csv"),
    )
    base.update(overrides)
    return RunConfig(**base)


class TestPipelineSqlite:
    def test_guard_rejects_wrong_database(self, engine):
        provider = FakeProvider({})
        config = _config(engine, provider, database="wrong-db")
        assert current_database(engine) == ":memory:"
        with pytest.raises(AssertionError, match="启动守卫失败"):
            run_pipeline(engine, config)

    def test_dry_run_writes_nothing(self, engine, tmp_path):
        _seed(engine, ["000001.SZ", "600519.SH"])
        script = {
            "000001.SZ": ProviderResult(
                wind_code="000001.SZ",
                security_number="000001",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            ),
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.EMPTY,
            ),
        }
        provider = FakeProvider(script)
        config = _config(engine, provider, cache_dir=tmp_path)
        result = run_pipeline(engine, config)
        stats = fetch_coverage_stats(engine)
        assert stats["companies_with_industry_before"] == 0
        assert result.report["eligible_apply_rows"] == 1
        assert result.report["dry_run_no_change_ok"] is True
        assert stats["missing"] == 2

    def test_apply_fills_only_missing_and_cleans_nan(self, engine, tmp_path):
        _seed(
            engine, ["000001.SZ", "600519.SH", "600036.SH"]
        )  # 600036.SH 已有行业 + 正常来源，不得被覆盖
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE companies SET industry_l1='银行', industry_source='research_report' "
                    "WHERE wind_code='600036.SH'"
                )
            )
        script = {
            "000001.SZ": ProviderResult(
                wind_code="000001.SZ",
                security_number="000001",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
                industry_l2="白酒Ⅱ",
            ),
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.UNMAPPED,
            ),
        }
        provider = FakeProvider(script)
        config = _config(
            engine,
            provider,
            cache_dir=tmp_path,
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        result = run_pipeline(engine, config)
        stats = fetch_coverage_stats(engine)
        assert stats["companies_with_industry_before"] == 2  # 000001 补 + 600036 原
        assert stats["missing"] == 1
        assert stats["nan_source_count"] == 0  # 占位值同事务清洗
        assert result.apply_result["companies_updated"] >= 1
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT industry_l1, industry_source FROM companies WHERE wind_code='600036.SH'"
                )
            ).fetchone()
        assert (row[0], row[1]) == ("银行", "research_report")
        # apply 后重生成的 CSV 写入指定路径且无 nan 来源（档案 §7.4）
        csv_path = tmp_path / "industry_mapping.csv"
        assert csv_path.exists()
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        assert "000001.SZ" in csv_text
        assert '"nan"' not in csv_text.splitlines()[0]

    def test_rollback_on_failure(self, engine):
        _seed(engine, ["000001.SZ", "000002.SZ", "000003.SZ"])
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TRIGGER boom BEFORE UPDATE ON companies "
                "WHEN NEW.wind_code = '000002.SZ' "
                "BEGIN SELECT RAISE(ABORT, 'boom'); END"
            )
        rows = [
            ("000001.SZ", "食品饮料", None, None, "akshare"),
            ("000002.SZ", "电子", None, None, "akshare"),
            ("000003.SZ", "银行", None, None, "akshare"),
        ]
        with pytest.raises(IntegrityError):
            apply_industry_fill(engine, expected_database=":memory:", rows=rows)
        stats = fetch_coverage_stats(engine)
        assert stats["companies_with_industry_before"] == 0  # 整体回滚
        assert stats["missing"] == 3

    def test_apply_idempotent_second_run(self, engine, tmp_path):
        """第二次 apply（新 run）：缺失条件不再命中，零覆盖改写（档案 §9 门禁 5）。"""
        _seed(engine, ["000001.SZ"])
        script = {
            "000001.SZ": ProviderResult(
                wind_code="000001.SZ",
                security_number="000001",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            )
        }
        config = _config(
            engine,
            FakeProvider(script),
            cache_dir=tmp_path,
            run_id="r1",
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        first = run_pipeline(engine, config)
        assert first.apply_result["companies_updated"] == 1
        # 新 run（不 resume）：候选集为空（已补全），apply 零更新
        config2 = _config(
            engine,
            FakeProvider(script),
            cache_dir=tmp_path,
            run_id="r2",
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        second = run_pipeline(engine, config2)
        assert second.apply_result["companies_updated"] == 0
        stats = fetch_coverage_stats(engine)
        assert stats["missing"] == 0

    def test_apply_does_not_overwrite_existing_by_default(self, engine, tmp_path):
        """默认模式 SQL 带缺失条件：即使 provider 返回已覆盖代码也不覆盖。"""
        _seed(engine, ["000001.SZ", "600036.SH"])
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE companies SET industry_l1='银行', industry_source='research_report' "
                    "WHERE wind_code='600036.SH'"
                )
            )
        script = {
            "000001.SZ": ProviderResult(
                wind_code="000001.SZ",
                security_number="000001",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            ),
            "600036.SH": ProviderResult(
                wind_code="600036.SH",
                security_number="600036",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            ),
        }
        provider = FakeProvider(script)
        config = _config(
            engine,
            provider,
            cache_dir=tmp_path,
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        run_pipeline(engine, config)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT industry_l1 FROM companies WHERE wind_code='600036.SH'")
            ).fetchone()
        assert row[0] == "银行"  # 未被覆盖（candidate 本就不含已覆盖代码）

    def test_no_implicit_50_truncation(self, engine, tmp_path):
        codes = [f"{i:06d}.SZ" for i in range(60)]
        _seed(engine, codes)
        script = {
            code: ProviderResult(
                wind_code=code,
                security_number=code.split(".")[0],
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            )
            for code in codes
        }
        provider = FakeProvider(script)
        config = _config(engine, provider, cache_dir=tmp_path)  # 无 limit
        run_pipeline(engine, config)
        assert len(provider.queried) == 60  # 默认全量，不截断为 50

    def test_limit_controls_batch(self, engine, tmp_path):
        codes = [f"{i:06d}.SZ" for i in range(60)]
        _seed(engine, codes)
        provider = FakeProvider({})
        config = _config(engine, provider, cache_dir=tmp_path, limit=50)
        run_pipeline(engine, config)
        assert len(provider.queried) == 50

    def test_research_report_deterministic_fill(self, engine, tmp_path):
        _seed(engine, ["000001.SZ", "600519.SH"])
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO research_reports (wind_code, sec_name, industry_l1, sw_indu_code) "
                    "VALUES ('600519.SH', '贵州茅台', '食品饮料', '801124')"
                )
            )
        provider = FakeProvider({})  # 无脚本：600519 走研报路径，000001 EMPTY
        config = _config(
            engine,
            provider,
            cache_dir=tmp_path,
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        result = run_pipeline(engine, config)
        assert result.research_filled == 1
        stats = fetch_coverage_stats(engine)
        assert stats["companies_with_industry_before"] == 1
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT industry_source, sw_indu_code FROM companies WHERE wind_code='600519.SH'"
                )
            ).fetchone()
        assert (row[0], row[1]) == ("research_report", "801124")

    def test_resume_skips_success_cache(self, engine, tmp_path):
        codes = [f"{i:06d}.SZ" for i in range(5)]
        _seed(engine, codes)
        script = {
            code: ProviderResult(
                wind_code=code,
                security_number=code.split(".")[0],
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            )
            for code in codes
        }
        provider = FakeProvider(script)
        config = _config(engine, provider, cache_dir=tmp_path, run_id="run1")
        run_pipeline(engine, config)
        first_queries = list(provider.queried)

        provider2 = FakeProvider(script)
        config2 = _config(engine, provider2, cache_dir=tmp_path, run_id="run1")
        run_pipeline(engine, config2)
        assert provider2.queried == []  # 全部命中缓存
        assert len(first_queries) == 5

    def test_apply_blocked_when_gate_missing_record(self, engine, tmp_path):
        """审查整改 P1：任一输入代码缺 staging 记录，apply 前必须拒绝，库零变化。"""
        _seed(engine, ["000001.SZ", "600519.SH"])
        provider = OmittingProvider(
            {
                "000001.SZ": ProviderResult(
                    wind_code="000001.SZ",
                    security_number="000001",
                    query_status=QueryStatus.SUCCESS,
                    industry_l1="食品饮料",
                )
            },
            omit={"600519.SH"},
        )
        config = _config(
            engine,
            provider,
            cache_dir=tmp_path,
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        with pytest.raises(RuntimeError, match="质量门禁失败，拒绝 apply"):
            run_pipeline(engine, config)
        stats = fetch_coverage_stats(engine)
        # 行数与覆盖率完全不变（fail-closed：不允许任何行写入）
        assert stats["companies_total"] == 2
        assert stats["companies_with_industry_before"] == 0
        assert stats["missing"] == 2
        assert stats["nan_source_count"] == 2

    def test_invalid_industry_value_downgraded_to_unmapped_not_written(
        self, engine, tmp_path
    ):
        """非法行业值经 _persist 降级为 UNMAPPED（合法终态），apply 照常执行但不写入。

        口径说明（复核整改）：这不是"门禁拒绝 apply"——staging 门禁对 UNMAPPED 放行，
        整批 apply 执行、仅非法记录被排除出写入行；库行数与覆盖率不变。
        """
        _seed(engine, ["000001.SZ", "600519.SH"])
        script = {
            "000001.SZ": ProviderResult(
                wind_code="000001.SZ",
                security_number="000001",
                query_status=QueryStatus.SUCCESS,
                industry_l1="火星行业",  # 不在 31 申万一级允许集合
            ),
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.EMPTY,
            ),
        }
        provider = FakeProvider(script)
        config = _config(
            engine,
            provider,
            cache_dir=tmp_path,
            apply=True,
            mapping_csv_path=tmp_path / "industry_mapping.csv",
        )
        result = run_pipeline(engine, config)
        assert result.apply_result["companies_updated"] == 0
        assert result.report["akshare_unmapped"] == 1  # 降级为 UNMAPPED 而非写入
        stats = fetch_coverage_stats(engine)
        # 行数与覆盖率完全不变
        assert stats["companies_total"] == 2
        assert stats["companies_with_industry_before"] == 0
        assert stats["missing"] == 2
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT industry_l1, industry_l2, sw_indu_code, industry_source "
                    "FROM companies ORDER BY wind_code"
                )
            ).fetchall()
        # 行业三列零写入；industry_source 的 nan→NULL 是 apply 事务既定清洗（档案 §8）
        assert [(r[0], r[1], r[2]) for r in rows] == [
            (None, None, None),
            (None, None, None),
        ]
        assert [r[3] for r in rows] == [None, None]
