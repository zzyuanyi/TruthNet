"""B7 题库词表审计 — Phase E Task B（诊断性，纯文件，不连库）.

对 数据1 1410 题（data/raw/1/clean.xlsx：多轮长Q）做公司名词表覆盖审计：

- 词表来源：data/processed/security_master.csv（sec_name 权威）+
  data/fixtures/selected_aliases_v1.json（精选多义 alias）；
- 对每题 question 做最长优先的公司名命中检测（exact + contains）；
- 统计：题库结构（会话数/单轮多轮/think_flag/长度）、词表命中率、
  Top 公司提及、疑似未覆盖公司名（词表无法命中的 query 抽样）；
- 多义简称分布：同一 alias 命中多 code（如 平安/国药）——实体歧义压力源。

只读文件，不连任何数据库，不写库。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load_sec_names(path: Path) -> dict[str, str]:
    """security_master.csv → {sec_name: wind_code}（BOM 兼容）。"""
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            name = (row.get("sec_name") or "").strip()
            code = (row.get("wind_code") or "").strip()
            if name and re.fullmatch(r"\d{6}(?:\.(?:S[HZ]|BJ))?", code or ""):
                out[name] = code
    return out


def _load_aliases(path: Path) -> dict[str, list[str]]:
    """selected_aliases_v1.json → {alias: [wind_codes]}。"""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, list[str]] = {}
    for item in data.get("aliases", []):
        alias = (item.get("alias") or "").strip()
        codes = list(item.get("wind_codes") or [])
        if alias and codes:
            out[alias] = codes
    return out


def _load_questions(path: Path) -> list[dict]:
    """1410 题 xlsx → [{session_id, question, think_flag}]。"""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    out: list[dict] = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            continue
        idx = {str(h).strip(): i for i, h in enumerate(header) if h is not None}
        for r in rows:
            if not r:
                continue
            out.append(
                {
                    "session_id": str(r[idx.get("session_id", 0)] or ""),
                    "question": str(r[idx.get("question", 1)] or ""),
                    "think_flag": str(r[idx.get("think_flag", 2)] or ""),
                }
            )
    wb.close()
    return out


def _longest_name_hit(question: str, names: list[str]) -> tuple[str, str] | None:
    """最长优先命中（确保 康美药业 优先于 康美）。返回 (matched_name, 上下文)。"""
    for name in sorted(names, key=len, reverse=True):
        if name in question:
            return name, ""
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="data/raw/1/clean.xlsx")
    parser.add_argument(
        "--output", default="data/reports/question_bank_wordlist_audit.json"
    )
    parser.add_argument(
        "--sample-uncovered",
        type=int,
        default=12,
        help="疑似未覆盖 query 抽样展示条数",
    )
    args = parser.parse_args()

    q_path = Path(args.questions)
    if not q_path.exists():
        print(f"[BLOCKED] 题库文件不存在: {q_path}（数据组共享渠道获取）")
        return 2

    sec_map = _load_sec_names(_ROOT / "data/processed/security_master.csv")
    alias_map = _load_aliases(_ROOT / "data/fixtures/selected_aliases_v1.json")
    questions = _load_questions(q_path)

    print(f"词表: sec_name={len(sec_map)}  alias={len(alias_map)}")
    print(f"题库: {len(questions)} 题")

    # ── 结构统计 ────────────────────────────────────────────
    sess_ids = Counter(q["session_id"] for q in questions)
    think = Counter(q["think_flag"] for q in questions)
    lens = sorted(len(q["question"]) for q in questions)
    single_turn = sum(1 for sid, n in sess_ids.items() if n == 1)
    multi_sessions = sum(1 for sid, n in sess_ids.items() if n > 1)
    print(f"会话数: {len(sess_ids)}（单轮 {single_turn} / 多轮 {multi_sessions}）")
    print(f"think_flag: {dict(think)}")
    print(
        f"问题长度: min={lens[0]} p50={lens[len(lens)//2]} "
        f"max={lens[-1]} avg={sum(lens)/len(lens):.0f}"
    )

    # ── 词表命中 ────────────────────────────────────────────
    names = sorted(sec_map.keys(), key=len, reverse=True)
    hit_counts: Counter = Counter()
    code_counts: Counter = Counter()
    by_sid: dict[str, set] = defaultdict(set)
    uncov: list[str] = []
    for q in questions:
        text = q["question"]
        hit = _longest_name_hit(text, names)
        if hit:
            name = hit[0]
            hit_counts[name] += 1
            code_counts[sec_map[name]] += 1
            by_sid[q["session_id"]].add(sec_map[name])
        else:
            # alias 命中（含多义）
            matched_alias = None
            for alias in sorted(alias_map, key=len, reverse=True):
                if alias in text:
                    matched_alias = alias
                    for code in alias_map[alias]:
                        code_counts[code] += 1
                        by_sid[q["session_id"]].add(code)
                    break
            if not matched_alias:
                uncov.append(text)

    mentioned_any = sum(
        1
        for q in questions
        if _longest_name_hit(q["question"], names)
        or any(a in q["question"] for a in alias_map)
    )
    print(
        f"\n词表命中: {mentioned_any}/{len(questions)} 题提到至少一家词表内公司 "
        f"({mentioned_any/len(questions):.1%})"
    )
    print(f"完全未命中词表: {len(uncov)} 题（{len(uncov)/len(questions):.1%}）")

    # ── 多义 alias 压力 ─────────────────────────────────────
    multi_sense = {a: cs for a, cs in alias_map.items() if len(cs) > 1}
    alias_used = [a for a in alias_map if any(a in q["question"] for q in questions)]
    print(
        f"\n多义 alias（库内已定义 {len(multi_sense)} 个，题库用到 {len(alias_used)} 个）:"
    )
    for a in alias_used:
        used_in = sum(1 for q in questions if a in q["question"])
        if a in multi_sense:
            print(f"  ⚠ {a} -> {multi_sense[a]}（题库 {used_in} 题）——歧义确认压力")
        else:
            print(f"  · {a} -> {alias_map[a]}（题库 {used_in} 题）")

    # ── Top 公司 ────────────────────────────────────────────
    print("\nTop 10 提及公司（按 query 命中）:")
    for name, n in hit_counts.most_common(10):
        print(f"  {n:>3d}  {name} ({sec_map[name]})")

    # ── 疑似未覆盖抽样 ──────────────────────────────────────
    print(
        f"\n疑似未覆盖公司名/语境 query 抽样（{min(args.sample_uncovered, len(uncov))} 条）:"
    )
    for text in uncov[: args.sample_uncovered]:
        print(f"  · {text[:80]}")

    report = {
        "wordlist": {"sec_names": len(sec_map), "aliases": len(alias_map)},
        "bank": {
            "questions": len(questions),
            "sessions": len(sess_ids),
            "multi_turn_sessions": multi_sessions,
            "think_flag": dict(think),
            "len_min": lens[0],
            "len_p50": lens[len(lens) // 2],
            "len_max": lens[-1],
        },
        "coverage": {
            "mentioned_any": mentioned_any,
            "total": len(questions),
            "coverage_ratio": round(mentioned_any / len(questions), 4),
            "uncov_count": len(uncov),
            "uncov_ratio": round(len(uncov) / len(questions), 4),
        },
        "multi_sense_aliases_used": {
            a: alias_map[a] for a in alias_used if len(alias_map[a]) > 1
        },
        "top_companies": [
            {"name": n, "wind_code": sec_map[n], "hits": c}
            for n, c in hit_counts.most_common(10)
        ],
        "uncov_samples": uncov[: args.sample_uncovered],
    }
    out_path = _ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n输出: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
