"""实体名称标准化单元测试 — V12 Task 6."""

from app.infrastructure.graph.normalizer import (
    extract_wind_code_suffix,
    make_display_name,
    normalize_entity_name,
)


class TestNormalizeEntityName:
    def test_ascii_lowercase(self):
        assert normalize_entity_name("ABC Corp") == "abc corp"

    def test_fullwidth_to_halfwidth(self):
        # 全角字母
        result = normalize_entity_name("ＡＢＣ")
        assert result == "abc"

    def test_leading_trailing_whitespace(self):
        assert normalize_entity_name("  康美药业  ") == "康美药业"

    def test_multiple_inner_spaces(self):
        assert normalize_entity_name("康美  药业") == "康美 药业"

    def test_nfkc_normalization(self):
        # 全角数字
        result = normalize_entity_name("１２３")
        assert result == "123"

    def test_empty_string(self):
        assert normalize_entity_name("") == ""

    def test_none_equivalent(self):
        assert normalize_entity_name("") == ""


class TestExtractWindCodeSuffix:
    def test_sh_suffix(self):
        code, suffix = extract_wind_code_suffix("600519.SH")
        assert code == "600519"
        assert suffix == ".SH"

    def test_sz_suffix(self):
        code, suffix = extract_wind_code_suffix("000001.SZ")
        assert code == "000001"
        assert suffix == ".SZ"

    def test_no_suffix(self):
        code, suffix = extract_wind_code_suffix("600518")
        assert code == "600518"
        assert suffix is None

    def test_lowercase(self):
        code, suffix = extract_wind_code_suffix("600518.sh")
        assert code == "600518"
        assert suffix == ".SH"

    def test_none_input(self):
        code, suffix = extract_wind_code_suffix(None)
        assert code is None
        assert suffix is None

    def test_invalid_format(self):
        code, suffix = extract_wind_code_suffix("INVALID")
        assert code == "INVALID"


class TestMakeDisplayName:
    def test_trim(self):
        assert make_display_name("  康美药业  ") == "康美药业"

    def test_preserve_case(self):
        assert make_display_name("ST康美") == "ST康美"
