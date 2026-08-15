"""AkShare provider 适配器（档案 v1.1 §5.1，口径以 2026-08-14 实测为准）。

实测探测结论（akshare 1.18.91，记录于 probe 报告）：
  1. `stock_info_shenwan_industry` 在当前版本不存在（AttributeError）——
     DATA_CHECKLIST 6.2 的引用已失效；
  2. `stock_industry_clf_hist_sw` 可用，但其 industry_code 体系（如 480301）
     无法与 sw_index_* 的 801xxx 指数代码稳定关联，按档案 §5.1"禁止猜测口径"
     不采用批量路径 [待人工口径确认后重新评估]；
  3. 东财 push2 直连可用且实测返回申万二级风格名称（600519 → 行业="白酒Ⅱ"）；
  4. 因此正式路径 = 逐股查询（档案允许的回退），首选东财 push2 直连
     （少一层 akshare 封装），akshare 包装为兜底；任何返回值先过
     normalizer（二级→一级映射 + 允许集合校验），不能映射进 unmapped。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from backend.app.application.services.industry_fill.constants import (
    DEFAULT_RATE_LIMIT_SLEEP,
    PROVIDER_AKSHARE,
    QueryStatus,
)
from backend.app.application.services.industry_fill.normalizer import (
    map_l2_to_l1,
)
from backend.app.application.services.industry_fill.provider import (
    ProgressCounter,
    ProviderResult,
    call_with_retry,
    raw_value_hash,
)

log = logging.getLogger(__name__)

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"
# 东财行情主机轮换：主站可能瞬时重置（RemoteDisconnected），按序回退镜像。
# 2026-08-14 实测：push2/82.push2 曾可用后转入重置，push2delay 稳定返回 f127。
_PUSH2_HOSTS = [
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "push2delay.eastmoney.com",
]
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 批量接口不可用原因（实测口径记录，随 probe 报告输出）
_BATCH_UNAVAILABLE_REASON = (
    "stock_info_shenwan_industry 在 akshare 1.18.91 不存在；"
    "stock_industry_clf_hist_sw 行业代码体系无法与申万 801xxx 指数代码"
    "稳定关联，禁止猜测口径（档案 §5.1）——回退逐股查询"
)


class _Push2Throttled(OSError):
    """push2 限流/空 data 响应（rc!=0 或 data:null）——可重试异常，禁止当作 EMPTY。"""


def akshare_version() -> str | None:
    """已安装的 akshare 版本；未安装返回 None（不抛异常）。"""
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("akshare")
    except PackageNotFoundError:
        return None
    except Exception:  # noqa: BLE001 - 版本探测失败不阻塞
        return None


def _bare_number(wind_code: str) -> str:
    return wind_code.split(".")[0] if "." in wind_code else wind_code


class AkShareProvider:
    """行业数据源适配器：逐股东财 push2 直连为主，akshare 包装兜底。"""

    name = PROVIDER_AKSHARE

    def __init__(self, *, mapping_version: str, dataset_version: str) -> None:
        self.mapping_version = mapping_version
        self.dataset_version = dataset_version
        self._ak = None
        self._last_host: str | None = None
        self._tl = threading.local()  # 每线程一个 Session（连接复用，实测提速 20 倍+）

    def _session(self):
        sess = getattr(self._tl, "session", None)
        if sess is None:
            import requests

            sess = requests.Session()
            sess.headers.update(
                {
                    "User-Agent": _UA,
                    "Referer": "https://quote.eastmoney.com/",
                }
            )
            self._tl.session = sess
        return sess

    def _hosts_in_order(self) -> list[str]:
        hosts = list(_PUSH2_HOSTS)
        if self._last_host and self._last_host in hosts:
            hosts.remove(self._last_host)
            hosts.insert(0, self._last_host)
        return hosts

    # ── 依赖与探测 ─────────────────────────────────────────
    def _import_ak(self):
        if self._ak is None:
            import akshare as ak  # 延迟导入：CLI 在环境注入后才可导入

            self._ak = ak
        return self._ak

    def probe(self) -> dict:
        """接口探测：版本、批量接口可用性、直连样例；不写库。"""

        info: dict = {
            "provider": self.name,
            "akshare_version": akshare_version(),
            "endpoints": [],
            "samples": [],
            "notes": [],
        }
        # 口径契约（无条件成立）：批量行业接口不可作为权威分类来源，禁止猜测口径。
        # 正式路径始终为逐证券确定性查询（东财 push2 直连 + akshare 兜底）。
        info["notes"].append(
            "批量行业接口不可作为权威分类来源；禁止猜测口径，正式路径采用逐证券确定性查询。"
        )
        if akshare_version() is None:
            info["notes"].append("akshare 未安装，AkShare fallback 不可用")
        else:
            # 批量接口候选实测
            ak = self._import_ak()
            if not hasattr(ak, "stock_info_shenwan_industry"):
                info["notes"].append("ak.stock_info_shenwan_industry 不存在于当前版本")
            else:
                try:
                    df = ak.stock_info_shenwan_industry()
                    info["endpoints"].append("ak.stock_info_shenwan_industry")
                    info["batch_columns"] = [str(c) for c in df.columns]
                    info["batch_rows"] = int(len(df))
                    info["samples"].append(
                        {
                            "endpoint": "batch",
                            "rows": df.head(3).to_dict(orient="records"),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    info["notes"].append(f"批量接口异常: {exc!r}")
            info["notes"].append(_BATCH_UNAVAILABLE_REASON)

        # 直连 push2 采样（固定 600519，主机轮换，只记录字段）
        try:
            data = self._fetch_direct("600519")
            info["endpoints"].append("eastmoney.push2.direct")
            info["samples"].append(
                {
                    "endpoint": "push2_per_stock",
                    "host": self._last_host,
                    "symbol": "600519",
                    "fields": {
                        "f57": data.get("f57"),
                        "f58": data.get("f58"),
                        "f127": data.get("f127"),
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001
            info["notes"].append(f"push2 直连异常（全部主机）: {exc!r}")

        return info

    # ── 直连查询 ───────────────────────────────────────────
    def _fetch_direct(self, bare: str) -> dict:
        """主机轮换请求（Session 连接复用）；成功主机记忆并置顶，全部失败抛最后异常。"""
        secid = f"{1 if bare.startswith(('6', '9')) else 0}.{bare}"
        last_exc: BaseException | None = None
        for host in self._hosts_in_order():
            result, _attempts, err = call_with_retry(
                lambda h=host: self._session().get(
                    f"https://{h}/api/qt/stock/get",
                    params={
                        "secid": secid,
                        "fields": "f57,f58,f127",
                        "invt": "2",
                        "fltt": "2",
                    },
                    headers={
                        "User-Agent": _UA,
                        "Referer": "https://quote.eastmoney.com/",
                    },
                    timeout=10,
                ),
                max_retries=1,
                backoff_seconds=0.5,
            )
            if err is None and result is not None:
                self._last_host = host
                payload = json.loads(result.text)
                data = payload.get("data")
                if data is None:
                    # 限流/降级响应（rc!=0 或 data:null）→ 可重试异常，换主机继续
                    raise _Push2Throttled(
                        f"{host} 限流/空 data（rc={payload.get('rc')!r}）"
                    )
                return data
            last_exc = err if err is not None else last_exc
        raise (
            last_exc if last_exc is not None else ConnectionError("push2 全部主机失败")
        )

    def _fetch_akshare(self, bare: str) -> dict:
        ak = self._import_ak()
        df, _attempts, err = call_with_retry(
            lambda: ak.stock_individual_info_em(symbol=bare),
            max_retries=2,
            backoff_seconds=1.0,
        )
        if err is not None or df is None or getattr(df, "empty", True):
            raise (err if err is not None else ValueError("akshare 返回空"))
        items: dict[str, str] = {}
        for _, row in df.iterrows():
            k = str(row.get("item") or "").strip()
            v = str(row.get("value") or "").strip()
            if k and v and v.lower() != "nan":
                items[k] = v
        return {"f58": items.get("股票简称", ""), "f127": items.get("行业", "-")}

    def _query_one(
        self, wind_code: str, *, max_retries: int, backoff_seconds: float
    ) -> ProviderResult:
        """逐股查询：直连 push2 优先，akshare 兜底；失败分类四态。"""
        bare = _bare_number(wind_code)
        base = ProviderResult(
            wind_code=wind_code,
            security_number=bare,
            query_status=QueryStatus.ERROR,
            provider=self.name,
            provider_endpoint="eastmoney.push2.direct",
        )
        try:
            data = self._fetch_direct(bare)
            base.provider_endpoint = "eastmoney.push2.direct"
        except Exception as direct_exc:  # noqa: BLE001
            try:
                data = self._fetch_akshare(bare)
                base.provider_endpoint = "ak.stock_individual_info_em"
            except Exception as ak_exc:  # noqa: BLE001
                base.attempts = 1
                base.last_error = (
                    f"direct={type(direct_exc).__name__}:{direct_exc}; "
                    f"akshare={type(ak_exc).__name__}:{ak_exc}"
                )
                return base

        ind_raw = str(data.get("f127") or "").strip()
        base.attempts = 1
        if not ind_raw or ind_raw == "-":
            base.query_status = QueryStatus.EMPTY
            return base
        base.raw_value_hash = raw_value_hash(f"push2:{wind_code}:{ind_raw}")
        l1, l2 = map_l2_to_l1(ind_raw)
        if l1 is None:
            base.query_status = QueryStatus.UNMAPPED
            base.industry_l2 = l2
            base.last_error = f"行业值无法映射到申万一级: {ind_raw!r}"
            return base
        base.query_status = QueryStatus.SUCCESS
        base.industry_l1 = l1
        base.industry_l2 = l2
        return base

    # ── 统一入口 ───────────────────────────────────────────
    def query_many(
        self,
        codes: list[str],
        *,
        retry_empty: bool = False,
        cached: dict[str, ProviderResult] | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        on_progress: Callable[[int, int, dict[str, int]], None] | None = None,
        on_result: Callable[[ProviderResult], None] | None = None,
        concurrency: int = 4,
    ) -> list[ProviderResult]:
        cached = cached or {}
        counter = ProgressCounter()
        by_code: dict[str, ProviderResult] = {}

        def task(code: str) -> tuple[str, ProviderResult, bool]:
            if code in cached:
                st = cached[code].query_status
                if st in (QueryStatus.SUCCESS, QueryStatus.UNMAPPED):
                    return code, cached[code], True
                if st == QueryStatus.EMPTY and not retry_empty:
                    return code, cached[code], True
                # error 允许按重试策略继续（档案 §6.1/§6.3）；empty 加 --retry-empty 重查
            res = self._query_one(
                code, max_retries=max_retries, backoff_seconds=backoff_seconds
            )
            time.sleep(DEFAULT_RATE_LIMIT_SLEEP)
            return code, res, False

        def finish(code: str, res: ProviderResult, was_cached: bool, done: int) -> None:
            by_code[code] = res
            if was_cached:
                counter.cached += 1
            else:
                self._count(counter, res)
            if on_result is not None:
                on_result(res)  # 逐码回调：每查询完成一个代码即落盘（档案 §6.2）
            if on_progress is not None:
                on_progress(done, len(codes), counter.as_dict())

        workers = max(1, min(concurrency, len(codes)))
        if workers == 1:
            for idx, code in enumerate(codes):
                code2, res, was_cached = task(code)
                finish(code2, res, was_cached, idx + 1)
        else:
            done = 0
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(task, code) for code in codes]
                for fut in as_completed(futures):
                    code2, res, was_cached = fut.result()
                    done += 1
                    finish(code2, res, was_cached, done)
        return [by_code[c] for c in codes]

    @staticmethod
    def _count(counter: ProgressCounter, res: ProviderResult) -> ProgressCounter:
        if res.query_status == QueryStatus.SUCCESS:
            counter.success += 1
        elif res.query_status == QueryStatus.EMPTY:
            counter.empty += 1
        elif res.query_status == QueryStatus.UNMAPPED:
            counter.unmapped += 1
        elif res.query_status == QueryStatus.ERROR:
            counter.error += 1
        return counter
