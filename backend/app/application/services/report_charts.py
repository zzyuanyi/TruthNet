"""PDF 报告图表绘制 — 统一风格规范（8/23 设计）。

风格规范：
  - 色彩：与前端风险色一致（red #ef4444 / orange #f97316 / yellow #eab308 /
    blue #3b82f6 / green #22c55e / unknown #94a3b8）；网格 #e4e4e7、边框 #d4d4d8。
  - 字体：全部 STSong-Light；图表标题 9pt、正文 10pt、轴标签 7pt。
  - 组件：① 综合风险色块（圆角矩形 + 五级图例）
         ② 关键指标趋势折线（LinePlot，规则 severity 色，期次短格式 X 轴）
         ③ 股东持股横向条形图（HorizontalBarChart，risk_level 色 + 百分比标签）
  - 降级：数据不足跳过对应图；任何绘制异常由调用方 try/except 兜底不阻塞报告。
"""

from __future__ import annotations

from reportlab.graphics.charts.axes import XValueAxis
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors

RISK_COLORS = {
    "red": "#ef4444",
    "orange": "#f97316",
    "yellow": "#eab308",
    "blue": "#3b82f6",
    "green": "#22c55e",
    "unknown": "#94a3b8",
}
RISK_LEVEL_CN = {
    "red": "红色（高危）",
    "orange": "橙色（中高危）",
    "yellow": "黄色（中等）",
    "blue": "蓝色（低风险）",
    "green": "绿色（正常）",
    "unknown": "未知（数据不足）",
}
_GRID = colors.HexColor("#e4e4e7")
_BORDER = colors.HexColor("#d4d4d8")
_SUBTEXT = colors.HexColor("#52525b")
_FONT = "STSong-Light"


def _period_short(period: str) -> str:
    """20251231 → 2025-12；2025-12-31 → 2025-12。"""
    p = str(period or "")
    if len(p) >= 8 and p[:4].isdigit() and p[4:6].isdigit():
        return f"{p[:4]}-{p[4:6]}"
    if len(p) >= 7 and p[:4].isdigit() and p[5:7].isdigit():
        return p[:7]
    return p


# ── ① 综合风险色块 ─────────────────────────────────────────


def risk_badge_drawing(risk_level: str, overall_score) -> Drawing:
    """当前风险等级大色块 + 五级色点图例（宽 460 × 高 46）。"""
    level = str(risk_level or "unknown")
    color = colors.HexColor(RISK_COLORS.get(level, RISK_COLORS["unknown"]))
    level_cn = RISK_LEVEL_CN.get(level, level)
    score_txt = (
        f"{overall_score:.3f}"
        if isinstance(overall_score, (int, float))
        else str(overall_score or "—")
    )
    d = Drawing(460, 46)
    d.add(Rect(0, 6, 300, 34, rx=6, ry=6, strokeColor=_BORDER, fillColor=color))
    d.add(
        String(
            16,
            18,
            f"综合风险等级：{level_cn}",
            fontName=_FONT,
            fontSize=13,
            fillColor=colors.white,
        )
    )
    d.add(
        String(
            186,
            18,
            f"综合分：{score_txt}",
            fontName=_FONT,
            fontSize=11,
            fillColor=colors.white,
        )
    )
    # 五级图例（右区，7.5pt 灰字 + 色点）
    order = [
        ("red", "高危"),
        ("orange", "中高危"),
        ("yellow", "中等"),
        ("blue", "低风险"),
        ("green", "正常"),
    ]
    x = 316
    y = 28
    for lv, cn in order:
        d.add(
            Rect(
                x,
                y + 3,
                8,
                8,
                rx=2,
                ry=2,
                strokeColor=None,
                fillColor=colors.HexColor(RISK_COLORS[lv]),
            )
        )
        d.add(String(x + 11, y, cn, fontName=_FONT, fontSize=7.5, fillColor=_SUBTEXT))
        x += 8 + len(cn) * 7.5 + 14
    return d


# ── ② 关键指标趋势折线 ─────────────────────────────────────


def trend_drawing(
    title: str, points: list[tuple[str, float]], severity: str
) -> Drawing:
    """单规则趋势折线（245 × 95pt）。points: [(period, value), ...]，按时间升序。"""
    n = len(points)
    color = colors.HexColor(RISK_COLORS.get(severity, RISK_COLORS["unknown"]))
    d = Drawing(245, 95)
    d.add(String(2, 82, title[:16], fontName=_FONT, fontSize=9, fillColor=colors.black))
    lp = LinePlot()
    lp.x = 34
    lp.y = 18
    lp.width = 205
    lp.height = 58
    lp.data = [[(i, v) for i, (_p, v) in enumerate(points)]]
    lp.lines[0].strokeColor = color
    lp.lines[0].strokeWidth = 2
    # X 轴：期次短格式，每 2 期一个刻度（最多 4 个 label 防拥挤）
    xaxis = XValueAxis()
    xaxis.valueMin = -0.3
    xaxis.valueMax = n - 0.7
    xaxis.valueStep = 2
    xaxis.labelTextFormat = lambda v, _p=points: (
        _period_short(_p[int(v)][0]) if 0 <= int(v) < n else ""
    )
    xaxis.labels.fontName = _FONT
    xaxis.labels.fontSize = 6.5
    xaxis.labels.fillColor = _SUBTEXT
    xaxis.strokeColor = _GRID
    xaxis.tickUp = 2
    xaxis.tickDown = 0
    lp.xValueAxis = xaxis
    # Y 轴
    yaxis = lp.yValueAxis
    yaxis.labels.fontName = _FONT
    yaxis.labels.fontSize = 6.5
    yaxis.labels.fillColor = _SUBTEXT
    yaxis.strokeColor = _GRID
    yaxis.tickLeft = 2
    yaxis.tickRight = 0
    d.add(lp)
    return d


# ── ③ 股东持股横向条形图 ───────────────────────────────────


def holding_bar_drawing(
    holders: list[tuple[str, float, str]],
) -> Drawing | None:
    """前 N 大股东持股横向条形图（宽 250）。

    holders: [(股东名, 持股比例 %, risk_level), ...]，已按比例降序。
    """
    if len(holders) < 2:
        return None
    names = [h[0] for h in holders]
    pcts = [h[1] for h in holders]
    # 条色统一为最高风险等级色（任一红→红，全绿→绿）
    risk_rank = {
        "red": 0,
        "orange": 1,
        "yellow": 2,
        "blue": 3,
        "green": 4,
        "unknown": 5,
    }
    top_risk = min(holders, key=lambda h: risk_rank.get(h[2], 5))[2]
    bar_color = colors.HexColor(RISK_COLORS.get(top_risk, RISK_COLORS["green"]))
    row_h = 20
    chart_h = row_h * len(holders) + 12
    d = Drawing(250, chart_h + 14)
    d.add(
        String(
            2,
            chart_h + 2,
            "主要股东持股比例",
            fontName=_FONT,
            fontSize=9,
            fillColor=colors.black,
        )
    )
    bc = HorizontalBarChart()
    bc.x = 118
    bc.y = 8
    bc.width = 96
    bc.height = row_h * len(holders)
    bc.data = [pcts]
    bc.categoryAxis.categoryNames = names
    bc.categoryAxis.labels.fontName = _FONT
    bc.categoryAxis.labels.fontSize = 6.5
    bc.categoryAxis.labels.fillColor = _SUBTEXT
    bc.categoryAxis.strokeColor = _GRID
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = max(pcts) * 1.25 if max(pcts) > 0 else 10
    bc.valueAxis.visible = False  # 数值轴隐藏，只留条形+标签
    bc.valueAxis.strokeColor = _GRID
    bc.bars[0].fillColor = bar_color
    bc.bars[0].strokeColor = None
    bc.barLabelFormat = "%.2f%%"
    bc.barLabels.fontName = _FONT
    bc.barLabels.fontSize = 6.5
    bc.barLabels.fillColor = _SUBTEXT
    d.add(bc)
    return d


def truncate_holder(name: str, limit: int = 10) -> str:
    """股东名超长截断（按字符），加省略号。"""
    n = str(name or "")
    return n if len(n) <= limit else n[: limit - 1] + "…"


# ── 趋势数据提取（报告渲染侧复用） ──────────────────────────

# 与前端 RuleCard/FinanceTrendOverview 一致的规则→history 数值字段映射；
# 未列出的规则（R6/R7 等）回退取 history 中第一个数值字段。
CHART_KEYS = {
    "R1": "gap",
    "R2": "cf_to_profit_ratio",
    "R3": "cash_to_assets",
    "R4": "growth_gap",
    "R5": "gross_margin",
}


def extract_trend_points(rule: dict) -> list[tuple[str, float]] | None:
    """从规则 history 提取 (period, value) 序列；不足 2 期返回 None。"""
    history = rule.get("history") or []
    key = CHART_KEYS.get(str(rule.get("rule_id") or ""))
    pts: list[tuple[str, float]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        period = str(item.get("period") or "")
        if key:
            v = item.get(key)
        else:
            v = next(
                (
                    item[k]
                    for k in item
                    if k != "period" and isinstance(item[k], (int, float))
                ),
                None,
            )
        if isinstance(v, (int, float)):
            pts.append((period, float(v)))
    return pts if len(pts) >= 2 else None


def trend_metric_name(rule: dict) -> str:
    """趋势图指标名（用于标题）：映射表优先，否则 history 首个数值字段。"""
    key = CHART_KEYS.get(str(rule.get("rule_id") or ""))
    if key:
        return key
    history = rule.get("history") or []
    for item in history:
        if isinstance(item, dict):
            for k in item:
                if k != "period" and isinstance(item[k], (int, float)):
                    return k
    return "value"


def pick_trend_rules(rules: list[dict], limit: int = 4) -> list[dict]:
    """选可绘图规则：触发/关注优先，再按 R1-R7 顺序；最多 limit 条。"""
    rank = {
        "triggered": 0,
        "attention": 1,
        "not_triggered": 2,
        "insufficient_data": 3,
        "not_applicable": 4,
    }
    order = {f"R{i}": i for i in range(1, 8)}
    candidates = [r for r in rules if extract_trend_points(r) is not None]
    candidates.sort(
        key=lambda r: (
            rank.get(str(r.get("status")), 5),
            order.get(str(r.get("rule_id")), 99),
        )
    )
    return candidates[:limit]
