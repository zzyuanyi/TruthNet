"""ResolveEntity — V12 §7.2. 从 user_query 解析公司实体。

Phase B→C 过渡：原 5 家 mock 公司 → MySQL companies 表查询。
"""

from __future__ import annotations

import json
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

_CONTEXT_CONTINUATION_CUES = (
    "它",
    "该公司",
    "这家公司",
    "上家公司",
    "继续",
    "再看",
    "刚才",
    "前面",
    "综合",
    "财务",
    "报表",
    "营收",
    "利润",
    "现金流",
    "存货",
    "应收",
    "股权",
    "股东",
    "公告",
    "评级",
    "舆情",
    "风险",
    "造假",
    "舞弊",
)


def _should_continue_previous_company(query: str) -> bool:
    """仅明确追问时继承上一家公司，寒暄/感谢不得触发整套分析。"""
    q = (query or "").strip().lower()
    return bool(q) and any(cue in q for cue in _CONTEXT_CONTINUATION_CUES)


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


def _parse_aliases(value) -> list[str]:
    """Normalize JSON aliases returned by ORM or textual SQL queries."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
                for a in _parse_aliases(r.get("aliases")):
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


def _find_company_candidates(query: str, limit: int = 5) -> list[CompanyRef]:
    """Return deterministic candidates only when text matches multiple companies."""
    if settings.SQL_BACKEND != "mysql":
        from app.infrastructure.persistence.sqlite.company_repository import (
            _MOCK_COMPANIES,
        )

        matches: list[CompanyRef] = []
        for item in _MOCK_COMPANIES:
            aliases = (item.code, item.name, item.short_name)
            if any(alias and alias in query for alias in aliases):
                wind_code = normalize_wind_code(item.code)
                matches.append(
                    CompanyRef(
                        entity_id=make_listed_company_entity_id(wind_code),
                        wind_code=wind_code,
                        sec_name=item.short_name or item.name,
                        exchange=wind_code.rsplit(".", maxsplit=1)[-1],
                        industry_l1=item.industry,
                    )
                )
        return matches[:limit] if len(matches) > 1 else []

    try:
        with _get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT entity_id, wind_code, sec_name, exchange_code, "
                        "industry_l1, aliases FROM companies "
                        "WHERE is_latest = 1 AND sec_name IS NOT NULL "
                        "ORDER BY sec_name, wind_code"
                    ),
                )
                .mappings()
                .all()
            )
        candidates: list[CompanyRef] = []
        seen: set[str] = set()
        for row in rows:
            sec_name = str(row.get("sec_name") or "")
            prefix_hit = len(sec_name) >= 2 and sec_name[:2] in query
            alias_hit = any(
                alias in query for alias in _parse_aliases(row.get("aliases"))
            )
            if not prefix_hit and not alias_hit:
                continue
            wind_code = str(row["wind_code"])
            if wind_code in seen:
                continue
            seen.add(wind_code)
            candidates.append(
                CompanyRef(
                    entity_id=str(row["entity_id"]),
                    wind_code=wind_code,
                    sec_name=sec_name,
                    exchange=str(row.get("exchange_code") or ""),
                    industry_l1=str(row.get("industry_l1") or ""),
                )
            )
            if len(candidates) >= limit:
                break
        return candidates if len(candidates) > 1 else []
    except Exception:
        logger.exception("实体候选查询失败: query=%.50s", query)
        return []


def resolve_entity_node(state: AgentState) -> dict:
    user_query = state.get("user_query", "")
    request_context = state.get("request_context")
    explicit_company_code = (
        getattr(request_context, "company_code", "") if request_context else ""
    )
    # 实体解析先于 plan_modules 执行。明确寒暄、使用引导或范围外问题若继续
    # 做公司名子串匹配，会把“今天天气怎么样”误识别为“今天国际”。这里只
    # 短路高置信确定性意图；问候后带真实分析诉求时检测器返回 None，照常解析。
    from app.agents.nodes.plan_modules import detect_chitchat_intent

    if not explicit_company_code and detect_chitchat_intent(user_query) in {
        "chitchat",
        "guide",
        "unsupported",
    }:
        return {"company": None}

    # 指代消解：memory 节点已解析出实体名（如"它"→"康美药业"），
    # 追加到搜索文本，使指代轮次能继续公司分析。
    search_text = user_query
    mc = state.get("memory_context")
    if mc is not None:
        resolved = getattr(mc, "resolved_entity_name", "") or ""
        if resolved:
            search_text = f"{user_query} {resolved}"

    company = _find_company(explicit_company_code or search_text)

    # 主语省略延续：query 无公司名但含明确追问线索时，延续最近对话主体
    # （V12 §7.6 当前主体恢复）。
    if (
        company is None
        and not explicit_company_code
        and mc is not None
        and _should_continue_previous_company(user_query)
    ):
        prev = getattr(mc, "previous_companies", []) or []
        if prev:
            company = _find_company(prev[0])
            if company is not None:
                logger.info(
                    "ResolveEntity: query 无公司名，延续最近主体 %s", company.sec_name
                )

    if company is None:
        candidates = (
            [] if explicit_company_code else _find_company_candidates(search_text)
        )
        return {"company": None, "company_candidates": candidates}

    return {"company": company, "company_candidates": []}
