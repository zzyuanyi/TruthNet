#!/usr/bin/env python3
"""补算指标 3（多轮主体保持率）与指标 6（模块超时率）— 独立补算 runner。

背景：official_runner.py v3.3.3 只对目标行输出 observed，不落盘上下文行的
实体结果，也不透传模块耗时，导致指标 3/6 在初评报告中标 N/A。本脚本复用
official_runner 的全部守卫（SHA 校验 / 测试库守卫 / sidecar 来源校验 /
多轮上下文执行 / 会话清理），仅修改数据采集：
  - 每个执行的轮次（含 context 行）都记录实体 codes；
  - 每个目标行透传 module_status 各模块 duration_ms。

用法：
  python tests/evaluation/compute_missing_metrics.py [--report PATH]

输出指标：
  3 多轮主体保持率：对所有有 expected_company 的深度题（labels_77.json，
    30 题）所在 session 的多轮对话，逐轮判定系统 codes 是否命中该轮
    expected_company，correct / total。分母=有标签轮次。
  6 模块超时率：目标行 module_status.duration_ms 与 deadline 基准
    （finance=3s / equity=4s / events=3s，V12 §13.2）比较，调用
    metrics.module_timeout_rate()。

不写回 sidecar；不产生评分。只补算两个 N/A 指标。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))
sys.path.insert(0, str(_EVAL_DIR))

from official_runner import (  # noqa: E402
    DEFAULT_INPUT,
    _enforce_test_db,
    _load_sidecar,
    _validate_sidecar_against_excel,
    _cleanup_sessions,
    _sha256,
    EXPECTED_SHA,
    SESSION_PREFIX,
)

DEFAULT_REPORT = _EVAL_DIR / "official_metrics_missing_v1.txt"


def _run_with_context_capture(
    items: list[dict],
    loader_rows: list[dict],
    expected_by_row: dict[int, str],
) -> tuple[list[dict], list[str]]:
    """复用 official_runner._run_with_context 的主循环，但：
      1) 每个轮次（含 context 行）记录实体 codes + 该轮 expected_company；
      2) 目标行透传 module_status.duration_ms。
    返回 (per_turn_records, session_ids)。"""
    from app.agents.graph import agent_graph
    from app.agents.state import RuntimeState

    compiled = agent_graph.compile()

    sessions: dict[str, list[dict]] = {}
    for item in items:
        sessions.setdefault(str(item["session_id"]), []).append(item)
    target_rows_by_session = {
        sid: {int(item["source_row"]) for item in group}
        for sid, group in sessions.items()
    }

    per_turn: list[dict] = []
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
                continue
            question = str(q.get("query") or "")
            if not question.strip():
                continue
            is_target = row_idx in targets
            item = group_by_row.get(row_idx)
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
            except Exception as exc:  # noqa: BLE001
                if is_target:
                    per_turn.append(
                        {
                            "turn_id": f"eval_turn_{row_idx:04d}",
                            "row": row_idx,
                            "session_id": sid,
                            "question": question,
                            "is_target": True,
                            "expected_company": expected_by_row.get(row_idx, ""),
                            "codes": [],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                continue

            resolution = result.get("entity_resolution_result")
            codes = sorted(
                {
                    str(m.selected_wind_code)
                    for m in (getattr(resolution, "mentions", None) or [])
                    if getattr(m, "selected_wind_code", None)
                }
            )
            rec = {
                "turn_id": f"eval_turn_{row_idx:04d}",
                "row": row_idx,
                "session_id": sid,
                "question": question,
                "is_target": is_target,
                "codes": codes,
                "expected_company": expected_by_row.get(row_idx, ""),
            }
            if is_target:
                ms = result.get("module_status") or {}
                rec["module_duration_ms"] = {
                    name: (getattr(m, "duration_ms", None)) for name, m in ms.items()
                }
            per_turn.append(rec)
    return per_turn, sorted(set(session_ids))


def _compute_metrics(records: list[dict]) -> dict:
    """从采集记录计算指标 3 / 6。"""
    from metrics import entity_retention_rate, module_timeout_rate

    # ── 指标 3：多轮主体保持率（有 expected_company 标签的轮次）──
    # 复用 metrics.entity_retention_rate 的 dict 形态（按 turn_id 关联）：
    # 命中轮 company_code=expected_company（保持），未命中=哨兵（不保持）；
    # 分母 = 有标签轮次（含执行报错的轮次——报错无 codes 视为未保持）。
    labeled = [r for r in records if r.get("expected_company")]
    turns_for_metric: list[dict] = []
    expected_entity: dict[str, str] = {}
    for r in labeled:
        tid = r["turn_id"]
        expected_entity[tid] = r["expected_company"]
        hit = r["expected_company"] in (r.get("codes") or [])
        turns_for_metric.append(
            {
                "turn_id": tid,
                "company_code": r["expected_company"] if hit else "__NO_RETENTION__",
            }
        )
    correct = 0
    rate: float | None = None
    try:
        rate = entity_retention_rate(
            turns_for_metric, expected_entity, field="company_code", id_key="turn_id"
        )
        correct = round(rate * len(expected_entity)) if expected_entity else 0
    except ValueError as exc:  # noqa: BLE001 — 输入契约冲突时如实报告，不伪造
        print(f"[metric3] entity_retention_rate 输入契约错误: {exc}")
    entity_retention = {
        "total_labeled_turns": len(labeled),
        "correct": correct,
        "rate": round(rate, 4) if rate is not None else None,
        "method": (
            "逐轮判定：系统该轮 codes 是否包含 labels_77.json expected_company；"
            "分母=有主体标签的深度题轮次（多轮上下文执行），报错轮次计未保持"
        ),
    }

    # ── 指标 6：模块超时率（目标行 module_status.duration_ms）──
    modules: list[dict] = []
    for r in records:
        if r.get("error") or not r.get("module_duration_ms"):
            continue
        for name, dur in r["module_duration_ms"].items():
            modules.append(
                {
                    "module_name": name,
                    "duration_ms": dur,
                }
            )
    timeout_rate = module_timeout_rate(modules)

    # 另算每个模块的实际耗时统计（供报告引用）
    durations: dict[str, list[int]] = {}
    for m in modules:
        if m["duration_ms"] is not None:
            durations.setdefault(m["module_name"], []).append(m["duration_ms"])

    return {
        "3_entity_retention_rate": entity_retention,
        "6_module_timeout_rate": {
            "by_module": timeout_rate,
            "module_duration_stats": {
                name: {
                    "count": len(v),
                    "avg_ms": round(sum(v) / len(v), 1) if v else None,
                    "max_ms": max(v) if v else None,
                }
                for name, v in durations.items()
            },
            "method": (
                "目标行 module_status.duration_ms 与 deadline 基准比较"
                "（finance=3s / equity=4s / events=3s，V12 §13.2）"
            ),
        },
    }


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
        help="官方文件哈希变化时继续人工复核观察（不给评分）",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    actual_sha = _sha256(input_path)
    requires_reannotation = actual_sha != EXPECTED_SHA
    if requires_reannotation and not args.accept_new_hash:
        print(
            f"ERROR: 官方文件 SHA-256 = {actual_sha}，期望 {EXPECTED_SHA}，fail closed。",
            file=sys.stderr,
        )
        return 2
    if requires_reannotation:
        print(
            f"[warn] 官方文件 SHA-256 = {actual_sha} ≠ 期望，requires_reannotation=true"
        )
    else:
        print(f"[hash] 官方文件 SHA-256 = {actual_sha} ✓")

    _enforce_test_db()

    from dataset_loader import load_clean_xlsx

    dataset = load_clean_xlsx(input_path)
    loader_rows = dataset.questions
    print(f"[loader] 官方文件 {len(loader_rows)} 行（dataset_loader）")

    items = _load_sidecar()
    _validate_sidecar_against_excel(items, loader_rows)
    print(f"[sidecar] {len(items)} 条目标行，来源校验通过")

    # expected_company 标签：labels_77.json 的 (session_id, question) → expected_company，
    # 与 sidecar 按同一 (session_id, question) 匹配到 source_row（不依赖任何顺序假设）。
    labels_77 = json.loads(
        Path(_REPO / "data" / "annotations" / "labels_77.json").read_text(
            encoding="utf-8"
        )
    )
    expected_by_row: dict[int, str] = {}
    matched_lab = 0
    for lab in labels_77.get("items", []):
        exp = lab.get("expected_company") or ""
        if not exp:
            continue
        lab_key = (
            str(lab.get("session_id") or ""),
            str(lab.get("question") or "").strip(),
        )
        cands = [
            it
            for it in items
            if (str(it.get("session_id") or ""), str(it.get("question") or "").strip())
            == lab_key
        ]
        if len(cands) != 1:
            print(
                f"[warn] labels_77 {lab.get('question_id')} 匹配 sidecar {len(cands)} 条，跳过"
            )
            continue
        expected_by_row[int(cands[0]["source_row"])] = str(exp)
        matched_lab += 1
    print(f"[labels] 有 expected_company 的题 {matched_lab} 条 → source_row 已关联")

    session_ids: list[str] = []
    try:
        records, session_ids = _run_with_context_capture(
            items, loader_rows, expected_by_row
        )
    finally:
        _cleanup_sessions(session_ids)

    metrics = _compute_metrics(records)

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("TruthNet 评测缺失指标补算 — 指标3/6")
    lines.append("=" * 72)
    lines.append(json.dumps(metrics, ensure_ascii=False, indent=2))
    text = "\n".join(lines) + "\n"

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"[report] {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
