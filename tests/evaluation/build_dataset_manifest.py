#!/usr/bin/env python3
"""从 clean.xlsx 生成 dataset_manifest.json — Phase C 数据任务 9.

用法:
    python -m tests.evaluation.build_dataset_manifest [--out manifest.json]

输出:
    tests/evaluation/dataset_manifest.json（questions_1410 / questions_77 / dataset_hash）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tests.evaluation.dataset_loader import (  # noqa: E402
    DEFAULT_MANIFEST,
    load_clean_xlsx,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成评测集 manifest")
    ap.add_argument("--out", default=str(DEFAULT_MANIFEST), help="输出路径")
    args = ap.parse_args()

    ds = load_clean_xlsx()
    manifest = ds.to_manifest()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(
        f"manifest 已生成: {out}\n"
        f"  会话数: {manifest['session_count']}\n"
        f"  问题数: {manifest['question_count']} (1410)\n"
        f"  深度题数: {manifest['deep_question_count']} (77)\n"
        f"  选择规则: {manifest['deep_selection_rule']}\n"
        f"  dataset_hash: {manifest['dataset_hash']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
