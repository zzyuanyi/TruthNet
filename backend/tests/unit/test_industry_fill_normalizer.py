"""normalizer 单元测试（档案 v1.1 §5.2/§8/§10.1）。"""

from __future__ import annotations

from backend.app.application.services.industry_fill import normalizer
from backend.app.application.services.industry_fill.constants import SW_L1_ALLOWED


class TestNormalizeOptionalText:
    def test_none_and_placeholders_become_none(self):
        assert normalizer.normalize_optional_text(None) is None
        assert normalizer.normalize_optional_text("") is None
        assert normalizer.normalize_optional_text("  ") is None
        assert normalizer.normalize_optional_text("nan") is None
        assert normalizer.normalize_optional_text("None") is None
        assert normalizer.normalize_optional_text("null") is None
        assert normalizer.normalize_optional_text("  NaN  ") is None
        assert normalizer.normalize_optional_text(float("nan")) is None

    def test_valid_text_kept_stripped(self):
        assert normalizer.normalize_optional_text(" 白酒 ") == "白酒"
        assert normalizer.normalize_optional_text(42) == "42"


class TestNormalizeL1:
    def test_allowlist_hit(self):
        assert normalizer.normalize_l1("食品饮料") == "食品饮料"
        assert normalizer.normalize_l1(" 医药生物 ") == "医药生物"

    def test_not_in_allowlist_rejected(self):
        assert normalizer.normalize_l1("食品饮料X") is None
        assert normalizer.normalize_l1("") is None
        assert normalizer.normalize_l1("nan") is None

    def test_allowlist_has_31_shenwan_l1(self):
        assert len(SW_L1_ALLOWED) == 31


class TestMapL2ToL1:
    def test_exact_mapping(self):
        assert normalizer.map_l2_to_l1("白酒Ⅱ") == ("食品饮料", "白酒Ⅱ")
        assert normalizer.map_l2_to_l1("半导体") == ("电子", "半导体")

    def test_curated_alias(self):
        # 东财名"白酒"→申万二级"白酒Ⅱ"（档案 v1.1 §5.2 别名差异）
        assert normalizer.map_l2_to_l1("白酒") == ("食品饮料", "白酒Ⅱ")

    def test_fullwidth_normalized(self):
        assert normalizer.map_l2_to_l1("ＩＴ服务Ⅱ") == ("计算机", "IT服务Ⅱ")

    def test_unknown_l2_unmapped_not_guessed(self):
        l1, l2 = normalizer.map_l2_to_l1("神秘未知行业")
        assert l1 is None
        assert l2 == "神秘未知行业"

    def test_empty_value(self):
        assert normalizer.map_l2_to_l1("") == (None, None)
        assert normalizer.map_l2_to_l1(None) == (None, None)

    def test_hardcoded_table_values_all_in_allowlist(self):
        assert set(normalizer.L2_TO_L1.values()) <= SW_L1_ALLOWED
