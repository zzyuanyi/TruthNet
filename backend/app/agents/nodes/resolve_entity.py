"""ResolveEntity — V12 §7.2. 从 user_query 解析公司实体。

Phase B→C 过渡：原 5 家 mock 公司 → MySQL companies 表查询。
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.agents.state import AgentState, CompanyRef
from app.core.config import settings
from app.infrastructure.graph.normalizer import (
    make_listed_company_entity_id,
    normalize_wind_code,
)

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def _get_engine() -> Engine:
    """惰性缓存 MySQL engine。"""
    global _engine
    if _engine is None:
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        _engine = create_engine(url, echo=False)
    return _engine


def _find_lite_company(query: str) -> CompanyRef | None:
    """在 Lite Profile 的确定性 mock 公司中解析实体。

    TODO: Phase C 统一由 CompanyRepository 注入，移除该兼容分支。
    """
    from app.infrastructure.persistence.sqlite.company_repository import _MOCK_COMPANIES

    matches = []
    for company in _MOCK_COMPANIES:
        aliases = (company.code, company.name, company.short_name)
        if any(alias and alias in query for alias in aliases):
            matches.append(company)

    if not matches:
        for company in _MOCK_COMPANIES:
            short_name = company.short_name or company.name
            if len(short_name) >= 2 and short_name[:2] in query:
                matches.append(company)

    if len(matches) != 1:
        return None

    company = matches[0]
    wind_code = normalize_wind_code(company.code)
    return CompanyRef(
        entity_id=make_listed_company_entity_id(wind_code),
        wind_code=wind_code,
        sec_name=company.short_name or company.name,
        exchange=wind_code.rsplit(".", maxsplit=1)[-1],
        industry_l1=company.industry,
    )


def _find_company(query: str) -> CompanyRef | None:
    """从用户输入中查找公司：先 Wind Code 匹配，再名称模糊匹配。"""
    if settings.SQL_BACKEND != "mysql":
        return _find_lite_company(query)

    try:
        with _get_engine().connect() as conn:
            # 1. 查找 Wind Code 模式（6位数字，可选后缀）
            wind_match = re.search(
                r"\b(\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?)\b", query, re.IGNORECASE
            )
            if wind_match:
                raw_code = wind_match.group(1).upper()
                try:
                    normalized = normalize_wind_code(raw_code)
                except ValueError:
                    normalized = raw_code

                row = (
                    conn.execute(
                        text(
                            "SELECT entity_id, wind_code, sec_name, exchange_code, industry_l1 "
                            "FROM companies WHERE wind_code = :code AND is_latest = 1 LIMIT 1"
                        ),
                        {"code": normalized},
                    )
                    .mappings()
                    .first()
                )

                if row:
                    return CompanyRef(
                        entity_id=str(row["entity_id"]),
                        wind_code=str(row["wind_code"]),
                        sec_name=str(row["sec_name"]),
                        exchange=str(row.get("exchange_code", "") or ""),
                        industry_l1=str(row.get("industry_l1", "") or ""),
                    )

            # 2. 完整名称匹配：LOCATE(sec_name, query)
            row = (
                conn.execute(
                    text(
                        "SELECT entity_id, wind_code, sec_name, exchange_code, industry_l1 "
                        "FROM companies "
                        "WHERE is_latest = 1 AND sec_name IS NOT NULL "
                        "AND LOCATE(sec_name, :query) > 0 "
                        "ORDER BY CHAR_LENGTH(sec_name) DESC LIMIT 1"
                    ),
                    {"query": query},
                )
                .mappings()
                .first()
            )

            if row:
                return CompanyRef(
                    entity_id=str(row["entity_id"]),
                    wind_code=str(row["wind_code"]),
                    sec_name=str(row["sec_name"]),
                    exchange=str(row.get("exchange_code", "") or ""),
                    industry_l1=str(row.get("industry_l1", "") or ""),
                )

            # 3. 简称匹配：检查 query 子串是否命中 aliases 中存储的简称
            row = (
                conn.execute(
                    text(
                        "SELECT entity_id, wind_code, sec_name, exchange_code, industry_l1, aliases "
                        "FROM companies "
                        "WHERE is_latest = 1 AND aliases IS NOT NULL "
                        "ORDER BY CHAR_LENGTH(sec_name) DESC"
                    ),
                )
                .mappings()
                .all()
            )

            # 收集所有别名命中的公司，仅唯一命中时返回
            alias_hits: list[dict] = []
            for r in row:
                aliases = r.get("aliases")
                if not aliases or not isinstance(aliases, list):
                    continue
                for alias in aliases:
                    a = str(alias).strip()
                    if not a:
                        continue
                    if a in query:
                        alias_hits.append(
                            {
                                "entity_id": str(r["entity_id"]),
                                "wind_code": str(r["wind_code"]),
                                "sec_name": str(r["sec_name"]),
                                "exchange": str(r.get("exchange_code", "") or ""),
                                "industry_l1": str(r.get("industry_l1", "") or ""),
                            }
                        )
                        break  # 每条公司只命中一次

            if len(alias_hits) == 1:
                return CompanyRef(**alias_hits[0])

            # 4. 前缀兜底：sec_name 前 2 字出现在 query 中，恰好 1 家时返回
            # "康美" in query → 康美药业, "平安" → 平安银行
            rows = (
                conn.execute(
                    text(
                        "SELECT entity_id, wind_code, sec_name, exchange_code, industry_l1 "
                        "FROM companies "
                        "WHERE is_latest = 1 "
                        "AND sec_name IS NOT NULL "
                        "AND sec_name <> wind_code "
                        "AND CHAR_LENGTH(sec_name) >= 2 "
                        "AND LOCATE(LEFT(sec_name, 2), :query) > 0"
                    ),
                    {"query": query},
                )
                .mappings()
                .all()
            )

            if len(rows) == 1:
                r = rows[0]
                return CompanyRef(
                    entity_id=str(r["entity_id"]),
                    wind_code=str(r["wind_code"]),
                    sec_name=str(r["sec_name"]),
                    exchange=str(r.get("exchange_code", "") or ""),
                    industry_l1=str(r.get("industry_l1", "") or ""),
                )

    except Exception:
        logger.exception("实体解析查询失败: query=%.50s", query)

    return None


def resolve_entity_node(state: AgentState) -> dict:
    user_query = state.get("user_query", "")
    company = _find_company(user_query)

    if company is None:
        return {"company": None}

    return {"company": company}
