"""MySQL 数据读取工具 — 供规则函数使用."""

from sqlalchemy import create_engine, text

from app.domain.finance.field_mapping import get_table

_ENGINE = None


def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        from app.core.config import settings

        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _ENGINE = create_engine(url, pool_pre_ping=True)
    return _ENGINE


def fetch_field(company_code: str, field_name: str, periods: int = 8) -> list:
    """查询某个财务字段最近 N 期的值（按 report_period 升序）.

    Args:
        company_code: 如 '600518.SH'
        field_name: 如 'acct_rcv'
        periods: 回溯期数

    Returns:
        按时间升序排列的值列表，缺失值为 None
    """
    table = get_table(field_name)
    engine = _get_engine()
    sql = text(f"""
        SELECT {field_name} FROM {table}
        WHERE wind_code = :code
          AND statement_type = '408006000'
        ORDER BY report_period ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"code": company_code}).fetchall()
    values = [float(r[0]) if r[0] is not None else None for r in rows]
    # 取最近 periods 期
    return values[-periods:] if len(values) > periods else values


def fetch_company_field(company_code: str, field_name: str) -> int | str | None:
    """查询 companies 表某个字段.

    Args:
        company_code: 如 '600518.SH'
        field_name: 'comp_type_code' | 'industry_l1' | 'sec_name'
    """
    engine = _get_engine()
    sql = text(f"SELECT {field_name} FROM companies WHERE wind_code = :code LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(sql, {"code": company_code}).fetchone()
    return row[0] if row else None


def fetch_industry_peers(
    industry_l1: str, field_name: str, table_name: str, as_of_period: str = "20260331"
) -> list:
    """查询同行业所有公司在某个报告期的某个字段值列表."""
    engine = _get_engine()
    sql = text(f"""
        SELECT t.{field_name}
        FROM {table_name} t
        JOIN companies c ON t.wind_code = c.wind_code
        WHERE c.industry_l1 = :industry
          AND t.report_period = :period
          AND t.statement_type = '408006000'
          AND c.comp_type_code = 1
    """)
    with engine.connect() as conn:
        rows = conn.execute(
            sql, {"industry": industry_l1, "period": as_of_period}
        ).fetchall()
    return [float(r[0]) for r in rows if r[0] is not None]
