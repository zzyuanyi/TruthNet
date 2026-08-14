"""MySQL CompanyRepository Adapter — full profile.

从 MySQL companies 表查询真实公司数据。
- 只选择 is_latest=1；
- 优先精确代码，其次精确名称，再进行受限前缀/包含匹配；
- 使用参数化 SQL（SQLAlchemy text），不拼接用户输入；
- 返回真实 entity_id，不通过字符串重新生成。
"""

import logging
import re

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from app.application.models.company_resolution import (
    CandidateLookupResult,
    CandidateMatch,
)
from app.agents.state import CompanyRef
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

# 候选查询列（CompanyRef 轻量字段）
_LOOKUP_COLS = (
    "entity_id, wind_code, sec_name, exchange_code, industry_l1, "
    "listing_date, comp_type_code"
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
    """将 aliases 规范为字符串列表（2026-08-12 四轮审查 P2-1：共享实现）。

    与 resolve_entity 对话解析共用 app.domain.company.aliases，
    避免 dict/嵌套 list 形态下"画像搜索能识别而 WS 不能"。
    """
    from app.domain.company.aliases import aliases_to_list

    return aliases_to_list(raw)


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
    """MySQL 公司仓库 — full profile 真实查询.

    连接配置在实例创建时**一次性捕获**（审查 P1：实例生命周期内不再
    读取可变全局 settings），Engine 基于捕获值懒建——中途切换
    settings.MYSQL_DATABASE 不会让旧实例的 Engine 连到新库。
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self._engine: Engine | None = None
        self._host = host if host is not None else settings.MYSQL_HOST
        self._port = port if port is not None else settings.MYSQL_PORT
        self._database = database if database is not None else settings.MYSQL_DATABASE
        self._user = user if user is not None else settings.MYSQL_USER
        self._password = password if password is not None else settings.MYSQL_PASSWORD

    # ── 连接 ────────────────────────────────────────────

    def _get_engine(self) -> Engine:
        if self._engine is None:
            # v3.1 P1-6：URL.create() 防密码含 @/: 等特殊字符解析失败
            url = URL.create(
                "mysql+pymysql",
                username=self._user,
                password=self._password,
                host=self._host,
                port=self._port,
                database=self._database,
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

    # ── 候选召回（v3.1 冻结方案 P1-2/P1-3/P0-2）────────────────

    @staticmethod
    def _row_to_ref(row) -> CompanyRef:
        return CompanyRef(
            entity_id=str(row["entity_id"]),
            wind_code=str(row["wind_code"]),
            sec_name=str(row["sec_name"]),
            exchange=str(row.get("exchange_code") or ""),
            industry_l1=str(row.get("industry_l1") or ""),
            listing_date=str(row.get("listing_date") or ""),
            comp_type_code=str(row.get("comp_type_code") or ""),
        )

    def lookup_mention(self, text_query: str, limit: int = 6) -> CandidateLookupResult:
        """候选召回 — 只接收一个 mention.text，返回候选（P0-2 组件边界）。

        匹配顺序（P1-2 match_kind）：
          exact_code（wind code 精确）→ exact_name（sec_name 相等）→
          exact_alias（aliases 精确命中）→ contains（mention 包含完整
          sec_name）→ reverse_contains（sec_name 包含 mention，
          "茅台"→"贵州茅台"）/ prefix（sec_name 以 mention 开头）。
          exact_legal_name 依赖 legal_name 列，当前 companies 表无此列
          （_SELECT_COLS 无 legal_name），本轮不产生该 kind。

        截断（P1-3）：每步查询 limit+1 行，合并后 truncated =
          len(merged) > limit；恰 limit 个不误判。
        同步实现（拍板：保留同步 SQL，SQL 位于 infrastructure adapter）。
        """
        t = (text_query or "").strip()
        if not t:
            return CandidateLookupResult()
        merged: list[CandidateMatch] = []
        seen: set[str] = set()
        query_limit = limit + 1  # P1-3：limit+1 判截断，恰 limit 不误判

        def _append(match: CandidateMatch) -> None:
            code = match.company.wind_code
            if code in seen:
                return
            seen.add(code)
            merged.append(match)

        with self._get_engine().connect() as conn:
            # ESCAPE 方言差异：MySQL 字符串中 '\\' 表示单反斜杠；
            # SQLite 直接接受单反斜杠（'\\' 是两个字符会报错）
            escape_clause = (
                "ESCAPE '\\\\'" if conn.dialect.name == "mysql" else "ESCAPE '\\'"
            )
            # 1. exact_code
            norm = _normalize_input_code(t)
            if norm:
                row = (
                    conn.execute(
                        text(
                            f"SELECT {_LOOKUP_COLS} FROM companies "
                            "WHERE is_latest = 1 AND wind_code = :code LIMIT 1"
                        ),
                        {"code": norm},
                    )
                    .mappings()
                    .first()
                )
                if row:
                    _append(
                        CandidateMatch(
                            company=self._row_to_ref(row),
                            match_kind="exact_code",
                            matched_text=t,
                            rank=0,
                        )
                    )

            # 2. contains / exact_name（mention 包含完整 sec_name）
            rows = (
                conn.execute(
                    text(
                        f"SELECT {_LOOKUP_COLS} FROM companies "
                        "WHERE is_latest = 1 AND sec_name IS NOT NULL "
                        "AND INSTR(:text, sec_name) > 0 "
                        "ORDER BY LENGTH(sec_name), sec_name, wind_code "
                        "LIMIT :limit"
                    ),
                    {"text": t, "limit": query_limit},
                )
                .mappings()
                .all()
            )
            for r in rows:
                kind = "exact_name" if str(r["sec_name"]) == t else "contains"
                _append(
                    CandidateMatch(
                        company=self._row_to_ref(r),
                        match_kind=kind,
                        matched_text=str(r["sec_name"]),
                        rank=1 if kind == "exact_name" else 3,
                    )
                )

            # 3. exact_alias（aliases 非空记录，Python 逐条精确匹配）
            #    先于 reverse_contains/prefix：去重时保留 rank 更小的 exact_alias
            alias_rows = (
                conn.execute(
                    text(
                        f"SELECT {_LOOKUP_COLS}, aliases FROM companies "
                        "WHERE is_latest = 1 AND aliases IS NOT NULL AND aliases <> ''"
                    ),
                )
                .mappings()
                .all()
            )
            for r in alias_rows:
                if t in _aliases_to_list(r.get("aliases")):
                    _append(
                        CandidateMatch(
                            company=self._row_to_ref(r),
                            match_kind="exact_alias",
                            matched_text=t,
                            rank=2,
                        )
                    )

            # 4. reverse_contains / prefix（sec_name 包含 mention；
            #    前缀命中的标 prefix，其余非前缀子串标 reverse_contains）
            name = _escape_like(t)
            rows = (
                conn.execute(
                    text(
                        f"SELECT {_LOOKUP_COLS}, "
                        "CASE WHEN sec_name LIKE :prefix " + escape_clause + " "
                        "THEN 'prefix' ELSE 'reverse_contains' END AS match_kind "
                        "FROM companies "
                        "WHERE is_latest = 1 AND sec_name IS NOT NULL "
                        "AND sec_name <> wind_code "
                        "AND LENGTH(sec_name) >= 2 "
                        "AND sec_name LIKE :contains " + escape_clause + " "
                        "ORDER BY LENGTH(sec_name), sec_name, wind_code "
                        "LIMIT :limit"
                    ),
                    {
                        "prefix": f"{name}%",
                        "contains": f"%{name}%",
                        "limit": query_limit,
                    },
                )
                .mappings()
                .all()
            )
            for r in rows:
                kind = str(r["match_kind"])  # prefix | reverse_contains
                _append(
                    CandidateMatch(
                        company=self._row_to_ref(r),
                        match_kind=kind,
                        matched_text=t,
                        rank=4,
                    )
                )

        merged.sort(
            key=lambda m: (m.rank, len(m.company.sec_name), m.company.wind_code)
        )
        truncated = len(merged) > limit
        return CandidateLookupResult(matches=merged[:limit], truncated=truncated)
