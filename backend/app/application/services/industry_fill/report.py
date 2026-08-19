"""运行报告与指标输出（档案 v1.1 §9）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_METRIC_KEYS = [
    "companies_total",
    "companies_with_industry_before",
    "research_report_codes",
    "research_report_matched",
    "candidate_missing_count",
    "akshare_success",
    "akshare_empty",
    "akshare_unmapped",
    "akshare_error",
    "name_inference_success",
    "staging_rows",
    "eligible_apply_rows",
    "companies_updated",
    "companies_with_industry_after",
    "final_coverage",
    "source_distribution",
    "existing_values_overwritten",
    "duplicate_wind_codes",
    "nan_source_count",
    # provider 运行统计（档案 v1.1 §6.4 收口批次）
    "provider_requests",
    "provider_retries",
    "provider_throttles",
    "provider_fallbacks",
    "provider_batch_requests",
    "provider_batch_misses",
    # Task C C7：批量限流/熔断可诊断统计（report_stats 计算后经 build_report 白名单透出）
    "provider_batch_throttled",
    "provider_batch_circuit_opens",
    "provider_batch_circuit_failfast",
    "provider_host_distribution",
    "effective_concurrency",
    "provider_pressure",
    # P0 就绪门禁与 apply 后置步骤
    "apply_readiness_ok",
    "apply_readiness_problems",
    "post_apply_steps",
]


def build_report(
    metrics: dict[str, Any], gates: list[str], problems: list[str]
) -> dict:
    """汇总为可审阅 dict；缺失指标补 0/None 以稳定输出（档案 §9 全部键）。"""
    out: dict[str, Any] = {}
    for key in REPORT_METRIC_KEYS:
        out[key] = metrics.get(key)
    out["quality_gates"] = gates
    out["gate_problems"] = problems
    return out


def render_text(report: dict, *, title: str) -> str:
    lines = [f"=== {title} ==="]
    for key in REPORT_METRIC_KEYS:
        value = report.get(key)
        if key in ("source_distribution", "provider_host_distribution"):
            lines.append(f"{key}: {json.dumps(value or {}, ensure_ascii=False)}")
        elif key == "post_apply_steps":
            lines.append(f"{key}: {json.dumps(value or [], ensure_ascii=False)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append(f"quality_gates: {len(report.get('quality_gates') or [])} 项通过")
    for problem in report.get("gate_problems") or []:
        lines.append(f"  [门禁失败] {problem}")
    return "\n".join(lines)


def save_report(report: dict, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return out_path
