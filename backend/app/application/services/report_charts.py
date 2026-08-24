"""PDF 报告图表绘制 — 简约大气金融研报风（8/23 v2 设计）。

风格规范：
  - 色彩：风险语义色（red #ef4444 / orange #f97316 / yellow #eab308 /
    blue #3b82f6 / green #22c55e / unknown #94a3b8）；中性：正文 #1f2937、
    次要 #6b7280、卡片背景 #fafafc、卡片边框 #e5e7eb、网格 #eef1f5。
  - 字体：全部 STSong-Light；标题 10pt、轴标签 6.5pt、页脚 8pt。
  - 组件：① 风险评分卡（大号等级 + 五级分段色带）
         ② 关键指标趋势卡片（中文指标 + 面积渐变 + 最新值）
         ③ 股东持股条形卡片（圆角条 + 百分比）
  - 降级：数据不足跳过对应图；任何绘制异常由调用方 try/except 兜底不阻塞报告。
"""

from __future__ import annotations

from reportlab.graphics.charts.axes import XValueAxis
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
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
RISK_SHORT_CN = {
    "red": "高危",
    "orange": "中高危",
    "yellow": "中等",
    "blue": "低风险",
    "green": "正常",
    "unknown": "未知",
}
_GRID = colors.HexColor("#eef1f5")
_SUBTEXT = colors.HexColor("#6b7280")
_TEXT = colors.HexColor("#1f2937")
_CARD_BG = colors.HexColor("#fafafc")
_CARD_BORDER = colors.HexColor("#e5e7eb")
_ACCENT = colors.HexColor("#2563eb")
_FONT = "STSong-Light"

# 指标英文 → 中文（趋势图标题用；避免显示英文/截断）
METRIC_CN = {
    "gap": "存贷比缺口",
    "cf_to_profit_ratio": "现金流/利润比",
    "cash_to_assets": "存贷比",
    "growth_gap": "营收增速差",
    "gross_margin": "毛利率",
    "oth_rcv_to_assets": "其他应收款占比",
    "net_profit_yoy": "净利润同比",
    "revenue_yoy_gap": "营收增速差",
}


def _period_short(period: str) -> str:
    """20251231 → 2025-12；2025-12-31 → 2025-12。"""
    p = str(period or "")
    if len(p) >= 8 and p[:4].isdigit() and p[4:6].isdigit():
        return f"{p[:4]}-{p[4:6]}"
    if len(p) >= 7 and p[:4].isdigit() and p[5:7].isdigit():
        return p[:7]
    return p


def _fade(color: colors.Color, ratio: float) -> colors.Color:
    """颜色向白色淡化（ratio 0=原色，1=全白）。reportlab Color 无 blend 方法。"""
    return colors.Color(
        color.red + (1 - color.red) * ratio,
        color.green + (1 - color.green) * ratio,
        color.blue + (1 - color.blue) * ratio,
    )


def _cn(value: str) -> str:
    """英文 key → 中文（找不到原样返回）。"""
    return METRIC_CN.get(value, value)


# ── ① 风险评分卡 ─────────────────────────────────────────


def risk_badge_drawing(risk_level: str, overall_score) -> Drawing:
    """风险评分卡：大号等级 + 五级分段色带 + 综合分（宽 470 × 高 84）。"""
    level = str(risk_level or "unknown")
    color = colors.HexColor(RISK_COLORS.get(level, RISK_COLORS["unknown"]))
    short_cn = RISK_SHORT_CN.get(level, level)
    score_txt = (
        f"{overall_score:.3f}"
        if isinstance(overall_score, (int, float))
        else str(overall_score or "—")
    )
    d = Drawing(470, 84)
    # 面板背景
    d.add(Rect(0, 0, 470, 84, rx=9, ry=9, strokeColor=_CARD_BORDER, fillColor=_CARD_BG))
    # 左侧：等级色块（大）
    d.add(Rect(14, 14, 176, 56, rx=8, ry=8, strokeColor=None, fillColor=color))
    d.add(
        String(
            30, 42, "综合风险等级", fontName=_FONT, fontSize=9, fillColor=colors.white
        )
    )
    d.add(String(30, 24, short_cn, fontName=_FONT, fontSize=17, fillColor=colors.white))
    d.add(
        String(
            118,
            24,
            f"分 {score_txt}",
            fontName=_FONT,
            fontSize=11,
            fillColor=colors.white,
        )
    )
    # 右侧：五级分段色带（当前级实色高亮描边，其余淡化）
    order = [
        ("red", "高危"),
        ("orange", "中高危"),
        ("yellow", "中等"),
        ("blue", "低风险"),
        ("green", "正常"),
    ]
    seg_w = 46
    gap = 6
    x0 = 206
    y0 = 32
    for i, (lv, cn) in enumerate(order):
        x = x0 + i * (seg_w + gap)
        base = colors.HexColor(RISK_COLORS[lv])
        is_cur = lv == level
        seg_fill = base if is_cur else _fade(base, 0.68)
        d.add(
            Rect(
                x,
                y0,
                seg_w,
                14,
                rx=4,
                ry=4,
                strokeColor=_ACCENT if is_cur else None,
                strokeWidth=1.5 if is_cur else 0,
                fillColor=seg_fill,
            )
        )
        d.add(
            String(x + 4, y0 - 13, cn, fontName=_FONT, fontSize=7, fillColor=_SUBTEXT)
        )
    # 当前等级说明
    d.add(
        String(
            206,
            8,
            f"当前等级：{short_cn}（综合分 {score_txt}）",
            fontName=_FONT,
            fontSize=7.5,
            fillColor=_SUBTEXT,
        )
    )
    return d


# ── ② 关键指标趋势卡片 ───────────────────────────────────


def trend_drawing(
    title: str, points: list[tuple[str, float]], severity: str
) -> Drawing:
    """单指标趋势卡片（238 × 132pt）。title 建议为中文指标名（如「毛利率（R5）」）。"""
    n = len(points)
    color = colors.HexColor(RISK_COLORS.get(severity, RISK_COLORS["unknown"]))
    # 卡片背景 + 边框
    d = Drawing(238, 132)
    d.add(
        Rect(0, 0, 238, 132, rx=8, ry=8, strokeColor=_CARD_BORDER, fillColor=_CARD_BG)
    )
    # 标题（中文化兜底）
    _title = title
    for k, v in METRIC_CN.items():
        if k in _title:
            _title = _title.replace(k, v)
    d.add(String(14, 112, _title[:18], fontName=_FONT, fontSize=10, fillColor=_TEXT))
    # 最新值（右上）
    latest = points[-1][1]
    d.add(
        String(
            224,
            112,
            f"{_fmt_value(latest)[0]}",
            fontName=_FONT,
            fontSize=9,
            fillColor=color,
            textAnchor="end",
        )
    )
    # 图区
    lx, ly, lw, lh = 30, 16, 194, 74
    # 面积填充（折线下浅色）
    if n >= 2:
        xs = [lx + (i + 0.3) / n * lw for i in range(n)]
        ymin = min(points, key=lambda p: p[1])[1]
        ymax = max(points, key=lambda p: p[1])[1]
        span = (ymax - ymin) or 1.0

        # 简化为线性映射到图高（顶部 10% 留白）
        def y_of(v: float) -> float:
            pad = 8
            return ly + pad + (v - ymin) / span * (lh - 2 * pad)

        poly_points = [
            (xs[0], y_of(points[0][1])),
            *[(xs[i], y_of(points[i][1])) for i in range(1, n)],
            (xs[-1], ly),
            (xs[0], ly),
        ]
        flat: list[float] = [c for pt in poly_points for c in pt]
        light = _fade(color, 0.85)
        d.add(Polygon(flat, strokeColor=None, fillColor=light))
    lp = LinePlot()
    lp.x = lx
    lp.y = ly
    lp.width = lw
    lp.height = lh
    lp.data = [[(i, v) for i, (_p, v) in enumerate(points)]]
    lp.lines[0].strokeColor = color
    lp.lines[0].strokeWidth = 2.4
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
    yaxis = lp.yValueAxis
    yaxis.labels.fontName = _FONT
    yaxis.labels.fontSize = 6.5
    yaxis.labels.fillColor = _SUBTEXT
    yaxis.strokeColor = _GRID
    yaxis.tickLeft = 2
    yaxis.tickRight = 0
    d.add(lp)
    return d


def _fmt_value(v: float) -> tuple[str, str]:
    """数值 → (展示字符串, 单位后缀)。"""
    if abs(v) >= 1000:
        return f"{v:,.0f}", ""
    if abs(v) >= 100:
        return f"{v:.1f}", ""
    return f"{v:.2f}", ""


# ── ③ 股东持股条形卡片 ───────────────────────────────────


def holding_bar_drawing(
    holders: list[tuple[str, float, str]],
) -> Drawing | None:
    """前 N 大股东持股条形卡片（宽 238）。

    holders: [(股东名, 持股比例 %, risk_level), ...]，已按比例降序。
    """
    if len(holders) < 2:
        return None
    names = [h[0] for h in holders]
    pcts = [h[1] for h in holders]
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
    row_h = 22
    pad = 12
    chart_h = row_h * len(holders) + pad
    card_h = chart_h + 34
    d = Drawing(238, card_h)
    d.add(
        Rect(
            0, 0, 238, card_h, rx=8, ry=8, strokeColor=_CARD_BORDER, fillColor=_CARD_BG
        )
    )
    d.add(
        String(
            14,
            card_h - 18,
            "主要股东持股比例",
            fontName=_FONT,
            fontSize=10,
            fillColor=_TEXT,
        )
    )
    # 条形 + 右侧圆角条 + 标签（手绘，保证圆角/留白）
    label_w = 92
    bar_x = label_w + 6
    bar_w = 118
    max_pct = max(pcts) if pcts else 10
    for i, (nm, pct) in enumerate(zip(names, pcts)):
        y = card_h - 34 - (i + 1) * row_h + 4
        # 股东名
        d.add(String(14, y + 3, nm[:9], fontName=_FONT, fontSize=7, fillColor=_SUBTEXT))
        # 条形底（浅灰轨道）
        d.add(Rect(bar_x, y, bar_w, 12, rx=6, ry=6, strokeColor=None, fillColor=_GRID))
        # 条形实心
        w = max(bar_w * (pct / max_pct), 6)
        d.add(Rect(bar_x, y, w, 12, rx=6, ry=6, strokeColor=None, fillColor=bar_color))
        # 百分比标签
        d.add(
            String(
                bar_x + bar_w + 6,
                y + 3,
                f"{pct:.2f}%",
                fontName=_FONT,
                fontSize=7,
                fillColor=_TEXT,
            )
        )
    return d


def truncate_holder(name: str, limit: int = 10) -> str:
    """股东名超长截断（按字符），加省略号。"""
    n = str(name or "")
    return n if len(n) <= limit else n[: limit - 1] + "…"


# ── 趋势数据提取（报告渲染侧复用） ──────────────────────────

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
    """趋势图指标名（中文）：映射表优先，否则 history 首个数值字段英文原样。"""
    key = CHART_KEYS.get(str(rule.get("rule_id") or ""))
    if key:
        return METRIC_CN.get(key, key)
    history = rule.get("history") or []
    for item in history:
        if isinstance(item, dict):
            for k in item:
                if k != "period" and isinstance(item[k], (int, float)):
                    return METRIC_CN.get(k, k)
    return "指标"


def trend_title(rule: dict) -> str:
    """趋势图标题：中文指标名（规则号）。"""
    return f"{trend_metric_name(rule)}（{rule.get('rule_id') or ''}）"


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
