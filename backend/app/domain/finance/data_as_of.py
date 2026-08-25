"""公司真实数据截止期推导（2026-08-16 口径整改）。

背景：画像页「数据截止日」曾显示硬编码兜底串 "20260331"，
与库内真实报告期不符（如 600519.SH 三表最新仅 20251231）。
决策（团队拍板）：**禁止硬编码默认期**——

1. 用户显式传 as_of 时以用户值为准（规则引擎内部已有
   "请求期晚于最新披露期 → 回落到最新真实期"语义）；
2. 未传时从三表（母公司口径 408006000）推导该公司最新 report_period；
3. 三表均无数据时返回空串，由调用方/前端如实展示「-」，不伪造日期。

注意：本模块只读推导、绝不写库。
"""

from __future__ import annotations

from sqlalchemy import text

# 财务口径基线约束（8/2 确认）：母公司报表口径 408006000
_PARENT_STATEMENT_TYPE = "408006000"
_TABLES = ("income_statement", "balance_sheet", "cash_flow")


def resolve_company_data_as_of(wind_code: str) -> str:
    """返回该公司三表（母公司口径）最新 report_period（YYYYMMDD 字符串）。

    无数据 / 查询异常 → 返回 ""。
    """
    if not wind_code:
        return ""
    try:
        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        latest: str = ""
        with engine.connect() as conn:
            for table in _TABLES:
                value = conn.execute(
                    text(
                        f"SELECT MAX(report_period) FROM {table} "
                        "WHERE wind_code = :c AND statement_type = :s"
                    ),
                    {"c": wind_code, "s": _PARENT_STATEMENT_TYPE},
                ).scalar()
                if value is not None:
                    candidate = str(value).strip()
                    if candidate:
                        # 统一为 YYYYMMDD：fixture/SQLite 的 report_period 可能是
                        # ISO 格式（如 2018-12-31），下游按 "%Y%m%d" 解析。
                        candidate = candidate.replace("-", "")
                        if candidate > latest:
                            latest = candidate
        return latest
    except Exception:  # noqa: BLE001 — 推导失败不阻塞主流程，如实返回空串
        return ""
