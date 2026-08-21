"""Provenance ID 工厂 — Phase C 任务 16.

全局唯一、确定性、可重放的 Claim/Evidence ID 生成。

Evidence ID: ev_<source_namespace>_<sha256(...)[:16]>
Claim ID:    clm_<sha256(...)[:16]>

同一来源/字段/期间/数据版本重复生成 → 相同 Evidence ID。
同一次 turn 重试 → 相同 Claim ID；不同 turn / 不同公司不冲突。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# ── 命名空间 ──────────────────────────────────────────────
NS_FINANCE = "fin"
NS_EQUITY = "eq"
NS_ANNOUNCEMENT = "ann"
NS_EVENT_CLUSTER = "evt"
NS_REPORT = "report"
NS_REGULATION = "reg"
NS_COMPANY_REGISTRY = "cr"  # R11: 公司事实轻量查询证据
NS_WEB_SEARCH = "ws"  # Phase E 会5: 联网搜索来源证据


def _digest(*parts: Any, length: int = 16) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def make_evidence_id(
    *,
    source_namespace: str,
    source_type: str,
    source_record_id: str,
    field_path: str | None = None,
    period: str | None = None,
    dataset_version: str | None = None,
    company_code: str | None = None,
    rule_id: str | None = None,
    turn_id: str | None = None,
) -> str:
    """确定性生成 Evidence ID.

    digest 输入（基础六段，保持原算法）:
        source_type | source_record_id | field_path | period |
        dataset_version | company_code
    仅当 rule_id 非空时追加第七段 —— 用于区分同一来源/字段被多条
    规则引用的情况（如 R1/R4 共用 oper_rev 字段）；equity/events
    等非规则证据不传 rule_id，ID 与旧算法保持一致。
    仅当 turn_id 非空时追加第八段 —— 用于动态来源（如 web_search
    联网回填）跨轮次隔离：静态数据源（财务表/公告/研报）按
    「来源/字段/期间」幂等复用 ID 是设计；但联网搜索内容每次可能
    不同，若不隔离轮次，同一公司同一指标在不同轮次会生成相同 ID，
    内容不同触发 persist 冲突 → 整事务回滚（81 题 row 280/1152 复现）。
    """
    digest_parts = [
        source_type,
        source_record_id,
        field_path,
        period,
        dataset_version,
        company_code,
    ]
    if rule_id:
        digest_parts.append(rule_id)
    if turn_id:
        digest_parts.append(turn_id)
    digest = _digest(*digest_parts)
    return f"ev_{source_namespace}_{digest}"


def make_claim_id(
    *,
    turn_id: str,
    company_code: str,
    claim_type: str,
    rule_id: str | None = None,
    event_cluster_id: str | None = None,
    ordinal: int = 0,
    claim_text: str = "",
    rule_version: str = "",
) -> str:
    """确定性生成 Claim ID.

    digest 输入: turn_id | company_code | claim_type | rule_id |
                 event_cluster_id | ordinal | normalized_claim_text | rule_version

    同一次 turn 重试（输入一致）→ 相同 ID；不同 turn 因 turn_id 不同不冲突。
    """
    normalized_text = re.sub(r"\s+", " ", (claim_text or "")).strip()
    digest = _digest(
        turn_id,
        company_code,
        claim_type,
        rule_id or "",
        event_cluster_id or "",
        ordinal,
        normalized_text,
        rule_version,
    )
    return f"clm_{digest}"


# ── 旧 ID 兼容判定（用于审计/迁移） ──────────────────────

_LEGACY_EVIDENCE_RE = re.compile(r"^ev_eq_01$|^ev_bs_|^ev_is_|^ev_cf_|^ann_")
_LEGACY_CLAIM_RE = re.compile(r"^claim_[Rr][0-9]_|^claim_eq_01$|^claim_events_01$")


def is_legacy_evidence_id(evidence_id: str) -> bool:
    """判断是否为旧的固定/字段式 Evidence ID（应迁移）。"""
    return bool(_LEGACY_EVIDENCE_RE.match(evidence_id or ""))


def is_legacy_claim_id(claim_id: str) -> bool:
    """判断是否为旧的固定 Claim ID（跨轮次会冲突）。"""
    return bool(_LEGACY_CLAIM_RE.match(claim_id or ""))
