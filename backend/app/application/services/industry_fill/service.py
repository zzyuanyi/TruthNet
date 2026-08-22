"""行业补全编排服务（档案 v1.1 §3 总体链路）。

链路：
  快照 → 缺失代码 → 研报确定性补全 → AkShare provider（批量优先/逐股回退）
  → 标准化映射 → staging 持久化 → 质量门禁 → dry-run 报告 →（--apply）单事务更新
  → 占位值清洗 → 重生成 industry_mapping.csv → 覆盖率/来源验收。

名称推断兜底已从链路移除（档案 v1.1 §13：不用名称猜测强行补齐）；
指标 name_inference_success 恒为 0 并在报告注明 legacy。
"""

from __future__ import annotations

import json
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
from backend.app.application.services.industry_fill.universe import (
    CurrentUniverseSnapshot,
    bare_security_code,
    partition_missing_codes,
)
from backend.app.application.services.industry_fill.validation import (
    check_apply_readiness,
    check_dry_run_no_change,
    validate_staging,
)

log = logging.getLogger(__name__)

ApplyRow = tuple[str, str | None, str | None, str | None, str]


class PostApplyRebuildError(RuntimeError):
    """apply 已提交、但后续 benchmark 重建失败——数据库不会自动回滚，需手动恢复。"""


def _save_partial_report(result: PipelineResult, gate: Any) -> None:
    """apply 提交后步骤失败路径：尽力落盘部分报告（含 post_apply_steps/run_dir）。

    rebuild/CSV 失败会提前抛 PostApplyRebuildError，完整 report（build_report 之后）
    在 CLI 不可达；这里在异常传播前把已有指标+门禁写入 run_dir/report.json，
    供取证与恢复（对抗审查 F）。best-effort：失败不影响主异常传播。
    """
    if result.run_dir is None:
        return
    try:
        partial = build_report(
            result.report,
            list(getattr(gate, "checks", []) or []),
            list(getattr(gate, "problems", []) or []),
        )
        out = result.run_dir / "report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(partial, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        log.info("部分报告已落盘（apply 后步骤失败取证）: %s", out)
    except Exception:  # noqa: BLE001
        log.exception("部分报告落盘失败（不影响主异常传播）")


def _resolve_benchmark_script(script_path: str = "") -> Path:
    if script_path:
        return Path(script_path)
    return (
        Path(__file__).resolve().parents[5] / "scripts" / "build_industry_benchmarks.py"
    )


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
    # apply readiness 门禁人工例外：默认 unmapped_count==0 强制；显式开启才放行
    allow_unmapped: bool = False
    # CLI 正式链路必须传入带来源/哈希的当前沪深京 A 股快照；直接单测可留空。
    current_universe: CurrentUniverseSnapshot | None = None


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
    raw_missing, research_fills = compute_missing_codes(snapshot, report_map)
    all_missing_l1 = sorted(
        code
        for code, info in snapshot.items()
        if not (info.get("industry_l1") or "").strip()
    )
    not_current_universe: list[str] = []
    missing = raw_missing
    current_wind_codes: list[str] = []
    current_missing_l1_codes: set[str] = set()
    current_missing_l2_codes: set[str] = set()
    if config.current_universe is not None:
        missing, not_current_universe = partition_missing_codes(
            all_missing_l1, config.current_universe
        )
        queryable_missing = set(raw_missing)
        missing = [code for code in missing if code in queryable_missing]
        research_fills = {
            code: fill
            for code, fill in research_fills.items()
            if bare_security_code(code) in config.current_universe.codes
        }
        current_codes_in_db = {
            bare_security_code(code)
            for code in snapshot
            if bare_security_code(code) in config.current_universe.codes
        }
        current_rows = [
            (code, info)
            for code, info in snapshot.items()
            if bare_security_code(code) in config.current_universe.codes
        ]
        current_wind_codes = sorted(code for code, _info in current_rows)
        current_missing_l1_codes = {
            code
            for code, info in current_rows
            if not (info.get("industry_l1") or "").strip()
        }
        current_missing_l2_codes = {
            code
            for code, info in current_rows
            if not (info.get("industry_l2") or "").strip()
        }
        current_missing_l1 = len(current_missing_l1_codes)
        current_missing_l2 = len(current_missing_l2_codes)
        current_count = len(current_rows)
        missing_company_codes = sorted(
            config.current_universe.codes - current_codes_in_db
        )
        result.report.update(config.current_universe.report_fields())
        result.report.update(
            {
                "current_universe_in_companies": current_count,
                "current_universe_missing_from_companies": len(missing_company_codes),
                "current_universe_missing_company_codes": [
                    {
                        "code": code,
                        "name": config.current_universe.names.get(code, ""),
                    }
                    for code in missing_company_codes
                ],
                "current_universe_missing_l1": current_missing_l1,
                "current_universe_missing_l2": current_missing_l2,
                "current_universe_l1_coverage": round(
                    100.0 * (current_count - current_missing_l1) / current_count, 2
                )
                if current_count
                else 0.0,
                "current_universe_l2_coverage": round(
                    100.0 * (current_count - current_missing_l2) / current_count, 2
                )
                if current_count
                else 0.0,
                "raw_missing_industry_l1": len(all_missing_l1),
                "not_current_universe_missing_l1": len(not_current_universe),
                "current_universe_company_master_complete": not missing_company_codes,
            }
        )
    candidate_missing_count = len(missing)
    if config.replace:
        if config.current_universe is None:
            raise RuntimeError("--replace 必须带当前 A 股范围快照，禁止覆盖历史证券")
        # 显式 refresh：核验全部当前上市公司；历史/退市证券永不进入覆盖候选。
        missing = current_wind_codes
        research_fills = {}
    result.research_filled = len(research_fills)
    log.info(
        "companies=%d, 研报可确定性补全=%d, 原始缺失=%d, 当前上市待查询=%d, "
        "非当前上市豁免=%d",
        len(snapshot),
        len(research_fills),
        len(all_missing_l1),
        len(missing),
        len(not_current_universe),
    )

    # 2) 本次候选集合（offset/limit 只控制本次，不改变全量缺失清单，档案 §4）
    candidate = missing[config.offset :]
    if config.limit is not None:
        candidate = candidate[: config.limit]
    result.report["candidate_query_count"] = len(candidate)
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
    result.report["verified_existing_rows"] = len(results) if config.replace else 0

    # provider 运行统计（自适应节流/主机分布/有效并发，档案 v1.1 §6.4）
    if hasattr(config.provider, "report_stats"):
        result.report.update(config.provider.report_stats())

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

    # 7b) apply 就绪门禁（P0 收口：ERROR/UNMAPPED 拒绝 apply；EMPTY 允许保留）
    #     始终计算并写入报告（dry-run 也能看到将被阻止的项），apply 时强制执行。
    readiness = check_apply_readiness(results, allow_unmapped=config.allow_unmapped)
    result.report["apply_readiness_problems"] = readiness.problems
    result.report["apply_readiness_ok"] = readiness.ok
    if config.apply and not readiness.ok:
        raise RuntimeError(
            "apply readiness 门禁失败，拒绝 apply：" + "；".join(readiness.problems)
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
    existing_overwrites = 0
    source_upgrades = 0
    existing_l1_mismatches = 0
    existing_l2_mismatches = 0
    for res in results:
        if res.query_status != QueryStatus.SUCCESS or not res.industry_l1:
            continue
        if config.replace:
            existing = snapshot[res.wind_code]
            l1_changed = (existing.get("industry_l1") or "").strip() != res.industry_l1
            l2_changed = (existing.get("industry_l2") or "").strip() != (
                res.industry_l2 or ""
            ).strip()
            fields_changed = l1_changed or l2_changed
            existing_l1_mismatches += int(l1_changed)
            existing_l2_mismatches += int(l2_changed)
            source_upgrade = (existing.get("industry_source") or "").startswith(
                "name_inference"
            )
            if not fields_changed and not source_upgrade:
                continue
            existing_overwrites += int(fields_changed)
            source_upgrades += int(source_upgrade)
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
    result.report["existing_values_overwritten"] = existing_overwrites
    result.report["existing_source_upgrades"] = source_upgrades
    result.report["existing_l1_mismatches"] = existing_l1_mismatches
    result.report["existing_l2_mismatches"] = existing_l2_mismatches

    if config.current_universe is not None:
        planned_l1 = {
            row[0] for row in research_rows + provider_rows if (row[1] or "").strip()
        }
        planned_l2 = {
            row[0] for row in research_rows + provider_rows if (row[2] or "").strip()
        }
        projected_missing_l1 = current_missing_l1_codes - planned_l1
        projected_missing_l2 = current_missing_l2_codes - planned_l2
        classification_complete = not projected_missing_l1 and not projected_missing_l2
        result.report.update(
            {
                "current_universe_projected_missing_l1": len(projected_missing_l1),
                "current_universe_projected_missing_l2": len(projected_missing_l2),
                "current_universe_classification_complete": classification_complete,
            }
        )
        if config.apply and not classification_complete:
            raise RuntimeError(
                "当前上市且已入 companies 的证券仍存在行业缺口，拒绝 apply："
                f"projected_missing_l1={len(projected_missing_l1)}, "
                f"projected_missing_l2={len(projected_missing_l2)}"
            )

    before = fetch_coverage_stats(engine)
    result.report.update(
        {
            "companies_total": before["companies_total"],
            "companies_with_industry_before": before["companies_with_industry_before"],
            "research_report_codes": before["research_report_codes"],
            "research_report_matched": before["research_report_matched"],
            "candidate_missing_count": candidate_missing_count,
            "duplicate_wind_codes": before["duplicate_wind_codes"],
            "nan_source_count": before["nan_source_count"],
        }
    )

    # 9) dry-run（默认）或 apply（单事务 + 占位值清洗 + 基准重建）
    dry_run_ok: bool | None = None
    if config.apply:
        rows = research_rows + provider_rows
        # 预检：benchmark 重建在 DB 写入前可运行（防"库已改、基准未建"部分状态）
        if not config.skip_benchmark_rebuild:
            _preflight_benchmarks(config.benchmark_rebuild_exe)
        apply_out = apply_industry_fill(
            engine,
            expected_database=config.database,
            rows=rows,
            replace=config.replace,
            as_of=date.today(),
        )
        result.apply_result = apply_out
        result.report["companies_updated"] = apply_out["companies_updated"]
        result.report["post_apply_steps"] = []
        # CSV 重生成也是提交后步骤：失败同样必须显式"不会自动回滚"（对抗审查 E）
        try:
            _regenerate_mapping_csv(engine, config.mapping_csv_path)
        except Exception as exc:  # noqa: BLE001 - pandas/磁盘/Windows 文件占用等
            _save_partial_report(result, gate)
            raise PostApplyRebuildError(
                f"industry_mapping.csv 重生成失败：{exc}；注意：行业字段已提交数据库，"
                "数据库不会自动回滚——请修复后重新生成 CSV 并重建基准（恢复路径见档案 §7.4）。"
            ) from exc
        result.report["post_apply_steps"].append("industry_mapping.csv 已重生成")
        if not config.skip_benchmark_rebuild:
            try:
                _rebuild_benchmarks(config.database, config.benchmark_rebuild_exe)
            except RuntimeError as exc:
                _save_partial_report(result, gate)
                raise PostApplyRebuildError(
                    f"{exc}；注意：行业字段已提交数据库，数据库不会自动回滚——"
                    "请修复 benchmark 脚本后重新运行 rebuild（恢复路径见档案 §7.4）。"
                ) from exc
            result.report["post_apply_steps"].append("industry_benchmarks 已重建并校验")
        # 最后一步覆盖读同样是提交后步骤：失败必须显式"不会自动回滚"并落盘部分报告，
        # 否则 SQLAlchemy OperationalError（非 RuntimeError）会在 CLI 层裸奔
        # （对抗审查 H3）。
        try:
            after = fetch_coverage_stats(engine)
        except Exception as exc:  # noqa: BLE001 - 连接中断/读失败
            _save_partial_report(result, gate)
            raise PostApplyRebuildError(
                f"apply 后覆盖统计读取失败：{exc}；注意：行业字段已提交数据库，"
                "数据库不会自动回滚——请确认库内数据后按档案 §7.4 完成 CSV/基准重建。"
            ) from exc
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


def _preflight_benchmarks(script_path: str = "") -> None:
    """apply 前预检 benchmark 系统可重建（--verify-only）。

    防止"companies 已写入、industry_benchmarks 却建不起来"的部分状态：
    表缺失（退出码 2）或既有数据损坏（退出码 1）→ 在 DB 写入前 fail-closed（零写入）。
    """
    script = _resolve_benchmark_script(script_path)
    if not script.exists():
        raise RuntimeError(f"benchmark 脚本不存在，无法预检: {script}")
    verify = subprocess.run(
        [sys.executable, str(script), "--verify-only"],
        stdout=None,
        stderr=None,
        check=False,
    )
    if verify.returncode == 2:
        raise RuntimeError(
            "benchmark 预检失败：industry_benchmarks 表缺失，拒绝 apply（零写入）"
        )
    if verify.returncode == 1:
        # 退出码 1 既可能是"数据校验不过"，也可能是脚本自身异常（DB 连接/依赖）
        # 崩溃——Python 未捕获异常默认也是 1。两者都 fail-closed（零写入），
        # 但诊断需提示两种可能，避免误导运维只查数据完整性（对抗审查 G）。
        raise RuntimeError(
            "benchmark 预检失败（退出码 1）：既有 industry_benchmarks 数据校验不过，"
            "或脚本执行异常（DB 连接/依赖失败），拒绝 apply（零写入）——"
            "请查看上方透传输出定位具体原因"
        )
    if verify.returncode != 0:
        raise RuntimeError(
            f"benchmark 预检失败：退出码 {verify.returncode}，拒绝 apply（零写入）"
        )
    log.info("benchmark 预检通过：industry_benchmarks 可重建 ✓")


def _rebuild_benchmarks(database: str, script_path: str = "") -> None:
    """apply 后重建并校验离线基准表（档案 v1.1 §7.4）。

    子进程 stdio 透传（不捕获管道，兼容沙箱）；脚本继承当前进程环境变量，
    因而沿用目标库凭据注入。
    """
    script = _resolve_benchmark_script(script_path)
    if not script.exists():
        raise RuntimeError(f"benchmark 脚本不存在，无法重建: {script}")
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
