"""当前 A 股证券主表增量同步（只补缺失，不覆盖既有实体）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text

from app.application.services.industry_fill.universe import CurrentUniverseSnapshot
from app.infrastructure.graph.normalizer import make_listed_company_entity_id


@dataclass(frozen=True)
class MissingCompany:
    code: str
    wind_code: str
    sec_name: str
    exchange_code: str
    entity_id: str


def wind_code_for_current_a_share(code: str) -> str:
    """当前沪深京 A 股代码转换为项目 Wind 后缀；非法前缀拒绝猜测。"""
    if code.startswith(("4", "8", "9")):
        suffix = "BJ"
    elif code.startswith(("0", "2", "3")):
        suffix = "SZ"
    elif code.startswith(("5", "6", "7")):
        suffix = "SH"
    else:
        raise ValueError(f"无法确定交易所的当前 A 股代码: {code}")
    return f"{code}.{suffix}"


def plan_missing_companies(
    existing_wind_codes: set[str], snapshot: CurrentUniverseSnapshot
) -> list[MissingCompany]:
    existing_bare = {str(code).split(".", 1)[0] for code in existing_wind_codes}
    planned: list[MissingCompany] = []
    for code in sorted(snapshot.codes - existing_bare):
        wind_code = wind_code_for_current_a_share(code)
        planned.append(
            MissingCompany(
                code=code,
                wind_code=wind_code,
                sec_name=snapshot.names[code],
                exchange_code={"SH": "XSHG", "SZ": "XSHE", "BJ": "BJ"}[
                    wind_code.rsplit(".", 1)[1]
                ],
                entity_id=make_listed_company_entity_id(wind_code),
            )
        )
    return planned


def fetch_existing_wind_codes(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return {
            str(row[0]) for row in conn.execute(text("SELECT wind_code FROM companies"))
        }


def insert_missing_companies(
    engine: Engine,
    rows: list[MissingCompany],
    *,
    dataset_version: str,
    snapshot: CurrentUniverseSnapshot,
) -> int:
    """单事务插入仍缺失的公司；竞争写入时按 wind_code 幂等跳过。"""
    if not rows:
        return 0
    sql = text(
        "INSERT INTO companies "
        "(entity_id, wind_code, sec_name, exchange_code, comp_type_code, "
        " source_record_id, source_file, source_type, dataset_version, revision_no, "
        " is_latest, ingested_at, updated_at, quality_flags) "
        "SELECT :entity_id, :wind_code, :sec_name, :exchange_code, NULL, "
        " :source_record_id, :source_file, :source_type, :dataset_version, 1, "
        " 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :quality_flags "
        "WHERE NOT EXISTS (SELECT 1 FROM companies WHERE wind_code = :wind_code)"
    )
    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            result = conn.execute(
                sql,
                {
                    "entity_id": row.entity_id,
                    "wind_code": row.wind_code,
                    "sec_name": row.sec_name,
                    "exchange_code": row.exchange_code,
                    "source_record_id": f"{snapshot.sha256}:{row.code}",
                    "source_file": snapshot.source,
                    "source_type": "current_a_share_universe",
                    "dataset_version": dataset_version,
                    "quality_flags": '{"company_type_pending": true, "industry_pending": true}',
                },
            )
            inserted += int(result.rowcount or 0)
    return inserted
