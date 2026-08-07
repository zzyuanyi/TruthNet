"""股权证据与股东记录共享服务 — Phase D #12 修复（A2/B2 统一入口）.

统一 REST / Agent(WS) / 报告三条路径：
  - make_equity_edge_evidence_id: 股权边 → canonical Evidence ID（与 Agent 落库一致）；
  - build_edge_evidence_map:      边集合 → {relationship_id: canonical evidence_id}；
  - materialize_equity_evidence:  幂等落库（GET /equity 画像链路可立即回查）；
  - fetch_shareholder_records:    读取 top_shareholders 最新记录（比例比对用）。

约束：
  - evidence_ids 只允许 canonical ev_eq_*（可经 GET /evidence/{id} 回查）；
  - 裸 relationship_id / source_record_id 仅作为来源定位键，不直接作为证据 ID；
  - materialize 幂等：同 ID 同内容复用；同 ID 不同内容不覆盖（跳过并记录）。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.domain.provenance.id_factory import NS_EQUITY, make_evidence_id

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _get_engine() -> Engine:
    backend = settings.SQL_BACKEND
    if backend in _engines:
        return _engines[backend]
    if backend == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
        _engines[backend] = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _engines[backend] = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return _engines[backend]


# ── 边属性统一读取（dict / Pydantic 对象兼容） ──────────────


def _edge_attr(edge, name: str):
    """从 dict 或 Pydantic 对象读取边属性；缺失返回 None。"""
    if isinstance(edge, dict):
        return edge.get(name)
    return getattr(edge, name, None)


# ── canonical Evidence ID ─────────────────────────────────


def make_equity_edge_evidence_id(
    *,
    edge=None,
    relationship_id: str = "",
    source_record_id: str = "",
    report_period=None,
    ann_dt=None,
    company_code: str = "",
    graph_version: str = "",
) -> str:
    """股权边 → canonical Evidence ID（与 agents/nodes/equity.py _evidence_for_edge 一致）。

    edge 提供时优先取边属性；否则用显式参数。无稳定来源键 → 返回空串。
    """
    if edge is not None:
        relationship_id = _edge_attr(edge, "relationship_id") or ""
        source_record_id = _edge_attr(edge, "source_record_id") or ""
        report_period = _edge_attr(edge, "report_period")
        ann_dt = _edge_attr(edge, "ann_dt")
    rel_id = relationship_id or source_record_id or ""
    if not rel_id:
        return ""
    period = report_period or ann_dt or ""
    return make_evidence_id(
        source_namespace=NS_EQUITY,
        source_type="neo4j_relationship",
        source_record_id=rel_id,
        field_path="ownership_pct",
        period=period,
        dataset_version=graph_version,
        company_code=company_code,
    )


def build_edge_evidence_map(
    *, edges, company_code: str, graph_version: str
) -> dict[str, str]:
    """边集合 → {relationship_id（或 source_record_id）: canonical evidence_id}。

    与 Agent 路径同一算法，保证 REST/WS 输出的 evidence_ids 可相互回查。
    """
    out: dict[str, str] = {}
    for edge in edges:
        eid = make_equity_edge_evidence_id(
            edge=edge, company_code=company_code, graph_version=graph_version
        )
        if not eid:
            continue
        key = (
            _edge_attr(edge, "relationship_id")
            or _edge_attr(edge, "source_record_id")
            or ""
        )
        if key and key not in out:
            out[key] = eid
    return out


# ── 幂等落库（REST 画像链路可回查） ─────────────────────────


def materialize_equity_evidence(
    *,
    edges,
    company_code: str,
    graph_version: str,
    trace_id: str = "",
    turn_id: str | None = None,
) -> tuple[int, list[str]]:
    """幂等落库股权边证据；返回 (新增数, 冲突跳过列表)。

    与 Agent 路径同一 canonical ID 算法：同边同内容 → 幂等复用；
    同 ID 不同内容 → 跳过（不覆盖已落库内容，避免与 Agent 冲突）。
    """
    added = 0
    conflicts: list[str] = []
    trace = trace_id or f"rest_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    try:
        with _get_engine().begin() as conn:
            for edge in edges:
                eid = make_equity_edge_evidence_id(
                    edge=edge, company_code=company_code, graph_version=graph_version
                )
                if not eid:
                    continue
                rel_id = (
                    _edge_attr(edge, "relationship_id")
                    or _edge_attr(edge, "source_record_id")
                    or ""
                )
                period = (
                    _edge_attr(edge, "report_period")
                    or _edge_attr(edge, "ann_dt")
                    or ""
                )
                pct = _edge_attr(edge, "ownership_pct")
                value = (
                    f"{pct:.2f}" if isinstance(pct, (int, float)) else str(pct or "")
                )
                src = _edge_attr(edge, "source") or ""
                tgt = _edge_attr(edge, "target") or ""
                title = f"{src}→{tgt} 持股 {value}"

                existing = conn.execute(
                    text(
                        "SELECT source_record_id, period, value "
                        "FROM evidence_refs WHERE evidence_id = :eid LIMIT 1"
                    ),
                    {"eid": eid},
                ).first()
                if existing is not None:
                    if existing[0] == rel_id and str(existing[2] or "") == value:
                        continue  # 同内容幂等复用
                    conflicts.append(eid)
                    continue
                conn.execute(
                    text(
                        "INSERT INTO evidence_refs "
                        "(evidence_id, source_type, source_record_id, company_code, "
                        " field_path, period, value, unit, statement_scope, "
                        " source_title, source_uri, source_excerpt, retrieval_score, "
                        " dataset_version, retrieved_at, turn_id, trace_id, "
                        " module, source_table) "
                        "VALUES (:eid, 'neo4j_relationship', :srid, :cc, "
                        " 'ownership_pct', :per, :val, NULL, 'ownership_record', "
                        " :title, NULL, NULL, NULL, :dv, :retrieved, "
                        " :turn, :trace, 'equity', 'neo4j:OWNS')"
                    ),
                    {
                        "eid": eid,
                        "srid": rel_id,
                        "cc": company_code,
                        "per": period or None,
                        "val": value,
                        "title": title,
                        "dv": graph_version or settings.DATASET_VERSION,
                        "retrieved": now,
                        "turn": turn_id,
                        "trace": trace,
                    },
                )
                added += 1
        if added or conflicts:
            logger.info(
                "materialize_equity_evidence: company=%s added=%d conflicts=%d",
                company_code,
                added,
                len(conflicts),
            )
    except Exception:  # noqa: BLE001 — 落库失败不阻断画像链路
        logger.warning(
            "materialize_equity_evidence: 落库失败 company=%s",
            company_code,
            exc_info=True,
        )
        return 0, []
    return added, conflicts


# ── 股东记录（比例比对 / 一致行动校验） ─────────────────────


def fetch_shareholder_records(wind_code: str) -> list[dict]:
    """读取 MySQL top_shareholders 最新记录（供链路比例比对）。

    Returns:
        [{holder_name, pct, report_period, source_record_id}, ...]
    """
    try:
        from app.domain.finance._fetch import _get_engine as _fin_engine

        with _fin_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT s_holder_name, s_holder_pct, report_period, "
                        "source_record_id FROM top_shareholders "
                        "WHERE wind_code = :c ORDER BY report_period DESC LIMIT 20"
                    ),
                    {"c": wind_code},
                )
                .mappings()
                .fetchall()
            )
        return [
            {
                "holder_name": r["s_holder_name"],
                "pct": r["s_holder_pct"],
                "report_period": str(r["report_period"] or ""),
                "source_record_id": r["source_record_id"],
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001 — 股东记录读取失败不影响链路基础数据
        logger.warning("equity: top_shareholders 读取失败", exc_info=True)
        return []
