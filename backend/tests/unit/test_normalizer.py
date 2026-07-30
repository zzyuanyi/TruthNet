"""Wind Code 规范化器 — 单元测试.

验证 P1 统一 Wind Code helper 的所有格式和边界情况。
"""

import pytest

from backend.app.infrastructure.graph.normalizer import (
    entity_id_to_wind_code,
    get_exchange_code,
    infer_suffix_from_digits,
    make_listed_company_entity_id,
    normalize_wind_code,
    parse_entity_id,
    parse_wind_code,
)


class TestParseWindCode:
    """parse_wind_code 测试."""

    def test_sh_with_suffix(self):
        assert parse_wind_code("600518.SH") == ("600518", "SH")

    def test_sz_with_suffix(self):
        assert parse_wind_code("000001.SZ") == ("000001", "SZ")

    def test_xshg_normalized(self):
        assert parse_wind_code("600518.XSHG") == ("600518", "SH")

    def test_xshe_normalized(self):
        assert parse_wind_code("000001.XSHE") == ("000001", "SZ")

    def test_bj_with_suffix(self):
        assert parse_wind_code("430047.BJ") == ("430047", "BJ")

    def test_bare_code(self):
        assert parse_wind_code("600518") == ("600518", None)

    def test_lowercase_suffix(self):
        assert parse_wind_code("600518.sh") == ("600518", "SH")

    def test_stripped_whitespace(self):
        assert parse_wind_code("  600518.SH  ") == ("600518", "SH")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_wind_code("60051.SH")

    def test_invalid_suffix_raises(self):
        with pytest.raises(ValueError):
            parse_wind_code("600518.XX")

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            parse_wind_code(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_wind_code("")


class TestInferSuffix:
    """infer_suffix_from_digits 测试."""

    def test_sh_prefix(self):
        assert infer_suffix_from_digits("600518") == "SH"

    def test_sz_prefix_0(self):
        assert infer_suffix_from_digits("000001") == "SZ"

    def test_sz_prefix_3(self):
        assert infer_suffix_from_digits("300750") == "SZ"

    def test_bj_prefix_4(self):
        assert infer_suffix_from_digits("430047") == "BJ"

    def test_bj_prefix_8(self):
        assert infer_suffix_from_digits("830799") == "BJ"

    def test_bj_prefix_9(self):
        assert infer_suffix_from_digits("920123") == "BJ"

    def test_unknown_prefix_returns_none(self):
        assert infer_suffix_from_digits("700001") is None

    def test_invalid_length_returns_none(self):
        assert infer_suffix_from_digits("60051") is None


class TestNormalizeWindCode:
    """normalize_wind_code 测试."""

    def test_full_sh(self):
        assert normalize_wind_code("600518.SH") == "600518.SH"

    def test_full_sz(self):
        assert normalize_wind_code("000001.SZ") == "000001.SZ"

    def test_full_bj(self):
        assert normalize_wind_code("430047.BJ") == "430047.BJ"

    def test_xshg_to_sh(self):
        assert normalize_wind_code("600518.XSHG") == "600518.SH"

    def test_xshe_to_sz(self):
        assert normalize_wind_code("000001.XSHE") == "000001.SZ"

    def test_bare_infer_sh(self):
        assert normalize_wind_code("600518") == "600518.SH"

    def test_bare_infer_sz(self):
        assert normalize_wind_code("000001") == "000001.SZ"

    def test_bare_infer_bj(self):
        assert normalize_wind_code("430047") == "430047.BJ"

    def test_bare_infer_bj_8(self):
        assert normalize_wind_code("830799") == "830799.BJ"

    def test_bare_infer_bj_9(self):
        assert normalize_wind_code("920123") == "920123.BJ"

    def test_lowercase(self):
        assert normalize_wind_code("600518.sh") == "600518.SH"

    def test_whitespace(self):
        assert normalize_wind_code("  000001.SZ  ") == "000001.SZ"

    def test_ambiguous_fail_closed(self):
        """无法推断的裸代码必须 fail-closed，不得默认 .SH."""
        with pytest.raises(ValueError, match="无法推断"):
            normalize_wind_code("700001")

    def test_ambiguous_no_fail(self):
        """fail_on_ambiguous=False 时返回裸代码."""
        assert normalize_wind_code("700001", fail_on_ambiguous=False) == "700001"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            normalize_wind_code("not-a-code")


class TestEntityId:
    """entity_id 生成和解析测试."""

    def test_make_sh(self):
        assert make_listed_company_entity_id("600518.SH") == "company_600518_SH"

    def test_make_sz(self):
        assert make_listed_company_entity_id("000001.SZ") == "company_000001_SZ"

    def test_make_bj(self):
        assert make_listed_company_entity_id("430047.BJ") == "company_430047_BJ"

    def test_make_from_xshg(self):
        assert make_listed_company_entity_id("600518.XSHG") == "company_600518_SH"

    def test_make_from_bare(self):
        assert make_listed_company_entity_id("600518") == "company_600518_SH"

    def test_parse_valid(self):
        assert parse_entity_id("company_600518_SH") == ("600518", "SH")

    def test_parse_sz(self):
        assert parse_entity_id("company_000001_SZ") == ("000001", "SZ")

    def test_parse_bj(self):
        assert parse_entity_id("company_430047_BJ") == ("430047", "BJ")

    def test_parse_invalid_returns_none(self):
        assert parse_entity_id("ent_abc123") is None

    def test_parse_old_format_returns_none(self):
        assert parse_entity_id("600518") is None

    def test_entity_id_to_wind_code(self):
        assert entity_id_to_wind_code("company_600518_SH") == "600518.SH"
        assert entity_id_to_wind_code("company_000001_SZ") == "000001.SZ"
        assert entity_id_to_wind_code("company_430047_BJ") == "430047.BJ"

    def test_entity_id_to_wind_code_invalid(self):
        assert entity_id_to_wind_code("invalid") is None

    def test_roundtrip(self):
        """entity_id → wind_code → entity_id 必须稳定."""
        original = "company_600518_SH"
        wind = entity_id_to_wind_code(original)
        assert wind == "600518.SH"
        assert make_listed_company_entity_id(wind) == original

    def test_consistency_kangmei(self):
        """康美药业在所有路径下统一."""
        assert normalize_wind_code("600518.SH") == "600518.SH"
        assert make_listed_company_entity_id("600518.SH") == "company_600518_SH"


class TestExchangeCode:
    """exchange_code 映射测试."""

    def test_sh(self):
        assert get_exchange_code("SH") == "XSHG"

    def test_sz(self):
        assert get_exchange_code("SZ") == "XSHE"

    def test_bj(self):
        assert get_exchange_code("BJ") == "BJ"


class TestConsistencyAcrossPaths:
    """确保所有路径下的统一性."""

    def test_kangmei_identity(self):
        """康美药业: wind_code=600518.SH, entity_id=company_600518_SH."""
        assert normalize_wind_code("600518") == "600518.SH"
        assert normalize_wind_code("600518.SH") == "600518.SH"
        assert normalize_wind_code("600518.XSHG") == "600518.SH"
        assert make_listed_company_entity_id("600518") == "company_600518_SH"
        assert make_listed_company_entity_id("600518.SH") == "company_600518_SH"
        assert make_listed_company_entity_id("600518.XSHG") == "company_600518_SH"

    def test_shenzhen_identity(self):
        assert normalize_wind_code("000001") == "000001.SZ"
        assert normalize_wind_code("300750") == "300750.SZ"
        assert make_listed_company_entity_id("000001") == "company_000001_SZ"

    def test_beijing_identity(self):
        assert normalize_wind_code("430047") == "430047.BJ"
        assert normalize_wind_code("830799") == "830799.BJ"
        assert make_listed_company_entity_id("430047") == "company_430047_BJ"
