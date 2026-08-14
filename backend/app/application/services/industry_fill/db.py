"""数据库访问层（档案 v1.1 §7）：快照、研报确定性补全、apply 与覆盖率统计。

设计约束：
- apply 使用单次批量事务（禁止逐条 engine.begin()）；
- 默认只补缺失：SQL 必须带 `industry_l1 IS NULL OR TRIM(industry_l1)=''`；
- apply 前后均执行 SELECT DATABASE() 守卫；
- 占位值清洗（industry_source='nan'→NULL）与补全同批事务；
- 兼容 MySQL（pymysql）与 SQLite（集成测试用），SQL 保持可移植。
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import Engine, text

from backend.app.application.services.industry_fill.constants import (
    SOURCE_RESEARCH_REPORT,
)
from backend.app.application.services.industry_fill.normalizer import (
    normalize_optional_text,
)

log = logging.getLogger(__name__)


def current_database(engine: Engine) -> str:
    """读取当前连接库名；SQLite 返回文件路径（无 DATABASE 概念，守卫等效）。"""
    if engine.dialect.name == "sqlite":
        return str(engine.url.database or ":memory:")
    with engine.connect() as conn:
        return str(conn.execute(text("SELECT DATABASE()")).scalar() or "")


def fetch_companies_snapshot(engine: Engine) -> dict[str, dict]:
    """companies 行业相关字段快照：wind_code → {sec_name, industry_l1, ...}。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wind_code, sec_name, industry_l1, industry_l2, "
                "sw_indu_code, industry_source, industry_as_of FROM companies"
            )
        ).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        out[str(row[0])] = {
            "sec_name": normalize_optional_text(row[1]),
            "industry_l1": normalize_optional_text(row[2]),
            "industry_l2": normalize_optional_text(row[3]),
            "sw_indu_code": normalize_optional_text(row[4]),
            "industry_source": normalize_optional_text(row[5]),
            "industry_as_of": str(row[6]) if row[6] is not None else None,
        }
    return out


def fetch_report_industry_map(engine: Engine) -> dict[str, dict]:
    """研报确定性补全：research_reports 中 (wind_code → 行业) 映射。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wind_code, MAX(sec_name), MAX(industry_l1), MAX(sw_indu_code) "
                "FROM research_reports "
                "WHERE industry_l1 IS NOT NULL AND TRIM(industry_l1) <> '' "
                "GROUP BY wind_code"
            )
        ).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        out[str(row[0])] = {
            "sec_name": normalize_optional_text(row[1]),
            "industry_l1": normalize_optional_text(row[2]),
            "sw_indu_code": normalize_optional_text(row[3]),
            "source": SOURCE_RESEARCH_REPORT,
        }
    return out


def compute_missing_codes(
    snapshot: dict[str, dict], report_map: dict[str, dict]
) -> tuple[list[str], dict[str, dict]]:
    """缺失代码快照 + 研报可直接确定性补全的行（档案 §3 链路）。"""
    missing: list[str] = []
    research_fills: dict[str, dict] = {}
    for code, info in snapshot.items():
        if not (info.get("industry_l1") or "").strip():
            if code in report_map:
                research_fills[code] = report_map[code]
            else:
                missing.append(code)
    return sorted(missing), research_fills


def apply_industry_fill(
    engine: Engine,
    *,
    expected_database: str,
    rows: list[tuple[str, str | None, str | None, str | None, str]],
    replace: bool = False,
    as_of: date | None = None,
) -> dict:
    """阶段二：单次批量事务更新 companies（档案 §7.2/§7.3）。

    rows: [(wind_code, l1, l2, sw, source)]，由调用方按缺失/覆盖条件预筛。
    同一事务清洗 industry_source='nan' 占位值（档案 v1.1 §8）。
    任一异常整体回滚；提交后重新统计覆盖率与来源分布。
    """
    actual = current_database(engine)
    if str(actual or "").lower() != str(expected_database or "").lower():
        raise AssertionError(
            f"apply 前守卫失败：SELECT DATABASE()={actual!r}，期望 {expected_database!r}"
        )
    day = as_of or date.today()
    updated = 0
    with engine.begin() as conn:  # 单事务：任一失败整体回滚
        for wind_code, l1, l2, sw, source in rows:
            if replace:
                clause = "WHERE wind_code = :wc"
            else:
                clause = (
                    "WHERE wind_code = :wc "
                    "AND (industry_l1 IS NULL OR TRIM(industry_l1) = '')"
                )
            result = conn.execute(
                text(
                    "UPDATE companies SET industry_l1=:l1, industry_l2=:l2, "
                    "sw_indu_code=:sw, industry_source=:src, industry_as_of=:asof "
                    f"{clause}"
                ),
                {
                    "l1": l1,
                    "l2": l2,
                    "sw": sw,
                    "src": source,
                    "asof": day.isoformat(),
                    "wc": wind_code,
                },
            )
            updated += result.rowcount or 0
        # 占位值清洗（同一事务，档案 v1.1 §8：不单独大规模改写历史来源值）
        conn.execute(
            text(
                "UPDATE companies SET industry_source = NULL "
                "WHERE LOWER(TRIM(COALESCE(industry_source,''))) "
                "IN ('nan','none','null')"
            )
        )
    post = fetch_coverage_stats(engine)
    return {
        "companies_updated": updated,
        "companies_with_industry_after": post["companies_with_industry_before"],
        "nan_source_count": post["nan_source_count"],
    }


def fetch_coverage_stats(engine: Engine) -> dict:
    """只读覆盖率与来源统计（档案 §9 验收 SQL / 附录 A）。"""
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar()
        covered = conn.execute(
            text(
                "SELECT COUNT(*) FROM companies "
                "WHERE industry_l1 IS NOT NULL AND TRIM(industry_l1) <> ''"
            )
        ).scalar()
        nan_src = conn.execute(
            text(
                "SELECT COUNT(*) FROM companies "
                "WHERE LOWER(TRIM(COALESCE(industry_source,''))) "
                "IN ('nan','none','null')"
            )
        ).scalar()
        dup = conn.execute(
            text(
                "SELECT COUNT(*) FROM (SELECT wind_code FROM companies "
                "GROUP BY wind_code HAVING COUNT(*) > 1) t"
            )
        ).scalar()
        src_rows = conn.execute(
            text(
                "SELECT COALESCE(industry_source,'<NULL>'), COUNT(*) "
                "FROM companies GROUP BY industry_source ORDER BY 2 DESC"
            )
        ).fetchall()
        rr_total = conn.execute(text("SELECT COUNT(*) FROM research_reports")).scalar()
        rr_codes = conn.execute(
            text("SELECT COUNT(DISTINCT wind_code) FROM research_reports")
        ).scalar()
        rr_with_ind = conn.execute(
            text(
                "SELECT COUNT(DISTINCT wind_code) FROM research_reports "
                "WHERE industry_l1 IS NOT NULL AND TRIM(industry_l1) <> ''"
            )
        ).scalar()
        rr_matched = conn.execute(
            text(
                "SELECT COUNT(*) FROM (SELECT DISTINCT r.wind_code "
                "FROM research_reports r JOIN companies c ON c.wind_code = r.wind_code "
                "WHERE r.industry_l1 IS NOT NULL AND TRIM(r.industry_l1) <> '') t"
            )
        ).scalar()
    missing = int(total or 0) - int(covered or 0)
    return {
        "companies_total": int(total or 0),
        "companies_with_industry_before": int(covered or 0),
        "missing": missing,
        "final_coverage": (
            round(100.0 * int(covered or 0) / int(total or 0), 2) if total else 0.0
        ),
        "source_distribution": {str(k): int(v) for k, v in src_rows},
        "nan_source_count": int(nan_src or 0),
        "duplicate_wind_codes": int(dup or 0),
        "research_report_codes": int(rr_with_ind or 0),
        "research_report_matched": int(rr_matched or 0),
        "research_report_distinct_codes": int(rr_codes or 0),
        "research_reports_total_rows": int(rr_total or 0),
    }
