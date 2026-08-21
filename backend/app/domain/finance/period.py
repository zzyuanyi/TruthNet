"""报告期解析工具 — Phase C 后端任务 13.

统一解析:
  - YYYYMMDD      → 原样（20260331）
  - YYYY-MM-DD    → 20260331
  - YYYYQ1~YYYYQ4 → 对应季末日期（2026Q2 → 20260630，绝不产生 2026Q201）

用于 comparisons 端点 as_of 解析，避免非法日期。
"""

from __future__ import annotations

import re
from datetime import date

_QUARTER_END = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}


def normalize_period(value: str | None) -> str | None:
    """把各种报告期格式规范化为 YYYYMMDD；无法解析返回 None。"""
    if not value:
        return None
    raw = str(value).strip()

    # YYYYMMDD
    if re.fullmatch(r"\d{8}", raw):
        return raw if is_valid_period(raw) else None

    # YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        normalized = f"{m.group(1)}{m.group(2)}{m.group(3)}"
        return normalized if is_valid_period(normalized) else None

    # YYYYQn
    m = re.fullmatch(r"(\d{4})[Qq]([1-4])", raw)
    if m:
        year, q = m.group(1), int(m.group(2))
        return f"{year}{_QUARTER_END[q]}"

    # YYYYQn → 兼容 "2026 Q2" 带空格
    m = re.fullmatch(r"(\d{4})\s*[Qq]\s*([1-4])", raw)
    if m:
        year, q = m.group(1), int(m.group(2))
        return f"{year}{_QUARTER_END[q]}"

    return None


def is_valid_period(value: str) -> bool:
    """校验 YYYYMMDD 基本合法性（月份 01-12，日按季度末）。"""
    if not re.fullmatch(r"\d{8}", value):
        return False
    try:
        date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return False
    return True


_QUARTER_END_MMDD = ("0331", "0630", "0930", "1231")


def is_quarter_end(period: str) -> bool:
    """YYYYMMDD 是否为完整季度末日期（0331/0630/0930/1231）。

    仅月份匹配不够——20240330 的月份是 3 但日期不是季度末，返回 False。
    （8.11：从 rule_r2 提取为公共函数，R2 与 CV-NUM-01 共用）
    """
    if len(period) != 8 or not period.isdigit():
        return False
    return period[4:] in _QUARTER_END_MMDD


def next_quarter(period: str) -> str | None:
    """YYYYMMDD 报告期的下一季度末日期（跨年 1231→0331 正常连续）。

    非法或非季度末期返回 None（20240330 → None）。
    """
    if not is_quarter_end(period):
        return None
    y, m = int(period[:4]), int(period[4:6])
    m += 3
    if m > 12:
        m -= 12
        y += 1
    return f"{y}{_QUARTER_END_MMDD[(m // 3) - 1]}"
