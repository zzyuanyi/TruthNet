"""财务数据读取 — 双后端 + 固定母公司报表口径.

设计要点（Phase C 口径修正）:
- 遵循 settings.SQL_BACKEND: lite → SQLite（本地测试/CI），full → MySQL。
- 项目财务反欺诈规则固定采用母公司报表口径
  （PARENT_STATEMENT_TYPE=408006000，scope=parent_company）。
  不查询合并报表（408001000），不做任何口径切换，不输出口径降级 warning。
- 若某字段无母公司报表数据，返回空 values + coverage=0 + 明确的"缺少母公司报表" warning，
  绝不回退到合并口径。
- as_of 过滤: 只取 report_period <= as_of 的报告期（字符串比较，YYYYMMDD）。
"""

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, text

from app.domain.finance.field_mapping import get_table
from app.domain.finance.statement_type import (
    PARENT_STATEMENT_SCOPE,
    PARENT_STATEMENT_TYPE,
)

_ENGINES: dict[str, object] = {}


@dataclass
class SeriesResult:
    """字段时序读取结果 — 携带口径与覆盖率信息."""

    values: list  # 按 report_period 升序的值列表，缺失为 None
    scope: str = PARENT_STATEMENT_SCOPE  # 恒为 "parent_company"
    statement_type: str = PARENT_STATEMENT_TYPE  # 恒为 "408006000"
    coverage: float = 0.0  # 期望窗口内有效值占比
    warning: str | None = None  # 覆盖不足或母公司数据缺失时的警告
    periods: list = field(default_factory=list)  # 实际读取到的报告期


def _repo_root() -> Path:
    # backend/app/domain/finance/_fetch.py -> 项目根
    return Path(__file__).resolve().parents[4]


def _get_engine():
    from app.core.config import settings

    backend = settings.SQL_BACKEND
    if backend in _ENGINES:
        return _ENGINES[backend]

    if backend == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _ENGINES[backend] = create_engine(url, pool_pre_ping=True)
    else:  # sqlite（lite profile）
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _ENGINES[backend] = create_engine(f"sqlite:///{path.as_posix()}")
    return _ENGINES[backend]


def fetch_series(
    company_code: str,
    field_name: str,
    periods: int = 8,
    as_of: str = "20260331",
) -> SeriesResult:
    """读取某财务字段最近 N 期 — 固定母公司报表口径（408006000）。

    只执行一次母公司查询；无记录时返回空 SeriesResult，coverage=0，
    warning 明确提示缺少母公司报表数据（statement_type=408006000）。
    """
    table = get_table(field_name)
    engine = _get_engine()
    as_of_clause = " AND report_period <= :as_of" if as_of else ""

    sql = text(
        f"SELECT report_period, {field_name} FROM {table} "
        f"WHERE wind_code = :code AND statement_type = :stmt "
        f"{as_of_clause} ORDER BY report_period ASC"
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "code": company_code,
                "stmt": PARENT_STATEMENT_TYPE,
                "as_of": as_of,
            },
        ).fetchall()

    if not rows:
        return SeriesResult(
            values=[],
            scope=PARENT_STATEMENT_SCOPE,
            statement_type=PARENT_STATEMENT_TYPE,
            coverage=0.0,
            warning=(
                f"{field_name} 缺少母公司报表数据"
                f"（statement_type={PARENT_STATEMENT_TYPE}）"
            ),
        )

    periods_actual = [r[0] for r in rows]
    values = [float(r[1]) if r[1] is not None else None for r in rows]
    values = values[-periods:] if len(values) > periods else values
    periods_actual = (
        periods_actual[-periods:] if len(periods_actual) > periods else periods_actual
    )

    valid = sum(1 for v in values if v is not None)
    coverage = round(valid / periods, 2) if periods else 0.0
    warning: str | None = None
    if coverage < 0.5:
        warning = f"{field_name} 覆盖率仅 {coverage:.0%}（有效 {valid}/{periods} 期）"

    return SeriesResult(
        values=values,
        scope=PARENT_STATEMENT_SCOPE,
        statement_type=PARENT_STATEMENT_TYPE,
        coverage=coverage,
        warning=warning,
        periods=periods_actual,
    )


def fetch_field(
    company_code: str,
    field_name: str,
    periods: int = 8,
    as_of: str = "20260331",
) -> list:
    """兼容旧调用：仅返回值列表（固定母公司报表口径）。"""
    return fetch_series(company_code, field_name, periods, as_of).values


def fetch_company_field(company_code: str, field_name: str) -> int | str | None:
    """查询 companies 表某个字段."""
    engine = _get_engine()
    sql = text(f"SELECT {field_name} FROM companies WHERE wind_code = :code LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(sql, {"code": company_code}).fetchone()
    return row[0] if row else None


def fetch_industry_peers(
    industry_l1: str,
    field_name: str,
    table_name: str,
    as_of_period: str = "20260331",
) -> tuple[list, str]:
    """查询同行业公司在某报告期的字段值列表 — 固定母公司报表口径。

    同行业比较只取母公司口径（408006000）数据，不混入合并口径。
    未命中母公司数据时返回空列表。

    Returns:
        (values, scope)  # scope 恒为 "parent_company"
    """
    engine = _get_engine()
    table = table_name

    sql = text(
        f"SELECT t.{field_name} "
        f"FROM {table} t "
        f"JOIN companies c ON t.wind_code = c.wind_code "
        f"WHERE c.industry_l1 = :industry "
        f"AND t.report_period = :period "
        f"AND t.statement_type = :stmt "
        f"AND c.comp_type_code = 1"
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "industry": industry_l1,
                "period": as_of_period,
                "stmt": PARENT_STATEMENT_TYPE,
            },
        ).fetchall()
    return (
        [float(r[0]) for r in rows if r[0] is not None],
        PARENT_STATEMENT_SCOPE,
    )
