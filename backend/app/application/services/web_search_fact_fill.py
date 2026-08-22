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

from pydantic import BaseModel

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


_IPO_PRICE_RE = re.compile(
    r"(?:首发价格|首发价|发行价格|发行价)\s*(?:为|是|:|：)?\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*元\s*(?:/股|每股)?"
)


def extract_ipo_price_from_hits(hits: list[SearchResult]) -> str | None:
    """从公告/快讯摘要提取首发价格；多值冲突时不猜。"""
    values: set[str] = set()
    for hit in hits or []:
        for text in (hit.snippet, hit.title):
            for match in _IPO_PRICE_RE.finditer(text or ""):
                values.add(f"{match.group(1)}元/股")
    return next(iter(values)) if len(values) == 1 else None


def extract_executive_compensation_excerpt(
    hits: list[SearchResult],
) -> str | None:
    """返回明确涉及高管薪酬的联网摘要，不把无关研报当作事实。"""
    for hit in hits or []:
        for text in (hit.snippet, hit.title):
            value = " ".join(str(text or "").split()).strip()
            if value and any(
                cue in value for cue in ("高管薪酬", "董监高薪酬", "薪酬", "报酬")
            ):
                return value[:300]
    return None


class _MetricExtraction(BaseModel):
    """财务指标联网提取结果（数字锁定：value 必须原样出现在 snippet 中）。"""

    value: str = ""  # 数值+单位原文，如 "77.54%" / "89.54亿元"
    period: str = ""  # 来源期次表述，如 "2025H1" / "2025-12-31" / "最新"
    quote: str = ""  # 支持该值的 snippet 原文片段
    source_title: str = ""
    source_url: str = ""


def _is_placeholder_value(value: str) -> bool:
    """占位值过滤：'0.00%'/'--'/'-' 等是财务页占位符，不是真值。

    真实 0% 毛利率的公司极罕见（营收>0 则毛利通常非 0），且 0% 对
    财务分析无信息量；宁可拒答也不把占位符当事实。
    """
    norm = value.strip().replace(",", "").replace(" ", "")
    if norm in ("0", "0%", "0.0%", "0.00%", "--", "-", "None", "null", "无", "暂无"):
        return True
    return False


def extract_metric_from_hits(
    hits: list[SearchResult], metric_label: str
) -> dict | None:
    """从联网结果提取财务指标数值（会5 回填；数字锁定 + fail-closed）。

    - 相关性 Gate：仅保留 snippet/title 含指标标签的结果；
    - LLM 结构化提取 value/period/quote；**数字锁定**：value 中的数字必须
      原样出现在结果文本里（_llm_numeric_lock），quote 必须逐字出现在
      结果文本中——防编造；
    - 无命中 / LLM 失败 / 数字无法锁定 / 多来源冲突 → None，调用方保持
      原「数据不足」拒答（fail-closed，不猜测）。
    """
    from app.agents.llm_sync import run_llm_structured
    from app.application.services._llm_numeric_lock import unlocked_numbers

    candidates = [
        h
        for h in (hits or [])
        if metric_label in (h.snippet or "") or metric_label in (h.title or "")
    ]
    if not candidates:
        return None
    locked_text = "\n".join(
        f"- [{h.title}]({h.url})\n{h.snippet}"
        for h in candidates
        if (h.snippet or h.title or h.url)
    )
    if not locked_text.strip():
        return None
    messages = [
        {
            "role": "system",
            "content": (
                "你是金融数据提取器。从联网搜索结果中提取指定财务指标的最新数值。"
                "只输出 JSON。value 必须原样取自下方搜索结果文本，禁止计算、"
                "换算、四舍五入或编造；period 用来源中的期次表述（如 2025H1、"
                "2025-12-31，无期次则填「最新」）；quote 是从搜索结果原文逐字"
                "复制、能支撑该数值的片段。"
            ),
        },
        {
            "role": "user",
            "content": f"指标：{metric_label}\n搜索结果：\n{locked_text}",
        },
    ]
    try:
        out = run_llm_structured(messages, _MetricExtraction)
    except Exception:  # noqa: BLE001 — 提取失败不阻断主链路
        return None
    if out is None or not str(out.value or "").strip():
        return None
    value = " ".join(str(out.value).split())
    # 占位值过滤：0.00%/--/None 等财务页占位符（含"毛利率 0.00%"页）
    if _is_placeholder_value(value):
        return None
    # 数字锁定：提取值中的数字必须都在结果文本中（非空即存在编造数字）
    if unlocked_numbers([value], locked_text):
        return None
    # quote 必须逐字出现在结果文本中（防拼接/改写）
    quote = " ".join(str(out.quote or "").split()).strip()
    if quote and quote not in " ".join(locked_text.split()):
        return None
    return {
        "value": value,
        "period": " ".join(str(out.period or "").split()) or "最新",
        "quote": quote,
        "source_title": str(out.source_title or ""),
        "source_url": str(out.source_url or ""),
    }
