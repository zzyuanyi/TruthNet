"""评测数据集加载器 — Phase C 数据任务 9.

职责:
  - 解析真实 `data/raw/1/clean.xlsx`（35 会话 / 1410 问 / 77 深度题 think_flag=1）
  - 生成不可修改的 dataset hash（sha256，含全部内容）
  - 明确 77 道深度题选择规则（think_flag == 1）
  - 供 runner 以 --manifest 加载真实评测集（mock/real 可选）

隔离原则:
  - 本模块只读取 data/raw/1/（评测集），不参与规则调参
  - 规则调参代码不得 import 本模块读取答案
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

DEEP_QUESTION_FLAG = "think_flag"
EXPECTED_COLS = {
    "session_id",
    "query",
    "expected_company",
    "expected_risk_level",
    DEEP_QUESTION_FLAG,
}

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CLEAN_XLSX = REPO_ROOT / "data" / "raw" / "1" / "clean.xlsx"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "dataset_manifest.json"


@dataclass
class Dataset:
    """评测数据集."""

    questions: list[dict] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)
    deep_question_ids: list[str] = field(default_factory=list)
    dataset_hash: str = ""
    source_file: str = ""
    columns: list[str] = field(default_factory=list)

    def to_manifest(self) -> dict:
        """转为 manifest 结构（questions_1410 / questions_77 / hash）。"""
        return {
            "source_file": self.source_file,
            "session_count": len(self.sessions),
            "question_count": len(self.questions),
            "deep_question_count": len(self.deep_question_ids),
            "deep_selection_rule": f"{DEEP_QUESTION_FLAG} == 1",
            "dataset_hash": self.dataset_hash,
            "questions_1410": self.questions,
            "questions_77": [
                q
                for q in self.questions
                if q.get("question_id") in set(self.deep_question_ids)
            ],
        }


def _parse_bool_int(value) -> int:
    """解析 think_flag 值：兼容 0/1、'0'/'1'、'True'/'False'。"""
    if value is None:
        return 0
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "是"):
        return 1
    if s in ("0", "false", "no", ""):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def compute_dataset_hash(questions: list[dict]) -> str:
    """不可修改 dataset hash：对全部问题内容做规范化 sha256。"""
    canonical = json.dumps(
        questions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_clean_xlsx(path: str | Path | None = None) -> Dataset:
    """解析 clean.xlsx → Dataset.

    列名兼容：session_id / query / expected_company / expected_risk_level / think_flag。
    若 think_flag 列不存在（老版本），77 题选择规则退化为按 expected_risk_level
    非空且 query 含深度标志，但此时 deep_question_ids 为空（不伪造）。
    """
    xlsx_path = Path(path) if path else DEFAULT_CLEAN_XLSX
    if not xlsx_path.exists():
        raise FileNotFoundError(f"评测集不存在: {xlsx_path}")

    import pandas as pd

    df = pd.read_excel(xlsx_path, dtype=str)
    df = df.fillna("")
    columns = list(df.columns)

    # 兼容列名
    def col(*names: str) -> str | None:
        for n in names:
            if n in columns:
                return n
        return None

    c_session = col("session_id", "session")
    c_query = col("query", "question", "问题")
    c_company = col("expected_company", "expected_company_code", "company")
    c_risk = col("expected_risk_level", "risk_level", "风险等级")
    c_think = col("think_flag", "is_deep", "深度题")

    if c_query is None:
        raise ValueError(f"clean.xlsx 缺少 query 列: {columns}")

    questions: list[dict] = []
    for idx, row in df.iterrows():
        qid = f"q{idx + 1:04d}"
        query = str(row[c_query] or "")
        if not query.strip():
            continue
        questions.append(
            {
                "question_id": qid,
                "session_id": str(row[c_session] or "") if c_session else "",
                "query": query,
                "expected_company": str(row[c_company] or "") if c_company else "",
                "expected_risk_level": str(row[c_risk] or "") if c_risk else "",
                "think_flag": _parse_bool_int(row[c_think]) if c_think else 0,
            }
        )

    sessions = sorted({q["session_id"] for q in questions if q["session_id"]})
    deep_ids = [q["question_id"] for q in questions if q.get("think_flag") == 1]
    # 相对路径（禁止硬编码盘符/绝对路径）
    try:
        source_file = str(xlsx_path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        source_file = str(xlsx_path)
    return Dataset(
        questions=questions,
        sessions=sessions,
        deep_question_ids=deep_ids,
        dataset_hash=compute_dataset_hash(questions),
        source_file=source_file,
        columns=columns,
    )


def load_manifest(path: str | Path | None = None) -> dict:
    """加载 dataset_manifest.json（若存在）。"""
    manifest_path = Path(path) if path else DEFAULT_MANIFEST
    if not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)
