"""ResolveEntity — V12 §7.2. 从 user_query 解析公司实体。

Bug fix: 不再无条件返回康美药业。根据用户输入中的公司名称/代码查找。
未知公司返回 None，进入 short-circuit → 提示用户提供完整名称。
"""

from app.agents.state import AgentState, CompanyRef
from app.infrastructure.graph.normalizer import normalize_wind_code

# Phase B mock 公司注册表（与 companies router 共享数据源）
_MOCK_ENTITY_MAP: dict[str, CompanyRef] = {
    "600518": CompanyRef(
        entity_id="company_600518_SH",
        wind_code="600518.SH",
        sec_name="康美药业",
        exchange="XSHG",
        industry_l1="中药",
    ),
    "600519": CompanyRef(
        entity_id="company_600519_SH",
        wind_code="600519.SH",
        sec_name="贵州茅台",
        exchange="XSHG",
        industry_l1="白酒",
    ),
    "000858": CompanyRef(
        entity_id="company_000858_SZ",
        wind_code="000858.SZ",
        sec_name="五粮液",
        exchange="XSHE",
        industry_l1="白酒",
    ),
    "300750": CompanyRef(
        entity_id="company_300750_SZ",
        wind_code="300750.SZ",
        sec_name="宁德时代",
        exchange="XSHE",
        industry_l1="电池",
    ),
    "002415": CompanyRef(
        entity_id="company_002415_SZ",
        wind_code="002415.SZ",
        sec_name="海康威视",
        exchange="XSHE",
        industry_l1="安防",
    ),
}

# 公司名称别名映射
_NAME_ALIASES: dict[str, str] = {
    "康美": "600518",
    "康美药业": "600518",
    "茅台": "600519",
    "贵州茅台": "600519",
    "五粮液": "000858",
    "宁德时代": "300750",
    "宁德": "300750",
    "海康威视": "002415",
    "海康": "002415",
}


def _find_company(query: str) -> CompanyRef | None:
    """从用户输入中查找公司。先尝试代码匹配，再尝试名称匹配。"""
    import re

    # 1. 查找 Wind Code 模式（6位数字，可选 .SH/.SZ/.BJ 后缀）
    wind_match = re.search(
        r"\b(\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?)\b", query, re.IGNORECASE
    )
    if wind_match:
        code = wind_match.group(1).upper()
        try:
            normalized = normalize_wind_code(code)
            digits, _suffix = normalized.split(".")
            if digits in _MOCK_ENTITY_MAP:
                return _MOCK_ENTITY_MAP[digits]
        except (ValueError, KeyError):
            pass

    # 2. 查找名称别名（模糊子串匹配）
    for name, code in _NAME_ALIASES.items():
        if name in query:
            if code in _MOCK_ENTITY_MAP:
                return _MOCK_ENTITY_MAP[code]

    return None


def resolve_entity_node(state: AgentState) -> dict:
    user_query = state.get("user_query", "")

    company = _find_company(user_query)

    if company is None:
        return {
            "company": None,
        }

    return {
        "company": company,
    }
