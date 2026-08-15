"""质量门禁（档案 v1.1 §9）。

所有门禁失败必须 fail-closed：dry-run 不得进入 apply，apply 事务整体回滚。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.application.services.industry_fill.constants import QueryStatus
from backend.app.application.services.industry_fill.normalizer import normalize_l1
from backend.app.application.services.industry_fill.provider import ProviderResult


@dataclass
class GateReport:
    ok: bool = True
    problems: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.problems.append(message)

    def pass_(self, message: str) -> None:
        self.checks.append(message)


def validate_staging(
    records: list[ProviderResult],
    input_codes: list[str],
    *,
    skipped_codes: set[str] | None = None,
    replace: bool = False,
) -> GateReport:
    """staging 结果门禁（档案 §9 门禁 1-4、9）。

    - 输入缺失代码无重复；
    - 每个输入代码都有 staging 记录或被显式 skipped；
    - success 记录 industry_l1 非空且属于允许集合；
    - success 记录 source 合法、无 nan、代码非空；
    - empty/unmapped/error 不得混为 success。
    """
    report = GateReport()
    skipped = skipped_codes or set()

    if len(input_codes) != len(set(input_codes)):
        report.fail("输入缺失代码存在重复")

    by_code: dict[str, list[ProviderResult]] = {}
    for rec in records:
        by_code.setdefault(rec.wind_code, []).append(rec)

    for code in input_codes:
        if code not in by_code and code not in skipped:
            report.fail(f"{code} 无 staging 记录且未标记 skipped")

    for rec in records:
        if rec.query_status == QueryStatus.SUCCESS:
            l1 = normalize_l1(rec.industry_l1)
            if l1 is None:
                report.fail(
                    f"{rec.wind_code} success 但 industry_l1 非法: {rec.industry_l1!r}"
                )
            if not rec.wind_code or not rec.wind_code.strip():
                report.fail(f"{rec.wind_code!r} success 但 wind_code 为空")
        elif rec.query_status not in {
            QueryStatus.EMPTY,
            QueryStatus.UNMAPPED,
            QueryStatus.ERROR,
            QueryStatus.SKIPPED,
        }:
            report.fail(f"{rec.wind_code} 非法 query_status: {rec.query_status!r}")

    if report.ok:
        report.pass_(
            f"staging 门禁通过：{len(input_codes)} 输入代码、"
            f"{len(records)} 条记录、{len(skipped)} 条 skipped"
        )
    return report


def check_apply_readiness(
    records: list[ProviderResult], *, allow_unmapped: bool = False
) -> GateReport:
    """apply 前就绪门禁（档案 §9 门禁 5 扩展；P0 收口批次）。

    与 staging integrity gate 分离：integrity 允许 error/unmapped 存在以便完整
    报告诊断；就绪门禁在 --apply 前强制 fail-closed（零写入）。

    - error_count != 0 → 拒绝：存在未解决 provider 错误，必须先 --resume 重查；
    - unmapped_count != 0 且未显式 allow_unmapped → 拒绝（不隐式忽略）；
    - EMPTY 是合法终态，允许保留（dry-run 语义）。
    """
    report = GateReport()
    error_count = sum(1 for r in records if r.query_status == QueryStatus.ERROR)
    if error_count:
        report.fail(
            "unresolved provider errors remain; resume required before apply"
            f"（error_count={error_count}）"
        )
    unmapped_count = sum(1 for r in records if r.query_status == QueryStatus.UNMAPPED)
    if unmapped_count and not allow_unmapped:
        report.fail(
            f"unmapped_count={unmapped_count} 存在未映射行业，默认拒绝 apply；"
            "人工例外需显式 --allow-unmapped（禁止隐式忽略）"
        )
    if report.ok:
        report.pass_("apply readiness 门禁通过：error=0、unmapped=0")
    return report


def plan_apply_rows(
    records: list[ProviderResult],
    current_industry: dict[str, str | None],
    *,
    replace: bool = False,
) -> tuple[list[ProviderResult], int]:
    """生成可写入行清单（档案 §7.2）。

    默认模式只补缺失（current_industry 为空者）；--replace 允许覆盖。
    返回 (eligible_rows, would_overwrite_count)。
    """
    eligible: list[ProviderResult] = []
    overwrite = 0
    for rec in records:
        if rec.query_status != QueryStatus.SUCCESS:
            continue
        existing = (current_industry.get(rec.wind_code) or "").strip()
        if existing:
            if not replace:
                continue
            overwrite += 1
        eligible.append(rec)
    return eligible, overwrite


def check_dry_run_no_change(before: dict, after: dict) -> GateReport:
    """dry-run 后业务表不变断言（档案 §9 门禁 6）。"""
    report = GateReport()
    for key in ("companies_total", "covered", "missing", "nan_source"):
        if before.get(key) != after.get(key):
            report.fail(
                f"dry-run 前后 {key} 变化: {before.get(key)!r} -> {after.get(key)!r}"
            )
    if report.ok:
        report.pass_("dry-run 未改变业务表")
    return report
