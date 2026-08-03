"""事件聚类核心逻辑单元测试 — Phase C 数据任务 4.

覆盖:
- 公告去重
- fcode 分类聚类
- 时间窗聚类
- 情绪多数判定
- 确定性（同输入同输出）
"""

from app.domain.events.clustering import (
    cluster_announcements,
    dedup_announcements,
    majority_sentiment,
)


def _ann(obj_id, dt, title="公告", fcode="5506010000", sentiment="neutral"):
    return {
        "object_id": obj_id,
        "ann_dt": dt,
        "n_info_title": title,
        "n_info_fcode": fcode,
        "sentiment": sentiment,
    }


def test_dedup_by_object_id():
    anns = [
        _ann("a1", "2026-03-01"),
        _ann("a1", "2026-03-02"),  # 重复
        _ann("a2", "2026-03-03"),
    ]
    out = dedup_announcements(anns)
    assert len(out) == 2
    assert [a["object_id"] for a in out] == ["a1", "a2"]


def test_cluster_by_fcode_and_time_window():
    anns = [
        _ann("a1", "2026-03-01", fcode="5506010000"),  # 股东大会
        _ann("a2", "2026-03-10", fcode="5506010000"),  # 10 天内 → 同簇
        _ann("a3", "2026-05-01", fcode="5506010000"),  # 隔 >30 天 → 新簇
        _ann("a4", "2026-03-02", fcode="5507060000"),  # 违纪违规 → 不同类别
    ]
    clusters = cluster_announcements(anns)
    ids = [sorted(c["object_id"] for c in cl) for cl in clusters]
    assert ["a1", "a2"] in ids  # 同 fcode 同时间窗
    assert ["a3"] in ids  # 同 fcode 不同时间窗
    assert ["a4"] in ids  # 不同 fcode


def test_cluster_deterministic():
    anns = [
        _ann("a1", "2026-03-01"),
        _ann("a2", "2026-03-10"),
        _ann("a3", "2026-05-01"),
    ]
    c1 = cluster_announcements(anns)
    c2 = cluster_announcements(anns)
    assert c1 == c2


def test_majority_sentiment_negative():
    anns = [
        _ann("a1", "d", sentiment="negative"),
        _ann("a2", "d", sentiment="negative"),
        _ann("a3", "d", sentiment="neutral"),
    ]
    label, score = majority_sentiment(anns)
    assert label == "negative"
    assert score < 0


def test_majority_sentiment_fallback_fcode():
    # 无已存 sentiment，用 fcode 映射（质押冻结 → negative）
    anns = [_ann("a1", "d", fcode="5203000000", sentiment="")]
    label, score = majority_sentiment(anns)
    assert label == "negative"


def test_majority_sentiment_empty():
    label, score = majority_sentiment([])
    assert label == "neutral"
    assert score == 0.0
