"""MySQL CompanyRepository Adapter — full profile.

从 MySQL companies 表查询真实公司数据。
- 只选择 is_latest=1；
- 优先精确代码，其次精确名称，再进行受限前缀/包含匹配；
- 使用参数化 SQL（SQLAlchemy text），不拼接用户输入；
- 返回真实 entity_id，不通过字符串重新生成。
"""

import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.domain.company.models import CompanyRecord, CompanySearchResult
from app.infrastructure.graph.normalizer import normalize_wind_code

logger = logging.getLogger(__name__)

# 列选择常量（与 companies 表结构对齐）
_SELECT_COLS = (
    "entity_id, wind_code, sec_name, aliases, exchange_code, industry_l1, "
    "industry_l2, sw_indu_code, comp_type_code, listing_date, dataset_version, "
    "source_record_id, source_type, quality_flags, is_latest"
)

# 匹配 600518_SH / 600518.SH / 600518 形式的代码
_CODE_RE = re.compile(r"^\d{6}(?:[._](?:SH|SZ|BJ))?$", re.IGNORECASE)


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符，防止用户输入注入模式."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_input_code(value: str) -> str | None:
    """将用户输入规范化为 Wind Code；无法解析返回 None."""
    v = value.strip()
    if not v:
        return None
    # 600518_SH → 600518.SH
    m = re.match(r"^(\d{6})_(SH|SZ|BJ)$", v, re.IGNORECASE)
    if m:
        return f"{m.group(1)}.{m.group(2).upper()}"
    try:
        return normalize_wind_code(v)
    except ValueError:
        return None


def _aliases_to_list(raw) -> list[str]:
    """将 aliases JSON 规范为字符串列表."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, dict):
        out = []
        for v in raw.values():
            if isinstance(v, list):
                out.extend(str(x) for x in v)
            else:
                out.append(str(v))
        return out
    return []


def _quality_flags_dict(raw) -> dict:
    """将 quality_flags JSON 列规范为 dict（pymysql 返回字符串，需 json.loads）。"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            import json

            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _row_to_record(row) -> CompanyRecord:
    """将 SQLAlchemy Row/Mapping 转为 CompanyRecord."""
    d = dict(row)
    return CompanyRecord(
        entity_id=str(d["entity_id"]),
        wind_code=str(d["wind_code"]),
        sec_name=str(d["sec_name"]),
        aliases=_aliases_to_list(d.get("aliases")),
        exchange_code=d.get("exchange_code"),
        industry_l1=d.get("industry_l1"),
        industry_l2=d.get("industry_l2"),
        sw_indu_code=d.get("sw_indu_code"),
        comp_type_code=d.get("comp_type_code"),
        listing_date=d.get("listing_date"),
        dataset_version=d.get("dataset_version"),
        source_record_id=d.get("source_record_id"),
        source_type=d.get("source_type"),
        quality_flags=_quality_flags_dict(d.get("quality_flags")),
        is_latest=bool(d.get("is_latest", True)),
    )


class MySQLCompanyRepository:
    """MySQL 公司仓库 — full profile 真实查询."""

    def __init__(self):
        self._engine: Engine | None = None

    # ── 连接 ────────────────────────────────────────────

    def _get_engine(self) -> Engine:
        if self._engine is None:
            url = (
                f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
                f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
                "?charset=utf8mb4"
            )
            self._engine = create_engine(url, echo=False, pool_pre_ping=True)
        return self._engine

    async def check_connection(self) -> bool:
        try:
            with self._get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("MySQL 连接不可用: %s", e)
            return False

    # ── 查询 ────────────────────────────────────────────

    async def get_by_code(self, code: str) -> CompanyRecord | None:
        """按代码获取（支持 600518 / 600518.SH / 600518_SH / company_600518_SH）。"""
        v = code.strip()
        if not v:
            return None

        # entity_id 形式直接匹配
        if v.startswith("company_") or v.startswith("ent_"):
            return await self.get_by_entity_id(v)

        normalized = _normalize_input_code(v)
        if normalized is None:
            # 非代码形式：退回名称精确匹配
            with self._get_engine().connect() as conn:
                row = (
                    conn.execute(
                        text(
                            f"SELECT {_SELECT_COLS} FROM companies "
                            "WHERE is_latest = 1 AND sec_name = :name LIMIT 1"
                        ),
                        {"name": v},
                    )
                    .mappings()
                    .first()
                )
            return _row_to_record(row) if row else None

        with self._get_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        f"SELECT {_SELECT_COLS} FROM companies "
                        "WHERE is_latest = 1 AND wind_code = :code LIMIT 1"
                    ),
                    {"code": normalized},
                )
                .mappings()
                .first()
            )
        return _row_to_record(row) if row else None

    async def get_by_entity_id(self, entity_id: str) -> CompanyRecord | None:
        with self._get_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        f"SELECT {_SELECT_COLS} FROM companies "
                        "WHERE is_latest = 1 AND entity_id = :eid LIMIT 1"
                    ),
                    {"eid": entity_id},
                )
                .mappings()
                .first()
            )
        return _row_to_record(row) if row else None

    async def search(self, query: str, limit: int = 10) -> CompanySearchResult:
        """搜索公司 — 匹配质量排序.

        精确代码 > 精确名称 > 前缀匹配 > 包含匹配。
        单字符非代码查询返回空（避免误解析）。
        """
        q = (query or "").strip()
        if not q:
            # 空查询 → 返回全部（受限 limit）
            with self._get_engine().connect() as conn:
                rows = (
                    conn.execute(
                        text(
                            f"SELECT {_SELECT_COLS} FROM companies "
                            "WHERE is_latest = 1 ORDER BY wind_code LIMIT :limit"
                        ),
                        {"limit": limit},
                    )
                    .mappings()
                    .all()
                )
            recs = [_row_to_record(r) for r in rows]
            return CompanySearchResult(companies=recs, total=len(recs))

        # 单字符非代码 → 拒绝
        if len(q) == 1 and not _CODE_RE.match(q):
            return CompanySearchResult(companies=[], total=0)

        exact_code = _normalize_input_code(q)
        name = _escape_like(q)
        prefix = f"{name}%"
        contains = f"%{name}%"

        params = {
            "code": exact_code,
            "name": q,
            "prefix": prefix,
            "contains": contains,
            "limit": limit,
        }
        sql = (
            f"SELECT {_SELECT_COLS}, "
            "CASE "
            "  WHEN :code IS NOT NULL AND wind_code = :code THEN 0 "
            "  WHEN sec_name = :name THEN 1 "
            "  WHEN sec_name LIKE :prefix ESCAPE '\\\\' THEN 2 "
            "  ELSE 3 "
            "END AS match_rank "
            "FROM companies "
            "WHERE is_latest = 1 AND ("
            "  (:code IS NOT NULL AND wind_code = :code) "
            "  OR sec_name = :name "
            "  OR sec_name LIKE :prefix ESCAPE '\\\\' "
            "  OR sec_name LIKE :contains ESCAPE '\\\\' "
            ") "
            "ORDER BY match_rank ASC, CHAR_LENGTH(sec_name) ASC "
            "LIMIT :limit"
        )

        with self._get_engine().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        recs = [_row_to_record(r) for r in rows]
        return CompanySearchResult(companies=recs, total=len(recs))

    async def list_all(self, limit: int = 100) -> list[CompanyRecord]:
        with self._get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        f"SELECT {_SELECT_COLS} FROM companies "
                        "WHERE is_latest = 1 ORDER BY wind_code LIMIT :limit"
                    ),
                    {"limit": limit},
                )
                .mappings()
                .all()
            )
        return [_row_to_record(r) for r in rows]
