"""provider 重试策略与 AkShare 适配器单元测试（档案 v1.1 §5.1/§6.3）。

网络调用通过 monkeypatch _fetch_direct / _fetch_akshare 注入，不发真实请求。
"""

from __future__ import annotations

import sys

import pandas as pd
import pytest

from backend.app.application.services.industry_fill import akshare_provider
from backend.app.application.services.industry_fill.akshare_provider import (
    AkShareProvider,
)
from backend.app.application.services.industry_fill.constants import QueryStatus
from backend.app.application.services.industry_fill.provider import (
    ProviderResult,
    call_with_retry,
    is_retryable,
)


class _FakeAk:
    def __init__(self, per_stock: dict | None = None):
        self.per_stock = per_stock or {}

    def stock_individual_info_em(self, symbol: str):
        if symbol in self.per_stock:
            payload = self.per_stock[symbol]
            if isinstance(payload, Exception):
                raise payload
            return pd.DataFrame(
                {"item": list(payload), "value": list(payload.values())}
            )
        raise ValueError(f"no data for {symbol}")


@pytest.fixture()
def fake_ak(monkeypatch):
    fake = _FakeAk()
    monkeypatch.setitem(sys.modules, "akshare", fake)
    monkeypatch.setattr(akshare_provider, "DEFAULT_RATE_LIMIT_SLEEP", 0)
    return fake


def _provider() -> AkShareProvider:
    return AkShareProvider(
        mapping_version="sw-l2-to-l1-v1", dataset_version="official-2026-07-12"
    )


class TestIsRetryable:
    def test_timeout_connection_retryable(self):
        assert is_retryable(TimeoutError())
        assert is_retryable(ConnectionError())
        assert is_retryable(OSError())

    def test_value_error_not_retryable(self):
        assert not is_retryable(ValueError("bad"))

    def test_http_status_retryable(self):
        class _Resp:
            status_code = 429

        class _Exc(Exception):
            response = _Resp()

        assert is_retryable(_Exc())

        class _Resp5:
            status_code = 503

        class _Exc5(Exception):
            response = _Resp5()

        assert is_retryable(_Exc5())


class TestCallWithRetry:
    def test_retry_then_success(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError()
            return "ok"

        value, attempts, err = call_with_retry(fn, max_retries=3, backoff_seconds=0.01)
        assert value == "ok"
        assert attempts == 3
        assert err is None

    def test_non_retryable_stops_immediately(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise ValueError("parse error")

        value, attempts, err = call_with_retry(fn, max_retries=3, backoff_seconds=0.01)
        assert value is None
        assert attempts == 1
        assert isinstance(err, ValueError)


class TestQueryOneDirect:
    def test_success_via_direct(self, monkeypatch):
        def fake_direct(self, bare):
            assert bare == "600519"
            return {"f127": "白酒Ⅱ", "f58": "贵州茅台"}

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fake_direct)
        res = _provider()._query_one("600519.SH", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.industry_l1 == "食品饮料"
        assert res.industry_l2 == "白酒Ⅱ"
        assert res.provider_endpoint == "eastmoney.push2.direct"

    def test_empty_dash(self, monkeypatch):
        monkeypatch.setattr(
            AkShareProvider, "_fetch_direct", lambda self, bare: {"f127": "-"}
        )
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.EMPTY

    def test_unmapped(self, monkeypatch):
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare: {"f127": "神秘未知行业"},
        )
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.UNMAPPED
        assert res.industry_l2 == "神秘未知行业"

    def test_direct_failure_falls_back_to_akshare(self, monkeypatch, fake_ak):
        def fail_direct(self, bare):
            raise ConnectionError("reset")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fail_direct)
        fake_ak.per_stock["600519"] = {"股票简称": "贵州茅台", "行业": "白酒Ⅱ"}
        res = _provider()._query_one("600519.SH", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.provider_endpoint == "ak.stock_individual_info_em"

    def test_both_fail_error_status(self, monkeypatch, fake_ak):
        def fail_direct(self, bare):
            raise ConnectionError("reset")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fail_direct)
        fake_ak.per_stock["000001"] = ValueError("boom")
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.ERROR
        assert "ConnectionError" in (res.last_error or "")
        assert "ValueError" in (res.last_error or "")

    def test_throttled_response_is_error_not_empty(self, monkeypatch, fake_ak):
        """rc!=0 / data:null 是限流，必须分类为 error，禁止当作 EMPTY（防假空值）。"""

        class _Resp:
            text = '{"rc": 123, "data": null}'

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        fake_ak.per_stock["000001"] = ValueError("fallback also fails")
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.ERROR
        assert "限流" in (res.last_error or "")


class TestQueryMany:
    def test_cached_success_not_requeried(self, monkeypatch):
        cached = {
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.SUCCESS,
                industry_l1="食品饮料",
            )
        }

        def boom(self, bare):  # pragma: no cover - 若被调用说明缓存失效
            raise AssertionError("不应查询")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", boom)
        results = _provider().query_many(
            ["600519.SH"], cached=cached, max_retries=1, backoff_seconds=0.01
        )
        assert results[0].query_status == QueryStatus.SUCCESS

    def test_retry_empty_flag_requeries(self, monkeypatch):
        cached = {
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.EMPTY,
            )
        }
        monkeypatch.setattr(
            AkShareProvider, "_fetch_direct", lambda self, bare: {"f127": "白酒Ⅱ"}
        )
        results = _provider().query_many(
            ["600519.SH"],
            cached=cached,
            retry_empty=True,
            max_retries=1,
            backoff_seconds=0.01,
        )
        assert results[0].query_status == QueryStatus.SUCCESS

    def test_cached_error_requeried_without_flag(self, monkeypatch):
        """档案 §6.1：error 允许按重试策略继续——缓存 error 默认重查。"""
        cached = {
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.ERROR,
                last_error="timeout",
            )
        }
        monkeypatch.setattr(
            AkShareProvider, "_fetch_direct", lambda self, bare: {"f127": "白酒Ⅱ"}
        )
        results = _provider().query_many(
            ["600519.SH"],
            cached=cached,
            max_retries=1,
            backoff_seconds=0.01,
        )
        assert results[0].query_status == QueryStatus.SUCCESS

    def test_cached_unmapped_not_requeried(self, monkeypatch):
        cached = {
            "600519.SH": ProviderResult(
                wind_code="600519.SH",
                security_number="600519",
                query_status=QueryStatus.UNMAPPED,
            )
        }

        def boom(self, bare):  # pragma: no cover - 若被调用说明策略错误
            raise AssertionError("unmapped 不应重查")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", boom)
        results = _provider().query_many(
            ["600519.SH"], cached=cached, max_retries=1, backoff_seconds=0.01
        )
        assert results[0].query_status == QueryStatus.UNMAPPED

    def test_probe_reports_batch_unavailable(self, monkeypatch):
        class _Resp:
            text = '{"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}'

            def json(self):
                return {"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        class _FakeAkWithoutBatch:
            """akshare 已安装但 stock_info_shenwan_industry 批量接口不可用的场景。"""

        monkeypatch.setattr(akshare_provider, "_PUSH2_HOSTS", ["example.invalid"])
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        # 确定性环境：模拟 akshare 已安装（与 CI 未安装 akshare 解耦），
        # 断言批量不可用诊断仍带"禁止猜测口径"契约。
        monkeypatch.setattr(akshare_provider, "akshare_version", lambda: "1.18.91")
        monkeypatch.setattr(
            AkShareProvider, "_import_ak", lambda self: _FakeAkWithoutBatch()
        )
        info = _provider().probe()
        assert "eastmoney.push2.direct" in info["endpoints"]
        assert any("禁止猜测口径" in n for n in info["notes"])
        assert info["akshare_version"] is not None

    def test_probe_reports_batch_unavailable_without_akshare(self, monkeypatch):
        """akshare 未安装（CI 环境）：批量不可用诊断仍须含禁止猜测口径契约，且给出回退提示。"""

        class _Resp:
            text = '{"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}'

            def json(self):
                return {"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(akshare_provider, "_PUSH2_HOSTS", ["example.invalid"])
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        monkeypatch.setattr(akshare_provider, "akshare_version", lambda: None)
        info = _provider().probe()
        assert "eastmoney.push2.direct" in info["endpoints"]
        assert any("禁止猜测口径" in n for n in info["notes"])
        assert any("akshare 未安装" in n for n in info["notes"])
        assert info["akshare_version"] is None
