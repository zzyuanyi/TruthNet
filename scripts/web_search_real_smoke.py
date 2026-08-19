#!/usr/bin/env python
"""Web Search 真实联网 smoke runner — Phase E 会5（A7）。

在本地配置了真实 Bocha key 后运行：
  WEB_SEARCH_BACKEND=bocha WEB_SEARCH_API_KEY=<key> python scripts/web_search_real_smoke.py

行为：
  - 无本地 key → 标记 BLOCKED_BY_MISSING_LOCAL_API_KEY，不伪造"真实联网已通过"；
  - 有 key → 对固定公司集合做真实 Provider 直连 smoke，逐条记录
    query / HTTP outcome / result_count / top result domain / snippet 非空 /
    elapsed_ms / parse success；
  - 全程不打印完整 key；报告只写 ***configured***。

只允许 truthnet_test 数据库（本脚本不连库，仅强制约定检查）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.core.config import settings  # noqa: E402
from app.infrastructure.web_search.factory import (  # noqa: E402
    create_web_search_provider,
)

# 固定公司集合（同名消歧验证：带 wind_code + 交易所）
SMOKE_QUERIES = [
    "康美药业 600518.SH 上市日期 交易所",
    "宁德时代 300750.SZ 上市日期 交易所",
    "贵州茅台 600519.SH 上市日期 交易所",
]


def _key_status() -> str:
    key = os.getenv("WEB_SEARCH_API_KEY") or settings.WEB_SEARCH_API_KEY
    return "***configured***" if key else "MISSING"


def main() -> int:
    print("=" * 70)
    print("Web Search real smoke")
    print(f"  WEB_SEARCH_BACKEND = {settings.WEB_SEARCH_BACKEND or 'off'!r}")
    print(f"  WEB_SEARCH_API_KEY = {_key_status()}")
    print("=" * 70)

    backend = (settings.WEB_SEARCH_BACKEND or "off").lower()
    if backend != "bocha":
        print("\n[STATUS] BLOCKED_BY_MISSING_LOCAL_API_KEY / BACKEND_NOT_BOCHA")
        print("  提示: 设置 WEB_SEARCH_BACKEND=bocha + WEB_SEARCH_API_KEY=<key> 后重跑")
        return 2

    provider = create_web_search_provider("bocha")
    if provider is None or not getattr(provider, "_available", False):
        print("\n[STATUS] BLOCKED_BY_MISSING_LOCAL_API_KEY")
        print("  真实 key 未配置，未发起任何网络请求。未伪造真实联网结果。")
        return 2

    print(f"\nProvider: {provider.provider_name}\n")
    all_ok = True
    for query in SMOKE_QUERIES:
        t0 = time.perf_counter()
        try:
            hits = asyncio.run(provider.search(query))
            elapsed_ms = (time.perf_counter() - t0) * 1000
            top_domain = hits[0].domain if hits else "-"
            snippet_nonempty = bool(hits and hits[0].snippet)
            print(f"[query] {query}")
            print(
                f"  result_count={len(hits)}  top_domain={top_domain!r}  "
                f"snippet_nonempty={snippet_nonempty}  elapsed_ms={elapsed_ms:.0f}"
            )
            for h in hits[:3]:
                print(f"    - {h.title[:40]!r}  {h.url[:70]}  date={h.published_at}")
            if not hits:
                all_ok = False
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"[query] {query}")
            print(f"  FAILED after {elapsed_ms:.0f}ms: {type(exc).__name__}: {exc}")
            all_ok = False
        print("-" * 70)

    stats = provider.report_stats()
    print("Provider stats:")
    for k, v in stats.items():
        print(f"  {k}={v}")

    print("\n[STATUS]", "REAL_SMOKE_OK" if all_ok else "REAL_SMOKE_PARTIAL_EMPTY")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
