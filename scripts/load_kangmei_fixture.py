#!/usr/bin/env python
"""Kangmei 药业测试数据安全加载器（数据层 ONLY，无 DDL）。

设计原则：
- 仅操作数据（INSERT/DELETE/UPDATE），绝不含 CREATE/DROP/ALTER
- 幂等：可重复运行，行数稳定
- 只触碰 dataset_version="kangmei-fixture-v1" 的记录
- 使用 SQLAlchemy ORM（backend.app.infrastructure.persistence.models）
- 支持 SQLite（lite profile）和 MySQL（full profile）

用法:
    python scripts/load_kangmei_fixture.py                # 加载数据
    python scripts/load_kangmei_fixture.py --dry-run      # 预览（不写入）
    python scripts/load_kangmei_fixture.py --verify-only  # 仅校验已加载的数据
    python scripts/load_kangmei_fixture.py --dataset-version my-v2  # 自定义版本标记
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 确保 backend/ 在 sys.path 中，以便从任意位置运行
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_SRC = _REPO_ROOT / "backend"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

# 加载 .env（若存在）
from dotenv import load_dotenv  # noqa: E402

_env_path = _REPO_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

from sqlalchemy import URL as EngineURL, create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.infrastructure.persistence.models import (  # noqa: E402
    Announcement,
    BalanceSheet,
    Base,
    CashFlow,
    Company,
    IncomeStatement,
    ResearchReport,
    TopShareholder,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_DEFAULT_DATASET_VERSION = "kangmei-fixture-v1"
_WIND_CODE = "600518.SH"
_ENTITY_ID = "company_600518_SH"
_SOURCE_TYPE = "fixture"
_SOURCE_FILE = "scripts/load_kangmei_fixture.py"
_STATEMENT_TYPE = "408006000"  # 合并报表口径

# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------


def _build_database_url() -> tuple[EngineURL | str, str]:
    """构建数据库 URL，对齐 Alembic env.py 逻辑。

    返回 (url, backend_name)，其中 backend_name 为 "sqlite" 或 "mysql"。

    TRUTHNET_PROFILE=lite  -> SQLite
    TRUTHNET_PROFILE=full  -> MySQL
    """
    profile = os.getenv("TRUTHNET_PROFILE", "lite")
    sql_backend = os.getenv("SQL_BACKEND", "sqlite")

    if profile == "full" or sql_backend == "mysql":
        # 检查 pymysql 驱动是否可用
        try:
            import pymysql  # noqa: F401
        except ImportError:
            print(
                "[WARN] pymysql 未安装，MySQL 不可用，自动回退到 SQLite。\n"
                "       如需使用 MySQL，请运行: pip install pymysql",
                file=sys.stderr,
            )
            sqlite_path = os.getenv("SQLITE_PATH", "data/truthnet.db")
            if not os.path.isabs(sqlite_path):
                sqlite_path = str(_REPO_ROOT / sqlite_path)
            return f"sqlite:///{sqlite_path}", "sqlite"

        host = os.getenv("MYSQL_HOST", "localhost")
        port = int(os.getenv("MYSQL_PORT", "3306"))
        database = os.getenv("MYSQL_DATABASE", "truthnet")
        user = os.getenv("MYSQL_USER", "truthnet")
        password = os.getenv("MYSQL_PASSWORD", "")

        return (
            EngineURL.create(
                "mysql+pymysql",
                username=user,
                password=password,
                host=host,
                port=port,
                database=database,
                query={"charset": "utf8mb4"},
            ),
            "mysql",
        )
    else:
        sqlite_path = os.getenv("SQLITE_PATH", "data/truthnet.db")
        if not os.path.isabs(sqlite_path):
            sqlite_path = str(_REPO_ROOT / sqlite_path)
        return f"sqlite:///{sqlite_path}", "sqlite"


def _create_session_factory(database_url: Any, backend: str):
    """创建 SQLAlchemy session factory."""
    connect_args: dict[str, Any] = {}
    if backend == "sqlite":
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
    )
    return sessionmaker(bind=engine)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_system_fields(
    dataset_version: str,
    source_record_id: str,
    source_row: int | None = None,
) -> dict[str, Any]:
    """构建 SystemFieldsMixin 所需的公共字段字典。"""
    return {
        "source_record_id": source_record_id,
        "source_file": _SOURCE_FILE,
        "source_row": source_row,
        "source_type": _SOURCE_TYPE,
        "dataset_version": dataset_version,
        "revision_no": 1,
        "is_latest": True,
        "ingested_at": _utcnow(),
        "updated_at": _utcnow(),
        "quality_flags": None,
        "checksum": None,
    }


# ---------------------------------------------------------------------------
# 存量清理（仅 kangmei-fixture 标记的记录）
# ---------------------------------------------------------------------------


def _count_by_dataset(session: Session, model: type[Base], version: str) -> int:
    """统计指定 dataset_version 的记录数。"""
    return session.query(model).filter(model.dataset_version == version).count()


def _delete_by_dataset(session: Session, model: type[Base], version: str) -> int:
    """删除指定 dataset_version 的所有记录，返回删除行数。"""
    count = _count_by_dataset(session, model, version)
    if count > 0:
        session.query(model).filter(model.dataset_version == version).delete()
    return count


def clear_kangmei_fixture(session: Session, dataset_version: str) -> dict[str, int]:
    """删除所有 dataset_version 匹配的 Kangmei fixture 记录。

    先删派生表（如有），再删核心表。无 FK 依赖的核心表顺序无关紧要，
    但保持自底向上以策安全。
    """
    stats: dict[str, int] = {}
    # 核心表：从"叶子"开始（无 FK 约束，但保持好习惯）
    for model, label in [
        (ResearchReport, "research_reports"),
        (Announcement, "announcements"),
        (TopShareholder, "top_shareholders"),
        (CashFlow, "cash_flow"),
        (IncomeStatement, "income_statement"),
        (BalanceSheet, "balance_sheet"),
        (Company, "companies"),
    ]:
        stats[label] = _delete_by_dataset(session, model, dataset_version)
    session.flush()
    return stats


# ---------------------------------------------------------------------------
# 数据加载函数
# ---------------------------------------------------------------------------


def load_company(session: Session, dataset_version: str) -> Company:
    """加载康美药业公司记录。

    使用固定的 entity_id 以保证幂等。
    """
    existing = session.get(Company, _ENTITY_ID)
    if existing is not None:
        # 幂等：如果已存在且版本匹配则更新，否则报错（保护非 Kangmei 数据）
        if existing.dataset_version == dataset_version:
            return existing
        raise RuntimeError(
            f"公司 {_ENTITY_ID} 已存在但 dataset_version="
            f"{existing.dataset_version!r}（非 {dataset_version!r}），"
            f"拒绝覆盖非 fixture 数据。"
        )

    company = Company(
        entity_id=_ENTITY_ID,
        wind_code=_WIND_CODE,
        sec_name="康美药业股份有限公司",
        aliases=["康美药业", "康美", "Kangmei Pharmaceutical"],
        exchange_code="XSHG",
        industry_l1="医药生物",
        industry_l2="中药",
        sw_indu_code="370101",
        comp_type_code=1,
        listing_date=date(2001, 3, 19),
        industry_source="申万研究所",
        industry_as_of=date(2024, 1, 1),
        # 系统字段
        source_record_id="kmfy_company",
        source_file=_SOURCE_FILE,
        source_row=None,
        source_type=_SOURCE_TYPE,
        dataset_version=dataset_version,
        revision_no=1,
        is_latest=True,
        ingested_at=_utcnow(),
        updated_at=_utcnow(),
        quality_flags=None,
        checksum=None,
    )
    session.add(company)
    session.flush()
    return company


# ---- 资产负债表 -----------------------------------------------------------


def _build_balance_sheets(dataset_version: str) -> list[BalanceSheet]:
    """构建 4 期资产负债表（2015–2018，单位：万元）。

    2015–2017 为造假高峰期（货币资金虚增），2018 为差错更正后数据。
    """
    periods: list[dict[str, Any]] = [
        {
            "report_period": "2015-12-31",
            "ann_dt": "2016-04-25",
            "monetary_cap": 1_580_000.0,
            "acct_rcv": 280_000.0,
            "oth_rcv": 18_000.0,
            "inventories": 980_000.0,
            "tot_cur_assets": 2_950_000.0,
            "fix_assets": 620_000.0,
            "goodwill": 35_000.0,
            "tot_assets": 3_810_000.0,
            "st_borrow": 460_000.0,
            "lt_borrow": 180_000.0,
            "acct_payable": 240_000.0,
            "tot_cur_liab": 1_380_000.0,
            "tot_liab": 2_050_000.0,
            "tot_shrhldr_eqy_incl_min_int": 1_760_000.0,
        },
        {
            "report_period": "2016-12-31",
            "ann_dt": "2017-04-28",
            "monetary_cap": 2_730_000.0,
            "acct_rcv": 310_000.0,
            "oth_rcv": 22_000.0,
            "inventories": 1_260_000.0,
            "tot_cur_assets": 4_450_000.0,
            "fix_assets": 780_000.0,
            "goodwill": 55_000.0,
            "tot_assets": 5_480_000.0,
            "st_borrow": 820_000.0,
            "lt_borrow": 240_000.0,
            "acct_payable": 320_000.0,
            "tot_cur_liab": 2_270_000.0,
            "tot_liab": 3_100_000.0,
            "tot_shrhldr_eqy_incl_min_int": 2_380_000.0,
        },
        {
            "report_period": "2017-12-31",
            "ann_dt": "2018-04-26",
            "monetary_cap": 3_420_000.0,
            "acct_rcv": 430_000.0,
            "oth_rcv": 38_000.0,
            "inventories": 1_570_000.0,
            "tot_cur_assets": 5_640_000.0,
            "fix_assets": 880_000.0,
            "goodwill": 65_000.0,
            "tot_assets": 6_870_000.0,
            "st_borrow": 1_130_000.0,
            "lt_borrow": 350_000.0,
            "acct_payable": 450_000.0,
            "tot_cur_liab": 3_160_000.0,
            "tot_liab": 4_220_000.0,
            "tot_shrhldr_eqy_incl_min_int": 2_650_000.0,
        },
        {
            "report_period": "2018-12-31",
            "ann_dt": "2019-04-30",
            "monetary_cap": 180_000.0,
            "acct_rcv": 380_000.0,
            "oth_rcv": 22_000.0,
            "inventories": 920_000.0,
            "tot_cur_assets": 1_620_000.0,
            "fix_assets": 830_000.0,
            "goodwill": 0.0,
            "tot_assets": 2_650_000.0,
            "st_borrow": 1_350_000.0,
            "lt_borrow": 420_000.0,
            "acct_payable": 510_000.0,
            "tot_cur_liab": 3_480_000.0,
            "tot_liab": 4_680_000.0,
            "tot_shrhldr_eqy_incl_min_int": -2_030_000.0,
        },
    ]

    results: list[BalanceSheet] = []
    for i, p in enumerate(periods):
        bs = BalanceSheet(
            wind_code=_WIND_CODE,
            report_period=p["report_period"],
            statement_type=_STATEMENT_TYPE,
            ann_dt=p["ann_dt"],
            monetary_cap=p["monetary_cap"],
            acct_rcv=p["acct_rcv"],
            oth_rcv=p["oth_rcv"],
            inventories=p["inventories"],
            tot_cur_assets=p["tot_cur_assets"],
            fix_assets=p["fix_assets"],
            goodwill=p["goodwill"],
            tot_assets=p["tot_assets"],
            st_borrow=p["st_borrow"],
            lt_borrow=p["lt_borrow"],
            acct_payable=p["acct_payable"],
            tot_cur_liab=p["tot_cur_liab"],
            tot_liab=p["tot_liab"],
            tot_shrhldr_eqy_incl_min_int=p["tot_shrhldr_eqy_incl_min_int"],
            **_make_system_fields(
                dataset_version, f"kmfy_bs_{p['report_period']}", i + 1
            ),
        )
        results.append(bs)
    return results


def load_balance_sheets(session: Session, dataset_version: str) -> list[BalanceSheet]:
    records = _build_balance_sheets(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---- 利润表 ---------------------------------------------------------------


def _build_income_statements(dataset_version: str) -> list[IncomeStatement]:
    """构建 4 期利润表（2015–2018，单位：万元）。

    2018 年为差错更正后数据，出现巨额亏损。
    """
    periods: list[dict[str, Any]] = [
        {
            "report_period": "2015-12-31",
            "ann_dt": "2016-04-25",
            "oper_rev": 1_800_000.0,
            "tot_oper_rev": 1_806_000.0,
            "less_oper_cost": 1_310_000.0,
            "less_selling_dist_exp": 125_000.0,
            "less_gerl_admin_exp": 98_000.0,
            "less_fin_exp": 72_000.0,
            "oper_profit": 200_000.0,
            "tot_profit": 195_000.0,
            "net_profit_excl_min_int_inc": 165_000.0,
            "net_profit_after_ded_nr_lp": 163_000.0,
        },
        {
            "report_period": "2016-12-31",
            "ann_dt": "2017-04-28",
            "oper_rev": 2_160_000.0,
            "tot_oper_rev": 2_164_000.0,
            "less_oper_cost": 1_570_000.0,
            "less_selling_dist_exp": 156_000.0,
            "less_gerl_admin_exp": 118_000.0,
            "less_fin_exp": 86_000.0,
            "oper_profit": 232_000.0,
            "tot_profit": 228_000.0,
            "net_profit_excl_min_int_inc": 195_000.0,
            "net_profit_after_ded_nr_lp": 188_000.0,
        },
        {
            "report_period": "2017-12-31",
            "ann_dt": "2018-04-26",
            "oper_rev": 2_640_000.0,
            "tot_oper_rev": 2_648_000.0,
            "less_oper_cost": 1_930_000.0,
            "less_selling_dist_exp": 188_000.0,
            "less_gerl_admin_exp": 142_000.0,
            "less_fin_exp": 105_000.0,
            "oper_profit": 280_000.0,
            "tot_profit": 275_000.0,
            "net_profit_excl_min_int_inc": 235_000.0,
            "net_profit_after_ded_nr_lp": 228_000.0,
        },
        {
            "report_period": "2018-12-31",
            "ann_dt": "2019-04-30",
            "oper_rev": 1_820_000.0,
            "tot_oper_rev": 1_824_000.0,
            "less_oper_cost": 1_560_000.0,
            "less_selling_dist_exp": 165_000.0,
            "less_gerl_admin_exp": 135_000.0,
            "less_fin_exp": 138_000.0,
            "oper_profit": -176_000.0,
            "tot_profit": -192_000.0,
            "net_profit_excl_min_int_inc": -195_000.0,
            "net_profit_after_ded_nr_lp": -198_000.0,
        },
    ]

    results: list[IncomeStatement] = []
    for i, p in enumerate(periods):
        rec = IncomeStatement(
            wind_code=_WIND_CODE,
            report_period=p["report_period"],
            statement_type=_STATEMENT_TYPE,
            ann_dt=p["ann_dt"],
            oper_rev=p["oper_rev"],
            tot_oper_rev=p["tot_oper_rev"],
            less_oper_cost=p["less_oper_cost"],
            less_selling_dist_exp=p["less_selling_dist_exp"],
            less_gerl_admin_exp=p["less_gerl_admin_exp"],
            less_fin_exp=p["less_fin_exp"],
            oper_profit=p["oper_profit"],
            tot_profit=p["tot_profit"],
            net_profit_excl_min_int_inc=p["net_profit_excl_min_int_inc"],
            net_profit_after_ded_nr_lp=p["net_profit_after_ded_nr_lp"],
            **_make_system_fields(
                dataset_version, f"kmfy_is_{p['report_period']}", i + 1
            ),
        )
        results.append(rec)
    return results


def load_income_statements(
    session: Session, dataset_version: str
) -> list[IncomeStatement]:
    records = _build_income_statements(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---- 现金流量表 -----------------------------------------------------------


def _build_cash_flows(dataset_version: str) -> list[CashFlow]:
    """构建 4 期现金流量表（单位：万元）。

    关键信号：2017–2018 经营现金流持续为负，与账面利润严重背离。
    """
    periods: list[dict[str, Any]] = [
        {
            "report_period": "2015-12-31",
            "ann_dt": "2016-04-25",
            "net_cash_flows_oper_act": 42_000.0,
            "net_cash_flows_inv_act": -185_000.0,
            "net_cash_flows_fnc_act": 220_000.0,
            "net_incr_cash_cash_equ": 77_000.0,
            "free_cash_flow": -143_000.0,
        },
        {
            "report_period": "2016-12-31",
            "ann_dt": "2017-04-28",
            "net_cash_flows_oper_act": 38_000.0,
            "net_cash_flows_inv_act": -210_000.0,
            "net_cash_flows_fnc_act": 280_000.0,
            "net_incr_cash_cash_equ": 108_000.0,
            "free_cash_flow": -172_000.0,
        },
        {
            "report_period": "2017-12-31",
            "ann_dt": "2018-04-26",
            "net_cash_flows_oper_act": -185_000.0,
            "net_cash_flows_inv_act": -245_000.0,
            "net_cash_flows_fnc_act": 320_000.0,
            "net_incr_cash_cash_equ": -110_000.0,
            "free_cash_flow": -430_000.0,
        },
        {
            "report_period": "2018-12-31",
            "ann_dt": "2019-04-30",
            "net_cash_flows_oper_act": -320_000.0,
            "net_cash_flows_inv_act": -95_000.0,
            "net_cash_flows_fnc_act": 150_000.0,
            "net_incr_cash_cash_equ": -265_000.0,
            "free_cash_flow": -415_000.0,
        },
    ]

    results: list[CashFlow] = []
    for i, p in enumerate(periods):
        rec = CashFlow(
            wind_code=_WIND_CODE,
            report_period=p["report_period"],
            statement_type=_STATEMENT_TYPE,
            ann_dt=p["ann_dt"],
            net_cash_flows_oper_act=p["net_cash_flows_oper_act"],
            net_cash_flows_inv_act=p["net_cash_flows_inv_act"],
            net_cash_flows_fnc_act=p["net_cash_flows_fnc_act"],
            net_incr_cash_cash_equ=p["net_incr_cash_cash_equ"],
            free_cash_flow=p["free_cash_flow"],
            **_make_system_fields(
                dataset_version, f"kmfy_cf_{p['report_period']}", i + 1
            ),
        )
        results.append(rec)
    return results


def load_cash_flows(session: Session, dataset_version: str) -> list[CashFlow]:
    records = _build_cash_flows(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---- 十大股东 -------------------------------------------------------------


def _build_top_shareholders(dataset_version: str) -> list[TopShareholder]:
    """构建康美药业前 5 大股东（截至 2018-12-31）。"""
    shareholders: list[dict[str, Any]] = [
        {
            "s_holder_name": "康美实业投资控股有限公司",
            "s_holder_aname": "康美实业",
            "s_holder_pct": 31.91,
            "s_holder_quantity": 1_585_000_000.0,
            "s_holder_holdercategory": "境内一般法人",
            "s_holder_sequence": 1,
            "holder_entity_id": "company_km_sy",
            "entity_match_confidence": 1.0,
        },
        {
            "s_holder_name": "广东粤财信托有限公司",
            "s_holder_aname": "粤财信托",
            "s_holder_pct": 4.52,
            "s_holder_quantity": 224_500_000.0,
            "s_holder_holdercategory": "信托计划",
            "s_holder_sequence": 2,
            "holder_entity_id": "company_yc_xt",
            "entity_match_confidence": 0.95,
        },
        {
            "s_holder_name": "中国证券金融股份有限公司",
            "s_holder_aname": "证金公司",
            "s_holder_pct": 3.77,
            "s_holder_quantity": 187_200_000.0,
            "s_holder_holdercategory": "国有法人",
            "s_holder_sequence": 3,
            "holder_entity_id": "company_zj_gs",
            "entity_match_confidence": 1.0,
        },
        {
            "s_holder_name": "许冬瑾",
            "s_holder_aname": None,
            "s_holder_pct": 2.48,
            "s_holder_quantity": 123_100_000.0,
            "s_holder_holdercategory": "境内自然人",
            "s_holder_sequence": 4,
            "holder_entity_id": None,
            "entity_match_confidence": None,
        },
        {
            "s_holder_name": "普宁市金信典当行有限公司",
            "s_holder_aname": "金信典当",
            "s_holder_pct": 2.05,
            "s_holder_quantity": 101_800_000.0,
            "s_holder_holdercategory": "境内一般法人",
            "s_holder_sequence": 5,
            "holder_entity_id": "company_jx_dd",
            "entity_match_confidence": 0.85,
        },
    ]

    results: list[TopShareholder] = []
    for i, sh in enumerate(shareholders):
        rec = TopShareholder(
            wind_code=_WIND_CODE,
            ann_dt="2019-04-30",
            s_holder_enddate="2018-12-31",
            s_holder_name=sh["s_holder_name"],
            s_holder_aname=sh["s_holder_aname"],
            s_holder_pct=sh["s_holder_pct"],
            s_holder_quantity=sh["s_holder_quantity"],
            s_holder_holdercategory=sh["s_holder_holdercategory"],
            s_holder_sequence=sh["s_holder_sequence"],
            report_period="2018-12-31",
            holder_entity_id=sh["holder_entity_id"],
            entity_match_confidence=sh["entity_match_confidence"],
            **_make_system_fields(dataset_version, f"kmfy_tsh_{i + 1:02d}", i + 1),
        )
        results.append(rec)
    return results


def load_top_shareholders(
    session: Session, dataset_version: str
) -> list[TopShareholder]:
    records = _build_top_shareholders(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---- 公告 -----------------------------------------------------------------


def _build_announcements(dataset_version: str) -> list[Announcement]:
    """构建康美药业关键事件公告。"""
    announcements: list[dict[str, Any]] = [
        {
            "object_id": "kmfy_ann_20181229_csrc",
            "ann_dt": "2018-12-29",
            "n_info_title": "康美药业股份有限公司关于收到中国证券监督管理委员会立案调查通知的公告",
            "n_info_fcode": "010305",
            "sentiment": "negative",
            "sentiment_method": "manual_fixture",
            "source_uri": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1205599888",
            "content_hash": None,
        },
        {
            "object_id": "kmfy_ann_20190430_restate",
            "ann_dt": "2019-04-30",
            "n_info_title": "康美药业股份有限公司关于前期会计差错更正的公告",
            "n_info_fcode": "010305",
            "sentiment": "negative",
            "sentiment_method": "manual_fixture",
            "source_uri": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1205987654",
            "content_hash": None,
        },
        {
            "object_id": "kmfy_ann_20190517_st",
            "ann_dt": "2019-05-17",
            "n_info_title": "康美药业股份有限公司关于公司股票被实施其他风险警示的公告",
            "n_info_fcode": "010305",
            "sentiment": "negative",
            "sentiment_method": "manual_fixture",
            "source_uri": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1206123456",
            "content_hash": None,
        },
        {
            "object_id": "kmfy_ann_20190816_penalty",
            "ann_dt": "2019-08-16",
            "n_info_title": "康美药业股份有限公司关于收到中国证监会《行政处罚及市场禁入事先告知书》的公告",
            "n_info_fcode": "010305",
            "sentiment": "negative",
            "sentiment_method": "manual_fixture",
            "source_uri": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1206312345",
            "content_hash": None,
        },
    ]

    results: list[Announcement] = []
    for i, a in enumerate(announcements):
        rec = Announcement(
            object_id=a["object_id"],
            wind_code=_WIND_CODE,
            ann_dt=a["ann_dt"],
            n_info_title=a["n_info_title"],
            n_info_fcode=a["n_info_fcode"],
            sentiment=a["sentiment"],
            sentiment_method=a["sentiment_method"],
            source_uri=a["source_uri"],
            content_hash=a["content_hash"],
            **_make_system_fields(dataset_version, a["object_id"], i + 1),
        )
        results.append(rec)
    return results


def load_announcements(session: Session, dataset_version: str) -> list[Announcement]:
    records = _build_announcements(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---- 研报 -----------------------------------------------------------------


def _build_research_reports(dataset_version: str) -> list[ResearchReport]:
    """构建康美药业相关研报。"""
    reports: list[dict[str, Any]] = [
        {
            "report_id": "kmfy_rpt_20190506_citics",
            "sec_code": "600518",
            "exchange_code": "XSHG",
            "sec_name": "康美药业",
            "org_name": "中信证券研究部",
            "title": "康美药业（600518.SH）会计差错更正点评：差错更正暴露内控缺陷，下调至卖出评级",
            "publish_date": "2019-05-06",
            "abstract": (
                "康美药业公告前期会计差错更正，涉及货币资金调减299亿元。"
                "公司2017年末货币资金由341.5亿元更正为42.5亿元，差异巨大。"
                "下调至卖出评级，目标价下调至3.0元。"
            ),
            "rating_org": "卖出",
            "rating_change": "down",
            "industry_l1": "医药生物",
            "sw_indu_code": "370101",
            "source_uri": "https://research.citics.com/report/600518_20190506",
            "content_hash": None,
        },
        {
            "report_id": "kmfy_rpt_20190820_gtja",
            "sec_code": "600518",
            "exchange_code": "XSHG",
            "sec_name": "康美药业",
            "org_name": "国泰君安证券研究所",
            "title": "康美药业（600518.SH）行政处罚点评：造假金额创A股纪录，退市风险加大",
            "publish_date": "2019-08-20",
            "abstract": (
                "证监会拟对康美药业处以60万元罚款并市场禁入。"
                "公司2016-2018年累计虚增营业收入约275亿元，虚增货币资金约887亿元，"
                "虚增固定资产、在建工程约36亿元。维持卖出评级。"
            ),
            "rating_org": "卖出",
            "rating_change": "maintain",
            "industry_l1": "医药生物",
            "sw_indu_code": "370101",
            "source_uri": "https://research.gtja.com/report/600518_20190820",
            "content_hash": None,
        },
    ]

    results: list[ResearchReport] = []
    for i, r in enumerate(reports):
        rec = ResearchReport(
            report_id=r["report_id"],
            wind_code=_WIND_CODE,
            sec_code=r["sec_code"],
            exchange_code=r["exchange_code"],
            sec_name=r["sec_name"],
            org_name=r["org_name"],
            title=r["title"],
            publish_date=r["publish_date"],
            abstract=r["abstract"],
            rating_org=r["rating_org"],
            rating_change=r["rating_change"],
            industry_l1=r["industry_l1"],
            sw_indu_code=r["sw_indu_code"],
            source_uri=r["source_uri"],
            content_hash=r["content_hash"],
            **_make_system_fields(dataset_version, r["report_id"], i + 1),
        )
        results.append(rec)
    return results


def load_research_reports(
    session: Session, dataset_version: str
) -> list[ResearchReport]:
    records = _build_research_reports(dataset_version)
    session.add_all(records)
    session.flush()
    return records


# ---------------------------------------------------------------------------
# 数据校验
# ---------------------------------------------------------------------------


def verify_fixture(session: Session, dataset_version: str) -> dict[str, Any]:
    """校验 Kangmei fixture 数据完整性。

    返回包含状态、计数和问题的字典。
    """
    result: dict[str, Any] = {
        "status": "pass",
        "dataset_version": dataset_version,
        "wind_code": _WIND_CODE,
        "entity_id": _ENTITY_ID,
        "counts": {},
        "issues": [],
    }

    checks: list[tuple[type[Base], str, int, str]] = [
        (Company, "companies", 1, "公司记录"),
        (BalanceSheet, "balance_sheet", 4, "资产负债表（4 期）"),
        (IncomeStatement, "income_statement", 4, "利润表（4 期）"),
        (CashFlow, "cash_flow", 4, "现金流量表（4 期）"),
        (TopShareholder, "top_shareholders", 5, "前十大股东（5 条）"),
        (Announcement, "announcements", 4, "公告（4 条）"),
        (ResearchReport, "research_reports", 2, "研报（2 条）"),
    ]

    for model, label, expected, description in checks:
        count = _count_by_dataset(session, model, dataset_version)
        result["counts"][label] = count
        if count != expected:
            result["status"] = "fail"
            result["issues"].append(
                f"  [FAIL] {description}: 期望 {expected} 条，实际 {count} 条"
            )
        else:
            result["issues"].append(f"  [PASS] {description}: {count} 条")

    # 额外校验：确认未影响非 Kangmei 数据
    non_kangmei = (
        session.query(Company)
        .filter(
            Company.wind_code == _WIND_CODE,
            Company.dataset_version != dataset_version,
        )
        .count()
    )
    if non_kangmei > 0:
        result["issues"].append(
            f"  [WARN] 存在 {non_kangmei} 条非 {dataset_version} 的康美公司记录（非本脚本管理）"
        )

    return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run_load(
    session_factory: Any | None,
    dataset_version: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行完整的数据加载流程。

    返回统计字典。dry_run 时 session_factory 可为 None。
    """
    stats: dict[str, Any] = {
        "dataset_version": dataset_version,
        "dry_run": dry_run,
        "deleted": {},
        "loaded": {},
        "verify": {},
    }

    if dry_run:
        print("=" * 60)
        print("  DRY RUN — 不会实际写入数据库")
        print("=" * 60)
        # dry-run 只构建对象，不持久化
        stats["loaded"] = {
            "companies": 1,
            "balance_sheet": len(_build_balance_sheets(dataset_version)),
            "income_statement": len(_build_income_statements(dataset_version)),
            "cash_flow": len(_build_cash_flows(dataset_version)),
            "top_shareholders": len(_build_top_shareholders(dataset_version)),
            "announcements": len(_build_announcements(dataset_version)),
            "research_reports": len(_build_research_reports(dataset_version)),
        }
        print("\n将加载以下数据:")
        for label, count in stats["loaded"].items():
            print(f"  - {label}: {count} 条")
        return stats

    session = session_factory()
    try:
        # ---- Step 1: 清理旧 Kangmei fixture 数据 ----
        print("清理旧 Kangmei fixture 数据 ...")
        deleted = clear_kangmei_fixture(session, dataset_version)
        stats["deleted"] = deleted
        for label, count in deleted.items():
            if count > 0:
                print(f"  - {label}: 删除 {count} 条")

        # ---- Step 2: 加载 ----
        print("\n加载康美药业 fixture 数据 ...")

        print("  [1/7] 公司信息 ...")
        load_company(session, dataset_version)
        stats["loaded"]["companies"] = 1

        print("  [2/7] 资产负债表（4 期）...")
        load_balance_sheets(session, dataset_version)
        stats["loaded"]["balance_sheet"] = 4

        print("  [3/7] 利润表（4 期）...")
        load_income_statements(session, dataset_version)
        stats["loaded"]["income_statement"] = 4

        print("  [4/7] 现金流量表（4 期）...")
        load_cash_flows(session, dataset_version)
        stats["loaded"]["cash_flow"] = 4

        print("  [5/7] 前十大股东（5 条）...")
        load_top_shareholders(session, dataset_version)
        stats["loaded"]["top_shareholders"] = 5

        print("  [6/7] 公告（4 条）...")
        load_announcements(session, dataset_version)
        stats["loaded"]["announcements"] = 4

        print("  [7/7] 研报（2 条）...")
        load_research_reports(session, dataset_version)
        stats["loaded"]["research_reports"] = 2

        # ---- Step 3: 提交 ----
        session.commit()
        print("\n提交成功。")

        # ---- Step 4: 校验 ----
        print("\n校验 fixture 数据 ...")
        stats["verify"] = verify_fixture(session, dataset_version)

        return stats

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_verify_only(
    session_factory: Any,
    dataset_version: str,
) -> dict[str, Any]:
    """仅校验已加载的 Kangmei fixture 数据。"""
    print(f"校验 dataset_version={dataset_version!r} ...\n")
    session = session_factory()
    try:
        result = verify_fixture(session, dataset_version)
        return result
    finally:
        session.close()


def _print_results(stats: dict[str, Any]) -> None:
    """打印加载和校验结果。"""
    print("\n" + "=" * 60)
    print("  结果汇总")
    print("=" * 60)

    ds = stats.get("dataset_version", "?")

    if stats.get("dry_run"):
        print("  模式: DRY RUN")
        print(f"  版本: {ds}")
        print("\n  [计划加载]")
        for label, count in stats.get("loaded", {}).items():
            print(f"    {label}: {count} 条")
        return

    deleted = stats.get("deleted", {})
    total_deleted = sum(deleted.values())
    if total_deleted > 0:
        print(f"\n  删除: {total_deleted} 条旧 {ds} 记录")
        for label, count in deleted.items():
            if count > 0:
                print(f"    - {label}: {count} 条")

    loaded = stats.get("loaded", {})
    total_loaded = sum(loaded.values())
    print(f"\n  加载: {total_loaded} 条新记录")
    for label, count in loaded.items():
        print(f"    + {label}: {count} 条")

    verify = stats.get("verify", {})
    if verify:
        status = verify.get("status", "?")
        print(f"\n  校验状态: {status.upper()}")
        for issue in verify.get("issues", []):
            print(issue)

    if stats.get("status") == "fail" or verify.get("status") == "fail":
        print("\n  [WARNING] 校验未通过，请检查上面的 FAIL 项。")
    else:
        print("\n  [OK] Kangmei fixture 数据加载成功。")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="康美药业测试数据安全加载器（仅数据，无 DDL）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/load_kangmei_fixture.py                    # 加载\n"
            "  python scripts/load_kangmei_fixture.py --dry-run          # 预览\n"
            "  python scripts/load_kangmei_fixture.py --verify-only      # 校验\n"
        ),
    )
    parser.add_argument(
        "--dataset-version",
        default=_DEFAULT_DATASET_VERSION,
        help=f"数据集版本标记（默认: {_DEFAULT_DATASET_VERSION}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览计划加载的数据，不实际写入数据库",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅校验已加载的数据，不执行写入操作",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dataset_version: str = args.dataset_version

    # 构建数据库 URL（仅在需要时创建连接）
    database_url, backend = _build_database_url()

    # 显示数据库信息
    url_str = str(database_url)
    if backend == "mysql":
        display_url = url_str.split("@")[-1] if "@" in url_str else url_str
        print(f"数据库: MySQL ({display_url})")
    else:
        print(f"数据库: SQLite ({url_str})")
    print(f"数据集版本: {dataset_version}")

    # --dry-run 不需要数据库连接
    if args.dry_run:
        stats = run_load(None, dataset_version, dry_run=True)
        _print_results(stats)
        return 0

    # 创建数据库连接
    session_factory = _create_session_factory(database_url, backend)

    if args.verify_only:
        result = run_verify_only(session_factory, dataset_version)
        _print_results(
            {
                "dataset_version": dataset_version,
                "verify": result,
                "loaded": {},
                "deleted": {},
            }
        )
        return 0 if result.get("status") == "pass" else 1

    # 正常加载
    stats = run_load(session_factory, dataset_version, dry_run=False)
    _print_results(stats)

    if stats.get("verify", {}).get("status") == "fail":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
