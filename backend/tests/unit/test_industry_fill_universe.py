"""当前 A 股范围快照与 eligibility 判定单元测试。"""

from __future__ import annotations

import pytest

from backend.app.application.services.industry_fill.universe import (
    bare_security_code,
    build_current_universe_snapshot,
    partition_missing_codes,
)


def _snapshot(rows):
    return build_current_universe_snapshot(
        rows,
        provider_version="test-1",
        retrieved_at="2026-08-21T00:00:00+00:00",
        min_size=1,
    )


def test_snapshot_normalizes_codes_and_has_stable_hash():
    first = _snapshot([(1, "平安银行"), ("600519", "贵州茅台")])
    second = _snapshot([("600519", "贵州茅台"), ("000001", "平安银行")])
    assert first.codes == frozenset({"000001", "600519"})
    assert first.sha256 == second.sha256


def test_snapshot_rejects_invalid_code_blank_name_and_conflict():
    with pytest.raises(RuntimeError, match="非法代码"):
        _snapshot([("A00001", "错误")])
    with pytest.raises(RuntimeError, match="简称为空"):
        _snapshot([("000001", "")])
    with pytest.raises(RuntimeError, match="简称冲突"):
        _snapshot([("000001", "甲"), ("000001", "乙")])


def test_snapshot_rejects_implausibly_small_response():
    with pytest.raises(RuntimeError, match="规模异常"):
        build_current_universe_snapshot(
            [("000001", "平安银行")], provider_version="test-1"
        )


def test_partition_queries_only_current_listings():
    snapshot = _snapshot([("000001", "平安银行"), ("920001", "北交样例")])
    eligible, not_current = partition_missing_codes(
        ["000001.SZ", "600001.SH", "920001.BJ", "A04024.SZ"], snapshot
    )
    assert eligible == ["000001.SZ", "920001.BJ"]
    assert not_current == ["600001.SH", "A04024.SZ"]


def test_bare_security_code_is_fail_closed():
    assert bare_security_code("600519.SH") == "600519"
    assert bare_security_code("600519") == "600519"
    assert bare_security_code("A04024.SZ") == ""
