"""SourceResolver — Phase C 任务 16.

按 EvidenceRef 定位底层来源记录（MySQL 财务表 / 公告 / Neo4j 关系 / 事件簇）。
找不到 → resolved=False，EvidenceRef 仍可返回（带 SOURCE_RECORD_NOT_FOUND）。
"""

from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _get_engine():
    """8/19 全面审查：改用公共工厂（完整 profile key + 缓存 + 切库 dispose）。

    原实现以模块级单例缓存，进程内切库后复用指向旧库的 Engine。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def _public_fields(row: dict, allow: set[str]) -> dict:
    """仅返回允许公开的字段（不泄露凭据）。"""
    return {k: v for k, v in row.items() if k in allow and v is not None}


_FIN_ALLOW = {
    "wind_code",
    "report_period",
    "statement_type",
    "ann_dt",
    "acct_rcv",
    "monetary_cap",
    "oth_rcv",
    "inventories",
    "tot_assets",
    "st_borrow",
    "lt_borrow",
    "oper_rev",
    "tot_oper_rev",
    "less_oper_cost",
    "oper_profit",
    "tot_profit",
    "net_profit_excl_min_int_inc",
    "net_profit_after_ded_nr_lp",
    "net_cash_flows_oper_act",
    "net_cash_flows_inv_act",
    "net_cash_flows_fnc_act",
    # 8/23 指标语义全库覆盖：新增可查科目一并允许公开（证据展示）
    "tot_cur_assets",
    "fix_assets",
    "goodwill",
    "acct_payable",
    "tot_cur_liab",
    "tot_liab",
    "tot_shrhldr_eqy_incl_min_int",
    "less_selling_dist_exp",
    "less_gerl_admin_exp",
    "less_fin_exp",
    "free_cash_flow",
    "net_incr_cash_cash_equ",
}


def _resolve_financial(source_record_id: str, source_table: str | None) -> dict:
    parts = (source_record_id or "").split("|")
    code = parts[0] if len(parts) > 0 and parts[0] else ""
    period = parts[1] if len(parts) > 1 and parts[1] else ""
    stmt = parts[2] if len(parts) > 2 and parts[2] else "408006000"
    table = source_table or "balance_sheet"
    if table not in ("balance_sheet", "income_statement", "cash_flow"):
        table = "balance_sheet"
    try:
        with _get_engine().connect() as conn:
            # 请求期可能晚于最新已披露报表（如 as_of=20260331 时最新期为
            # 20251231）——取 report_period <= 请求期的最近一条
            row = (
                conn.execute(
                    text(
                        f"SELECT * FROM {table} "
                        "WHERE wind_code = :code AND statement_type = :stmt "
                        "AND report_period <= :per "
                        "ORDER BY report_period DESC LIMIT 1"
                    ),
                    {"code": code, "per": period, "stmt": stmt},
                )
                .mappings()
                .first()
            )
        if not row:
            return {"resolved": False, "record": {}}
        return {"resolved": True, "record": _public_fields(dict(row), _FIN_ALLOW)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("财务来源解析失败: %s", exc)
        return {"resolved": False, "record": {}}


_ANN_ALLOW = {
    "object_id",
    "wind_code",
    "ann_dt",
    "n_info_title",
    "n_info_fcode",
    "sentiment",
    "sentiment_method",
    "source_uri",
    "content_hash",
}


def _resolve_announcement(source_record_id: str) -> dict:
    try:
        with _get_engine().connect() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM announcements WHERE object_id = :oid LIMIT 1"),
                    {"oid": source_record_id},
                )
                .mappings()
                .first()
            )
        if not row:
            return {"resolved": False, "record": {}}
        return {"resolved": True, "record": _public_fields(dict(row), _ANN_ALLOW)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("公告来源解析失败: %s", exc)
        return {"resolved": False, "record": {}}


def _resolve_neo4j_relationship(source_record_id: str) -> dict:
    try:
        from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

        adapter = Neo4jEquityGraph()
        rel = adapter.get_relationship_by_id_sync(source_record_id)
        if rel is None:
            return {"resolved": False, "record": {}}
        allow = {
            "relationship_id",
            "source_entity_id",
            "source_name",
            "target_entity_id",
            "target_name",
            "target_wind_code",
            "ownership_pct",
            "report_period",
            "ann_dt",
            "quantity",
            "is_latest",
            "graph_version",
        }
        return {
            "resolved": True,
            "record": {k: v for k, v in rel.items() if k in allow and v is not None},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j 来源解析失败: %s", exc)
        return {"resolved": False, "record": {}}


def _resolve_event_cluster(source_record_id: str) -> dict:
    try:
        from app.infrastructure.persistence.mysql.event_cluster_repository import (
            MySQLEventClusterRepository,
        )

        repo = MySQLEventClusterRepository()
        rec = repo.get_by_id_sync(source_record_id)
        if rec is None:
            return {"resolved": False, "record": {}}
        return {
            "resolved": True,
            "record": {
                "event_cluster_id": rec.event_cluster_id,
                "wind_code": rec.wind_code,
                "topic": rec.topic,
                "start_date": rec.start_date.isoformat(),
                "end_date": rec.end_date.isoformat(),
                "event_count": rec.event_count,
                "sentiment": rec.sentiment,
                "evidence_ids": rec.evidence_ids,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("事件簇来源解析失败: %s", exc)
        return {"resolved": False, "record": {}}


def _resolve_research_report(source_record_id: str) -> dict:
    """解析研报来源（评级拐点证据的最后一层回溯）。

    返回允许公开的字段：标题、公司、机构、发布日期、评级、摘要与来源 URI。
    """
    try:
        with _get_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT report_id, wind_code, sec_name, org_name, "
                        "publish_date, rating_org, rating_change, title, abstract, "
                        "source_uri, industry_l1 "
                        "FROM research_reports WHERE report_id = :rid LIMIT 1"
                    ),
                    {"rid": source_record_id},
                )
                .mappings()
                .first()
            )
        if row is None:
            return {"resolved": False, "record": {}}
        return {
            "resolved": True,
            "record": {k: (str(v) if v is not None else None) for k, v in row.items()},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("研报来源解析失败: %s", exc)
        return {"resolved": False, "record": {}}


def _resolve_company_registry(source_record_id: str) -> dict:
    """解析公司注册信息来源（R11：公司事实轻量查询的 Evidence 回查）。

    source_record_id = wind_code（如 600518.SH），返回可公开的公司主表字段。
    P2-1：复用模块内 _get_engine()，不每次新建连接池。
    """
    try:
        from sqlalchemy import text

        with _get_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT wind_code, sec_name, exchange_code, industry_l1, "
                        "listing_date, comp_type_code "
                        "FROM companies WHERE wind_code = :wc AND is_latest = 1 LIMIT 1"
                    ),
                    {"wc": source_record_id},
                )
                .mappings()
                .first()
            )
        if row is None:
            return {"resolved": False, "record": {}}
        return {
            "resolved": True,
            "record": {k: (str(v) if v is not None else None) for k, v in row.items()},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("公司注册信息解析失败: %s", exc)
        return {"resolved": False, "record": {}}


def resolve_source(
    *,
    source_type: str,
    source_record_id: str,
    source_table: str | None = None,
) -> dict:
    """按证据字段定位底层来源记录."""
    if source_type == "financial_statement":
        return _resolve_financial(source_record_id, source_table)
    if source_type == "announcement":
        return _resolve_announcement(source_record_id)
    if source_type == "neo4j_relationship":
        return _resolve_neo4j_relationship(source_record_id)
    if source_type == "event_cluster":
        return _resolve_event_cluster(source_record_id)
    if source_type == "research_report":
        return _resolve_research_report(source_record_id)
    if source_type == "company_registry":
        return _resolve_company_registry(source_record_id)
    return {"resolved": False, "record": {}}
