"""Company name aliases that are not present in the source company master."""

from __future__ import annotations


# Exact, well-known market names only. Values may be a canonical name or Wind
# code when the source company master contains only a code placeholder.
_COMPANY_NAME_ALIASES: dict[str, str] = {
    "太平洋保险": "中国太保",
    "中国太平洋保险": "中国太保",
    "平安集团": "中国平安",
    "上海机电": "600835.SH",
}


def normalize_company_name(value: str) -> str:
    """Map a complete market alias to the canonical security-master name."""
    text = (value or "").strip()
    return _COMPANY_NAME_ALIASES.get(text, text)


def is_company_name_alias(value: str) -> bool:
    """Return whether the complete input is an explicitly supported alias."""
    text = (value or "").strip()
    return text in _COMPANY_NAME_ALIASES
