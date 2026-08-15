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
        def fake_direct(self, bare, **kwargs):
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
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "-"},
        )
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.EMPTY

    def test_unmapped(self, monkeypatch):
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "神秘未知行业"},
        )
        res = _provider()._query_one("000001.SZ", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.UNMAPPED
        assert res.industry_l2 == "神秘未知行业"

    def test_direct_failure_falls_back_to_akshare(self, monkeypatch, fake_ak):
        def fail_direct(self, bare, **kwargs):
            raise ConnectionError("reset")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fail_direct)
        fake_ak.per_stock["600519"] = {"股票简称": "贵州茅台", "行业": "白酒Ⅱ"}
        res = _provider()._query_one("600519.SH", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.provider_endpoint == "ak.stock_individual_info_em"

    def test_both_fail_error_status(self, monkeypatch, fake_ak):
        def fail_direct(self, bare, **kwargs):
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


class TestHostRotation:
    """P0 收口批次：限流换主机必须 continue，而非 data:null 立即抛错。"""

    def test_throttle_on_host_a_continues_to_host_b(self, monkeypatch):
        """主机 A data:null（限流）→ 继续主机 B 成功；throttled 置位。"""

        class _RespThrottled:
            text = '{"rc": 123, "data": null}'

        class _RespOk:
            text = '{"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}'

        class _SessionStub:
            def __init__(self, throttle_hosts):
                self.throttle_hosts = set(throttle_hosts)

            def get(self, url, **kwargs):
                host = url.split("/")[2]
                return _RespThrottled() if host in self.throttle_hosts else _RespOk()

        monkeypatch.setattr(
            AkShareProvider,
            "_session",
            lambda self: _SessionStub(["push2.eastmoney.com"]),
        )
        res = _provider()._query_one("600519.SH", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.industry_l1 == "食品饮料"
        assert res.provider_endpoint == "eastmoney.push2.direct"
        assert res.throttled is True  # 虽经他机恢复，仍记录限流供降并发

    def test_all_hosts_throttled_falls_back_to_akshare(self, monkeypatch, fake_ak):
        """全部主机限流 → akshare 兜底成功（限流不是 EMPTY，必须继续兜底）。"""

        class _Resp:
            text = '{"rc": 123, "data": null}'

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        fake_ak.per_stock["600519"] = {"股票简称": "贵州茅台", "行业": "白酒Ⅱ"}
        res = _provider()._query_one("600519.SH", max_retries=1, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.provider_endpoint == "ak.stock_individual_info_em"
        assert res.throttled is True

    def test_connection_error_on_host_a_continues_to_host_b(self, monkeypatch):
        """连接错误换主机（原有行为保持），且失败主机进入冷却计数。"""

        class _RespOk:
            text = '{"data": {"f57": "600519", "f58": "贵州茅台", "f127": "白酒Ⅱ"}}'

        class _SessionStub:
            def __init__(self):
                self.calls = 0

            def get(self, url, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("reset")
                return _RespOk()

        stub = _SessionStub()
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: stub)
        # max_retries=0：host A 首击即失败 → 继续 host B 成功
        res = _provider()._query_one("600519.SH", max_retries=0, backoff_seconds=0.01)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.throttled is False


class TestRetryThreading:
    """CLI --max-retries/--backoff-seconds 必须贯穿到请求层（不再硬编码）。"""

    def test_fetch_direct_threads_retry_config(self, monkeypatch):
        captured = {}

        def fake_call_with_retry(fn, *, max_retries, backoff_seconds):
            captured["max_retries"] = max_retries
            captured["backoff_seconds"] = backoff_seconds
            return None, 1, ConnectionError("fail")

        monkeypatch.setattr(akshare_provider, "call_with_retry", fake_call_with_retry)
        with pytest.raises(ConnectionError):
            _provider()._fetch_direct("600519", max_retries=5, backoff_seconds=2.5)
        assert captured["max_retries"] == 5
        assert captured["backoff_seconds"] == 2.5

    def test_query_one_threads_config_into_direct_and_fallback(self, monkeypatch):
        captured = {}

        def fail_direct(
            self,
            bare,
            *,
            max_retries,
            backoff_seconds,
            attempts=None,
            throttled_flag=None,
        ):
            captured["direct_max_retries"] = max_retries
            captured["direct_backoff"] = backoff_seconds
            raise ConnectionError("reset")

        def record_ak(self, bare, *, max_retries, backoff_seconds, attempts=None):
            captured["ak_max_retries"] = max_retries
            captured["ak_backoff"] = backoff_seconds
            return {"f58": "贵州茅台", "f127": "白酒Ⅱ"}

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fail_direct)
        monkeypatch.setattr(AkShareProvider, "_fetch_akshare", record_ak)
        res = _provider()._query_one("600519.SH", max_retries=7, backoff_seconds=3.0)
        assert res.query_status == QueryStatus.SUCCESS
        assert res.provider_endpoint == "ak.stock_individual_info_em"
        assert captured["direct_max_retries"] == 7
        assert captured["direct_backoff"] == 3.0
        assert captured["ak_max_retries"] == 7
        assert captured["ak_backoff"] == 3.0


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
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "白酒Ⅱ"},
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
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "白酒Ⅱ"},
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

    def test_query_many_reports_stats(self, monkeypatch):
        """运行统计：请求数、重试数、限流数、有效并发（报告 §6.4 键）。"""

        def fake_direct(self, bare, **kwargs):
            return {"f127": "白酒Ⅱ"}

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fake_direct)
        prov = _provider()
        prov.query_many(["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01)
        stats = prov.report_stats()
        assert stats["provider_requests"] == 2
        assert stats["provider_retries"] == 0
        assert stats["provider_throttles"] == 0
        assert stats["provider_fallbacks"] == 0
        assert 1 <= stats["effective_concurrency"] <= 8

    def test_throttle_lowers_effective_concurrency(self, monkeypatch):
        """连续限流触发降并发（有界自适应节流：不再无限重试打爆上游）。"""

        def fake_direct(self, bare, **kwargs):
            raise ConnectionError("reset")  # 全部失败 → ERROR → on_throttle

        def _no_ak(self):
            raise ModuleNotFoundError("akshare 未安装（确定性测试环境）")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fake_direct)
        monkeypatch.setattr(AkShareProvider, "_import_ak", _no_ak)
        prov = _provider()
        prov.query_many(
            [f"{i:06d}.SZ" for i in range(8)], max_retries=0, backoff_seconds=0.0
        )
        stats = prov.report_stats()
        # 8 次 ERROR → 并发减半（4→2→1，clamp 到 1）
        assert stats["effective_concurrency"] == 1
        assert stats["provider_requests"] == 8
        assert stats["provider_retries"] == 0

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
