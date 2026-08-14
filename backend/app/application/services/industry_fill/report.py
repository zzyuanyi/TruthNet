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
        if key == "source_distribution":
            lines.append(f"{key}: {json.dumps(value or {}, ensure_ascii=False)}")
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
