"""AkShare provider 适配器（档案 v1.1 §5.1，口径以 2026-08-15 实测为准）。

数据源分层（收口批次定稿）：
  1. 主路径 = push2 批量 `ulist.np/get`（f100 = 申万二级名）。
     2026-08-15 口径认证实验（data/processed/f100_calib/f100_calib_result.json）：
     60 样本中批量 f100 与逐股 f127 均 57 只成功（同一 3 只缺失），双口径
     normalize+map 到申万一级后 57/57 一致、conflict=0 → 满足档案 §6 判据
     （无无法解释的冲突才启用批量），正式启用批量为主路径；
  2. 批量未覆盖的代码（退市/停牌/字段缺失）→ 逐股 push2 `stock/get` f127
     回退（逐码确定性查询，口径与批量同源）；
  3. akshare 包装为最后兜底（当前环境未安装时自动跳过）；
  4. 任何返回值先过 normalizer（二级→一级映射 + 允许集合校验），
     不能映射进 unmapped，禁止名称推断（档案 §13）。

akshare 的 `stock_info_shenwan_industry` 在当前版本不存在，且
`stock_industry_clf_hist_sw` 的 industry_code 体系（如 480301）无法与
申万 801xxx 指数代码稳定关联——akshare 批量路径仍按档案 §5.1"禁止猜测口径"
不采用（push2 批量与它是两个独立来源，本模块只启用已认证的 push2 批量）。

收口批次（大规模补全可靠性，档案 v1.1 §6.4 扩展）：
  - 主机轮换真正做到"限流换主机"：某主机 data:null / 连接失败 → 记录失败、
    进入冷却并继续下一主机，全部失败才抛错再走 akshare 兜底；
  - CLI 的 --max-retries / --backoff-seconds 真正贯穿到请求层（不再硬编码）；
  - 有界自适应节流：并发被钳制在 [1, 8]，连续限流/超时降并发、稳定成功
    缓慢恢复、host cooldown、负载感知 sleep + 抖动（见 throttle.py）；
  - 报告输出 requests / retry_count / throttle_count / fallback_count /
    host_distribution / effective_concurrency / batch_requests / batch_misses。
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
    MAX_CONCURRENCY,
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
from backend.app.application.services.industry_fill.throttle import RateController

log = logging.getLogger(__name__)

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"
_BATCH_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
# 批量请求单次证券数上限（口径认证实验同款 60；push2delay 实测可承载）
_BATCH_CHUNK = 60
# 东财行情主机轮换：主站可能瞬时重置（RemoteDisconnected），按序回退镜像。
# 2026-08-15 实测：push2/82.push2 被远端断连，push2delay 稳定返回 f127/f100。
_PUSH2_HOSTS = [
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "push2delay.eastmoney.com",
]
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# akshare 批量路径不可用原因（与 push2 批量是独立来源，仅作诊断说明）
_AKSHARE_BATCH_UNAVAILABLE_REASON = (
    "stock_info_shenwan_industry 在 akshare 1.18.91 不存在；"
    "stock_industry_clf_hist_sw 行业代码体系无法与申万 801xxx 指数代码"
    "稳定关联，禁止猜测口径（档案 §5.1）——akshare 批量不采用，"
    "push2 批量（已认证）不受影响"
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
        self._controller = RateController(4)
        self._stats_lock = threading.Lock()
        self._stats: dict = self._fresh_stats()

    @staticmethod
    def _fresh_stats() -> dict:
        return {
            "requests": 0,
            "retries": 0,
            "throttles": 0,
            "fallbacks": 0,
            "batch_requests": 0,
            "batch_misses": 0,
            "host_hits": {},
        }

    def _stats_reset(self) -> None:
        with self._stats_lock:
            self._stats = self._fresh_stats()

    def _stat_inc(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    def report_stats(self) -> dict:
        """运行统计（供 service 写入报告）：请求/重试/限流/兜底/主机分布/有效并发。"""
        with self._stats_lock:
            out = {
                "provider_requests": self._stats["requests"],
                "provider_retries": self._stats["retries"],
                "provider_throttles": self._stats["throttles"],
                "provider_fallbacks": self._stats["fallbacks"],
                "provider_batch_requests": self._stats["batch_requests"],
                "provider_batch_misses": self._stats["batch_misses"],
                "provider_host_distribution": dict(self._stats["host_hits"]),
            }
        snap = self._controller.snapshot()
        out["effective_concurrency"] = snap["effective_concurrency"]
        out["provider_pressure"] = snap["pressure"]
        return out

    def _session(self):
        sess = getattr(self._tl, "session", None)
        if sess is None:
            import requests

            sess = requests.Session()
            # 绕过 Windows 系统代理/环境代理：代理会破坏东财直连（档案 §5.1/§6.4，
            # 2026-08-15 实测系统代理把 push2/82.push2 请求代理到 127.0.0.1:7897 失败）。
            # 不设 trust_env=False 时 requests 会读取注册表代理（见对抗审查 H1）。
            sess.trust_env = False
            sess.headers.update(
                {
                    "User-Agent": _UA,
                    "Referer": "https://quote.eastmoney.com/",
                }
            )
            self._tl.session = sess
        return sess

    def _hosts_in_order(self) -> list[str]:
        # _last_host 由逐股回退工作线程写、这里读：加锁避免 data race（对抗审查 H6）
        hosts = list(_PUSH2_HOSTS)
        with self._stats_lock:
            last = self._last_host
        if last and last in hosts:
            hosts.remove(last)
            hosts.insert(0, last)
        return hosts

    def _ordered_hosts(self) -> list[str]:
        """按记忆顺序过滤冷却主机；全部冷却则返回空（fail-fast，对抗审查 H7）。

        冷却中的主机被跳过、不重锤；空列表由调用方立即抛 throttled 错误
        （请求被打回 ERROR，resume 会重试）。避免"整批失败→逐股风暴"时
        仍以全并发重锤 30s 冷却窗口内的主机。
        """
        return [h for h in self._hosts_in_order() if self._controller.host_allowed(h)]

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
        # 口径契约（无条件成立）：禁止猜测口径，仅采用确定性行业接口。
        # push2 批量 ulist.np/get（f100=申万二级名）已于 2026-08-15 口径认证
        # （60 样本 f127/f100 双口径 57/57 一致、0 冲突）→ 批量为主路径，逐股回退。
        info["notes"].append(
            "禁止猜测口径：仅采用确定性行业接口；push2 批量 ulist.np/get（f100=申万二级名）"
            "已认证（2026-08-15：60 样本与逐股 f127 57/57 一致、0 冲突）→ 批量主路径、"
            "逐股 f127 回退、akshare 兜底。"
        )
        if akshare_version() is None:
            info["notes"].append("akshare 未安装，AkShare fallback 不可用")
        else:
            # akshare 批量接口候选实测（与 push2 批量是独立来源，仍不可用）
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
                    info["notes"].append(f"akshare 批量接口异常: {exc!r}")
            info["notes"].append(_AKSHARE_BATCH_UNAVAILABLE_REASON)

        # push2 批量采样（固定 600519/000001，主机轮换，只记录字段）
        try:
            batch_map = self._fetch_batch(["600519", "000001"])
            info["endpoints"].append("eastmoney.push2.batch")
            info["samples"].append(
                {
                    "endpoint": "push2_batch",
                    "host": self._last_host,
                    "codes": sorted(batch_map),
                    "fields": {"f100": "申万二级名（与逐股 f127 同语义）"},
                }
            )
        except Exception as exc:  # noqa: BLE001
            info["notes"].append(f"push2 批量异常（全部主机）: {exc!r}")

        # 直连 push2 逐股采样（固定 600519，主机轮换，只记录字段）
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
    def _fetch_direct(
        self,
        bare: str,
        *,
        max_retries: int = 1,
        backoff_seconds: float = 0.5,
        attempts: list[int] | None = None,
        throttled_flag: list[bool] | None = None,
    ) -> dict:
        """主机轮换请求（Session 连接复用）。

        - 成功主机记忆并置顶；data:null / rc!=0 视为限流，记录失败并换下一主机；
        - 主机连续失败达到阈值进入冷却窗口（throttle.RateController）；
        - 全部主机失败才抛最后异常（然后由 _query_one 走 akshare 兜底）；
        - max_retries / backoff_seconds 由上层配置贯穿（不再硬编码）。
        attempts 为可选计数器列表（每主机 call_with_retry 尝试次数累加）。
        throttled_flag 为可选单元素列表：轮换中任一主机限流则置 True
        （即使最终由其他主机/兜底恢复，调用方也据此降并发）。
        """
        secid = f"{1 if bare.startswith(('6', '9')) else 0}.{bare}"
        hosts = self._ordered_hosts()
        if not hosts:
            # 全部主机在冷却窗口内：不重锤，直接判限流（resume 会重试，对抗审查 H7）
            self._stat_inc("throttles")
            raise _Push2Throttled("push2 全部主机处于冷却窗口，跳过请求")
        last_exc: BaseException | None = None
        for host in hosts:
            result, n_attempts, err = call_with_retry(
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
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            if attempts is not None:
                attempts.append(n_attempts)
            if n_attempts > 1:
                self._stat_inc("retries", n_attempts - 1)
            if err is None and result is not None:
                try:
                    payload = json.loads(result.text)
                except (ValueError, TypeError) as exc:
                    # 非 JSON 体（反爬 HTML/截断）→ 视为主机失败，换下一主机继续
                    self._controller.host_failed(host)
                    last_exc = exc
                    continue
                data = payload.get("data")
                rc = payload.get("rc")
                if data is None or (rc is not None and rc != 0):
                    # 限流/降级响应（rc!=0 或 data:null）→ 记录失败并换下一主机继续。
                    # 注意：此处必须先判 data/rc，再记账——host_ok 会清零失败计数，
                    # 若先记账会把"持续限流主机"记成成功且冷却永不触发（对抗审查 A）。
                    # rc!=0 但 data 非空同样视为限流（_Push2Throttled 契约，对抗审查 H2）；
                    # rc 键缺失（None）视为非降级（探测/桩场景兼容）。
                    self._stat_inc("throttles")
                    if throttled_flag is not None:
                        throttled_flag[0] = True
                    self._controller.host_failed(host)
                    last_exc = _Push2Throttled(f"{host} 限流/空 data（rc={rc!r}）")
                    continue
                # 真成功才记账：记忆主机置顶、清零失败计数、累计命中（_last_host 加锁，H6）
                self._controller.host_ok(host)
                with self._stats_lock:
                    self._last_host = host
                    self._stats["host_hits"][host] = (
                        self._stats["host_hits"].get(host, 0) + 1
                    )
                return data
            if err is not None:
                self._controller.host_failed(host)
                last_exc = err
        raise (
            last_exc if last_exc is not None else ConnectionError("push2 全部主机失败")
        )

    def _fetch_akshare(
        self,
        bare: str,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        attempts: list[int] | None = None,
    ) -> dict:
        ak = self._import_ak()
        df, n_attempts, err = call_with_retry(
            lambda: ak.stock_individual_info_em(symbol=bare),
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        if attempts is not None:
            attempts.append(n_attempts)
        if n_attempts > 1:
            self._stat_inc("retries", n_attempts - 1)
        if err is not None or df is None or getattr(df, "empty", True):
            raise (err if err is not None else ValueError("akshare 返回空"))
        items: dict[str, str] = {}
        for _, row in df.iterrows():
            k = str(row.get("item") or "").strip()
            v = str(row.get("value") or "").strip()
            if k and v and v.lower() != "nan":
                items[k] = v
        return {"f58": items.get("股票简称", ""), "f127": items.get("行业", "-")}

    def _build_result(
        self,
        wind_code: str,
        bare: str,
        ind_raw: str,
        *,
        endpoint: str,
        throttled: bool,
    ) -> ProviderResult:
        """统一分类：原始行业名 → 四态 ProviderResult（逐股与批量共用口径）。

        空/占位（-）→ EMPTY；无法映射到申万一级 → UNMAPPED；否则 SUCCESS。
        raw_value_hash 用 push2 前缀（批量/逐股同源，hash 仅用于去重）。
        """
        base = ProviderResult(
            wind_code=wind_code,
            security_number=bare,
            query_status=QueryStatus.ERROR,
            provider=self.name,
            provider_endpoint=endpoint,
        )
        base.throttled = throttled
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

    def _query_one(
        self, wind_code: str, *, max_retries: int, backoff_seconds: float
    ) -> ProviderResult:
        """逐股查询（批量未覆盖时的回退路径）：直连 push2 优先，akshare 兜底。

        max_retries / backoff_seconds 贯穿到直连与兜底（不再硬编码）。
        """
        bare = _bare_number(wind_code)
        self._stat_inc("requests")
        direct_attempts: list[int] = []
        ak_attempts: list[int] = []
        throttled_hit: list[bool] = [False]  # 轮换中任一主机限流即置位（供降并发）
        throttled = False
        endpoint = "eastmoney.push2.direct"
        ind_raw = ""
        try:
            data = self._fetch_direct(
                bare,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
                attempts=direct_attempts,
                throttled_flag=throttled_hit,
            )
            throttled = throttled_hit[0]
            ind_raw = str(data.get("f127") or "").strip()
        except Exception as direct_exc:  # noqa: BLE001
            throttled = isinstance(direct_exc, _Push2Throttled) or throttled_hit[0]
            self._stat_inc("fallbacks")
            try:
                data = self._fetch_akshare(
                    bare,
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                    attempts=ak_attempts,
                )
                endpoint = "ak.stock_individual_info_em"
                ind_raw = str(data.get("f127") or "").strip()
            except Exception as ak_exc:  # noqa: BLE001
                res = ProviderResult(
                    wind_code=wind_code,
                    security_number=bare,
                    query_status=QueryStatus.ERROR,
                    provider=self.name,
                    provider_endpoint="eastmoney.push2.direct",
                )
                res.attempts = sum(direct_attempts) + sum(ak_attempts)
                res.last_error = (
                    f"direct={type(direct_exc).__name__}:{direct_exc}; "
                    f"akshare={type(ak_exc).__name__}:{ak_exc}"
                )
                res.throttled = throttled
                return res

        res = self._build_result(
            wind_code, bare, ind_raw, endpoint=endpoint, throttled=throttled
        )
        res.attempts = sum(direct_attempts) + sum(ak_attempts)
        return res

    def _fetch_batch(
        self,
        bare_codes: list[str],
        *,
        max_retries: int = 1,
        backoff_seconds: float = 0.5,
        attempts: list[int] | None = None,
        throttled_flag: list[bool] | None = None,
    ) -> dict[str, str]:
        """push2 批量行情查询（ulist.np/get，f100 = 申万二级名）。

        与 _fetch_direct 相同的轮换/限流语义：某主机 data:null → 记录失败并换下一
        主机继续；全部失败才抛最后异常（由 query_many 整块退回逐股）。
        返回 bare 代码 → 原始行业名；f100 为空/占位（-）的代码不出现在返回
        （交由逐股回退），避免把"该证券无行业字段"误判成 EMPTY。
        """
        self._stat_inc("requests")
        with self._stats_lock:
            self._stats["batch_requests"] = self._stats.get("batch_requests", 0) + 1
        secids = []
        for bare in bare_codes:
            market = "1" if bare.startswith(("6", "9")) else "0"
            secids.append(f"{market}.{bare}")
        hosts = self._ordered_hosts()
        if not hosts:
            # 全部主机在冷却窗口内：不重锤，直接判限流（对抗审查 H7）
            self._stat_inc("throttles")
            raise _Push2Throttled("push2 批量：全部主机处于冷却窗口，跳过请求")
        last_exc: BaseException | None = None
        for host in hosts:
            result, n_attempts, err = call_with_retry(
                lambda h=host: self._session().get(
                    f"https://{h}/api/qt/ulist.np/get",
                    params={
                        "secids": ",".join(secids),
                        "fields": "f12,f14,f100",
                        "fltt": "2",
                        "invt": "2",
                    },
                    headers={
                        "User-Agent": _UA,
                        "Referer": "https://quote.eastmoney.com/",
                    },
                    timeout=15,
                ),
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            if attempts is not None:
                attempts.append(n_attempts)
            if n_attempts > 1:
                self._stat_inc("retries", n_attempts - 1)
            if err is None and result is not None:
                try:
                    payload = json.loads(result.text)
                except (ValueError, TypeError) as exc:
                    # 非 JSON 体（反爬 HTML/截断）→ 视为主机失败，换下一主机继续
                    self._controller.host_failed(host)
                    last_exc = exc
                    continue
                data = payload.get("data")
                rc = payload.get("rc")
                if data is None or (rc is not None and rc != 0):
                    # 限流/降级响应 → 记录失败并换下一主机继续（不是 EMPTY）。
                    # 同样先判 data/rc 再记账（对抗审查 A：防止冷却永不触发）。
                    # rc!=0 但 data 非空同样视为限流（H2）；rc 键缺失视为非降级。
                    self._stat_inc("throttles")
                    if throttled_flag is not None:
                        throttled_flag[0] = True
                    self._controller.host_failed(host)
                    last_exc = _Push2Throttled(f"{host} 批量限流/空 data（rc={rc!r}）")
                    continue
                diff = data.get("diff")
                if not diff:
                    # rc==0 但整块无任何证券返回（diff 空/缺失）→ 降级响应，
                    # 同样换主机继续，不把"持续空批量"的主机记成成功（对抗审查 H2）。
                    self._stat_inc("throttles")
                    if throttled_flag is not None:
                        throttled_flag[0] = True
                    self._controller.host_failed(host)
                    last_exc = _Push2Throttled(
                        f"{host} 批量响应空 diff（{len(bare_codes)} 码全缺）"
                    )
                    continue
                # 真成功才记账（_last_host 加锁，H6）
                self._controller.host_ok(host)
                with self._stats_lock:
                    self._last_host = host
                    self._stats["host_hits"][host] = (
                        self._stats["host_hits"].get(host, 0) + 1
                    )
                items = diff.values() if isinstance(diff, dict) else diff
                out: dict[str, str] = {}
                for item in items:
                    code = str(item.get("f12") or "").strip()
                    ind = str(item.get("f100") or "").strip()
                    if code and ind and ind != "-":
                        out[code] = ind
                return out
            if err is not None:
                self._controller.host_failed(host)
                last_exc = err
        raise (
            last_exc
            if last_exc is not None
            else ConnectionError("push2 批量全部主机失败")
        )

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
        """批量主路径 + 逐股回退 + akshare 兜底（口径认证见模块 docstring）。

        流程：
          1. 缓存命中（SUCCESS/UNMAPPED、或 EMPTY 且未开 --retry-empty）直接复用；
          2. 其余代码按 _BATCH_CHUNK=60 分块，每块一次 push2 `ulist.np/get`（f100）；
             块内 f100 为空的代码 → 逐股 f127 回退（同源确定性口径）；
          3. 整块批量失败（全部主机失败）→ 整块退回逐股；
          4. 逐股回退走线程池，并发受 controller 闸门与 concurrency 天花板双重约束
             （对抗审查 B：线程池不再 min(8, n) 无视调用方并发）；
          5. 逐码 on_result 回调落盘（staging 逐码持久化，档案 §6.2）。
        """
        cached = cached or {}
        counter = ProgressCounter()
        by_code: dict[str, ProviderResult] = {}
        controller = self._controller
        # set_capacity 同时把恢复上限钳到 concurrency（--concurrency 即天花板，审查 B）
        controller.set_capacity(concurrency)
        self._stats_reset()

        def cached_skip(code: str) -> bool:
            if code in cached:
                st = cached[code].query_status
                if st in (QueryStatus.SUCCESS, QueryStatus.UNMAPPED):
                    return True
                if st == QueryStatus.EMPTY and not retry_empty:
                    return True
            # error 允许按重试策略继续（档案 §6.1/§6.3）；empty 加 --retry-empty 重查
            return False

        def per_stock(code: str) -> tuple[str, ProviderResult, bool]:
            controller.enter()
            try:
                res = self._query_one(
                    code, max_retries=max_retries, backoff_seconds=backoff_seconds
                )
                # 在 worker 内即时记账（对抗审查 H4）：fallback 期间就开始降并发，
                # 而不是等线程池排空后在装配循环里一次性回调（那样早已打爆上游）。
                if res.throttled or res.query_status == QueryStatus.ERROR:
                    controller.on_throttle()
                else:
                    controller.on_success()
                return code, res, False
            finally:
                controller.exit()
                time.sleep(controller.sleep_seconds(DEFAULT_RATE_LIMIT_SLEEP))

        def emit(
            code: str,
            res: ProviderResult,
            *,
            was_cached: bool,
            done: int,
        ) -> None:
            by_code[code] = res
            if was_cached:
                counter.cached += 1
            else:
                self._count(counter, res)
            if on_result is not None:
                on_result(res)  # 逐码回调：每查询完成一个代码即落盘（档案 §6.2）
            if on_progress is not None:
                on_progress(done, len(codes), counter.as_dict())

        n = len(codes)
        if n == 0:
            return []

        # 1) 批量主路径（口径已认证：60 样本 f100/f127 57/57 一致、0 冲突）
        need = [c for c in codes if not cached_skip(c)]
        batch_results: dict[str, ProviderResult] = {}
        batch_miss: list[str] = []
        for start in range(0, len(need), _BATCH_CHUNK):
            chunk = need[start : start + _BATCH_CHUNK]
            bares = [_bare_number(c) for c in chunk]
            throttled_flag = [False]
            attempts: list[int] = []
            controller.enter()
            try:
                bmap = self._fetch_batch(
                    bares,
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                    attempts=attempts,
                    throttled_flag=throttled_flag,
                )
                for code in chunk:
                    raw = bmap.get(_bare_number(code))
                    if raw:
                        res = self._build_result(
                            code,
                            _bare_number(code),
                            raw,
                            endpoint="eastmoney.push2.batch",
                            throttled=throttled_flag[0],
                        )
                        res.attempts = sum(attempts)
                        batch_results[code] = res
                    else:
                        batch_miss.append(code)
                # 批量级节流记账：一次请求计一次，避免把 60 个代码放大成 60 次降并发
                if throttled_flag[0]:
                    controller.on_throttle()
                else:
                    controller.on_success()
            except Exception as batch_exc:  # noqa: BLE001
                log.warning(
                    "批量请求失败（%s）：%d 码整块退回逐股",
                    type(batch_exc).__name__,
                    len(chunk),
                )
                batch_miss.extend(chunk)
                controller.on_throttle()
            finally:
                controller.exit()
                time.sleep(controller.sleep_seconds(DEFAULT_RATE_LIMIT_SLEEP))

        with self._stats_lock:
            self._stats["batch_misses"] = len(batch_miss)

        # 2) 逐股回退（批量未覆盖 + 缓存重查），线程池受 concurrency 与闸门约束
        fallback_results: dict[str, ProviderResult] = {}
        if batch_miss:
            max_workers = max(1, min(concurrency, MAX_CONCURRENCY, len(batch_miss)))
            if max_workers == 1:
                for code in batch_miss:
                    _c, res, _w = per_stock(code)
                    fallback_results[code] = res
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = [pool.submit(per_stock, code) for code in batch_miss]
                    for fut in as_completed(futures):
                        _c, res, _w = fut.result()
                        fallback_results[_c] = res

        # 3) 按输入序装配（缓存直出 / 批量 / 逐股）
        done = 0
        for code in codes:
            done += 1
            if code in batch_results:
                emit(code, batch_results[code], was_cached=False, done=done)
            elif code in fallback_results:
                emit(code, fallback_results[code], was_cached=False, done=done)
            else:
                emit(code, cached[code], was_cached=True, done=done)
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
