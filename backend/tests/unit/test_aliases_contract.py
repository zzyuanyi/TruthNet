"""aliases JSON 契约测试（2026-08-12 三轮审查修订实施批 3）。

覆盖任意 dict / 嵌套 list / 字符串值 / 非法 JSON / 去空白。
"""

from app.infrastructure.persistence.mysql.company_repository import _aliases_to_list


def test_aliases_json_list_string():
    """数据库列 JSON 字符串（list 形式）。"""
    assert _aliases_to_list('["国药"]') == ["国药"]
    assert _aliases_to_list("[]") == []


def test_aliases_json_dict_string():
    """JSON dict 字符串：展开任意键。"""
    assert _aliases_to_list('{"list": ["甲"], "extra": "乙"}') == ["甲", "乙"]


def test_aliases_dict_any_keys():
    """dict 对象：不丢非 aliases/list 键（保留现有展开全部值能力）。"""
    assert _aliases_to_list({"names": ["甲", "乙"], "note": "丙"}) == ["甲", "乙", "丙"]
    assert _aliases_to_list({"list": ["甲"]}) == ["甲"]


def test_aliases_nested_list():
    """嵌套 list 递归展开。"""
    assert _aliases_to_list([["甲", "乙"], "丙"]) == ["甲", "乙", "丙"]


def test_aliases_invalid_json():
    """非法 JSON 字符串 → 空列表（不当作别名文本）。"""
    assert _aliases_to_list("not-json{{") == []
    assert _aliases_to_list('{"broken": ') == []


def test_aliases_none_and_empty():
    assert _aliases_to_list(None) == []
    assert _aliases_to_list("") == []
    assert _aliases_to_list("   ") == []


def test_aliases_strip_whitespace():
    assert _aliases_to_list([" 国药 ", ""]) == ["国药"]
    assert _aliases_to_list([" 甲 ", " 乙 "]) == ["甲", "乙"]
