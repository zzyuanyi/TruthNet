"""公司事实联网回填解析 — Phase E 会5（首个示范触发点）.

纯函数解析：从联网搜索结果解析公司事实值（当前：上市日期）。
与 provider 解耦——换 provider 只影响「能不能搜到」，不影响
「搜到了怎么解析」（会5 设计决策）。独立单测。
"""

from __future__ import annotations

import re

from app.application.ports.web_search_provider import SearchResult

# 匹配 2024-03-19 / 2024.03.19 / 2024/03/19 / 2024年3月19日
_DATE_RE = re.compile(r"((?:19|20)\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")


def extract_listing_date_from_hits(hits: list[SearchResult]) -> str | None:
    """从搜索结果解析上市日期 → 'YYYY-MM-DD'；无 → None.

    扫描顺序：snippet（可解析正文/摘要）→ title → published_at，
    返回第一个可解析的合法日期。snippet 语义统一为「可解析正文/摘要」，
    不针对任何 provider 的原始字段名写逻辑。
    """
    for hit in hits or []:
        for text in (hit.snippet, hit.title, hit.published_at or ""):
            found = _extract_date_from_text(text)
            if found:
                return found
    return None


def _extract_date_from_text(text: str) -> str | None:
    """从单段文本解析 YYYY-MM-DD；无合法日期 → None。"""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None
