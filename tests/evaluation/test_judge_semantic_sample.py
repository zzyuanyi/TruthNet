"""judge_semantic_sample CLI 测试（收口清单 P0-2 工具）。

覆盖：扁平 JSONL 加载与转换、error 记录补判、无漏行无重复校验、
汇总三率、main 输出与退出码。裁判层用假实现隔离真实 LLM。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "judge_semantic_sample.py"
_spec = importlib.util.spec_from_file_location("judge_semantic_sample", _SCRIPT)
judge_cli = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(judge_cli)

from semantic_judge import summarize_judgements  # noqa: E402


def _flat_row(
    source_row: int,
    question: str = "测试问题",
    answer: str = "测试回答",
    plan_intent: str = "indicator",
    indicator: str = "ROE",
    error: str = "",
) -> dict:
    row: dict = {
        "source_row": source_row,
        "session_id": f"s{source_row}",
        "turn_index": 1,
        "question": question,
        "answer": answer,
        "plan_intent": plan_intent,
        "indicator": indicator,
    }
    if error:
        row["error"] = error
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(autouse=True)
def _fake_judge(monkeypatch):
    """假裁判：非 error 记录全部判「正确」；error 记录跳过（与真实一致）。"""

    def fake_judge(records, *, batch_size=8):
        judgements = []
        for r in records:
            if r.get("error"):
                continue
            judgements.append(
                {
                    "source_row": int(r["item"]["source_row"]),
                    "classification": "正确",
                    "error_types": [],
                    "reason": "fake judge",
                }
            )
        return {"summary": summarize_judgements(judgements), "judgements": judgements}

    monkeypatch.setattr(judge_cli, "judge_records", fake_judge)


def test_load_flat_samples_converts_and_validates(tmp_path):
    rows = [
        _flat_row(1, question="康美营收"),
        _flat_row(2, question="茅台风险", error="EXEC_ERROR"),
    ]
    p = _write_jsonl(tmp_path / "sample.jsonl", rows)
    records = judge_cli.load_flat_samples(p)
    assert len(records) == 2
    assert records[0]["item"]["source_row"] == 1
    assert records[0]["observed"]["answer"] == "测试回答"
    assert records[0]["observed"]["plan_intent"] == "indicator"
    assert "error" not in records[0]
    assert records[1]["error"] == "EXEC_ERROR"


def test_load_flat_samples_duplicate_row_rejected(tmp_path):
    rows = [_flat_row(1), _flat_row(1)]
    p = _write_jsonl(tmp_path / "dup.jsonl", rows)
    with pytest.raises(ValueError, match="重复 source_row"):
        judge_cli.load_flat_samples(p)


def test_run_judgement_fills_error_records(tmp_path):
    rows = [
        _flat_row(1, question="康美营收"),
        _flat_row(2, question="茅台风险", error="EXEC_ERROR"),
        _flat_row(3, question="东吴证券公告"),
    ]
    p = _write_jsonl(tmp_path / "sample.jsonl", rows)
    records = judge_cli.load_flat_samples(p)
    result = judge_cli.run_judgement(records, batch_size=2)
    judgements = result["judgements"]
    # 裁判数 = 样本数（error 记录被补判），无漏行无重复
    assert len(judgements) == 3
    assert [j["source_row"] for j in judgements] == [1, 2, 3]
    err = next(j for j in judgements if j["source_row"] == 2)
    assert err["classification"] == "无法核验"
    assert err["error_types"] == ["执行错误"]
    assert "EXEC_ERROR" in err["reason"]
    summary = result["summary"]
    assert summary["sample_total"] == 3
    assert summary["error_records"] == 1
    assert summary["judged_records"] == 3
    assert summary["counts"]["正确"] == 2
    assert summary["strict_accuracy"] == pytest.approx(2 / 3)
    assert summary["accepted_rate"] == pytest.approx(2 / 3)
    assert summary["usable_rate"] == pytest.approx(2 / 3)


def test_run_judgement_missing_rows_detected(monkeypatch, tmp_path):
    """裁判返回漏条时应报错（防静默漏判）。"""
    rows = [_flat_row(1), _flat_row(2), _flat_row(3)]
    p = _write_jsonl(tmp_path / "sample.jsonl", rows)
    records = judge_cli.load_flat_samples(p)

    def partial_judge(records, *, batch_size=8):
        judgements = [
            {
                "source_row": int(r["item"]["source_row"]),
                "classification": "正确",
                "error_types": [],
                "reason": "fake",
            }
            for r in records[:2]
        ]
        return {"summary": summarize_judgements(judgements), "judgements": judgements}

    monkeypatch.setattr(judge_cli, "judge_records", partial_judge)
    with pytest.raises(ValueError, match="不一致"):
        judge_cli.run_judgement(records)


def test_main_writes_outputs(tmp_path, capsys):
    rows = [_flat_row(1), _flat_row(2, error="EXEC_ERROR")]
    sample = _write_jsonl(tmp_path / "sample.jsonl", rows)
    out = tmp_path / "judgement.jsonl"
    summary_path = tmp_path / "summary.json"
    rc = judge_cli.main(
        [
            str(sample),
            "--output",
            str(out),
            "--summary",
            str(summary_path),
            "--batch-size",
            "2",
        ]
    )
    assert rc == 0
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert {j["source_row"] for j in lines} == {1, 2}
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["error_records"] == 1
    assert summary["sample_total"] == 2
    captured = capsys.readouterr()
    assert "严格正确率=50.0%" in captured.out
    assert "error_records=1" in captured.out


def test_main_missing_file_returns_2(tmp_path):
    rc = judge_cli.main([str(tmp_path / "nope.jsonl")])
    assert rc == 2
