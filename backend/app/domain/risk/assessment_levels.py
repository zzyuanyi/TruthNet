"""risk_assessments.level 表契约 — v3.3.3 收口批次 D（方案 §3.5/§5 D1）。

轻量风险比较只消费 risk_assessments 表的等级契约
none/low/medium/high/critical（表注释见
infrastructure/persistence/models.py 的 RiskAssessment.level），
排序与展示完全使用本契约。

注意：与主系统 RiskOutput 的 canonical 等级
（unknown/green/blue/yellow/orange/red，见 domain/risk/severity.py）
是两套独立契约——未经业务确认不得猜测 raw→canonical 映射
（不得把 low 直接猜成 green、把 critical 直接猜成 red）。
"""

from __future__ import annotations

RISK_LEVEL_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

RISK_LEVEL_LABELS: dict[str, str] = {
    "none": "无",
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重",
}
