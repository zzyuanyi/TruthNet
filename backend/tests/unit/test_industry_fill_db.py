"""db 访问层单元测试：compute_missing_codes 的非标准代码过滤（数据治理红线 #26）。"""

from __future__ import annotations

from backend.app.application.services.industry_fill.db import (
    _is_queryable,
    compute_missing_codes,
)


def _snap(code: str, l1: str | None) -> dict:
    return {"industry_l1": l1}


class TestIsQueryable:
    def test_standard_and_bare_codes_are_queryable(self):
        assert _is_queryable("600519.SH")
        assert _is_queryable("000001.SZ")
        assert _is_queryable("920088.BJ")
        assert _is_queryable("600519")  # 裸 6 位

    def test_a_prefix_and_garbage_codes_are_not_queryable(self):
        assert not _is_queryable("A04024.SZ")
        assert not _is_queryable("A20721.SH")
        assert not _is_queryable("DY18028E.SH")
        assert not _is_queryable("0000EA")
        assert not _is_queryable("00MTMT")
        assert not _is_queryable("")
        assert not _is_queryable("833243!1.BJ")  # 畸形码


class TestComputeMissingCodes:
    def test_only_queryable_missing_codes_enter_candidates(self):
        snapshot = {
            "600519.SH": _snap("600519.SH", None),  # 标准缺失 → 进入候选
            "000001.SZ": _snap("000001.SZ", "食品饮料"),  # 已有行业 → 不进
            "A04024.SZ": _snap("A04024.SZ", None),  # A 前缀退市 → 跳过
            "0000EA": _snap("0000EA", None),  # 垃圾码 → 跳过
        }
        missing, research = compute_missing_codes(snapshot, {})
        assert missing == ["600519.SH"]
        assert research == {}

    def test_report_map_fills_take_precedence_over_skip(self):
        # A 前缀码若研报已有行业，仍走研报确定性补全（不进入 provider 候选）
        snapshot = {
            "600519.SH": _snap("600519.SH", None),
            "A04024.SZ": _snap("A04024.SZ", None),
        }
        report_map = {"A04024.SZ": {"industry_l1": "食品饮料"}}
        missing, research = compute_missing_codes(snapshot, report_map)
        assert missing == ["600519.SH"]
        assert set(research) == {"A04024.SZ"}
