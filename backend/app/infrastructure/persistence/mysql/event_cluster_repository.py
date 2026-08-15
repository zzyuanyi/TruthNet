"""MySQL EventClusterRepository Adapter — Phase C 任务 15.

消费事件簇交接数据（event_clusters + event_cluster_sources 派生表）。
提供幂等 upsert（同 ID 同内容 → skip；同 ID 不同内容 → conflict，不静默覆盖）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.domain.events.contracts import EventClusterRecord, EventSourceRef

logger = logging.getLogger(__name__)


def _canonical_fingerprint(record: EventClusterRecord) -> str:
    """内容指纹：同 ID 幂等判定依据（不含 created_at/updated_at）。"""
    payload = {
        "entity_id": record.entity_id,
        "wind_code": record.wind_code,
        "topic": record.topic,
        "summary": record.summary,
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
        "event_count": record.event_count,
        "sentiment": record.sentiment,
        "sentiment_score": record.sentiment_score,
        "sources": [
            {
                # source_id 是文件内 ID，入库后重建不保证一致，不参与幂等指纹
                "source_type": s.source_type,
                "source_record_id": s.source_record_id,
                "title": s.title,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "source_uri": s.source_uri,
                "content_hash": s.content_hash,
                "fcode": s.fcode,
            }
            for s in record.sources
        ],
        "evidence_ids": record.evidence_ids,
        "cluster_method": record.cluster_method,
        "cluster_version": record.cluster_version,
        "dataset_version": record.dataset_version,
        "quality_flags": record.quality_flags,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


class MySQLEventClusterRepository:
    """MySQL 事件簇仓库 — full profile."""

    def __init__(self):
        self._engine: Engine | None = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            url = (
                f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
                f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
                "?charset=utf8mb4"
            )
            self._engine = create_engine(url, echo=False, pool_pre_ping=True)
        return self._engine

    # ── 读取 ────────────────────────────────────────────

    async def get_by_id(self, event_cluster_id: str) -> EventClusterRecord | None:
        return self.get_by_id_sync(event_cluster_id)

    def get_by_id_sync(self, event_cluster_id: str) -> EventClusterRecord | None:
        """同步版 get_by_id（Agent 同步节点使用）."""
        with self._get_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT * FROM event_clusters WHERE event_cluster_id = :id LIMIT 1"
                    ),
                    {"id": event_cluster_id},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            src_rows = (
                conn.execute(
                    text(
                        "SELECT * FROM event_cluster_sources "
                        "WHERE event_cluster_id = :id ORDER BY sequence_no, id"
                    ),
                    {"id": event_cluster_id},
                )
                .mappings()
                .all()
            )
        return _row_to_cluster(dict(row), [dict(s) for s in src_rows])

    async def list_by_company(
        self,
        wind_code: str,
        start_date: date,
        end_date: date,
    ) -> list[EventClusterRecord]:
        return self.list_by_company_sync(wind_code, start_date, end_date)

    def list_by_company_sync(
        self,
        wind_code: str,
        start_date: date,
        end_date: date,
    ) -> list[EventClusterRecord]:
        """同步版 list_by_company（Agent 同步节点使用）."""
        with self._get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT * FROM event_clusters "
                        "WHERE wind_code = :code "
                        "  AND start_date <= :end AND end_date >= :start "
                        "ORDER BY start_date, event_cluster_id"
                    ),
                    {"code": wind_code, "start": start_date, "end": end_date},
                )
                .mappings()
                .all()
            )
            clusters = []
            skipped = 0
            for row in rows:
                src_rows = (
                    conn.execute(
                        text(
                            "SELECT * FROM event_cluster_sources "
                            "WHERE event_cluster_id = :id ORDER BY sequence_no, id"
                        ),
                        {"id": row["event_cluster_id"]},
                    )
                    .mappings()
                    .all()
                )
                # 批次 E：单行不合规（如 sources 为空违反契约 min_length=1）→
                # 跳过并告警，不再"一坏全坏"拖垮整家公司。
                try:
                    clusters.append(
                        _row_to_cluster(dict(row), [dict(s) for s in src_rows])
                    )
                except Exception as exc:  # noqa: BLE001
                    skipped += 1
                    logger.warning(
                        "event_cluster 行转换失败，跳过 event_cluster_id=%s: %s",
                        row.get("event_cluster_id"),
                        exc,
                    )
            if skipped:
                logger.warning(
                    "list_by_company_sync: %d/%d 簇因结构不合法被跳过 (wind_code=%s)",
                    skipped,
                    len(rows),
                    wind_code,
                )
        return clusters

    # ── 导入（幂等 upsert）──────────────────────────────

    def upsert(self, record: EventClusterRecord) -> dict:
        """幂等导入单条事件簇.

        返回 {"status": "inserted"|"updated"|"skipped"|"conflicted", "event_cluster_id": ...}
        同 ID 不同内容 → conflicted（不写入）。
        """
        fp = _canonical_fingerprint(record)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        with self._get_engine().begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT event_cluster_id FROM event_clusters "
                    "WHERE event_cluster_id = :id LIMIT 1"
                ),
                {"id": record.event_cluster_id},
            ).first()

            if existing:
                # 读取现有记录做内容比较
                cur = self._load_for_compare(conn, record.event_cluster_id)
                if cur is not None and cur == fp:
                    return {
                        "status": "skipped",
                        "event_cluster_id": record.event_cluster_id,
                    }
                return {
                    "status": "conflicted",
                    "event_cluster_id": record.event_cluster_id,
                    "detail": "同 ID 已有不同内容，拒绝覆盖",
                }

            conn.execute(
                text(
                    "INSERT INTO event_clusters "
                    "(event_cluster_id, entity_id, wind_code, topic, summary, "
                    " start_date, end_date, event_count, sentiment, sentiment_score, "
                    " cluster_method, cluster_version, dataset_version, quality_flags, "
                    " evidence_ids, created_at, updated_at) "
                    "VALUES (:id, :eid, :wc, :topic, :summary, :start, :end, "
                    ":count, :sent, :score, :method, :cver, :dv, :qf, :evids, "
                    ":created, :updated)"
                ),
                {
                    "id": record.event_cluster_id,
                    "eid": record.entity_id,
                    "wc": record.wind_code,
                    "topic": record.topic,
                    "summary": record.summary,
                    "start": record.start_date,
                    "end": record.end_date,
                    "count": record.event_count,
                    "sent": record.sentiment,
                    "score": record.sentiment_score,
                    "method": record.cluster_method,
                    "cver": record.cluster_version,
                    "dv": record.dataset_version,
                    "qf": json.dumps(record.quality_flags, ensure_ascii=False),
                    "evids": json.dumps(record.evidence_ids, ensure_ascii=False),
                    "created": record.created_at.replace(tzinfo=None),
                    "updated": (record.updated_at or now),
                },
            )
            # 每来源绑定 evidence_id（1:1 顺序映射；数量不一致则仅存簇级列表）
            ev_by_source = _map_evidence_to_sources(record)
            for seq, s in enumerate(record.sources):
                conn.execute(
                    text(
                        "INSERT INTO event_cluster_sources "
                        "(event_cluster_id, source_type, source_record_id, evidence_id, "
                        " source_title, source_uri, published_at, content_hash, "
                        " fcode, sequence_no) "
                        "VALUES (:id, :st, :srid, :ev, :title, :uri, :pub, :ch, "
                        " :fcode, :seq)"
                    ),
                    {
                        "id": record.event_cluster_id,
                        "st": s.source_type,
                        "srid": s.source_record_id,
                        "ev": ev_by_source.get(seq),
                        "title": s.title,
                        "uri": s.source_uri,
                        "pub": s.published_at,
                        "ch": s.content_hash,
                        "fcode": s.fcode,
                        "seq": seq,
                    },
                )
            return {"status": "inserted", "event_cluster_id": record.event_cluster_id}

    def _load_for_compare(self, conn, event_cluster_id: str) -> str | None:
        row = (
            conn.execute(
                text(
                    "SELECT event_cluster_id, entity_id, wind_code, topic, summary, "
                    "start_date, end_date, event_count, sentiment, sentiment_score, "
                    "cluster_method, cluster_version, dataset_version, quality_flags, "
                    "evidence_ids "
                    "FROM event_clusters WHERE event_cluster_id = :id LIMIT 1"
                ),
                {"id": event_cluster_id},
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        src_rows = (
            conn.execute(
                text(
                    "SELECT source_type, source_record_id, evidence_id, source_title, "
                    "source_uri, published_at, content_hash, fcode "
                    "FROM event_cluster_sources WHERE event_cluster_id = :id "
                    "ORDER BY sequence_no, id"
                ),
                {"id": event_cluster_id},
            )
            .mappings()
            .all()
        )
        record = _row_to_cluster(dict(row), [dict(s) for s in src_rows])
        return _canonical_fingerprint(record)


def _map_evidence_to_sources(record: EventClusterRecord) -> dict[int, str]:
    """按顺序将 evidence_ids 映射到 sources 下标（1:1 时）。"""
    if len(record.evidence_ids) == len(record.sources):
        return {i: eid for i, eid in enumerate(record.evidence_ids)}
    return {}


def _json_col(value):
    """MySQL JSON 列可能以 str 返回；统一解析为 Python 对象。"""
    if value is None or isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def _row_to_cluster(row: dict, sources: list[dict]) -> EventClusterRecord:
    """将 DB 行转回 EventClusterRecord."""
    evidence_ids = _json_col(row.get("evidence_ids")) or []
    return EventClusterRecord(
        event_cluster_id=row["event_cluster_id"],
        entity_id=row["entity_id"],
        wind_code=row["wind_code"],
        topic=row["topic"],
        summary=row.get("summary") or "",
        start_date=row["start_date"],
        end_date=row["end_date"],
        event_count=row["event_count"],
        sentiment=row["sentiment"],
        sentiment_score=row.get("sentiment_score"),
        sources=[
            EventSourceRef(
                source_id=f"{s['source_type']}_{s['source_record_id']}",
                source_type=s["source_type"],
                source_record_id=s["source_record_id"],
                title=s.get("source_title") or "",
                published_at=s.get("published_at"),
                source_uri=s.get("source_uri"),
                content_hash=s.get("content_hash"),
                fcode=s.get("fcode"),
            )
            for s in sources
        ],
        evidence_ids=[str(x) for x in evidence_ids],
        cluster_method=row.get("cluster_method") or "",
        cluster_version=row.get("cluster_version") or "",
        dataset_version=row.get("dataset_version") or "",
        quality_flags=_json_col(row.get("quality_flags")) or [],
        created_at=row.get("created_at") or datetime.now(timezone.utc),
        updated_at=row.get("updated_at"),
    )
