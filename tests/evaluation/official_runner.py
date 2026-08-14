#!/usr/bin/env python3
"""官方问题语料分项评测 runner — v3.3.3 收口批次 E（方案 §4/§5.2）。

职责（收口修订）：
  - 复用 tests/evaluation/dataset_loader.py 的 load_clean_xlsx 读官方文件；
  - --input 接受官方文件路径（默认 repo 相对副本 data/raw/1/clean.xlsx，
    不硬编码个人绝对路径）；
  - 文件 SHA-256 不符 fail closed；--accept-new-hash 仅允许继续人工
    复核观察（requires_reannotation=true），不得给出评分；
  - 逐条校验 sidecar 的 source_row/session_id/turn_index/question 与
    Excel 原行一致，不一致启动失败；
  - 测试库守卫：切 MYSQL_TEST 三件套 + SELECT DATABASE() 二次确认；
  - 连续多轮上下文：每个 session 从其首行执行到最大目标行，
    只对 sidecar 目标行输出 observed（context 行不计分不输出）；
  - data_status ∈ {"verified","supported"} 才进入评分分母；
    to_verify 只输出 observed 与 observation_count，不输出
    labeled/matched/accuracy；无可评分样本时明确写明；
  - 会话清理在 finally（异常也不得留下 eval session）；
  - 不把模型输出写回 sidecar。

用法：
  python tests/evaluation/official_runner.py [--input PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))
# tests 包在直接执行（非 pytest）环境下不可 import，改为同目录导入 loader
sys.path.insert(0, str(_EVAL_DIR))

EXPECTED_SHA = "f3b3c27f019e0f7841478bf5f678e11e86dfc4874f3394ec3b011a764b452629"
SIDECAR = Path(__file__).resolve().parent / "official_questions_v1.jsonl"
DEFAULT_INPUT = _REPO / "data" / "raw" / "1" / "clean.xlsx"
DEFAULT_REPORT = Path(__file__).resolve().parent / "official_report_v1.txt"
SESSION_PREFIX = "evalv333"
# 可评分状态（方案 §4.1）：集合由常量明确声明
SCORED_STATUSES = frozenset({"verified", "supported"})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _enforce_test_db() -> None:
    """测试库守卫（独立 runner 版，模式对齐 backend/tests/conftest.py）。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    from app.core.config import settings

    if settings.SQL_BACKEND != "mysql":
        raise SystemExit("[guard] 官方语料 runner 仅支持 mysql 模式")
    if settings.MYSQL_DATABASE.lower() == settings.MYSQL_TEST_DATABASE.lower():
        raise SystemExit(
            "[guard] .env 默认库已是测试库，拒绝（需演示库默认值+测试三件套）"
        )

    settings.MYSQL_DATABASE = settings.MYSQL_TEST_DATABASE
    settings.MYSQL_USER = settings.MYSQL_TEST_USER
    settings.MYSQL_PASSWORD = settings.MYSQL_TEST_PASSWORD
    os.environ["MYSQL_DATABASE"] = settings.MYSQL_DATABASE
    os.environ["MYSQL_USER"] = settings.MYSQL_USER
    os.environ["MYSQL_PASSWORD"] = settings.MYSQL_PASSWORD

    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            actual = conn.execute(text("SELECT DATABASE()")).scalar()
    finally:
        engine.dispose()
    if str(actual or "").lower() != settings.MYSQL_DATABASE.lower():
        raise SystemExit(
            f"[guard] SELECT DATABASE() = {actual!r}，期望 "
            f"{settings.MYSQL_DATABASE!r}，拒绝执行"
        )
    print(f"[guard] SELECT DATABASE() = {actual} ✓")


def _load_sidecar() -> list[dict]:
    rows: list[dict] = []
    with SIDECAR.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _validate_sidecar_against_excel(items: list[dict], loader_rows) -> None:
    """逐条校验 sidecar 与 Excel 原行（方案 §4.2）：不一致启动失败。"""
    by_row = {idx + 1: q for idx, q in enumerate(loader_rows)}
    session_pos: dict[str, int] = {}
    turn_by_row: dict[int, int] = {}
    for row_idx in sorted(by_row):
        q = by_row[row_idx]
        sid = str(q.get("session_id") or "")
        session_pos[sid] = session_pos.get(sid, 0) + 1
        turn_by_row[row_idx] = session_pos[sid]

    problems: list[str] = []
    for item in items:
        row_idx = int(item["source_row"])
        excel_q = by_row.get(row_idx)
        if excel_q is None:
            problems.append(f"row {row_idx}: Excel 无此行")
            continue
        if str(excel_q.get("session_id") or "") != str(item.get("session_id") or ""):
            problems.append(
                f"row {row_idx}: session_id 不一致 "
                f"({item.get('session_id')} vs {excel_q.get('session_id')})"
            )
        if str(turn_by_row.get(row_idx) or "") != str(item.get("turn_index") or ""):
            problems.append(
                f"row {row_idx}: turn_index 不一致 "
                f"({item.get('turn_index')} vs {turn_by_row.get(row_idx)})"
            )
        if (
            str(excel_q.get("query") or "").strip()
            != str(item.get("question") or "").strip()
        ):
            problems.append(f"row {row_idx}: question 与 Excel 原行不一致")
    if problems:
        raise SystemExit(
            "[sidecar] 来源校验失败（方案 §4.2 启动失败）：\n  "
            + "\n  ".join(problems[:10])
        )


def _cleanup_sessions(session_ids: list[str]) -> None:
    if not session_ids:
        return
    from app.application.services.session_cleanup_service import (
        SessionCleanupService,
    )

    svc = SessionCleanupService()
    total_turns = 0
    for sid in session_ids:
        stats = svc.cleanup_session(sid)
        total_turns += stats.get("turns", 0)
    print(f"[cleanup] 已清理 {len(session_ids)} 个 eval 会话（turns={total_turns}）")


def _run_with_context(
    items: list[dict],
    loader_rows: list[dict],
    *,
    compiled=None,
) -> tuple[list[dict], list[str]]:
    """按 session 分组：从 session 首行执行到最大目标行（方案 §4.3/§5 C1）。

    只对 sidecar 目标行输出 observed；context 行执行以保持多轮上下文
    但不计分不输出。session 行号交错隔离：
      - target 集合按 session 分组（target_rows_by_session），其他
        session 的 target 行不进入当前 session 的 target 判定；
      - 循环内再次校验 q.session_id == sid，交错行直接跳过；
      - 目标 item 只在当前 group 内查找（不再全局 next()）。
    compiled 参数用于测试注入 fake graph（不连接真实数据库）。
    """
    if compiled is None:
        from app.agents.graph import agent_graph

        compiled = agent_graph.compile()
    from app.agents.state import RuntimeState

    sessions: dict[str, list[dict]] = {}
    for item in items:
        sessions.setdefault(str(item["session_id"]), []).append(item)
    # 方案 §5 C1：target 集合按 session 分组，杜绝跨 session 误判
    target_rows_by_session = {
        sid: {int(item["source_row"]) for item in group}
        for sid, group in sessions.items()
    }

    records: list[dict] = []
    session_ids: list[str] = []
    by_row = {idx + 1: q for idx, q in enumerate(loader_rows)}
    for sid, group in sorted(sessions.items()):
        session_key = f"{SESSION_PREFIX}_{sid}"
        session_ids.append(session_key)
        targets = target_rows_by_session[sid]
        group_by_row = {int(i["source_row"]): i for i in group}
        max_row = max(group_by_row)
        session_rows = [
            row_idx
            for row_idx, q in by_row.items()
            if str(q.get("session_id") or "") == sid and row_idx <= max_row
        ]
        if not session_rows:
            continue
        first_row = min(session_rows)
        print(
            f"[context] session {sid}: 执行 {first_row}..{max_row} "
            f"（目标行 {len(group)} 条）"
        )
        for row_idx in range(first_row, max_row + 1):
            q = by_row.get(row_idx)
            if q is None:
                continue
            if str(q.get("session_id") or "") != sid:
                continue  # 方案 §5 C1：其他 session 的交错行不执行
            question = str(q.get("query") or "")
            if not question.strip():
                continue
            is_target = row_idx in targets
            item = group_by_row.get(row_idx)
            if is_target and item is None:
                # 目标集合由 group 派生，理论不可达；防御性记录错误
                records.append(
                    {
                        "item": {
                            "source_row": row_idx,
                            "session_id": sid,
                            "turn_index": 0,
                            "task_type": "unknown",
                            "data_status": "to_verify",
                            "question": question,
                        },
                        "error": f"目标行 {row_idx} 不在 session {sid} 的 sidecar group",
                    }
                )
                continue
            state = {
                "user_query": question,
                "runtime": RuntimeState(
                    trace_id=f"eval_trace_{row_idx:04d}",
                    session_id=session_key,
                    turn_id=f"eval_turn_{row_idx:04d}",
                ),
            }
            try:
                result = compiled.invoke(state)
            except Exception as exc:  # noqa: BLE001 — 单条失败记录后继续
                if is_target:
                    records.append(
                        {
                            "item": item,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                continue
            if not is_target:
                continue
            resolution = result.get("entity_resolution_result")
            plan = result.get("plan")
            final = result.get("final_response")
            comparison = getattr(plan, "comparison", None) if plan else None
            records.append(
                {
                    "item": item,
                    "observed": {
                        "relation": getattr(resolution, "intent", "") or "",
                        "codes": sorted(
                            {
                                str(m.selected_wind_code)
                                for m in (getattr(resolution, "mentions", None) or [])
                                if getattr(m, "selected_wind_code", None)
                            }
                        ),
                        "plan_intent": getattr(plan, "intent", "") if plan else "",
                        "comparison_scope": (getattr(comparison, "scope", "") or ""),
                        "comparison_mode": (getattr(comparison, "mode", "") or ""),
                        "metric_ids": list(getattr(comparison, "metric_ids", []) or []),
                        "indicator": getattr(plan, "indicator", "") if plan else "",
                        "answer": (getattr(final, "answer", "") or "")[:240],
                        "claims": len(result.get("claims", [])),
                        "evidence": len(result.get("evidence", [])),
                    },
                }
            )
    return records, sorted(set(session_ids))


def _summarize(records: list[dict], *, requires_reannotation: bool) -> dict:
    total = len(records)
    errors = sum(1 for r in records if "error" in r)
    ok = total - errors
    scored = [
        r
        for r in records
        if "error" not in r and r["item"].get("data_status") in SCORED_STATUSES
    ]
    summary = {
        "observation_count": ok,
        "errors": errors,
        "scored_count": len(scored),
        "observed_only_count": ok - len(scored),
        "requires_reannotation": requires_reannotation,
        "note": (
            "data_status ∈ {verified, supported} 才计分；"
            "to_verify 样本只输出 observed（方案 §4.1），"
            "无可评分样本时不报告准确率"
        ),
    }
    if not scored:
        summary["scoring"] = "无可评分样本（全部 to_verify），不输出任何准确率指标"
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="官方 clean.xlsx 路径（默认 repo 相对副本）",
    )
    ap.add_argument("--report", default=str(DEFAULT_REPORT), help="报告输出路径")
    ap.add_argument(
        "--accept-new-hash",
        action="store_true",
        help="官方文件哈希变化时继续人工复核观察（requires_reannotation=true，不给评分）",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    actual_sha = _sha256(input_path)
    requires_reannotation = actual_sha != EXPECTED_SHA
    if requires_reannotation and not args.accept_new_hash:
        print(
            f"ERROR: 官方文件 SHA-256 = {actual_sha}，期望 {EXPECTED_SHA}，"
            "fail closed（方案 §4.2）。若官方文件已更新，请人工复核标注后"
            "使用 --accept-new-hash（仅观察，不评分）。",
            file=sys.stderr,
        )
        return 2
    if requires_reannotation:
        print(
            f"[warn] 官方文件 SHA-256 = {actual_sha} ≠ 期望，"
            "requires_reannotation=true：本次仅人工复核观察，不评分。"
        )
    else:
        print(f"[hash] 官方文件 SHA-256 = {actual_sha} ✓")

    _enforce_test_db()

    # 复用 dataset_loader（方案 §4.2），不新建第二套 Excel 读取器
    from dataset_loader import load_clean_xlsx

    dataset = load_clean_xlsx(input_path)
    loader_rows = dataset.questions
    print(f"[loader] 官方文件 {len(loader_rows)} 行（dataset_loader）")

    items = _load_sidecar()
    _validate_sidecar_against_excel(items, loader_rows)
    print(f"[sidecar] {len(items)} 条目标行，来源校验通过")

    session_ids: list[str] = []
    try:
        records, session_ids = _run_with_context(items, loader_rows)
    finally:
        _cleanup_sessions(session_ids)

    summary = _summarize(records, requires_reannotation=requires_reannotation)
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("TruthNet 官方问题语料分项评测 — v3.3.3 收口批次 E canary")
    lines.append("=" * 72)
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("")
    lines.append("逐条 observed（人工核验依据，不写回 sidecar）：")
    lines.append("-" * 72)
    for record in records:
        item = record["item"]
        if "error" in record:
            lines.append(
                f"[row {item['source_row']} | s{item['session_id']}/t{item['turn_index']}] "
                f"ERROR {record['error']}"
            )
            continue
        obs = record["observed"]
        lines.append(
            f"[row {item['source_row']} | s{item['session_id']}/t{item['turn_index']} "
            f"| {item['task_type']} | status={item['data_status']}] "
            f"q={item['question'][:48]}"
        )
        lines.append(
            f"    relation={obs['relation']} codes={obs['codes']} "
            f"intent={obs['plan_intent']} scope={obs['comparison_scope']} "
            f"mode={obs['comparison_mode']} metrics={obs['metric_ids']} "
            f"indicator={obs['indicator']} "
            f"claims={obs['claims']} evidence={obs['evidence']}"
        )
        lines.append(f"    answer={obs['answer']}")
    text = "\n".join(lines) + "\n"

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"[report] {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
