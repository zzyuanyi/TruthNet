"""实体名称标准化 — V12 §8.6.

实体对齐基础组件：处理全角/半角、Unicode NFKC、前后空格、常见不可见字符。
为后续精确匹配和模糊匹配提供统一基础。
"""

import re
import unicodedata


def normalize_entity_name(name: str) -> str:
    """标准化实体名称，用于精确匹配.

    处理步骤:
    1. Unicode NFKC 正规化
    2. 全角字符转半角
    3. 去除前后空格和重复内部空格
    4. 去除常见不可见字符
    5. 英文统一小写

    Returns:
        标准化后的名称字符串.
    """
    if not name:
        return ""

    # 1. NFKC
    name = unicodedata.normalize("NFKC", name)

    # 2. 全角转半角
    result: list[str] = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:  # 全角标点
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # 全角空格
            result.append(" ")
        else:
            result.append(ch)
    name = "".join(result)

    # 3. 去除前后空格和重复内部空格
    name = " ".join(name.split())

    # 4. 去除不可见字符 (零宽空格、BOM等)
    name = re.sub(r"[​‌‍﻿ ]", "", name)

    # 5. 英文部分统一小写（保留中文）
    name = name.lower()

    return name


def extract_wind_code_suffix(code: str | None) -> tuple[str | None, str | None]:
    """从完整的 Wind 代码中提取 6 位代码和后缀.

    例如:
        "600518.SH" → ("600518", ".SH")
        "000001.SZ" → ("000001", ".SZ")
        "600518"    → ("600518", None)

    Returns:
        (code, suffix) 元组.
    """
    if not code:
        return None, None

    code = code.strip().upper()
    match = re.match(r"^(\d{6})(\.(S[ZH]|XSHE|XSHG))?$", code)
    if match:
        return match.group(1), match.group(2)
    return code, None


def make_display_name(canonical_name: str) -> str:
    """生成展示名称——保留原始大小写和格式（与标准化名称区分）."""
    return canonical_name.strip()
