"""Wind Code 规范化与实体 ID 生成 — 单一事实来源。

所有模块（API、MySQL、Neo4j、NetworkX、fixture、Chroma）必须复用此模块的 helper，
不得各自实现互不一致的 Wind Code 解析逻辑。

设计要求（V12，来自集成任务 P1）：
  1. .XSHG 规范化为 .SH
  2. .XSHE 规范化为 .SZ
  3. .BJ 必须被 parser 原生识别
  4. 北交所不只判断 8/9 开头，必须覆盖实际数据中出现的 4/8/9 开头
  5. 已有明确后缀时不得再次追加
  6. 对无法可靠判断的裸代码 fail-closed，不得默认 .SH
  7. 上市公司实体 ID 统一为 company_<6位代码>_<SH|SZ|BJ>
"""

import re
import unicodedata
from typing import Optional

# ── 交易所后缀映射（长→短）──
_EXCHANGE_TO_SHORT = {"XSHG": "SH", "XSHE": "SZ"}

_SHORT_TO_EXCHANGE = {
    "SH": "XSHG",
    "SZ": "XSHE",
    "BJ": "BJ",  # 北交所在数据中使用 BJ 作为 exchange_code
}

# ── 前缀推断表（仅对裸 6 位数字代码使用） ──
# 规则来源：上交所 6xxxxx，深交所主板 0xxxxx，深交所创业板 3xxxxx，
# 北交所（实际数据中出现的 4/8/9 开头代码）
_PREFIX_SUFFIX_MAP = {
    "6": "SH",  # 上海证券交易所
    "0": "SZ",  # 深圳证券交易所（主板）
    "3": "SZ",  # 深圳证券交易所（创业板）
    "4": "BJ",  # 北京证券交易所
    "8": "BJ",  # 北京证券交易所
    "9": "BJ",  # 北京证券交易所
}

# ── Wind Code 正则 ──
_WIND_CODE_RE = re.compile(
    r"^(?P<digits>\d{6})(?:\.(?P<suffix>S[ZH]|XSHG|XSHE|BJ))?$",
    re.IGNORECASE,
)


def parse_wind_code(code: str) -> tuple[str, Optional[str]]:
    """将 Wind Code 解析为 (纯数字代码, 短后缀或None)。

    Args:
        code: 输入代码，如 "600518.SH", "000001.XSHE", "600518", "430047.BJ"

    Returns:
        (digits, short_suffix_or_None)
        - digits: 6位数字代码
        - suffix: 规范化短后缀 SH/SZ/BJ，或 None

    Raises:
        ValueError: 代码格式无法解析

    Examples:
        >>> parse_wind_code("600518.SH")
        ("600518", "SH")
        >>> parse_wind_code("000001.XSHE")
        ("000001", "SZ")
        >>> parse_wind_code("600518")
        ("600518", None)
        >>> parse_wind_code("430047.BJ")
        ("430047", "BJ")
    """
    if not code or not isinstance(code, str):
        raise ValueError(f"无效的 Wind Code: {code!r}")

    code = code.strip()

    match = _WIND_CODE_RE.match(code)
    if not match:
        raise ValueError(f"无法解析 Wind Code 格式: {code!r}")

    digits = match.group("digits")
    suffix = match.group("suffix")

    if suffix is not None:
        suffix = suffix.upper()
        # 规范化 XSHG → SH, XSHE → SZ
        suffix = _EXCHANGE_TO_SHORT.get(suffix, suffix)

    return digits, suffix


def infer_suffix_from_digits(digits: str) -> Optional[str]:
    """根据 6 位数字代码前缀推断交易所短后缀。

    规则：
        - 6xxxxx → SH (上交所)
        - 0xxxxx, 3xxxxx → SZ (深交所)
        - 4xxxxx, 8xxxxx, 9xxxxx → BJ (北交所)
        - 其他 → None (无法推断)

    Args:
        digits: 6位数字代码

    Returns:
        短后缀 SH/SZ/BJ，或 None 表示无法可靠推断
    """
    if not digits or len(digits) != 6:
        return None
    first_char = digits[0]
    return _PREFIX_SUFFIX_MAP.get(first_char)


def normalize_wind_code(code: str, fail_on_ambiguous: bool = True) -> str:
    """规范化 Wind Code 为统一格式：{6位代码}.{SH|SZ|BJ}。

    处理规则：
        1. 去除前后空格
        2. 已有后缀：保留，但 XSHG→SH, XSHE→SZ
        3. 裸代码：根据首位数字推断
        4. 无法推断时：若 fail_on_ambiguous=True 抛出 ValueError；
           若 False 则保留裸代码

    Args:
        code: 任意格式的 Wind Code
        fail_on_ambiguous: True 时对无法推断的裸代码抛出异常；
                          False 时返回原始代码（去除空格）

    Returns:
        规范化后的 Wind Code，如 "600518.SH", "000001.SZ", "430047.BJ"

    Raises:
        ValueError: 代码格式无效或无法推断交易所

    Examples:
        >>> normalize_wind_code("600518.SH")
        "600518.SH"
        >>> normalize_wind_code("600518.XSHG")
        "600518.SH"
        >>> normalize_wind_code("000001.XSHE")
        "000001.SZ"
        >>> normalize_wind_code("600518")
        "600518.SH"
        >>> normalize_wind_code("430047.BJ")
        "430047.BJ"
        >>> normalize_wind_code("830799.BJ")
        "830799.BJ"
        >>> normalize_wind_code("920123.BJ")
        "920123.BJ"
        >>> normalize_wind_code("000001.sz")
        "000001.SZ"
    """
    digits, suffix = parse_wind_code(code)

    if suffix is not None:
        return f"{digits}.{suffix}"

    # 裸代码 — 尝试推断
    inferred = infer_suffix_from_digits(digits)
    if inferred is not None:
        return f"{digits}.{inferred}"

    if fail_on_ambiguous:
        raise ValueError(
            f"无法推断 {code!r} 的交易所后缀。"
            f"6位数字代码首位数 {digits[0]!r} 不匹配已知规则 "
            f"(SH: 6, SZ: 0/3, BJ: 4/8/9)。"
            f"请使用完整格式如 {digits}.SH 或 {digits}.SZ。"
        )

    return digits


def get_exchange_code(suffix: str) -> str:
    """将短后缀映射为 exchange_code 字段值。

    Args:
        suffix: SH, SZ, or BJ

    Returns:
        exchange_code: XSHG, XSHE, or BJ
    """
    suffix = suffix.upper()
    return _SHORT_TO_EXCHANGE.get(suffix, suffix)


def make_listed_company_entity_id(wind_code: str) -> str:
    """根据 Wind Code 生成本项目统一的上市公司实体 ID。

    格式：company_{6位代码}_{SH|SZ|BJ}

    示例：
        "600518.SH"  → "company_600518_SH"
        "000001.SZ"  → "company_000001_SZ"
        "430047.BJ"  → "company_430047_BJ"

    Args:
        wind_code: 任意格式 Wind Code（内部调用 normalize_wind_code）

    Returns:
        统一格式的实体 ID

    Raises:
        ValueError: wind_code 无效
    """
    normalized = normalize_wind_code(wind_code)
    digits, suffix = normalized.split(".")
    return f"company_{digits}_{suffix}"


def parse_entity_id(entity_id: str) -> Optional[tuple[str, str]]:
    """从 entity_id 中提取 Wind Code 信息。

    Args:
        entity_id: 如 "company_600518_SH"

    Returns:
        (wind_code_digits, suffix) 或 None（不匹配时）
    """
    match = re.match(r"^company_(\d{6})_(SH|SZ|BJ)$", entity_id)
    if not match:
        return None
    return match.group(1), match.group(2)


def entity_id_to_wind_code(entity_id: str) -> Optional[str]:
    """从 entity_id 反推 Wind Code。

    Args:
        entity_id: 如 "company_600518_SH"

    Returns:
        如 "600518.SH"，或 None
    """
    parsed = parse_entity_id(entity_id)
    if parsed is None:
        return None
    digits, suffix = parsed
    return f"{digits}.{suffix}"


# ═══════════════════════════════════════════════════════════
# 向后兼容别名
# ═══════════════════════════════════════════════════════════


def normalize_entity_name(name: str) -> str:
    """标准化实体名称（NFKC + 全角→半角 + 去空白）。

    向前兼容 V12 Task 6 旧接口。
    """
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    result: list[str] = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(ch)
    name = "".join(result)
    name = " ".join(name.split())
    name = re.sub(r"[​‌‍﻿ ]", "", name)
    return name.lower()


def make_display_name(canonical_name: str) -> str:
    """生成展示名称——保留原始大小写（兼容旧接口）."""
    return canonical_name.strip()


def extract_wind_code_suffix(code: str | None) -> tuple[str | None, str | None]:
    """从 Wind Code 提取 6 位代码和后缀（兼容旧接口）。

    Deprecated: 请使用 parse_wind_code() 代替。
    """
    if not code:
        return None, None
    try:
        digits, suffix = parse_wind_code(code)
        return digits, f".{suffix}" if suffix else None
    except ValueError:
        return code.strip().upper(), None
