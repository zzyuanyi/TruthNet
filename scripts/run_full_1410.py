"""全量 1410 官方语料 runner（8/22 后测集全量核查）。

复用 official_runner._run_with_context：按 session 连续执行，
1410 行全部作为目标行输出 observed。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "evaluation"))

from dataset_loader import load_clean_xlsx  # noqa: E402
from official_runner import (  # noqa: E402
    _cleanup_sessions,
    _enforce_test_db,
    _run_with_context,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _enforce_test_db()
    dataset = load_clean_xlsx(ROOT / "data" / "raw" / "1" / "clean.xlsx")
    items: list[dict] = []
    positions: dict[str, int] = {}
    for row_idx, row in enumerate(dataset.questions, start=1):
        sid = str(row.get("session_id") or "")
        positions[sid] = positions.get(sid, 0) + 1
        items.append(
            {
                "source_row": row_idx,
                "session_id": sid,
                "turn_index": positions[sid],
                "question": str(row.get("query") or ""),
                "task_type": "full_1410",
                "data_status": "to_verify",
                "annotation_source": "full_1410_audit",
            }
        )
    print(f"[full] selected={len(items)} sessions={len(positions)}")
    session_ids: list[str] = []
    try:
        records, session_ids = _run_with_context(items, dataset.questions)
    finally:
        _cleanup_sessions(session_ids)
    output = ROOT / "data" / "test-artifacts" / "full_1410_20260822.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            item = record["item"]
            observed = record.get("observed") or {}
            handle.write(
                json.dumps(
                    {
                        "source_row": item.get("source_row"),
                        "session_id": item.get("session_id"),
                        "turn_index": item.get("turn_index"),
                        "question": item.get("question"),
                        "answer": observed.get("answer", ""),
                        "plan_intent": observed.get("plan_intent", ""),
                        "indicator": observed.get("indicator", ""),
                        "error": record.get("error", ""),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    errors = sum(1 for record in records if record.get("error"))
    print(f"[full] observed={len(records)} errors={errors} report={output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
