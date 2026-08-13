"""评级规范化与拐点检测单元测试 — Phase C 数据任务 5.

覆盖:
- 评级规范化（原始 → 有序等级，变体处理）
- direction 规范化（下调/上调/维持）
- 低置信度跳过
- 同季度 >=2 家独立机构下调 → orange
- 确定性 inflection_id
"""

from app.domain.events.rating_inflection import (
    RatingChangeRecord,
    detect_inflections,
)
from app.domain.events.rating_normalizer import (
    MIN_CONFIDENCE,
    normalize_rating,
)


# ── 评级规范化 ─────────────────────────────────────────────


def test_normalize_buy():
    r = normalize_rating("买入")
    assert r.level == 4
    assert r.canonical == "买入"
    assert r.confidence >= 0.9


def test_normalize_strong_buy():
    r = normalize_rating("强烈推荐")
    assert r.level == 5


def test_normalize_hold():
    r = normalize_rating("中性")
    assert r.level == 2


def test_normalize_sell():
    r = normalize_rating("减持")
    assert r.level == 1


def test_normalize_variant_suffix():
    r = normalize_rating("买入-A")
    assert r.level == 4
    assert r.confidence >= 0.8


def test_normalize_unknown_low_confidence():
    r = normalize_rating("其他评级")
    assert r.level is None
    assert r.confidence < MIN_CONFIDENCE  # 低置信度应被跳过


def test_direction_down():
    r = normalize_rating("增持", "下调")
    assert r.direction == "down"


def test_direction_up():
    r = normalize_rating("买入", "上调")
    assert r.direction == "up"


def test_direction_keep():
    r = normalize_rating("增持", "维持")
    assert r.direction == "keep"


def test_empty_raw():
    r = normalize_rating(None)
    assert r.level is None
    assert r.confidence == 0.0


# ── 拐点检测 ───────────────────────────────────────────────


def _rec(wc, quarter, inst, direction="down"):
    return RatingChangeRecord(
        wind_code=wc, quarter=quarter, institution=inst, direction=direction
    )


def test_two_institutions_downgrade_orange():
    records = [
        _rec("600001.SH", "2026Q1", "机构A"),
        _rec("600001.SH", "2026Q1", "机构B"),
    ]
    infs = detect_inflections(records)
    assert len(infs) == 1
    assert infs[0].severity == "orange"
    assert set(infs[0].down_institutions) == {"机构A", "机构B"}


def test_single_downgrade_yellow():
    records = [_rec("600001.SH", "2026Q1", "机构A")]
    infs = detect_inflections(records)
    assert len(infs) == 1
    assert infs[0].severity == "yellow"


def test_keep_only_no_inflection():
    records = [_rec("600001.SH", "2026Q1", "机构A", direction="keep")]
    assert detect_inflections(records) == []


def test_duplicate_institution_deduplicated():
    # 同一机构两次下调只算 1 家独立机构
    records = [
        _rec("600001.SH", "2026Q1", "机构A"),
        _rec("600001.SH", "2026Q1", "机构A"),
    ]
    infs = detect_inflections(records)
    assert len(infs) == 1
    assert infs[0].severity == "yellow"


def test_inflection_id_deterministic():
    records = [
        _rec("600001.SH", "2026Q1", "机构A"),
        _rec("600001.SH", "2026Q1", "机构B"),
    ]
    infs1 = detect_inflections(records)
    infs2 = detect_inflections(records)
    assert infs1[0].inflection_id == infs2[0].inflection_id
    assert infs1[0].inflection_id.startswith("inf_")
