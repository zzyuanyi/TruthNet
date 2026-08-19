"""公司事实联网回填解析 — Phase E 会5（首个示范触发点）.

纯函数解析：从联网搜索结果解析公司事实值（当前：上市日期）。
与 provider 解耦——换 provider 只影响「能不能搜到」，不影响
「搜到了怎么解析」（会5 设计决策）。独立单测。

上市日期提取安全规则（Phase E 收口，8/19 审查）：
  - 只读 snippet / title 两个字段；**published_at（网页发布日期）绝不作为
    上市日期**——published_at 是搜索结果网页的发布时间，listing_date 是
    公司上市事实，二者语义完全不同。
  - 日期必须伴随「上市/挂牌」语义关键字（日期上下文窗口内），且无
    「发布于/成立于/公告日期/更新时间/披露」等反例语义，才被接受。
    「文章发布于 2026-08-18」「公司成立于 1997-01-01」「公告日期 2024-03-10」
    「更新时间 2025-06-01」「年报披露日期 2024-04-30」都不会误填成上市日期。
  - 多结果解析出的上市日期互不相同 → 无法可靠裁决 → 返回 None（fail-closed，
    不猜）。
  - 来源优先级：本轮不引入领域/域名加权（避免过度架构）；统一按
    fail-closed 处理。缺高可信来源 ≠ 可以伪造。
  - 解析不出 → None，绝不编造。
"""

from __future__ import annotations

import re

from app.application.ports.web_search_provider import SearchResult

# 匹配 2024-03-19 / 2024.03.19 / 2024/03/19 / 2024年3月19日
_DATE_RE = re.compile(r"((?:19|20)\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")

# 上市语义关键字（日期上下文窗口内出现其一才接受）
_LISTING_KEYS = ("上市", "挂牌")
# 反例语义（日期上下文窗口内出现则拒绝）：非上市事件的常见日期伴随词。
# 注意「公告」不加裸词——「上市公告日」本就是上市语义，裸「公告」会误伤；
# 仅拒绝明确的「公告日期/更新/披露/成立」等。
_NEG_KEYS = (
    "发布于",
    "更新于",
    "成立于",
    "成立日期",
    "创建于",
    "公告日期",
    "公告时间",
    "更新时间",
    "披露日期",
    "年报披露",
    "披露时间",
    "数据更新",
)

# 日期上下文窗口半宽（字符数）：在此窗口内匹配上市/反例关键字
_CTX = 16


def extract_listing_date_from_hits(hits: list[SearchResult]) -> str | None:
    """从搜索结果解析上市日期 → 'YYYY-MM-DD'；无 → None；多值冲突 → None.

    只读 snippet / title（published_at 禁止作为上市日期）。
    所有命中解析出的上市日期集合：
      - 恰好一个值 → 返回；
      - 多个互异值（无可靠裁决规则）→ fail-closed 返回 None，不猜。
    """
    accepted: set[str] = set()
    for hit in hits or []:
        for text in (hit.snippet, hit.title):
            value = _extract_listing_date_from_text(text)
            if value:
                accepted.add(value)
    if len(accepted) == 1:
        return next(iter(accepted))
    # 0 个 → 无；≥2 个互异 → 无法裁决 → fail-closed
    return None


def _extract_listing_date_from_text(text: str) -> str | None:
    """从单段文本解析上市日期；无/多候选 → None（fail-closed）。"""
    if not text:
        return None
    found: set[str] = set()
    for m in _DATE_RE.finditer(text):
        date = _valid_date(m)
        if not date:
            continue
        start = max(0, m.start() - _CTX)
        end = min(len(text), m.end() + _CTX)
        window = text[start:end]
        if _has_listing_key(window) and not _has_neg_key(window):
            found.add(date)
    if len(found) == 1:
        return next(iter(found))
    return None


def _valid_date(m: re.Match) -> str | None:
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _has_listing_key(window: str) -> bool:
    return any(key in window for key in _LISTING_KEYS)


def _has_neg_key(window: str) -> bool:
    return any(key in window for key in _NEG_KEYS)
