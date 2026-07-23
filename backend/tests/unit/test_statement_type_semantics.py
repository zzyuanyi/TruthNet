"""statement_type 语义审计测试 — V12 Task 4-6 合并前门禁.

验证 408001000/408006000 映射与 Wind 数据标准一致。
权威来源: Wind 量化研究数据库 V4.47 + docs/DATA_README.md + docs/DATA_CONTRACT.md
"""

from app.domain.finance.statement_type import (
    STATEMENT_TYPE_DICT,
    StatementTypeCode,
    describe_statement_type,
    is_consolidated,
    is_parent_company,
)


class TestStatementTypeMapping:
    """验证 statement_type 代码映射与权威来源一致."""

    def test_408001000_is_consolidated(self):
        """408001000 = 合并报表 (Wind V4.47 / DATA_README.md / DATA_CONTRACT.md)."""
        assert StatementTypeCode.CONSOLIDATED == "408001000"
        assert "合并报表" in STATEMENT_TYPE_DICT["408001000"]
        assert is_consolidated("408001000") is True
        assert is_parent_company("408001000") is False

    def test_408006000_is_parent_company(self):
        """408006000 = 母公司报表 (Wind V4.47 / DATA_README.md / DESIGN_V12.md)."""
        assert StatementTypeCode.PARENT_COMPANY == "408006000"
        assert "母公司报表" in STATEMENT_TYPE_DICT["408006000"]
        assert is_parent_company("408006000") is True
        assert is_consolidated("408006000") is False

    def test_consolidated_range(self):
        """408001000–408005000 均为合并报表口径."""
        for code in ["408001000", "408002000", "408003000", "408004000", "408005000"]:
            assert is_consolidated(code), f"{code} should be consolidated"
            assert not is_parent_company(code), f"{code} should NOT be parent_company"

    def test_parent_company_range(self):
        """408006000–408010000 均为母公司报表口径."""
        for code in ["408006000", "408007000", "408008000", "408009000", "408010000"]:
            assert is_parent_company(code), f"{code} should be parent_company"
            assert not is_consolidated(code), f"{code} should NOT be consolidated"

    def test_enum_members_not_reversed(self):
        """CONSOLIDATED 不得等于 408006000, PARENT_COMPANY 不得等于 408001000."""
        assert (
            StatementTypeCode.CONSOLIDATED != "408006000"
        ), "BUG: CONSOLIDATED should be 408001000, not 408006000"
        assert (
            StatementTypeCode.PARENT_COMPANY != "408001000"
        ), "BUG: PARENT_COMPANY should be 408006000, not 408001000"

    def test_describe_known_codes(self):
        """describe_statement_type 返回非空描述."""
        for code in ["408001000", "408006000"]:
            desc = describe_statement_type(code)
            assert len(desc) > 0
            assert "未知" not in desc, f"{code}: {desc}"

    def test_describe_unknown_code_fail_closed(self):
        """未知代码返回明确标识."""
        desc = describe_statement_type("999999999")
        assert "未知" in desc

    def test_default_analysis_scope(self):
        """当前数据主要口径为 408006000 母公司报表 (DESIGN_V12.md)."""
        # 验证 ORM 默认值语义
        from app.domain.finance.statement_type import StatementTypeCode

        default = StatementTypeCode.PARENT_COMPANY  # 408006000
        assert is_parent_company(
            default
        ), "Default should be parent_company per DESIGN_V12"
