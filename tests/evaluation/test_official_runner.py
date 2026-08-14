"""official_runner 单元测试 — v3.3.3 收口批次 E（方案 §4.1/§4.2）。

覆盖：sidecar 来源行不一致启动失败；to_verify 不计分（无可评分样本
明确声明）；verified 样本才进入评分分母。
"""

import pytest

from tests.evaluation.official_runner import (
    _run_with_context,
    _summarize,
    _validate_sidecar_against_excel,
)


def _loader_row(session_id, query):
    return {
        "question_id": "q0001",
        "session_id": session_id,
        "query": query,
        "expected_company": "",
        "expected_risk_level": "",
        "think_flag": 0,
    }


def _item(row, session_id="5", turn=1, question=None, status="to_verify"):
    return {
        "source_row": row,
        "session_id": session_id,
        "turn_index": turn,
        "question": question,
        "task_type": "indicator_short_answer",
        "data_status": status,
        "expected_metric_ids": [],
        "annotation_source": "rule+screening",
    }


def test_validate_sidecar_match_passes():
    rows = [_loader_row("5", "伊利股份的存货周转天数比双汇发展低多少？")]
    _validate_sidecar_against_excel(
        [_item(1, question="伊利股份的存货周转天数比双汇发展低多少？")], rows
    )


def test_validate_sidecar_question_mismatch_fails():
    rows = [_loader_row("5", "另一个问题")]
    with pytest.raises(SystemExit) as exc:
        _validate_sidecar_against_excel(
            [_item(1, question="伊利股份的存货周转天数比双汇发展低多少？")],
            rows,
        )
    assert "来源校验失败" in str(exc.value)


def test_validate_sidecar_session_mismatch_fails():
    rows = [_loader_row("6", "伊利股份的存货周转天数比双汇发展低多少？")]
    with pytest.raises(SystemExit):
        _validate_sidecar_against_excel(
            [
                _item(
                    1,
                    session_id="5",
                    question="伊利股份的存货周转天数比双汇发展低多少？",
                )
            ],
            rows,
        )


def test_validate_sidecar_turn_index_mismatch_fails():
    rows = [
        _loader_row("5", "第一问"),
        _loader_row("5", "第二问"),
    ]
    with pytest.raises(SystemExit):
        _validate_sidecar_against_excel([_item(2, turn=1, question="第二问")], rows)


def test_summarize_all_to_verify_no_scoring():
    """方案 §4.1：全部 to_verify → 无可评分样本，不输出准确率。"""
    records = [
        {"item": _item(1, question="q"), "observed": {}},
        {"item": _item(2, question="q2"), "observed": {}},
    ]
    summary = _summarize(records, requires_reannotation=False)
    assert summary["observation_count"] == 2
    assert summary["scored_count"] == 0
    assert summary["observed_only_count"] == 2
    assert "无可评分样本" in summary["scoring"]
    assert "accuracy" not in summary


def test_summarize_verified_samples_scored():
    records = [
        {
            "item": _item(1, question="q", status="verified"),
            "observed": {},
        },
        {
            "item": _item(2, question="q2", status="to_verify"),
            "observed": {},
        },
    ]
    summary = _summarize(records, requires_reannotation=False)
    assert summary["scored_count"] == 1
    assert summary["observed_only_count"] == 1


def test_summarize_error_counted_separately():
    records = [
        {"item": _item(1, question="q"), "error": "boom"},
        {"item": _item(2, question="q2"), "observed": {}},
    ]
    summary = _summarize(records, requires_reannotation=False)
    assert summary["errors"] == 1
    assert summary["observation_count"] == 1


def test_summarize_requires_reannotation_flag():
    records = [{"item": _item(1, question="q", status="verified"), "observed": {}}]
    summary = _summarize(records, requires_reannotation=True)
    assert summary["requires_reannotation"] is True


# ── session 交错隔离（方案 §5 C1/C2）─────────────────────────


class _FakeGraph:
    """记录 invoke 的 fake compiled graph（不连接真实数据库）。"""

    def __init__(self):
        self.invoked: list[str] = []
        self.raise_on: set[str] = set()

    def invoke(self, state):
        q = str(state.get("user_query") or "")
        self.invoked.append(q)
        if q in self.raise_on:
            raise RuntimeError(f"boom:{q}")
        return {}


def _interleaved_rows():
    """物理行交错：1(A), 2(B), 3(A target), 4(B target)。"""
    return [
        _loader_row("A", "qA1"),
        _loader_row("B", "qB1"),
        _loader_row("A", "qA2"),
        _loader_row("B", "qB2"),
    ]


def _interleaved_items():
    return [
        _item(3, session_id="A", turn=2, question="qA2"),
        _item(4, session_id="B", turn=2, question="qB2"),
    ]


def test_run_with_context_session_interleaving_isolated():
    """方案 §5 C2 反例：A 只执行 1、3；B 只执行 2、4。"""
    fake = _FakeGraph()
    records, session_ids = _run_with_context(
        _interleaved_items(), _interleaved_rows(), compiled=fake
    )
    assert fake.invoked == ["qA1", "qA2", "qB1", "qB2"]
    # 只输出目标行，context 行不进 observed 记录
    assert sorted(int(r["item"]["source_row"]) for r in records) == [3, 4]
    assert all("error" not in r for r in records)
    # finally 清理所需的全部 eval session 均返回
    assert session_ids == ["evalv333_A", "evalv333_B"]


def test_run_with_context_other_session_target_not_misjudged():
    """B 的 target 行 4 不得被 A 的 target 集合误判（原 next() 会 StopIteration）。"""
    # 只给 A 一个 target：行 4 是 B 的 target，但 A 的执行不得触碰
    items = [_item(3, session_id="A", turn=2, question="qA2")]
    fake = _FakeGraph()
    records, _ = _run_with_context(items, _interleaved_rows(), compiled=fake)
    assert fake.invoked == ["qA1", "qA2"]
    assert [int(r["item"]["source_row"]) for r in records] == [3]


def test_run_with_context_context_row_error_does_not_pollute():
    """context 行出错：不进入记录、不影响同 session 目标行与其他 session。"""
    fake = _FakeGraph()
    fake.raise_on = {"qB1"}  # B 的 context 行失败
    records, _ = _run_with_context(
        _interleaved_items(), _interleaved_rows(), compiled=fake
    )
    # A 不受影响；B 的目标行 4 仍被执行并记录
    assert fake.invoked == ["qA1", "qA2", "qB1", "qB2"]
    assert sorted(int(r["item"]["source_row"]) for r in records) == [3, 4]
    assert all("error" not in r for r in records)


def test_run_with_context_target_row_error_recorded():
    """目标行出错：记录 error；不影响其他 session。"""
    fake = _FakeGraph()
    fake.raise_on = {"qA2"}
    records, _ = _run_with_context(
        _interleaved_items(), _interleaved_rows(), compiled=fake
    )
    errors = [r for r in records if "error" in r]
    observed = [r for r in records if "error" not in r]
    assert [int(r["item"]["source_row"]) for r in errors] == [3]
    assert "boom:qA2" in errors[0]["error"]
    assert [int(r["item"]["source_row"]) for r in observed] == [4]
