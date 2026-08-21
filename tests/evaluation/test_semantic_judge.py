from tests.evaluation.semantic_judge import summarize_judgements


def test_summarize_semantic_judgements_reports_separate_rates():
    result = summarize_judgements(
        [
            {"classification": "正确"},
            {"classification": "合理拒答"},
            {"classification": "部分正确"},
            {"classification": "错误"},
        ]
    )
    assert result["counts"]["正确"] == 1
    assert result["strict_accuracy"] == 0.25
    assert result["accepted_rate"] == 0.5
    assert result["usable_rate"] == 0.75
    assert "sidecar" in result["note"]
