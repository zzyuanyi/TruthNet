"""行业补全编排服务（档案 v1.1 §3 总体链路）。

链路：
  快照 → 缺失代码 → 研报确定性补全 → AkShare provider（批量优先/逐股回退）
  → 标准化映射 → staging 持久化 → 质量门禁 → dry-run 报告 →（--apply）单事务更新
  → 占位值清洗 → 重生成 industry_mapping.csv → 覆盖率/来源验收。

名称推断兜底已从链路移除（档案 v1.1 §13：不用名称猜测强行补齐）；
指标 name_inference_success 恒为 0 并在报告注明 legacy。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from backend.app.application.services.industry_fill.constants import (
    DEFAULT_CACHE_DIR,
    PROGRESS_EVERY,
    SOURCE_AKSHARE,
    SOURCE_RESEARCH_REPORT,
    QueryStatus,
)
from backend.app.application.services.industry_fill.db import (
    apply_industry_fill,
    compute_missing_codes,
    current_database,
    fetch_companies_snapshot,
    fetch_coverage_stats,
    fetch_report_industry_map,
)
from backend.app.application.services.industry_fill.normalizer import normalize_l1
from backend.app.application.services.industry_fill.provider import IndustryProvider
from backend.app.application.services.industry_fill.report import build_report
from backend.app.application.services.industry_fill.staging import (
    RunMetadata,
    StagingStore,
)
from backend.app.application.services.industry_fill.validation import (
    check_dry_run_no_change,
    validate_staging,
)

log = logging.getLogger(__name__)

ApplyRow = tuple[str, str | None, str | None, str | None, str]


@dataclass
class RunConfig:
    database: str
    provider: IndustryProvider
    mapping_version: str
    dataset_version: str
    provider_version: str
    limit: int | None = None
    offset: int = 0
    apply: bool = False
    replace: bool = False
    max_retries: int = 3
    backoff_seconds: float = 1.0
    retry_empty: bool = False
    cache_dir: Path = Path(DEFAULT_CACHE_DIR)
    run_id: str = ""
    skip_benchmark_rebuild: bool = False
    benchmark_rebuild_exe: str = ""
    mapping_csv_path: Path = Path("data/processed/industry_mapping.csv")
    concurrency: int = 4


@dataclass
class PipelineResult:
    report: dict[str, Any] = field(default_factory=dict)
    research_filled: int = 0
    eligible_rows: int = 0
    run_dir: Path | None = None
    apply_result: dict[str, Any] = field(default_factory=dict)


def _progress_printer(done: int, total: int, counts: dict[str, int]) -> None:
    if done % PROGRESS_EVERY == 0 or done == total:
        log.info("  查询进度 %d/%d: %s", done, total, counts)


def run_pipeline(
    engine: Engine,
    config: RunConfig,
    *,
    cli_args: dict | None = None,
) -> PipelineResult:
    """执行完整链路；默认 dry-run（零写入），--apply 走单事务。"""
    result = PipelineResult()
    db_guard = current_database(engine)
    if str(db_guard or "").lower() != str(config.database or "").lower():
        raise AssertionError(
            f"启动守卫失败：SELECT DATABASE()={db_guard!r}，期望 {config.database!r}"
        )
    log.info("启动守卫通过：目标库 %s ✓", config.database)

    # 1) 快照、缺失代码、研报确定性补全
    snapshot = fetch_companies_snapshot(engine)
    report_map = fetch_report_industry_map(engine)
    missing, research_fills = compute_missing_codes(snapshot, report_map)
    result.research_filled = len(research_fills)
    log.info(
        "companies=%d, 研报可确定性补全=%d, 待查询缺失=%d",
        len(snapshot),
        len(research_fills),
        len(missing),
    )

    # 2) 本次候选集合（offset/limit 只控制本次，不改变全量缺失清单，档案 §4）
    candidate = missing[config.offset :]
    if config.limit is not None:
        candidate = candidate[: config.limit]
    log.info(
        "本次候选=%d（offset=%d, limit=%s），全量缺失=%d",
        len(candidate),
        config.offset,
        config.limit,
        len(missing),
    )

    # 3) staging 元数据与 resume（先校验旧元数据、再写入新元数据，fail-closed）
    run_dir = Path(config.cache_dir) / (config.run_id or "run")
    metadata = RunMetadata(
        run_id=config.run_id or "run",
        cli_args=cli_args or {},
        input_codes=sorted(candidate),
        provider=config.provider.name,
        provider_version=config.provider_version,
        mapping_version=config.mapping_version,
        dataset_version=config.dataset_version,
        database=config.database,
    )
    resume_available = (run_dir / "metadata.json").exists()
    store = StagingStore(run_dir, metadata=None if resume_available else metadata)
    cached: dict[str, Any] = {}
    if resume_available:
        cached = store.resume(metadata)  # 不匹配会抛 RuntimeError（fail-closed）
        store.write_metadata(metadata)  # 校验通过后更新本次参数摘要
        log.info("resume：复用 staging %d 条", len(cached))
    result.run_dir = run_dir

    # 4) provider 查询（成功缓存不重复打接口，档案 §6.1）；
    #    逐码回调即落盘 staging（档案 §6.2：不等待全量结束）。
    def _persist(res: Any) -> None:
        if res.query_status == QueryStatus.SUCCESS:
            l1 = normalize_l1(res.industry_l1)
            if l1 is None:
                res.query_status = QueryStatus.UNMAPPED
                res.last_error = f"success 但一级行业非法: {res.industry_l1!r}"
        record = dict(res.__dict__)
        record["query_status"] = getattr(
            res.query_status, "value", str(res.query_status)
        )
        store.append(record)

    results = config.provider.query_many(
        candidate,
        retry_empty=config.retry_empty,
        cached=cached,
        max_retries=config.max_retries,
        backoff_seconds=config.backoff_seconds,
        on_progress=_progress_printer,
        on_result=_persist,
        concurrency=config.concurrency,
    )
    result.report["staging_rows"] = len(store.records())

    # 6) 四态统计
    counts = {s: 0 for s in ("success", "empty", "unmapped", "error")}
    for res in results:
        if res.query_status.value in counts:
            counts[res.query_status.value] += 1
    result.report.update(
        {
            "akshare_success": counts["success"],
            "akshare_empty": counts["empty"],
            "akshare_unmapped": counts["unmapped"],
            "akshare_error": counts["error"],
            "name_inference_success": 0,  # 本链路不执行名称推断（档案 v1.1 §13）
        }
    )

    # 7) staging 门禁（档案 §9 门禁 1-4）
    gate = validate_staging(results, candidate)
    # fail-closed：apply 前门禁必须通过，任一问题直接拒绝，零写入（审查整改 P1）
    if config.apply and not gate.ok:
        raise RuntimeError(
            "staging 质量门禁失败，拒绝 apply：" + "；".join(gate.problems)
        )

    # 8) 写库计划：研报确定性 + akshare success，默认只补缺失
    current_l1 = {code: info.get("industry_l1") for code, info in snapshot.items()}
    research_rows: list[ApplyRow] = []
    for code, fill in research_fills.items():
        l1 = normalize_l1(fill.get("industry_l1"))
        if l1 and not (current_l1.get(code) or "").strip():
            research_rows.append(
                (code, l1, None, fill.get("sw_indu_code"), SOURCE_RESEARCH_REPORT)
            )
    provider_rows: list[ApplyRow] = []
    for res in results:
        if res.query_status != QueryStatus.SUCCESS or not res.industry_l1:
            continue
        provider_rows.append(
            (
                res.wind_code,
                res.industry_l1,
                res.industry_l2,
                res.sw_indu_code,
                SOURCE_AKSHARE,
            )
        )
    eligible_rows = len(research_rows) + len(provider_rows)
    result.eligible_rows = eligible_rows
    result.report["eligible_apply_rows"] = eligible_rows
    # 默认模式计划内零覆盖（已按缺失预筛；--replace 语义见 CLI 层）
    result.report["existing_values_overwritten"] = 0

    before = fetch_coverage_stats(engine)
    result.report.update(
        {
            "companies_total": before["companies_total"],
            "companies_with_industry_before": before["companies_with_industry_before"],
            "research_report_codes": before["research_report_codes"],
            "research_report_matched": before["research_report_matched"],
            "candidate_missing_count": len(missing),
            "duplicate_wind_codes": before["duplicate_wind_codes"],
            "nan_source_count": before["nan_source_count"],
        }
    )

    # 9) dry-run（默认）或 apply（单事务 + 占位值清洗 + 基准重建）
    dry_run_ok: bool | None = None
    if config.apply:
        rows = research_rows + provider_rows
        apply_out = apply_industry_fill(
            engine,
            expected_database=config.database,
            rows=rows,
            replace=config.replace,
            as_of=date.today(),
        )
        result.apply_result = apply_out
        result.report["companies_updated"] = apply_out["companies_updated"]
        _regenerate_mapping_csv(engine, config.mapping_csv_path)
        if not config.skip_benchmark_rebuild:
            _rebuild_benchmarks(config.database, config.benchmark_rebuild_exe)
        after = fetch_coverage_stats(engine)
    else:
        after = fetch_coverage_stats(engine)
        no_change = check_dry_run_no_change(
            {
                "companies_total": before["companies_total"],
                "covered": before["companies_with_industry_before"],
                "missing": before["missing"],
                "nan_source": before["nan_source_count"],
            },
            {
                "companies_total": after["companies_total"],
                "covered": after["companies_with_industry_before"],
                "missing": after["missing"],
                "nan_source": after["nan_source_count"],
            },
        )
        dry_run_ok = no_change.ok
        result.report["companies_updated"] = 0

    result.report["companies_with_industry_after"] = after[
        "companies_with_industry_before"
    ]
    result.report["final_coverage"] = after["final_coverage"]
    result.report["source_distribution"] = after["source_distribution"]
    result.report["nan_source_count"] = after["nan_source_count"]

    result.report = build_report(result.report, gate.checks, gate.problems)
    result.report["dry_run_no_change_ok"] = dry_run_ok
    result.report["quality_gates"] = gate.checks
    result.report["gate_problems"] = gate.problems
    return result


def _regenerate_mapping_csv(engine: Engine, out_path: Path) -> None:
    """apply 后重生成 industry_mapping.csv（档案 v1.1 §7.4，与库内一致）。"""
    import pandas as pd

    snapshot = fetch_companies_snapshot(engine)
    rows = [
        {
            "wind_code": code,
            "stock_name": info.get("sec_name") or "",
            "industry_l1": info.get("industry_l1") or "",
            "industry_l2": info.get("industry_l2") or "",
            "source": info.get("industry_source") or "",
        }
        for code, info in snapshot.items()
    ]
    df = pd.DataFrame(rows)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig", na_rep="")
    log.info("已重生成 %s（%d 行，无 nan 来源）", out_path, len(df))


def _rebuild_benchmarks(database: str, script_path: str = "") -> None:
    """apply 后重建并校验离线基准表（档案 v1.1 §7.4）。

    子进程 stdio 透传（不捕获管道，兼容沙箱）；脚本继承当前进程环境变量，
    因而沿用目标库凭据注入。
    """
    if script_path:
        script = Path(script_path)
    else:
        # ../../../../../../scripts/build_industry_benchmarks.py（代码仓库根）
        script = (
            Path(__file__).resolve().parents[5]
            / "scripts"
            / "build_industry_benchmarks.py"
        )
    log.info("重建 industry_benchmarks（%s）: %s", database, script)
    rebuild = subprocess.run(
        [sys.executable, str(script), "--rebuild"],
        stdout=None,
        stderr=None,
        check=False,
    )
    if rebuild.returncode != 0:
        raise RuntimeError(f"industry_benchmarks 重建失败，退出码 {rebuild.returncode}")
    verify = subprocess.run(
        [sys.executable, str(script), "--verify-only"],
        stdout=None,
        stderr=None,
        check=False,
    )
    if verify.returncode != 0:
        raise RuntimeError(f"industry_benchmarks 校验失败，退出码 {verify.returncode}")
    log.info("industry_benchmarks 重建与校验完成 ✓")
