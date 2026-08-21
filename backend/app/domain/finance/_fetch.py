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
from sqlalchemy import text

from app.domain.finance.field_mapping import get_table
from app.domain.finance.statement_type import (
    PARENT_STATEMENT_SCOPE,
    PARENT_STATEMENT_TYPE,
)
from app.domain.finance._engine_utils import _ENGINES


@dataclass
class SeriesResult:
    """字段时序读取结果 — 携带口径与覆盖率信息."""

    values: list  # 按 report_period 升序的值列表，缺失为 None
    scope: str = PARENT_STATEMENT_SCOPE  # 恒为 "parent_company"
    statement_type: str = PARENT_STATEMENT_TYPE  # 恒为 "408006000"
    coverage: float = 0.0  # 期望窗口内有效值占比
    warning: str | None = None  # 覆盖不足或母公司数据缺失时的警告
    periods: list = field(default_factory=list)  # 实际读取到的报告期


def align_by_period(**series: "SeriesResult") -> dict[str, dict[str, float | None]]:
    """按期次对齐多字段序列（P2-3）。

    命名参数：align_by_period(cash=cash_sr, assets=assets_sr)
    返回 {period: {field_name: value}}，按 period 升序；
    某字段在该期无数据 → None（调用方决定跳过，不按零处理）。
    """
    periods: set[str] = set()
    for s in series.values():
        periods.update(str(p) for p in (s.periods or []))
    ordered = sorted(periods)
    aligned: dict[str, dict[str, float | None]] = {}
    for p in ordered:
        row: dict[str, float | None] = {}
        for name, s in series.items():
            idx = s.periods.index(p) if p in s.periods else None
            row[name] = s.values[idx] if idx is not None else None
        aligned[p] = row
    return aligned


def prev_year_period(period: str, ordered_periods: list[str]) -> str | None:
    """返回 period 的**精确**前一年同月日报表期 key（P2-3 核验修订）。

    R6/R1/R4 的"4 期前"必须取去年同期（YYYY-1 + 相同 MMDD），不能按并集
    数组下标 -5 推断——各字段期次错位时下标会取到不同月日的期。
    精确去年同期不存在时返回 None（R2 审查修订：不得回退到两年前——
    20251231 + 20231231 会被误当同比）。
    """
    if len(period) == 8:
        prev = f"{int(period[:4]) - 1}{period[4:]}"
        return prev if prev in ordered_periods else None
    return None


def _engine_profile_key(settings) -> str:
    """兼容旧调用方，统一使用公共 Engine profile 口径。"""
    from app.domain.finance._engine_utils import engine_profile_key

    return engine_profile_key(settings)


def _get_engine():
    """保留模块级入口，兼容旧测试和调用方。"""
    from app.domain.finance._engine_utils import _ENGINES as shared_engines
    from app.domain.finance._engine_utils import get_engine

    # 旧测试会替换本模块的缓存字典；同步清理公共缓存，避免测试间复用
    # 已释放或指向旧 SQLite 临时库的 Engine。
    if _ENGINES is not shared_engines:
        for engine in _ENGINES.values():
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass
        shared_engines.clear()

    return get_engine()


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
