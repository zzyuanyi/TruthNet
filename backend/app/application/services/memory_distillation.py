"""远期记忆提炼注入 — Phase D #15.

策略（S1 可调用）：
  - none:                不注入任何记忆
  - recent_only:         只加载近期 N 轮全量（现状）
  - summary_plus_recent: 近期 N 轮全量 + 更早轮次的限长摘要

复用现有存储：
  - conversation_turns.summary:        单轮确定性摘要（可选，不新增列）
  - conversation_sessions.metadata:    远期记忆摘要结构（不新增表/列）
  - 不使用 panel_data 存放不相干数据。

摘要结构（memory-v1）：
  {version, text, covered_until_turn_index, source_turn_ids,
   evidence_ids, company_codes, key_facts, limitations, updated_at}

设计约束：
  - 有来源轮次；有 Evidence 时保留 Evidence；
  - 不把 LLM 新信息写入事实（LLM 输出必须经来源约束校验）；
  - 限长；幂等（同来源提炼结果稳定）；
  - 失败不阻塞当前轮（摘要损坏回退近期 N 轮）；
  - 不重复把相同历史摘要反复注入。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

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
        _engines[backend] = create_engine(url, echo=False)
    else:
        path = Path(settings.SQLITE_PATH)
        if not path.is_absolute():
            path = _repo_root() / path
        _engines[backend] = create_engine(f"sqlite:///{path.as_posix()}", echo=False)
    return _engines[backend]


@dataclass
class MemorySummary:
    """远期记忆摘要（memory-v1 结构）。"""

    version: str = "memory-v1"
    text: str = ""
    covered_until_turn_index: int = 0
    source_turn_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    company_codes: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "text": self.text,
            "covered_until_turn_index": self.covered_until_turn_index,
            "source_turn_ids": self.source_turn_ids,
            "evidence_ids": self.evidence_ids,
            "company_codes": self.company_codes,
            "key_facts": self.key_facts,
            "limitations": self.limitations,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "MemorySummary | None":
        if not data or not isinstance(data, dict):
            return None
        try:
            return cls(
                version=str(data.get("version", "memory-v1")),
                text=str(data.get("text", "")),
                covered_until_turn_index=int(data.get("covered_until_turn_index", 0)),
                source_turn_ids=list(data.get("source_turn_ids") or []),
                evidence_ids=list(data.get("evidence_ids") or []),
                company_codes=list(data.get("company_codes") or []),
                key_facts=list(data.get("key_facts") or []),
                limitations=list(data.get("limitations") or []),
                updated_at=str(data.get("updated_at", "")),
            )
        except Exception:  # noqa: BLE001 — 摘要损坏回退 None
            logger.warning("memory_distillation: 摘要结构损坏，回退", exc_info=True)
            return None


# ── 确定性抽取（第一步：公司/指标/结论/证据）──────────────


def _extract_company_codes(texts: list[str]) -> list[str]:
    """从历史问答文本中确定性抽取公司代码（6 位 + 后缀）。"""
    import re

    codes: list[str] = []
    seen: set[str] = set()
    pat = re.compile(r"(\d{6})\.(SH|SZ|BJ)")
    for t in texts:
        for m in pat.findall(t):
            code = f"{m[0]}.{m[1]}"
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes[:10]


def _extract_key_facts(rows: list[dict]) -> list[str]:
    """确定性抽取关键事实：风险等级 + 规则触发 + 公司。"""
    facts: list[str] = []
    seen: set[str] = set()
    for row in rows:
        q = str(row.get("question") or "")
        a = str(row.get("answer") or "")
        # 风险等级
        for rl in ("red", "orange", "yellow", "green"):
            if f"风险等级为 {rl}" in a or f"综合风险等级为 {rl}" in a:
                f = f"风险等级 {rl}"
                if f not in seen:
                    seen.add(f)
                    facts.append(f)
        # 规则触发
        import re

        for rid in re.findall(r"R\d+", a):
            f = f"触发 {rid}"
            if f not in seen:
                seen.add(f)
                facts.append(f)
        # 公司名（若问题含代码，说明关键主体）
        if q and any(c in q for c in ("康美", "茅台", "五粮液")):
            f = "涉及知名公司"
            if f not in seen:
                seen.add(f)
                facts.append(f)
    return facts[:20]


def _truncate(text: str, max_chars: int | None = None) -> str:
    """限长截断。"""
    limit = max_chars or settings.MEMORY_SUMMARY_MAX_CHARS
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# ── 提炼主函数 ─────────────────────────────────────────────


def _read_turns(session_id: str, recent_turns: int) -> list[dict]:
    """读取会话全部轮次（升序），返回 {turn_index, turn_id, question, answer, evidence_ids}。"""
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT turn_id, turn_index, question, answer "
                    "FROM conversation_turns WHERE session_id = :sid "
                    "ORDER BY turn_index ASC"
                ),
                {"sid": session_id},
            )
            .mappings()
            .all()
        )
        ev_rows = (
            conn.execute(
                text(
                    "SELECT e.turn_id, e.evidence_id FROM evidence_refs e "
                    "WHERE e.turn_id IN (SELECT turn_id FROM conversation_turns "
                    "WHERE session_id = :sid) ORDER BY e.turn_id"
                ),
                {"sid": session_id},
            )
            .mappings()
            .all()
        )
    ev_by_turn: dict[str, list[str]] = {}
    for r in ev_rows:
        ev_by_turn.setdefault(r["turn_id"], []).append(r["evidence_id"])
    return [
        {
            "turn_id": r["turn_id"],
            "turn_index": int(r["turn_index"]),
            "question": str(r["question"] or ""),
            "answer": str(r["answer"] or ""),
            "evidence_ids": ev_by_turn.get(r["turn_id"], [])[:10],
        }
        for r in rows
    ]


def build_summary_for_turns(
    turns: list[dict], max_chars: int | None = None
) -> MemorySummary:
    """为早期轮次构建确定性摘要（不依赖 LLM，来源约束天然满足）。

    确定性优先策略：抽取公司/指标/结论/证据 → 组织为限长文本。
    后续可升级为 LLM 压缩表达，但 LLM 输出必须经来源约束校验。
    """
    texts = [t.get("question", "") + " " + t.get("answer", "") for t in turns]
    company_codes = _extract_company_codes(texts)
    key_facts = _extract_key_facts(turns)
    evidence_ids: list[str] = []
    for t in turns:
        for eid in t.get("evidence_ids") or []:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
    source_turn_ids = [t["turn_id"] for t in turns if t.get("turn_id")]

    # 摘要文本：确定性拼接（来源轮次 → 关键事实 → 涉及公司）
    parts: list[str] = []
    if key_facts:
        parts.append("关键事实：" + "；".join(key_facts))
    if company_codes:
        parts.append("涉及公司：" + "、".join(company_codes))
    parts.append(f"覆盖轮次：第 {len(turns)} 轮")
    text_body = "；".join(parts)

    covered_until = max((t["turn_index"] for t in turns), default=0)
    return MemorySummary(
        text=_truncate(text_body, max_chars),
        covered_until_turn_index=covered_until,
        source_turn_ids=source_turn_ids[: settings.MEMORY_SUMMARY_MAX_SOURCE_TURNS],
        evidence_ids=evidence_ids[:50],
        company_codes=company_codes,
        key_facts=key_facts,
        limitations=[
            "确定性摘要（未启用 LLM 压缩）",
            "摘要不包含未出现在历史回答中的新事实",
        ],
    )


def load_or_build_summary(session_id: str) -> MemorySummary | None:
    """读取会话远期记忆摘要；无摘要时构建（幂等，同来源结果稳定）。

    失败不阻塞：任何异常返回 None，调用方回退近期 N 轮。
    """
    try:
        # 读取已有摘要（conversation_sessions.metadata.memory_summary）
        with _get_engine().connect() as conn:
            meta_row = conn.execute(
                text(
                    "SELECT metadata FROM conversation_sessions WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).first()
        meta = {}
        if meta_row and meta_row[0]:
            meta = (
                json.loads(meta_row[0])
                if isinstance(meta_row[0], str)
                else (meta_row[0] or {})
            )
        existing = MemorySummary.from_dict(meta.get("memory_summary"))
        if existing is not None and existing.text:
            return existing

        # 无摘要 → 构建早期轮次摘要并持久化
        recent = settings.MEMORY_RECENT_TURNS
        turns = _read_turns(session_id, recent)
        early = [t for t in turns if t["turn_index"] <= recent]
        if not early:
            return None
        summary = build_summary_for_turns(early)
        _persist_summary(session_id, summary)
        return summary
    except Exception:  # noqa: BLE001 — 提炼失败不阻塞当前轮
        logger.warning("memory_distillation: 摘要读取/构建失败", exc_info=True)
        return None


def _persist_summary(session_id: str, summary: MemorySummary) -> None:
    """写入 conversation_sessions.metadata（不覆盖其他元数据）。"""
    try:
        with _get_engine().connect() as conn:
            meta_row = conn.execute(
                text(
                    "SELECT metadata FROM conversation_sessions WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).first()
        meta = {}
        if meta_row and meta_row[0]:
            meta = (
                json.loads(meta_row[0])
                if isinstance(meta_row[0], str)
                else (meta_row[0] or {})
            )
        meta["memory_summary"] = summary.to_dict()
        import datetime

        summary.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta["memory_summary"]["updated_at"] = summary.updated_at
        with _get_engine().begin() as conn:
            conn.execute(
                text(
                    "UPDATE conversation_sessions SET metadata = :meta "
                    "WHERE session_id = :sid"
                ),
                {"meta": json.dumps(meta, ensure_ascii=False), "sid": session_id},
            )
    except Exception:  # noqa: BLE001
        logger.warning("memory_distillation: 摘要持久化失败", exc_info=True)


def load_context_with_memory(session_id: str) -> dict:
    """按策略组装记忆上下文。

    Returns:
        {"recent": [...], "summary": MemorySummary|None, "strategy": str}
    """
    strategy = settings.MEMORY_STRATEGY
    if strategy == "none":
        return {"recent": [], "summary": None, "strategy": strategy}
    try:
        recent = _read_turns(session_id, settings.MEMORY_RECENT_TURNS)
        recent = recent[-settings.MEMORY_RECENT_TURNS :]  # 只取最近 N 轮
        if strategy == "recent_only":
            return {"recent": recent, "summary": None, "strategy": strategy}
        summary = load_or_build_summary(session_id)
        return {"recent": recent, "summary": summary, "strategy": strategy}
    except Exception:  # noqa: BLE001 — 记忆失败不阻塞
        logger.warning("memory_distillation: 记忆加载失败，回退空", exc_info=True)
        return {"recent": [], "summary": None, "strategy": strategy}
