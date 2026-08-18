"""词表命中率审计 — 8/17 词表优化方向 2（数据驱动精简）。

读数据 1 测试集（1410 题），统计各开放词表逐词命中率：
- extractor 3 张：_SUBJECT_CLEAN_WORDS / _REQUEST_WORDS / _SUBJECT_TERMINATORS
- 意图 cue：plan_modules 的 _FINANCE_KW/_EQUITY_KW/_EVENTS_KW/_DIAGNOSIS_KW
  /_GUIDE_KW/_UNSUPPORTED_KW/_ANALYSIS_CUES/_RESEARCH_CUES/_CONTEXT_CUES
  /_SAME_COMPANY_COMPARE_CUES/_ASSESSMENT_CUES/_IMPACT_EVENT_REF_CUES
  /_IMPACT_REQUEST_CUES
- indicator_semantics：_LLM_FALLBACK_TRIGGER_WORDS / _UNSUPPORTED_PHRASES

输出：零命中词（数据 1 无覆盖）+ 低命中词（≤2 次）。仅供决策参考：
数据集未覆盖 ≠ 无用（真机演示词如"评价""金牌"未必在数据 1），
删除前需结合真实演示与语义必要性人工判断。

用法：
  $env:PYTHONPATH="backend"
  python scripts/wordlist_hit_audit.py <clean.xlsx 路径>
"""

from __future__ import annotations

import sys

import pandas as pd

from app.application.services.company_mention_extractor import (
    _REQUEST_WORDS,
    _SUBJECT_CLEAN_WORDS,
    _SUBJECT_TERMINATORS,
)
from app.application.services.indicator_semantics import (
    _LLM_FALLBACK_TRIGGER_WORDS,
    _UNSUPPORTED_PHRASES,
)
from app.agents.nodes.plan_modules import (
    _ANALYSIS_CUES,
    _ASSESSMENT_CUES,
    _CONTEXT_CUES,
    _DIAGNOSIS_KW,
    _EQUITY_KW,
    _EVENTS_KW,
    _FINANCE_KW,
    _GUIDE_KW,
    _IMPACT_EVENT_REF_CUES,
    _IMPACT_REQUEST_CUES,
    _RESEARCH_CUES,
    _SAME_COMPANY_COMPARE_CUES,
    _UNSUPPORTED_KW,
)


def _hit_count(questions: list[str], words: tuple[str, ...]) -> dict[str, int]:
    counts = {w: 0 for w in words}
    for q in questions:
        ql = q.lower()
        for w in words:
            if w in ql:
                counts[w] += 1
    return counts


def _report(
    title: str, words: tuple[str, ...], counts: dict[str, int], total: int
) -> None:
    zero = [w for w in words if counts[w] == 0]
    low = [(w, counts[w]) for w in words if 0 < counts[w] <= 2]
    print(f"\n=== {title}（{len(words)} 词 / {total} 题）===")
    print(f"  零命中 {len(zero)} 词: {zero}")
    print(f"  低命中(≤2) {len(low)} 词: {sorted(low, key=lambda x: x[1])}")
    hot = sorted(((w, counts[w]) for w in words if counts[w] > 2), key=lambda x: -x[1])[
        :10
    ]
    print(f"  高命中 TOP10: {hot}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/wordlist_hit_audit.py <clean.xlsx>")
        return 2
    df = pd.read_excel(sys.argv[1])
    qcol = "question" if "question" in df.columns else df.columns[1]
    questions = [str(x) for x in df[qcol].dropna().tolist()]
    total = len(questions)
    print(f"数据 1 测试集：{total} 题")

    tables: list[tuple[str, tuple[str, ...]]] = [
        ("extractor _SUBJECT_CLEAN_WORDS", _SUBJECT_CLEAN_WORDS),
        ("extractor _REQUEST_WORDS", _REQUEST_WORDS),
        ("extractor _SUBJECT_TERMINATORS", _SUBJECT_TERMINATORS),
        ("plan _FINANCE_KW", _FINANCE_KW),
        ("plan _EQUITY_KW", _EQUITY_KW),
        ("plan _EVENTS_KW", _EVENTS_KW),
        ("plan _DIAGNOSIS_KW", _DIAGNOSIS_KW),
        ("plan _GUIDE_KW", _GUIDE_KW),
        ("plan _UNSUPPORTED_KW", _UNSUPPORTED_KW),
        ("plan _ANALYSIS_CUES", _ANALYSIS_CUES),
        ("plan _RESEARCH_CUES", _RESEARCH_CUES),
        ("plan _CONTEXT_CUES", _CONTEXT_CUES),
        ("plan _SAME_COMPANY_COMPARE_CUES", _SAME_COMPANY_COMPARE_CUES),
        ("plan _ASSESSMENT_CUES", _ASSESSMENT_CUES),
        ("plan _IMPACT_EVENT_REF_CUES", _IMPACT_EVENT_REF_CUES),
        ("plan _IMPACT_REQUEST_CUES", _IMPACT_REQUEST_CUES),
        ("indicator _LLM_FALLBACK_TRIGGER_WORDS", _LLM_FALLBACK_TRIGGER_WORDS),
        ("indicator _UNSUPPORTED_PHRASES", _UNSUPPORTED_PHRASES),
    ]
    for title, words in tables:
        _report(title, words, _hit_count(questions, words), total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
