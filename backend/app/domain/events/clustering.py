"""事件聚类核心逻辑 — Phase C 数据任务 4.

聚类方法: semantic_rule_fcode_timewindow_v1
  - 公告清洗去重（object_id）
  - fcode 一级分类
  - 同类内按时间窗聚类（默认 30 天）
  - sentiment 取簇内多数（来源：已存 sentiment 或 fcode 映射）

无网络、无 LLM；cluster_method 只写 semantic_rule_*（不伪称 LLM）。
"""

from __future__ import annotations

from datetime import date

from app.domain.events.fcode_taxonomy import classify_sentiment

TIME_WINDOW_DAYS = 30


def first_fcode(ann: dict) -> str:
    """取公告主 fcode（多 fcode 取第一个）。"""
    raw = str(ann.get("n_info_fcode") or "")
    return raw.split("|")[0].strip() if raw else ""


def dedup_announcements(anns: list[dict]) -> list[dict]:
    """按 object_id 去重（保留首次出现）。"""
    seen: set[str] = set()
    out: list[dict] = []
    for a in anns:
        oid = str(a.get("object_id") or "")
        if oid in seen:
            continue
        seen.add(oid)
        out.append(a)
    return out


def cluster_announcements(
    anns: list[dict], time_window_days: int = TIME_WINDOW_DAYS
) -> list[list[dict]]:
    """按 fcode 类别 + 时间窗聚类.

    anns 需已按 ann_dt 升序。返回簇列表，每簇为公告 dict 列表。
    日期无法解析的公告单独成簇（不丢失来源）。
    """
    by_fcode: dict[str, list[dict]] = {}
    for a in anns:
        by_fcode.setdefault(first_fcode(a), []).append(a)

    clusters: list[list[dict]] = []
    for items in by_fcode.values():
        current: list[dict] = []
        for a in items:
            if not current:
                current = [a]
                continue
            last_dt = current[-1].get("ann_dt")
            this_dt = a.get("ann_dt")
            gap = time_window_days + 1
            try:
                gap = (
                    date.fromisoformat(str(this_dt)) - date.fromisoformat(str(last_dt))
                ).days
            except (ValueError, TypeError):
                pass
            if gap <= time_window_days:
                current.append(a)
            else:
                if current:
                    clusters.append(current)
                current = [a]
        if current:
            clusters.append(current)
    return clusters


def majority_sentiment(anns: list[dict]) -> tuple[str, float]:
    """簇内多数情绪 + 得分.

    来源优先级: 已存 sentiment > fcode 映射。方法随结果返回。
    """
    counts: dict[str, int] = {}
    for a in anns:
        stored = str(a.get("sentiment") or "")
        if stored in ("positive", "negative", "neutral"):
            label = stored
        else:
            raw_fcode = str(a.get("n_info_fcode") or "")
            label, _method, _conf = classify_sentiment(raw_fcode)
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return "neutral", 0.0
    majority = max(counts, key=lambda k: (counts[k], k))
    score = {
        "negative": -0.6,
        "positive": 0.6,
        "neutral": 0.0,
        "mixed": 0.0,
        "unknown": 0.0,
    }.get(majority, 0.0)
    return majority, score
