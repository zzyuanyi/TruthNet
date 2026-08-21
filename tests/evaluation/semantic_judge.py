"""官方 runner 的独立语义裁判层。

裁判结果不写回官方 sidecar，也不改变 official_runner 的 scored_count。
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field


CLASSIFICATIONS = ("正确", "合理拒答", "部分正确", "错误", "无法核验")
Classification = Literal["正确", "合理拒答", "部分正确", "错误", "无法核验"]


class SemanticJudgement(BaseModel):
    source_row: int
    classification: Classification
    error_types: list[str] = Field(default_factory=list)
    reason: str = ""


class SemanticJudgementBatch(BaseModel):
    items: list[SemanticJudgement] = Field(default_factory=list)


def _judge_messages(batch: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "你是金融问答系统的语义裁判。逐条比较用户问题、评测元数据和系统答案。"
                "只判断答案是否满足问题，不因为系统诚实拒答而扣分。"
                "分类只能是：正确、合理拒答、部分正确、错误、无法核验。"
                "正确：数值、期次、口径、结论与问题一致，或合理纠正错误前提；"
                "合理拒答：当前数据或能力确实不足，答案明确说明边界且没有编造；"
                "部分正确：主体或部分事实正确，但缺少问题要求的重要结果；"
                "错误：主体、指标、计算、期次、结论或证据明显不符；"
                "无法核验：题目依赖当日外部行情、外部事实或本轮外部服务失败，"
                "仅凭当前观测不能区分代码缺陷和外部不可用。返回结构化 JSON。"
            ),
        },
        {"role": "user", "content": f"待裁判样本：{batch}"},
    ]


def _sample_payload(record: dict) -> dict:
    item = record["item"]
    observed = record.get("observed", {})
    return {
        "source_row": item.get("source_row"),
        "question": item.get("question", ""),
        "task_type": item.get("task_type", ""),
        "expected": {
            "relation": item.get("expected_relation", ""),
            "metric_ids": item.get("expected_metric_ids", []),
            "comparison_scope": item.get("expected_comparison_scope", ""),
            "operation": item.get("expected_operation", ""),
            "period_policy": item.get("expected_period_policy", ""),
            "answer_mode": item.get("expected_answer_mode", ""),
            "codes": item.get("expected_codes", []),
        },
        "observed": {
            "relation": observed.get("relation", ""),
            "codes": observed.get("codes", []),
            "intent": observed.get("plan_intent", ""),
            "comparison_scope": observed.get("comparison_scope", ""),
            "comparison_mode": observed.get("comparison_mode", ""),
            "metric_ids": observed.get("metric_ids", []),
            "indicator": observed.get("indicator", ""),
            "answer": observed.get("answer", ""),
            "claims": observed.get("claims", 0),
            "evidence": observed.get("evidence", 0),
            "evidence_items": observed.get("evidence_items", []),
        },
    }


def summarize_judgements(judgements: list[dict]) -> dict:
    counts = Counter(item.get("classification", "无法核验") for item in judgements)
    total = len(judgements)
    correct = counts["正确"]
    accepted = correct + counts["合理拒答"]
    usable = accepted + counts["部分正确"]
    return {
        "total": total,
        "counts": {label: counts[label] for label in CLASSIFICATIONS},
        "strict_accuracy": correct / total if total else 0.0,
        "accepted_rate": accepted / total if total else 0.0,
        "usable_rate": usable / total if total else 0.0,
        "note": "这是独立语义裁判估计，不是官方自动评分，也不写回 sidecar；to_verify 样本仍不进入 official_runner 的 scored_count。",
    }


def judge_records(records: list[dict], *, batch_size: int = 8) -> dict:
    """分批调用结构化裁判，返回 summary + 逐条 judgement。"""
    from app.agents.llm_sync import run_llm_structured

    observed = [record for record in records if "error" not in record]
    results: list[dict] = []
    for start in range(0, len(observed), batch_size):
        batch_records = observed[start : start + batch_size]
        payload = [_sample_payload(record) for record in batch_records]
        output = run_llm_structured(_judge_messages(payload), SemanticJudgementBatch)
        returned = {item.source_row: item for item in (output.items if output else [])}
        for record in batch_records:
            row = int(record["item"]["source_row"])
            judgement = returned.get(row)
            if judgement is None:
                results.append(
                    {
                        "source_row": row,
                        "classification": "无法核验",
                        "error_types": ["语义裁判不可用"],
                        "reason": "裁判模型未返回该样本的结构化判定。",
                    }
                )
            else:
                results.append(judgement.model_dump())
    return {"summary": summarize_judgements(results), "judgements": results}
