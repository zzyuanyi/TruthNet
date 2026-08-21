"""当前沪深京 A 股范围快照与行业补全 eligibility 判定。

行业为空不等于补全失败。退市证券、旧三板代码或尚未进入项目数据版本的公司
不应反复打逐股接口。本模块通过 AkShare 聚合的上交所、深交所、北交所官方
证券清单建立带哈希、时间戳的当前范围快照；接口异常时 fail-closed，不使用
代码前缀或公司名称猜测上市状态。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_CODE_RE = re.compile(r"[0-9]{6}")
_MIN_UNIVERSE_SIZE = 1_000
UNIVERSE_SOURCE = "sse+szse+bse-via-akshare"


@dataclass(frozen=True)
class CurrentUniverseSnapshot:
    """一次可审计的当前沪深京 A 股代码快照。"""

    codes: frozenset[str]
    names: dict[str, str]
    source: str
    provider_version: str
    retrieved_at: str
    sha256: str

    def report_fields(self) -> dict[str, Any]:
        return {
            "current_universe_count": len(self.codes),
            "current_universe_source": self.source,
            "current_universe_provider_version": self.provider_version,
            "current_universe_retrieved_at": self.retrieved_at,
            "current_universe_sha256": self.sha256,
        }


def bare_security_code(wind_code: str) -> str:
    """取 wind_code 的 6 位证券代码；非法格式返回空串。"""

    bare = str(wind_code or "").strip().split(".", 1)[0]
    return bare if _CODE_RE.fullmatch(bare) else ""


def build_current_universe_snapshot(
    rows: list[tuple[object, object]],
    *,
    provider_version: str,
    retrieved_at: str | None = None,
    min_size: int = _MIN_UNIVERSE_SIZE,
) -> CurrentUniverseSnapshot:
    """校验代码/名称列表并构造稳定哈希；任何歧义均拒绝继续。"""

    names: dict[str, str] = {}
    for raw_code, raw_name in rows:
        code = str(raw_code or "").strip().zfill(6)
        name = str(raw_name or "").strip()
        if not _CODE_RE.fullmatch(code):
            raise RuntimeError(f"当前 A 股清单含非法代码: {raw_code!r}")
        if not name:
            raise RuntimeError(f"当前 A 股清单 {code} 的证券简称为空")
        existing = names.get(code)
        if existing is not None and existing != name:
            raise RuntimeError(
                f"当前 A 股清单代码重复且简称冲突: {code}={existing!r}/{name!r}"
            )
        names[code] = name
    if len(names) < min_size:
        raise RuntimeError(
            f"当前 A 股清单规模异常: {len(names)} < {min_size}，拒绝据此豁免缺失行业"
        )
    digest_payload = "\n".join(f"{code}\t{names[code]}" for code in sorted(names))
    return CurrentUniverseSnapshot(
        codes=frozenset(names),
        names=names,
        source=UNIVERSE_SOURCE,
        provider_version=provider_version,
        retrieved_at=retrieved_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sha256=hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
    )


def fetch_current_a_share_universe() -> CurrentUniverseSnapshot:
    """从沪深京官方清单聚合接口获取当前 A 股范围，失败时不降级猜测。"""

    try:
        import akshare as ak

        frame = ak.stock_info_a_code_name()
        if not {"code", "name"}.issubset(frame.columns):
            raise RuntimeError(
                f"当前 A 股清单字段异常: {list(frame.columns)!r}，期望 code/name"
            )
        rows = list(frame[["code", "name"]].itertuples(index=False, name=None))
        return build_current_universe_snapshot(
            rows,
            provider_version=str(getattr(ak, "__version__", "unknown")),
        )
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - 网络/解析失败必须 fail-closed
        raise RuntimeError(
            f"当前 A 股清单获取失败，拒绝继续行业 eligibility 判定: {exc}"
        ) from exc


def partition_missing_codes(
    missing_codes: list[str], snapshot: CurrentUniverseSnapshot
) -> tuple[list[str], list[str]]:
    """把行业缺失分为当前上市应查询与非当前上市豁免两组。"""

    eligible: list[str] = []
    not_current: list[str] = []
    for wind_code in missing_codes:
        bare = bare_security_code(wind_code)
        if bare and bare in snapshot.codes:
            eligible.append(wind_code)
        else:
            not_current.append(wind_code)
    return eligible, not_current
