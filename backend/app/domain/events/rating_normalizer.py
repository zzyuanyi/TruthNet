"""研报评级规范化 — Phase C 数据任务 5.

将 research_reports.rating_org 的原始评级（含变体）映射到有序等级。
保留原始值，同时给出规范化等级，供评级拐点检测使用。

有序等级（level，数值越大越积极）:
  5 = 强烈推荐 / 强力买入 / 强推
  4 = 买入
  3 = 增持 / 推荐 / 优于大市 / 超配 / 跑赢行业 / 收集
  2 = 中性 / 区间操作 / 同步大市 / 持有
  1 = 减持
  0 = 卖出

direction 从 rating_change 字段规范化: down / up / keep。
低置信度（< MIN_CONFIDENCE）不自动写入，由调用方跳过。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── 评级关键词 → 等级 ──────────────────────────────────────
_LEVEL_5 = {"强烈推荐", "强力买入", "强推"}
_LEVEL_4 = {"买入", "买进"}
_LEVEL_3 = {
    "增持",
    "推荐",
    "优于大市",
    "超配",
    "跑赢行业",
    "收集",
    "建议增持",
    "买入建议",
}
_LEVEL_2 = {"中性", "区间操作", "同步大市", "持有", "观望"}
_LEVEL_1 = {"减持", "减仓"}
_LEVEL_0 = {"卖出", "回避"}

_LEVEL_MAP: dict[int, tuple[str, ...]] = {
    5: tuple(_LEVEL_5),
    4: tuple(_LEVEL_4),
    3: tuple(_LEVEL_3),
    2: tuple(_LEVEL_2),
    1: tuple(_LEVEL_1),
    0: tuple(_LEVEL_0),
}

# 含变体后缀的精确等级（如 "买入-A" / "增持-A"）
_STRIP_SUFFIX = re.compile(r"[-_/—（）()\s]*(?:[A-Za-z]+\d*|[（(].*?[)）])?$")

# ── direction 关键词 ───────────────────────────────────────
_DOWN_WORDS = {"下调", "调低", "调降", "降低", "减持"}
_UP_WORDS = {"上调", "调高", "调升", "升级"}
_KEEP_WORDS = {"维持", "不变", "保持", "重申"}

MIN_CONFIDENCE = 0.7  # 低置信度不自动写入


@dataclass(frozen=True)
class NormalizedRating:
    """规范化后的评级."""

    raw: str
    level: int | None  # 0-5，无法映射为 None
    canonical: str  # 等级中文名（-1 表示未知）
    direction: str | None  # down / up / keep / None
    confidence: float  # [0,1]


_NAMES = {5: "强烈推荐", 4: "买入", 3: "增持", 2: "中性", 1: "减持", 0: "卖出"}


def normalize_rating(
    raw_rating: str | None, raw_change: str | None = None
) -> NormalizedRating:
    """规范化单条评级."""
    raw = (raw_rating or "").strip()
    if not raw:
        return NormalizedRating(
            raw="", level=None, canonical="未知", direction=None, confidence=0.0
        )

    # 1. direction 规范化
    direction: str | None = None
    if raw_change:
        for w in _DOWN_WORDS:
            if w in raw_change:
                direction = "down"
                break
        if direction is None:
            for w in _UP_WORDS:
                if w in raw_change:
                    direction = "up"
                    break
        if direction is None:
            for w in _KEEP_WORDS:
                if w in raw_change:
                    direction = "keep"
                    break

    # 2. 等级映射（精确优先，再去除变体后缀）
    level: int | None = None
    for lv, words in _LEVEL_MAP.items():
        if raw in words:
            level = lv
            break
    if level is None:
        base = _STRIP_SUFFIX.sub("", raw).strip()
        for lv, words in _LEVEL_MAP.items():
            if base in words:
                level = lv
                break

    if level is None:
        # 未知评级：保守不映射
        return NormalizedRating(
            raw=raw, level=None, canonical="未知", direction=direction, confidence=0.3
        )

    canonical = _NAMES[level]
    # 置信度：精确匹配高，变体匹配中高
    confidence = 0.95 if raw in _LEVEL_MAP[level] else 0.85
    return NormalizedRating(
        raw=raw,
        level=level,
        canonical=canonical,
        direction=direction,
        confidence=confidence,
    )


def level_name(level: int | None) -> str:
    """等级数字 → 中文名."""
    if level is None:
        return "未知"
    return _NAMES.get(level, f"等级{level}")
