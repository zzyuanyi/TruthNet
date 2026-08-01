"""fcode 分类边界测试 — 六类输入。"""

from app.domain.events.fcode_taxonomy import classify_sentiment, fcode_category_label


class TestClassification:
    def test_violation_is_negative(self):
        """违纪违规 5507060000 → negative。"""
        label, method, _ = classify_sentiment("5507060000")
        assert label == "negative"
        assert method == "fcode_map"

    def test_dividend_is_neutral(self):
        """利润分配 5107000000 → neutral。"""
        label, _, _ = classify_sentiment("5107000000")
        assert label == "neutral"

    def test_buyback_is_positive(self):
        """回购股权 5219000000 → positive。"""
        label, _, _ = classify_sentiment("5219000000")
        assert label == "positive"

    def test_unknown_fcode_is_unknown(self):
        label, method, _ = classify_sentiment("9999999999")
        assert label == "unknown"
        assert method == "unknown_fcode"

    def test_empty_fcode_is_unknown(self):
        for val in ["", None]:
            label, method, _ = classify_sentiment(val)
            assert label == "unknown"
            assert method == "no_fcode"

    def test_mixed_violation_and_unknown_is_negative(self):
        """违纪违规|未知 → negative（负面优先）。"""
        label, _, _ = classify_sentiment("5507060000|9999999999")
        assert label == "negative"

    def test_category_labels(self):
        assert fcode_category_label("5507060000") == "违纪违规"
        assert fcode_category_label("5107000000") == "利润分配"
        assert fcode_category_label("9999999999") == "未知(fcode_9999999999)"
