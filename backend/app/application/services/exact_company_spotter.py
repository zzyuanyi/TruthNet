"""数据库驱动全文公司名称 spotting — v3.3.3 收口批次 C/B（方案 §3.5/§3.3）。

并行通道：从 companies 表构建 sec_name 精确名称索引（进程级缓存 +
TTL 版本刷新，不维护第二套静态名单），对 query 全文做最长优先、
区间不重叠的精确匹配。官方反例（伊利/双汇、茅台/五粮液、中石化/
中石油）中 extractor 漏提的第二家公司 span 由本通道补召回。

边界：
  - 只召回完整 sec_name 的精确 span，不猜短称（短称仍走候选提案通道）；
  - 「茅台镇」「康美丽」等含公司名子串的文本不命中（必须完整名称）；
  - 身份绑定不在本模块：span 进入 resolver 主流程由 Repository
    二次链接（单一来源），本模块只提供 (text, start, end)；
  - 不向 _SUBJECT_TERMINATORS 等终止词表添加官方题目专用词；
  - 数据访问边界（收口批次 B）：本模块不导入 SQLAlchemy、不读取
    settings、不创建 Engine；名称索引由 CompanyNameIndexProvider
    （application port → infrastructure adapter）提供，缓存按
    provider.profile_key 隔离（backend/database 切换不互用）。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.company_name_provider import (
        CompanyNameIndexProvider,
    )

# 缓存 TTL（秒）：公司表在演示/评测期间基本稳定，60s 版本刷新足够
_CACHE_TTL_SECONDS = 60.0
# 名称最小长度（避免单字命中）
_MIN_NAME_LEN = 2

# 缓存按 provider.profile_key 隔离：{profile_key: (frozenset, checked_at)}
_CACHE: dict[str, tuple[frozenset[str], float]] = {}
_LOCK = threading.Lock()


def _default_provider() -> "CompanyNameIndexProvider":
    """默认 provider：与 CompanyRepository 同源的 backend-aware 工厂。"""
    from app.application.services.company_resolver import (
        get_company_name_index_provider,
    )

    return get_company_name_index_provider()


def _cached_names(provider: "CompanyNameIndexProvider") -> frozenset[str]:
    """按 provider.profile_key 隔离的进程级名称缓存（TTL 刷新）。"""
    key = getattr(provider, "profile_key", None) or "default"
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is None or now - cached[1] > _CACHE_TTL_SECONDS:
            names = provider.list_company_names()
            _CACHE[key] = (names, now)
        else:
            names = cached[0]
        return names


def invalidate_cache(profile_key: str | None = None) -> None:
    """测试/数据变更后强制刷新；不传 key 时清空全部 profile。"""
    with _LOCK:
        if profile_key is None:
            _CACHE.clear()
        else:
            _CACHE.pop(profile_key, None)


@dataclass(frozen=True)
class ExactNameSpan:
    text: str
    start: int
    end: int


def spot_exact_company_spans(
    query: str | None,
    provider: "CompanyNameIndexProvider | None" = None,
) -> list[ExactNameSpan]:
    """全文扫描精确公司名称 span（最长优先、区间不重叠）。

    返回按原文顺序的精确名称 span；无命中返回空列表。
    纯确定性、零 LLM；provider 注入优先（测试用静态名称集），
    缺省走 backend-aware 工厂；异常时返回空列表（不阻断主流程）。
    """
    q = query or ""
    if len(q) < _MIN_NAME_LEN:
        return []
    try:
        names = _cached_names(provider or _default_provider())
    except Exception:  # noqa: BLE001 — 索引失败不阻断实体主流程
        return []
    if not names:
        return []
    max_len = max(len(n) for n in names)
    spans: list[ExactNameSpan] = []
    i = 0
    n = len(q)
    while i <= n - _MIN_NAME_LEN:
        best: ExactNameSpan | None = None
        upper = min(max_len, n - i)
        for length in range(upper, _MIN_NAME_LEN - 1, -1):
            candidate = q[i : i + length]
            if candidate in names:
                best = ExactNameSpan(text=candidate, start=i, end=i + length)
                break
        if best is not None:
            spans.append(best)
            i = best.end  # 区间不重叠
        else:
            i += 1
    return spans
