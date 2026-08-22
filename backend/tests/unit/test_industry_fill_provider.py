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
    _eastmoney_secid,
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


def test_eastmoney_secid_distinguishes_bse_from_shanghai_b_share():
    assert _eastmoney_secid("920006") == "0.920006"
    assert _eastmoney_secid("600519") == "1.600519"
    assert _eastmoney_secid("900901") == "1.900901"
    assert _eastmoney_secid("000001") == "0.000001"


def _batch_empty(self, bares, **kwargs):
    """模拟真实 _fetch_batch 的统计记账：返回空 + 计入请求/批量统计。

    query_many 测试用：真实 _fetch_batch 内部会 _stat_inc("requests") 并累加
    batch_requests；monkeypatch 版必须同样记账，否则 provider_requests 断言失真。
    """
    self._stat_inc("requests")
    with self._stats_lock:
        self._stats["batch_requests"] = self._stats.get("batch_requests", 0) + 1
    return {}


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
    def test_bse_direct_uses_market_zero(self, monkeypatch):
        captured: dict = {}

        class _Resp:
            text = (
                '{"rc":0,"data":{"f57":"920006","f58":"晟楠科技","f127":"航空装备Ⅱ"}}'
            )

        class _SessionStub:
            def get(self, *args, **kwargs):
                captured.update(kwargs["params"])
                return _Resp()

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        result = _provider()._fetch_direct("920006", max_retries=0, backoff_seconds=0)

        assert captured["secid"] == "0.920006"
        assert result["f127"] == "航空装备Ⅱ"

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

    def test_persistent_throttle_host_enters_cooldown_across_queries(
        self, monkeypatch, fake_ak
    ):
        """对抗审查 A 回归：data:null 连续 3 次必须累积进冷却。

        旧代码 host_ok 先于 data:null 判断执行，把失败计数清零后 host_failed 再加 1，
        计数恒为 1，冷却永不触发（限流主机被持续敲打）。修复后应累积到阈值进冷却。
        """

        class _Resp:
            text = '{"rc": 123, "data": null}'

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        fake_ak.per_stock["000001"] = ValueError("fallback also fails")
        prov = _provider()
        for _ in range(3):
            prov._query_one("000001.SZ", max_retries=0, backoff_seconds=0.0)
        # 每次 data:null → host_failed（不再被 host_ok 清零），3 次后进入冷却
        assert not prov._controller.host_allowed("push2.eastmoney.com")
        assert not prov._controller.host_allowed("82.push2.eastmoney.com")
        assert not prov._controller.host_allowed("push2delay.eastmoney.com")


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
    def test_each_fallback_result_is_persisted_before_next_query(self, monkeypatch):
        """中途失败时，已完成代码必须已写 staging，不能等全批结束才回调。"""
        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)
        events: list[str] = []

        def fake_query_one(self, code, **kwargs):
            events.append(f"query:{code}")
            if code == "000002.SZ":
                raise RuntimeError("模拟第二码意外中断")
            return ProviderResult(
                wind_code=code,
                security_number=code.split(".")[0],
                query_status=QueryStatus.SUCCESS,
                industry_l1="银行",
            )

        monkeypatch.setattr(AkShareProvider, "_query_one", fake_query_one)

        with pytest.raises(RuntimeError, match="模拟第二码意外中断"):
            _provider().query_many(
                ["000001.SZ", "000002.SZ"],
                max_retries=0,
                backoff_seconds=0,
                concurrency=1,
                on_result=lambda result: events.append(f"persist:{result.wind_code}"),
            )

        assert events == [
            "query:000001.SZ",
            "persist:000001.SZ",
            "query:000002.SZ",
        ]

    def test_batch_result_callback_is_not_emitted_twice(self, monkeypatch):
        def batch_ok(self, bares, **kwargs):
            return {"600519": {"f100": "白酒Ⅱ", "f14": "贵州茅台"}}

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", batch_ok)
        persisted: list[str] = []
        results = _provider().query_many(
            ["600519.SH"],
            max_retries=0,
            backoff_seconds=0,
            on_result=lambda result: persisted.append(result.wind_code),
        )

        assert results[0].wind_code == "600519.SH"
        assert persisted == ["600519.SH"]

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
        # 批量主路径：批量未覆盖 → 逐股回退（走 _fetch_direct 假实现）
        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)
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
        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)
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
        """运行统计：请求数、重试数、限流数、批量/回退、有效并发（报告 §6.4 键）。"""
        # 批量主路径：批量返回空 → 2 码逐股回退。请求数 = 1 批量 + 2 逐股 = 3。
        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)

        def fake_direct(self, bare, **kwargs):
            return {"f127": "白酒Ⅱ"}

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", fake_direct)
        prov = _provider()
        prov.query_many(["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01)
        stats = prov.report_stats()
        assert stats["provider_requests"] == 3
        assert stats["provider_batch_requests"] == 1
        assert stats["provider_batch_misses"] == 2
        assert stats["provider_retries"] == 0
        assert stats["provider_throttles"] == 0
        assert stats["provider_fallbacks"] == 0
        assert 1 <= stats["effective_concurrency"] <= 8

    def test_throttle_lowers_effective_concurrency(self, monkeypatch):
        """连续限流触发降并发（有界自适应节流：不再无限重试打爆上游）。"""
        # 批量主路径：批量返回空 → 8 码逐股回退全部 ERROR。
        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)

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
        # 批量 1 次 on_success（容量不变）+ 8 次 ERROR → 并发减半（4→2→1，clamp 到 1）
        assert stats["effective_concurrency"] == 1
        assert stats["provider_requests"] == 9  # 1 批量 + 8 逐股
        assert stats["provider_batch_requests"] == 1
        assert stats["provider_batch_misses"] == 8
        assert stats["provider_retries"] == 0

    def test_probe_reports_batch_calibrated(self, monkeypatch):
        """probe 报告：push2 批量已认证启用（endpoint 存在 + 禁止猜测口径契约）。"""

        # 批量接口真实响应形状：data.diff 列表（f12/f14/f100），非逐股 f57/f58/f127
        _BATCH_PAYLOAD = (
            '{"rc": 0, "data": {"diff": ['
            '{"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"}, '
            '{"f12": "000001", "f14": "平安银行", "f100": "银行"}]}}'
        )

        class _Resp:
            text = _BATCH_PAYLOAD

            def json(self):
                return {
                    "rc": 0,
                    "data": {
                        "diff": [
                            {"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"},
                            {"f12": "000001", "f14": "平安银行", "f100": "银行"},
                        ]
                    },
                }

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        class _FakeAkWithoutBatch:
            """akshare 已安装但 stock_info_shenwan_industry 批量接口不可用的场景。"""

        monkeypatch.setattr(akshare_provider, "_PUSH2_HOSTS", ["example.invalid"])
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        # 确定性环境：模拟 akshare 已安装（与 CI 未安装 akshare 解耦）
        monkeypatch.setattr(akshare_provider, "akshare_version", lambda: "1.18.91")
        monkeypatch.setattr(
            AkShareProvider, "_import_ak", lambda self: _FakeAkWithoutBatch()
        )
        info = _provider().probe()
        assert "eastmoney.push2.batch" in info["endpoints"]
        assert "eastmoney.push2.direct" in info["endpoints"]
        assert any("禁止猜测口径" in n for n in info["notes"])
        assert any("批量主路径" in n for n in info["notes"])
        assert info["akshare_version"] is not None

    def test_probe_reports_batch_calibrated_without_akshare(self, monkeypatch):
        """akshare 未安装（CI 环境）：批量已认证 + 禁止猜测口径契约 + 回退提示。"""

        # 批量接口真实响应形状：data.diff 列表（f12/f14/f100）
        _BATCH_PAYLOAD = (
            '{"rc": 0, "data": {"diff": ['
            '{"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"}, '
            '{"f12": "000001", "f14": "平安银行", "f100": "银行"}]}}'
        )

        class _Resp:
            text = _BATCH_PAYLOAD

            def json(self):
                return {
                    "rc": 0,
                    "data": {
                        "diff": [
                            {"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"},
                            {"f12": "000001", "f14": "平安银行", "f100": "银行"},
                        ]
                    },
                }

        class _SessionStub:
            def get(self, *a, **k):
                return _Resp()

        monkeypatch.setattr(akshare_provider, "_PUSH2_HOSTS", ["example.invalid"])
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        monkeypatch.setattr(akshare_provider, "akshare_version", lambda: None)
        info = _provider().probe()
        assert "eastmoney.push2.batch" in info["endpoints"]
        assert "eastmoney.push2.direct" in info["endpoints"]
        assert any("禁止猜测口径" in n for n in info["notes"])
        assert any("akshare 未安装" in n for n in info["notes"])
        assert info["akshare_version"] is None


class TestBatchPrimary:
    """档案 §6 收口批次：push2 批量（f100）主路径，批量未覆盖逐股回退。"""

    def test_batch_primary_fills_codes(self, monkeypatch):
        """批量覆盖全部 → 全部走批量 endpoint，不触发逐股。"""

        def fake_batch(self, bares, **kwargs):
            return {"600519": "白酒Ⅱ", "000001": "银行"}

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", fake_batch)

        def boom(self, bare):  # pragma: no cover - 批量已覆盖不应走逐股
            raise AssertionError("批量已覆盖，不应逐股查询")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", boom)
        results = _provider().query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert [r.query_status for r in results] == [
            QueryStatus.SUCCESS,
            QueryStatus.SUCCESS,
        ]
        assert all(r.provider_endpoint == "eastmoney.push2.batch" for r in results)
        assert results[0].industry_l1 == "食品饮料"  # 白酒Ⅱ → 食品饮料
        assert results[1].industry_l1 == "银行"  # 银行 → 银行

    def test_bse_batch_uses_market_zero(self, monkeypatch):
        captured: dict = {}

        class _Resp:
            text = (
                '{"rc":0,"data":{"diff":['
                '{"f12":"920006","f14":"晟楠科技","f100":"航空装备Ⅱ"}'
                "]}}"
            )

        class _SessionStub:
            def get(self, *args, **kwargs):
                captured.update(kwargs["params"])
                return _Resp()

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        result = _provider()._fetch_batch(["920006"], max_retries=0, backoff_seconds=0)

        assert captured["secids"] == "0.920006"
        assert result == {"920006": "航空装备Ⅱ"}

    def test_batch_miss_falls_back_to_per_stock(self, monkeypatch):
        """批量只覆盖部分 → 未覆盖代码逐股 f127 回退（同源确定性口径）。"""

        def fake_batch(self, bares, **kwargs):
            return {"600519": "白酒Ⅱ"}

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", fake_batch)
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "银行"},
        )
        prov = _provider()
        results = prov.query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert results[0].query_status == QueryStatus.SUCCESS
        assert results[0].provider_endpoint == "eastmoney.push2.batch"
        assert results[1].query_status == QueryStatus.SUCCESS
        assert results[1].provider_endpoint == "eastmoney.push2.direct"
        assert prov.report_stats()["provider_batch_misses"] == 1

    def test_batch_exception_falls_back_entire_chunk(self, monkeypatch):
        """整块批量失败（全部主机失败）→ 整块退回逐股。"""

        def fail_batch(self, bares, **kwargs):
            raise ConnectionError("push2 批量全部主机失败")

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", fail_batch)
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "白酒Ⅱ"},
        )
        prov = _provider()
        results = prov.query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert [r.query_status for r in results] == [
            QueryStatus.SUCCESS,
            QueryStatus.SUCCESS,
        ]
        assert all(r.provider_endpoint == "eastmoney.push2.direct" for r in results)
        assert prov.report_stats()["provider_batch_misses"] == 2

    def test_batch_miss_with_concurrency_1_caps_recovery(self, monkeypatch):
        """对抗审查 B：concurrency=1 → 恢复上限也被钳到 1，稳定成功不会爬到 8。"""

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", _batch_empty)
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "白酒Ⅱ"},
        )
        prov = _provider()
        prov.query_many(
            ["600519.SH", "000001.SZ", "300750.SZ"],
            max_retries=1,
            backoff_seconds=0.01,
            concurrency=1,
        )
        # set_capacity 已把 _max_capacity 钳到 1，on_success 恢复不会越过用户设定
        assert prov._controller.capacity == 1


class _PayloadResp:
    def __init__(self, text: str):
        self.text = text


class _RotatingSession:
    """按 host 返回不同 payload 的会话桩，并记录请求顺序（测试真实解析路径）。"""

    def __init__(self, payload_by_host: dict[str, str]):
        self.payload_by_host = payload_by_host
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        host = url.split("/")[2]
        self.calls.append(host)
        return _PayloadResp(self.payload_by_host[host])


class TestSessionContract:
    def test_session_disables_trust_env(self):
        """对抗审查 H1：直连东财必须绕过 Windows 系统代理（trust_env=False）。"""
        assert _provider()._session().trust_env is False


class TestDegradedResponseRotation:
    """对抗审查 H2：rc!=0 / 空 diff / 缺 diff 键的降级响应必须换主机，不能被记成成功。"""

    def _stub(self, monkeypatch, payload_by_host):
        stub = _RotatingSession(payload_by_host)
        monkeypatch.setattr(AkShareProvider, "_session", lambda self: stub)
        return stub

    def test_fetch_direct_rc_nonzero_rotates_host(self, monkeypatch):
        hosts = akshare_provider._PUSH2_HOSTS
        stub = self._stub(
            monkeypatch,
            {
                hosts[0]: '{"rc": -1, "data": {"f57": "600519"}}',
                hosts[1]: '{"rc": 0, "data": {"f57": "600519", "f127": "白酒Ⅱ"}}',
            },
        )
        prov = _provider()
        data = prov._fetch_direct("600519", max_retries=0, backoff_seconds=0.0)
        assert data["f127"] == "白酒Ⅱ"
        assert stub.calls == [hosts[0], hosts[1]]  # rc!=0 → 换到第二主机
        assert prov.report_stats()["provider_throttles"] == 1
        assert prov._controller._host_failures[hosts[0]] == 1

    def test_fetch_direct_all_hosts_rc_nonzero_raises(self, monkeypatch):
        hosts = akshare_provider._PUSH2_HOSTS
        stub = self._stub(
            monkeypatch, {h: '{"rc": -1, "data": {"f57": "600519"}}' for h in hosts}
        )
        prov = _provider()
        with pytest.raises(akshare_provider._Push2Throttled):
            prov._fetch_direct("600519", max_retries=0, backoff_seconds=0.0)
        assert len(stub.calls) == len(hosts)
        assert prov.report_stats()["provider_throttles"] == len(hosts)

    def test_fetch_batch_empty_diff_rotates_host(self, monkeypatch):
        hosts = akshare_provider._PUSH2_HOSTS
        valid = (
            '{"rc": 0, "data": {"diff": ['
            '{"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"}]}}'
        )
        stub = self._stub(
            monkeypatch,
            {
                hosts[0]: '{"rc": 0, "data": {"diff": []}}',  # 空 diff → 降级
                hosts[1]: valid,
            },
        )
        prov = _provider()
        out = prov._fetch_batch(
            ["600519", "000001"], max_retries=0, backoff_seconds=0.0
        )
        assert out == {"600519": "白酒Ⅱ"}
        assert stub.calls == [hosts[0], hosts[1]]  # 空 diff → 换到第二主机
        assert prov.report_stats()["provider_throttles"] == 1
        assert prov._controller._host_failures[hosts[0]] == 1

    def test_fetch_batch_data_without_diff_key_rotates(self, monkeypatch):
        hosts = akshare_provider._PUSH2_HOSTS
        valid = (
            '{"rc": 0, "data": {"diff": ['
            '{"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"}]}}'
        )
        stub = self._stub(
            monkeypatch,
            {
                hosts[0]: '{"rc": 0, "data": {"f12": "600519"}}',  # 缺 diff 键 → 降级
                hosts[1]: valid,
            },
        )
        prov = _provider()
        out = prov._fetch_batch(
            ["600519", "000001"], max_retries=0, backoff_seconds=0.0
        )
        assert out == {"600519": "白酒Ⅱ"}
        assert stub.calls == [hosts[0], hosts[1]]
        assert prov.report_stats()["provider_throttles"] == 1

    def test_fetch_batch_rc_nonzero_with_data_rotates(self, monkeypatch):
        """rc!=0 但 data 非空（对抗审查 H2）也必须判限流。"""
        hosts = akshare_provider._PUSH2_HOSTS
        valid = (
            '{"rc": 0, "data": {"diff": ['
            '{"f12": "600519", "f14": "贵州茅台", "f100": "白酒Ⅱ"}]}}'
        )
        stub = self._stub(
            monkeypatch,
            {
                hosts[0]: '{"rc": 123, "data": {"diff": ['
                '{"f12": "600519", "f100": "白酒Ⅱ"}]}}',
                hosts[1]: valid,
            },
        )
        prov = _provider()
        out = prov._fetch_batch(
            ["600519", "000001"], max_retries=0, backoff_seconds=0.0
        )
        assert out == {"600519": "白酒Ⅱ"}
        assert stub.calls == [hosts[0], hosts[1]]
        assert prov.report_stats()["provider_throttles"] == 1

    def test_fetch_batch_all_hosts_empty_diff_raises(self, monkeypatch):
        hosts = akshare_provider._PUSH2_HOSTS
        stub = self._stub(
            monkeypatch, {h: '{"rc": 0, "data": {"diff": []}}' for h in hosts}
        )
        prov = _provider()
        with pytest.raises(akshare_provider._Push2Throttled):
            prov._fetch_batch(["600519"], max_retries=0, backoff_seconds=0.0)
        assert len(stub.calls) == len(hosts)
        assert prov.report_stats()["provider_throttles"] == len(hosts)


class TestAllHostsCooldownFailFast:
    """对抗审查 H7：全部主机冷却时 fail-fast（不重锤冷却窗口内的主机）。"""

    def _cool_all(self, prov):
        for h in akshare_provider._PUSH2_HOSTS:
            for _ in range(3):
                prov._controller.host_failed(h)

    def test_fetch_direct_all_cooled_skips_requests(self, monkeypatch):
        calls = {"n": 0}

        class _SessionStub:
            def get(self, *a, **k):
                calls["n"] += 1
                raise AssertionError("冷却中不应发请求")

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        prov = _provider()
        self._cool_all(prov)
        with pytest.raises(akshare_provider._Push2Throttled):
            prov._fetch_direct("600519", max_retries=0, backoff_seconds=0.0)
        assert calls["n"] == 0

    def test_fetch_batch_all_cooled_skips_requests(self, monkeypatch):
        calls = {"n": 0}

        class _SessionStub:
            def get(self, *a, **k):
                calls["n"] += 1
                raise AssertionError("冷却中不应发请求")

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        prov = _provider()
        self._cool_all(prov)
        with pytest.raises(akshare_provider._Push2Throttled):
            prov._fetch_batch(["600519"], max_retries=0, backoff_seconds=0.0)
        assert calls["n"] == 0


class TestBatchThrottleAndCircuit:
    """Task C C4/C5/C7：批量限流不转逐股（防风暴）+ 批量熔断 fail-fast + 统计。

    mock HTTP（monkeypatch _session / _fetch_batch），不发真实请求。
    """

    # ── C5 限流分类：_Push2Throttled → 整块 throttled，不转逐股 ──────────
    def test_batch_throttled_no_fanout_to_per_stock(self, monkeypatch):
        """批量限流失败 → 整块 ERROR(throttled)，零逐股（风暴根因修复）。"""

        def throttle_batch(self, bares, **kwargs):
            self._stat_inc("requests")
            with self._stats_lock:
                self._stats["batch_requests"] = self._stats.get("batch_requests", 0) + 1
            raise akshare_provider._Push2Throttled("push2 批量限流")

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", throttle_batch)

        def boom(self, bare, **kwargs):  # pragma: no cover - 限流不得转逐股
            raise AssertionError("限流时不得转逐股（1 个批量不得放大成 N 个逐股）")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", boom)
        prov = _provider()
        results = prov.query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert [r.query_status for r in results] == [
            QueryStatus.ERROR,
            QueryStatus.ERROR,
        ]
        assert all(r.throttled for r in results)
        assert all(r.provider_endpoint == "eastmoney.push2.batch" for r in results)
        stats = prov.report_stats()
        assert stats["provider_batch_throttled"] == 1
        assert stats["provider_batch_misses"] == 0
        assert stats["provider_fallbacks"] == 0

    def test_batch_throttled_flag_on_success_does_not_fanout_all(self, monkeypatch):
        """批量成功但块内个别 miss → 仅 miss 转逐股（限流 flag 不放大整块）。"""

        # 与旧行为一致：批量成功返回部分覆盖，未覆盖代码走逐股（合法 miss）
        def fake_batch(self, bares, **kwargs):
            return {"600519": "白酒Ⅱ"}

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", fake_batch)
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "银行"},
        )
        prov = _provider()
        results = prov.query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert results[0].provider_endpoint == "eastmoney.push2.batch"
        assert results[1].provider_endpoint == "eastmoney.push2.direct"
        assert prov.report_stats()["provider_batch_misses"] == 1

    def test_batch_connection_error_still_falls_back_to_per_stock(self, monkeypatch):
        """连接/网络失败（非限流）→ 整块转逐股（换源恢复合理，非风暴）。"""
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_batch",
            lambda self, bares, **kwargs: (_ for _ in ()).throw(
                ConnectionError("push2 批量全部主机失败")
            ),
        )
        monkeypatch.setattr(
            AkShareProvider,
            "_fetch_direct",
            lambda self, bare, **kwargs: {"f127": "白酒Ⅱ"},
        )
        prov = _provider()
        results = prov.query_many(
            ["600519.SH", "000001.SZ"], max_retries=1, backoff_seconds=0.01
        )
        assert [r.query_status for r in results] == [
            QueryStatus.SUCCESS,
            QueryStatus.SUCCESS,
        ]
        assert all(r.provider_endpoint == "eastmoney.push2.direct" for r in results)
        assert prov.report_stats()["provider_batch_throttled"] == 0

    # ── C11 resume 恢复语义：ERROR(throttled) 重查 → 收敛 ─────────────────
    def test_resume_recovery_loop_throttled_error(self, monkeypatch):
        """C11 恢复语义（--resume 重算收敛）：
        Phase1 批量限流 → 整块 ERROR(throttled) 零逐股；
        Phase2 以该批为 cached 再 resume（仍限流）→ 保持 ERROR(throttled)
          且零逐股（风暴根因不复发）；
        Phase3 上游恢复 → 收敛为 SUCCESS。
        cached_skip 对 ERROR 不跳过（档案 §6.1 重试契约），与熔断计数
        （跨 query_many 不重置）共同保证"限流风暴后可安全恢复"。"""
        state = {"call": 0}

        def flaky_batch(self, bares, **kwargs):
            self._stat_inc("requests")
            with self._stats_lock:
                self._stats["batch_requests"] = self._stats.get("batch_requests", 0) + 1
            state["call"] += 1
            if state["call"] in (1, 2):
                raise akshare_provider._Push2Throttled("push2 批量限流")
            return {"600519": "白酒Ⅱ", "000001": "银行"}

        monkeypatch.setattr(AkShareProvider, "_fetch_batch", flaky_batch)

        def boom(self, bare, **kwargs):  # pragma: no cover - 限流不得转逐股
            raise AssertionError("限流路径不得转逐股（1 个批量不得放大成 N 个逐股）")

        monkeypatch.setattr(AkShareProvider, "_fetch_direct", boom)
        prov = _provider()
        codes = ["600519.SH", "000001.SZ"]

        # Phase 1：批量限流 → 整块 ERROR(throttled)，零逐股
        r1 = prov.query_many(codes, max_retries=1, backoff_seconds=0.01)
        assert [r.query_status for r in r1] == [
            QueryStatus.ERROR,
            QueryStatus.ERROR,
        ]
        assert all(r.throttled for r in r1)
        assert prov.report_stats()["provider_batch_throttled"] == 1
        assert prov.report_stats()["provider_fallbacks"] == 0

        # Phase 2（--resume）：cached 为 Phase1 的 ERROR(throttled)，仍限流
        r2 = prov.query_many(
            codes,
            cached={c: r for c, r in zip(codes, r1)},
            max_retries=1,
            backoff_seconds=0.01,
        )
        assert [r.query_status for r in r2] == [
            QueryStatus.ERROR,
            QueryStatus.ERROR,
        ]
        assert all(r.throttled for r in r2)
        # 每 run 统计独立（_stats_reset），本 run 仍计 1 次批量限流
        assert prov.report_stats()["provider_batch_throttled"] == 1
        assert prov.report_stats()["provider_fallbacks"] == 0

        # Phase 3（上游恢复）：再 resume → 收敛为 SUCCESS（cached error 重查契约）
        r3 = prov.query_many(
            codes,
            cached={c: r for c, r in zip(codes, r1)},
            max_retries=1,
            backoff_seconds=0.01,
        )
        assert [r.query_status for r in r3] == [
            QueryStatus.SUCCESS,
            QueryStatus.SUCCESS,
        ]
        assert prov.report_stats()["provider_batch_throttled"] == 0
        assert prov.report_stats()["provider_batch_circuit_opens"] == 0

    # ── C4 批量熔断：连续失败 → 打开 → fail-fast 零网络 → half-open 恢复 ──
    def test_circuit_opens_and_fail_fast_zero_network(self, monkeypatch):
        """真实 _fetch_batch 路径：连续 3 次批量限流 → 熔断打开；
        后续 chunk fail-fast，不发任何网络请求（请求计数冻结）。"""
        calls = {"n": 0}

        class _SessionStub:
            def get(self, *a, **k):
                calls["n"] += 1
                return _PayloadResp('{"rc": -1, "data": null}')

        monkeypatch.setattr(AkShareProvider, "_session", lambda self: _SessionStub())
        prov = _provider()
        codes = [f"6005{i:02d}.SH" for i in range(190)]  # 4 chunks（3×60 → 熔断）
        prov.query_many(codes, max_retries=0, backoff_seconds=0.0, concurrency=2)
        # 前 3 chunk × 3 主机 = 9 次请求；第 4 chunk 熔断 fail-fast 零网络
        assert prov._batch_open_until > 0
        assert calls["n"] == 9
        stats = prov.report_stats()
        assert stats["provider_batch_circuit_opens"] == 1
        assert stats["provider_batch_circuit_failfast"] == 1

    def test_circuit_state_machine(self):
        """白盒：3 次失败打开；打开期间 fail-fast；成功清零；冷却后恢复。"""
        prov = _provider()
        prov._record_batch_failure()
        prov._record_batch_failure()
        assert not prov._batch_circuit_fail_fast()  # 未达阈值，不 fail-fast
        prov._record_batch_failure()  # 第 3 次 → 打开
        assert prov._batch_open_until > 0
        assert prov._batch_circuit_fail_fast()  # 打开期间 fail-fast
        assert prov.report_stats()["provider_batch_circuit_opens"] == 1
        # 冷却后半开：重新允许一次尝试
        prov._batch_open_until = 0.0
        assert not prov._batch_circuit_fail_fast()
        # 失败后成功 → 计数归零、熔断关闭
        prov._record_batch_failure()
        prov._record_batch_success()
        assert prov._batch_failures == 0
        assert prov._batch_open_until == 0.0

    # ── C7 统计可诊断 ──────────────────────────────────────
    def test_report_stats_includes_throttle_diagnostics(self):
        stats = _provider().report_stats()
        for key in (
            "provider_batch_throttled",
            "provider_batch_circuit_opens",
            "provider_batch_circuit_failfast",
        ):
            assert key in stats
            assert stats[key] == 0
