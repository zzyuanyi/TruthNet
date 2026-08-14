"""validation 门禁单元测试（档案 v1.1 §9）。"""

from __future__ import annotations

from backend.app.application.services.industry_fill.constants import QueryStatus
from backend.app.application.services.industry_fill.provider import ProviderResult
from backend.app.application.services.industry_fill.validation import (
    check_dry_run_no_change,
    plan_apply_rows,
    validate_staging,
)


def _res(code: str, status: QueryStatus, l1: str | None = None) -> ProviderResult:
    return ProviderResult(
        wind_code=code,
        security_number=code.split(".")[0],
        query_status=status,
        industry_l1=l1,
    )


class TestValidateStaging:
    def test_ok(self):
        report = validate_staging(
            [
                _res("000001.SZ", QueryStatus.SUCCESS, "食品饮料"),
                _res("600519.SH", QueryStatus.EMPTY),
            ],
            ["000001.SZ", "600519.SH"],
        )
        assert report.ok

    def test_duplicate_input_fails(self):
        report = validate_staging(
            [_res("000001.SZ", QueryStatus.EMPTY)], ["000001.SZ", "000001.SZ"]
        )
        assert not report.ok
        assert any("重复" in p for p in report.problems)

    def test_missing_record_fails(self):
        report = validate_staging(
            [_res("000001.SZ", QueryStatus.EMPTY)], ["000001.SZ", "600519.SH"]
        )
        assert not report.ok
        assert any("600519.SH" in p for p in report.problems)

    def test_success_with_invalid_l1_fails(self):
        report = validate_staging(
            [_res("000001.SZ", QueryStatus.SUCCESS, "不是行业")], ["000001.SZ"]
        )
        assert not report.ok
        assert any("industry_l1 非法" in p for p in report.problems)

    def test_empty_unmapped_error_not_mixed_as_success(self):
        report = validate_staging(
            [_res("000001.SZ", QueryStatus.UNMAPPED, None)], ["000001.SZ"]
        )
        assert report.ok  # unmapped 是合法终态，不属于 success


class TestPlanApplyRows:
    def test_default_only_fills_missing(self):
        rows, overwrite = plan_apply_rows(
            [
                _res("000001.SZ", QueryStatus.SUCCESS, "食品饮料"),
                _res("600519.SH", QueryStatus.SUCCESS, "食品饮料"),
            ],
            {"000001.SZ": None, "600519.SH": "食品饮料"},
        )
        assert [r.wind_code for r in rows] == ["000001.SZ"]
        assert overwrite == 0

    def test_replace_allows_overwrite(self):
        rows, overwrite = plan_apply_rows(
            [_res("600519.SH", QueryStatus.SUCCESS, "食品饮料")],
            {"600519.SH": "食品饮料"},
            replace=True,
        )
        assert [r.wind_code for r in rows] == ["600519.SH"]
        assert overwrite == 1


class TestDryRunNoChange:
    def test_no_change_ok(self):
        before = {"companies_total": 10, "covered": 5, "missing": 5, "nan_source": 5}
        assert check_dry_run_no_change(before, dict(before)).ok

    def test_change_fails(self):
        before = {"companies_total": 10, "covered": 5, "missing": 5, "nan_source": 5}
        after = dict(before)
        after["covered"] = 6
        assert not check_dry_run_no_change(before, after).ok
