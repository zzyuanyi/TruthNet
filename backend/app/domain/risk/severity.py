"""Canonical risk severity helpers shared by scoring and answer text."""

from __future__ import annotations

RISK_LEVEL_RANK: dict[str, int] = {
    "unknown": 0,
    "green": 1,
    "blue": 2,
    "yellow": 3,
    "orange": 4,
    "red": 5,
}

RISK_LEVEL_LABELS: dict[str, str] = {
    "unknown": "未知",
    "green": "绿色",
    "blue": "蓝色",
    "yellow": "黄色",
    "orange": "橙色",
    "red": "红色",
}


def normalize_risk_level(value: object, default: str = "unknown") -> str:
    """Return a canonical machine risk level without guessing unknown values."""
    level = str(value or "").strip().lower()
    return level if level in RISK_LEVEL_RANK else default


def highest_risk_level(values, default: str = "unknown") -> str:
    """Return the highest canonical level from an iterable."""
    normalized = [normalize_risk_level(value) for value in values]
    if not normalized:
        return default
    return max(normalized, key=lambda level: RISK_LEVEL_RANK[level])


def risk_level_label(value: object) -> str:
    """Map a machine level to user-facing Chinese while preserving unknowns."""
    level = normalize_risk_level(value)
    return RISK_LEVEL_LABELS[level]


def event_signal_severity(item: dict) -> str:
    """Derive a conservative severity from an announcement or event cluster."""
    explicit = normalize_risk_level(item.get("severity"))
    if explicit != "unknown":
        return explicit

    text = " ".join(
        str(item.get(key) or "") for key in ("title", "topic", "summary", "category")
    ).lower()
    severe_terms = ("立案", "处罚", "重大违法", "退市", "欺诈", "造假")
    if any(term in text for term in severe_terms):
        return "red"

    score = item.get("sentiment_score")
    try:
        if score is not None and float(score) <= -0.8:
            return "red"
    except (TypeError, ValueError):
        pass
    if str(item.get("sentiment") or "").lower() == "negative":
        return "orange"
    return "green"
