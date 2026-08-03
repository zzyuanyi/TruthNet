"""研报评级拐点检测 — Phase C 数据任务 5.

规则（开发手册 数据任务 5）:
  同一公司同一季度，至少 2 家独立机构发生评级下调 → orange warning。

输入: 规范化后的评级变更记录列表（from rating_changes 或 research_reports）。
输出: 结构化拐点列表，含确定性 inflection_id 与涉及的机构。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# 独立机构下调阈值：≥2 家 → orange
DOWN_ORANGE_THRESHOLD = 2


@dataclass(frozen=True)
class RatingChangeRecord:
    """单条评级变更（规范化后）."""

    wind_code: str
    quarter: str  # YYYYQn
    institution: str
    direction: str  # down / up / keep
    previous_rating: str | None = None
    current_rating: str | None = None
    report_id: str | None = None
    published_at: str | None = None
    confidence: float = 1.0


@dataclass
class RatingInflection:
    """评级拐点."""

    inflection_id: str
    wind_code: str
    quarter: str
    severity: str  # orange / yellow / none
    down_institutions: list[str] = field(default_factory=list)
    up_institutions: list[str] = field(default_factory=list)
    detail: str = ""


def _inflection_id(wind_code: str, quarter: str, direction: str) -> str:
    raw = f"inflection|{wind_code}|{quarter}|{direction}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"inf_{digest}"


def detect_inflections(
    records: list[RatingChangeRecord],
) -> list[RatingInflection]:
    """检测评级拐点.

    - 同 (wind_code, quarter) 独立下调机构 >= DOWN_ORANGE_THRESHOLD → orange
    - 恰好 1 家下调 → yellow
    - 无下调 → 不产生拐点
    """
    # 按 (wind_code, quarter) 分组
    groups: dict[tuple[str, str], list[RatingChangeRecord]] = {}
    for r in records:
        if r.direction not in ("down", "up"):
            continue
        groups.setdefault((r.wind_code, r.quarter), []).append(r)

    inflections: list[RatingInflection] = []
    for (wind_code, quarter), recs in sorted(groups.items()):
        # 独立机构（去重）
        down_insts = sorted({r.institution for r in recs if r.direction == "down"})
        up_insts = sorted({r.institution for r in recs if r.direction == "up"})
        if not down_insts:
            continue
        if len(down_insts) >= DOWN_ORANGE_THRESHOLD:
            severity = "orange"
            detail = (
                f"{quarter} {len(down_insts)} 家独立机构下调评级"
                f"（{'、'.join(down_insts[:3])}）"
            )
        else:
            severity = "yellow"
            detail = (
                f"{quarter} 有 1 家机构下调评级（{down_insts[0]}），未达橙色预警阈值"
            )
        inflections.append(
            RatingInflection(
                inflection_id=_inflection_id(wind_code, quarter, "down"),
                wind_code=wind_code,
                quarter=quarter,
                severity=severity,
                down_institutions=down_insts,
                up_institutions=up_insts,
                detail=detail,
            )
        )
    return inflections
