"""AnySearch 垂类真机探测 — 8/19 接入验证（匿名，不配 Key）.

验证 MCP finance 垂直域真实返回是否符合 provider 解析预期：
1. finance.quote cn_code=600519.SH（行情）
2. finance.news type=announcement cn_code=600518.SH（公告）
3. finance.fundamental type=indicator cn_code=600519.SH（三表/指标）

匿名限流低（实测 X-Ratelimit-Limit: 10/窗口），请勿频繁重跑。
用法：python scripts/anysearch_vertical_probe.py
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, "backend")

from app.infrastructure.web_search.anysearch.provider import (  # noqa: E402
    AnySearchWebSearchProvider,
)


async def main() -> int:
    provider = AnySearchWebSearchProvider(api_key="")
    cases = [
        ("行情 quote", "贵州茅台 600519.SH 今天股价", "600519.SH"),
        ("公告 news", "康美药业 600518.SH 最新公告", "600518.SH"),
        ("三表 fundamental", "贵州茅台 600519.SH 财报 净利润 营收", "600519.SH"),
        ("上市 fundamental", "康美药业 600518.SH 上市日期", "600518.SH"),
    ]
    for label, query, code in cases:
        print(f"\n===== {label} | query={query!r} =====")
        try:
            hits = await provider.search(query, max_results=3)
        except Exception as exc:  # noqa: BLE001
            print(f"  [异常] {type(exc).__name__}: {exc}")
            continue
        print(f"  hits={len(hits)}")
        for h in hits:
            print(f"  - title={h.title[:60]!r}")
            print(f"    url={h.url!r}  published_at={h.published_at}")
            print(f"    snippet={h.snippet[:200]!r}")
    print("\n===== report_stats =====")
    print(json.dumps(provider.report_stats(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
