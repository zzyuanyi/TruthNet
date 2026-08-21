"""280 条语义样本裁判 CLI（收口清单 P0-2）。

薄脚本：读取 run_semantic_sample.py 生成的扁平 JSONL → 复用
tests/evaluation/semantic_judge.py 的五分类裁判（judge_records/
summarize_judgements）→ 输出逐条判定 JSONL + 汇总 JSON。

约束（收口清单 §P0-2）：
- 只读取样本、调用裁判、输出文件；不写数据库、不复制第二套分类规则
- 样本中带 error 的记录补「无法核验/执行错误」判定，保证裁判数 = 样本数
  无漏行、无重复 source_row
- 五分类与三种比率（严格正确率/可接受率/含部分可用率）由
  semantic_judge.summarize_judgements 统一给出

用法：
  python scripts/judge_semantic_sample.py data/test-artifacts/semantic_sample_280.jsonl
  python scripts/judge_semantic_sample.py \
      data/test-artifacts/semantic_sample_280.jsonl \
      --output data/test-artifacts/judgement_280.jsonl \
      --summary data/test-artifacts/judgement_280_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT / "tests" / "evaluation") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests" / "evaluation"))

from semantic_judge import judge_records, summarize_judgements  # noqa: E402


def load_flat_samples(path: Path) -> list[dict]:
    """读取扁平 JSONL → judge_records 需要的内部 record 格式。

    扁平行（run_semantic_sample.py 输出）：source_row/session_id/
    turn_index/question/answer/plan_intent/indicator/error。
    内部 record：{"item": {...}, "observed": {...}}；expected_* 为空
    （样本文件不含期望答案，裁判以问题文本为准）。
    """
    records: list[dict] = []
    seen: set[int] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        source_row = row.get("source_row")
        if source_row is None:
            raise ValueError(f"样本行缺少 source_row: {line[:80]}")
        if source_row in seen:
            raise ValueError(f"重复 source_row={source_row}")
        seen.add(source_row)
        record: dict = {
            "item": {
                "source_row": source_row,
                "session_id": row.get("session_id", ""),
                "turn_index": row.get("turn_index", 0),
                "question": row.get("question", ""),
                "task_type": "semantic_sample",
            },
            "observed": {
                "answer": row.get("answer", ""),
                "plan_intent": row.get("plan_intent", ""),
                "indicator": row.get("indicator", ""),
            },
        }
        if row.get("error"):
            record["error"] = str(row["error"])
        records.append(record)
    return records


def run_judgement(records: list[dict], *, batch_size: int = 8) -> dict:
    """调 judge_records 裁判；error 记录补判定，保证裁判数 = 样本数。"""
    error_rows = {
        int(r["item"]["source_row"]): str(r.get("error", ""))
        for r in records
        if r.get("error")
    }
    result = judge_records(records, batch_size=batch_size)
    judgements = list(result["judgements"])
    judged_rows = {int(j["source_row"]) for j in judgements}
    for row in sorted(error_rows):
        if row not in judged_rows:
            judgements.append(
                {
                    "source_row": row,
                    "classification": "无法核验",
                    "error_types": ["执行错误"],
                    "reason": f"样本执行失败：{error_rows[row]}",
                }
            )
    judgements.sort(key=lambda j: int(j["source_row"]))
    # 校验：无漏行、无重复
    rows = [int(j["source_row"]) for j in judgements]
    if len(rows) != len(set(rows)):
        raise ValueError("裁判结果存在重复 source_row")
    expected = {int(r["item"]["source_row"]) for r in records}
    if set(rows) != expected:
        raise ValueError(
            f"裁判结果与样本不一致：漏 {expected - set(rows)} 多 {set(rows) - expected}"
        )
    summary = summarize_judgements(judgements)
    summary["sample_total"] = len(records)
    summary["error_records"] = len(error_rows)
    summary["judged_records"] = len(judgements)
    return {"summary": summary, "judgements": judgements}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="280 条语义样本五分类裁判（复用 semantic_judge，不写数据库）"
    )
    parser.add_argument(
        "sample_jsonl", type=Path, help="run_semantic_sample.py 输出的扁平 JSONL"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "test-artifacts" / "judgement_280.jsonl",
        help="逐条判定输出 JSONL（默认 data/test-artifacts/judgement_280.jsonl）",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "data" / "test-artifacts" / "judgement_280_summary.json",
        help="汇总输出 JSON（默认 data/test-artifacts/judgement_280_summary.json）",
    )
    parser.add_argument(
        "--batch-size", type=int, default=8, help="裁判批大小（默认 8）"
    )
    args = parser.parse_args(argv)

    if not args.sample_jsonl.exists():
        print(f"[judge] 样本文件不存在: {args.sample_jsonl}", file=sys.stderr)
        return 2
    records = load_flat_samples(args.sample_jsonl)
    print(f"[judge] sample={len(records)} (file={args.sample_jsonl.name})")

    result = run_judgement(records, batch_size=args.batch_size)
    summary = result["summary"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for j in result["judgements"]:
            handle.write(json.dumps(j, ensure_ascii=False) + "\n")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    counts = summary["counts"]
    print(
        "[judge] 正确={correct} 合理拒答={refuse} 部分正确={partial} "
        "错误={wrong} 无法核验={unverifiable} "
        "| 严格正确率={strict:.1%} 可接受率={accepted:.1%} 含部分可用率={usable:.1%}"
        " | error_records={errors}".format(
            correct=counts["正确"],
            refuse=counts["合理拒答"],
            partial=counts["部分正确"],
            wrong=counts["错误"],
            unverifiable=counts["无法核验"],
            strict=summary["strict_accuracy"],
            accepted=summary["accepted_rate"],
            usable=summary["usable_rate"],
            errors=summary["error_records"],
        )
    )
    print(f"[judge] 逐条判定 -> {args.output}")
    print(f"[judge] 汇总 -> {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
