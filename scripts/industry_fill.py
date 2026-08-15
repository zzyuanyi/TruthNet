#!/usr/bin/env python
"""行业分类覆盖补全 — 唯一正式入口（档案 v1.1）。

设计（修复档案《行业分类覆盖补全-具体修复档案》v1.1）：
  1. 不再存在隐式 [:50] 限制：默认全量，试跑必须显式 --limit；
  2. 研报确定性补全 → AkShare（批量接口优先、逐股回退）→ 申万层级映射；
  3. staging/cache 持久化（断点 --resume、失败分类、重试退避）；
  4. 默认 dry-run 零写入；--apply 走单事务批量更新 + 占位值清洗
     + 重生成 industry_mapping.csv + 重建 industry_benchmarks；
     apply 前 staging 质量门禁 fail-closed（任一问题直接拒绝，零写入）；
  5. 默认只补缺失（SQL 带缺失条件）；覆盖必须显式 --replace；
  6. 数据库双重守卫：凭据注入（测试库三件套）→ SELECT DATABASE() 确认。

用法（代码仓库根目录，PYTHONUTF8=1）：
    python scripts/industry_fill.py --database truthnet_test --probe
    python scripts/industry_fill.py --database truthnet_test --dry-run --limit 20
    python scripts/industry_fill.py --database truthnet_test --dry-run
    python scripts/industry_fill.py --database truthnet_test --resume <run_dir> --apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 注意：必须在导入 settings 之前完成凭据注入（acceptance_server.py 同款顺序），
# 因此 backend 业务模块全部延迟到 main() 内导入。
from backend.app.application.services.industry_fill.guards import (  # noqa: E402
    masked_profile,
    resolve_database_env,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("industry_fill")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--database",
        required=True,
        help="目标数据库名（必须与 .env 中声明的库一致；测试库自动注入测试三件套）",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="本次最多处理 N 个候选代码（默认不限制，禁止隐式 50）",
    )
    ap.add_argument("--offset", type=int, default=0, help="从缺失代码快照第 N 条开始")
    ap.add_argument(
        "--resume",
        type=str,
        default=None,
        help="读取之前 staging run 目录并跳过成功项（元数据不匹配则拒绝）",
    )
    ap.add_argument(
        "--cache",
        type=str,
        default=None,
        help="staging/cache 根目录（默认 data/processed/industry_fill_runs/<run_id>）",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="只查询并生成 staging 与报告（默认行为）"
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="通过全部门禁后单事务更新数据库（与 --dry-run 互斥）",
    )
    ap.add_argument(
        "--replace",
        action="store_true",
        help="允许覆盖已有行业（必须与 --apply 同时使用，默认关闭）",
    )
    ap.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="单代码/单批次最大重试次数（默认 3，日志打印）",
    )
    ap.add_argument(
        "--backoff-seconds",
        type=float,
        default=1.0,
        help="指数退避基数（默认 1.0s）",
    )
    ap.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="并发查询数（Session 连接复用 + 线程池，默认 4）",
    )
    ap.add_argument(
        "--provider",
        choices=["akshare"],
        default="akshare",
        help="数据源（当前只允许已实现并验证的 provider）",
    )
    ap.add_argument(
        "--retry-empty",
        action="store_true",
        help="resume 时对 empty 记录重新查询（默认不打接口）",
    )
    ap.add_argument(
        "--probe",
        action="store_true",
        help="仅做 AkShare 接口探测（版本/列名/样例），不连库不写库",
    )
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="只读输出覆盖率与来源分布统计后退出",
    )
    ap.add_argument(
        "--skip-benchmark-rebuild",
        action="store_true",
        help="apply 后跳过 industry_benchmarks 重建（与 --apply 互斥，测试链路用，正式验收禁止）",
    )
    return ap


def _validate_args(args: argparse.Namespace) -> None:
    if args.apply and args.dry_run:
        raise SystemExit("--dry-run 与 --apply 互斥（档案 §4）")
    if args.replace and not args.apply:
        raise SystemExit("--replace 必须与 --apply 一起使用（档案 §4）")
    if args.apply and args.skip_benchmark_rebuild:
        raise SystemExit(
            "--skip-benchmark-rebuild 不得与 --apply 同时使用："
            "正式 apply 必须同步重建并校验 industry_benchmarks（档案 §7.4）"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _validate_args(args)

    # 步骤 1：凭据注入（必须在导入 settings 之前，档案 §4/P1-3）
    env_file = _REPO_ROOT / ".env"
    _user, _password, database = resolve_database_env(args.database, env_file)

    # 步骤 2：此时才导入 settings
    from backend.app.core.config import settings

    if settings.MYSQL_DATABASE != args.database:
        raise SystemExit(
            f"配置顺序错误：settings.MYSQL_DATABASE={settings.MYSQL_DATABASE!r} "
            f"!= 目标库 {args.database!r}"
        )

    # 步骤 3：只读统计 / 接口探测（不写库）
    if args.report_only:
        return _report_only()

    if args.probe:
        return _probe()

    # 步骤 4：建连 + SELECT DATABASE() 守卫（run_pipeline 内再次双重确认）
    from sqlalchemy import create_engine

    from backend.app.application.services.industry_fill.constants import (
        DEFAULT_CACHE_DIR,
    )
    from backend.app.application.services.industry_fill.db import current_database
    from backend.app.application.services.industry_fill.guards import (
        verify_selected_database,
    )

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True)
    profile = masked_profile(
        settings.MYSQL_USER,
        settings.MYSQL_HOST,
        int(settings.MYSQL_PORT),
        settings.MYSQL_DATABASE,
    )
    log.info("数据库 profile: %s", profile)
    log.info("akshare 版本: %s", _akshare_version())
    log.info(
        "重试策略: max_retries=%d backoff=%ss", args.max_retries, args.backoff_seconds
    )
    verify_selected_database(current_database(engine), args.database)
    log.info("启动守卫通过：SELECT DATABASE()=%s ✓", args.database)

    # 步骤 5：provider 与 run 配置
    from backend.app.application.services.industry_fill.akshare_provider import (
        AkShareProvider,
        akshare_version,
    )
    from backend.app.application.services.industry_fill.normalizer import (
        mapping_version,
    )
    from backend.app.application.services.industry_fill.service import (
        RunConfig,
        run_pipeline,
    )

    provider = AkShareProvider(
        mapping_version=mapping_version(),
        dataset_version=settings.DATASET_VERSION,
    )
    provider_version = akshare_version() or "not-installed"

    # resume：复用既有 run 目录（元数据不匹配 fail-closed）
    if args.resume:
        resume_path = Path(args.resume)
        if resume_path.is_file():
            resume_path = resume_path.parent
        cache_root = resume_path.parent
        run_id = resume_path.name
    else:
        from backend.app.application.services.industry_fill.staging import new_run_id

        cache_root = Path(args.cache) if args.cache else Path(DEFAULT_CACHE_DIR)
        run_id = new_run_id()

    config = RunConfig(
        database=args.database,
        provider=provider,
        mapping_version=mapping_version(),
        dataset_version=settings.DATASET_VERSION,
        provider_version=provider_version,
        limit=args.limit,
        offset=args.offset,
        apply=args.apply,
        replace=args.replace,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
        retry_empty=args.retry_empty,
        cache_dir=cache_root,
        run_id=run_id,
        concurrency=args.concurrency,
        skip_benchmark_rebuild=args.skip_benchmark_rebuild,
        benchmark_rebuild_exe=str(
            _REPO_ROOT / "scripts" / "build_industry_benchmarks.py"
        ),
        mapping_csv_path=_REPO_ROOT / "data" / "processed" / "industry_mapping.csv",
    )

    # 步骤 6：执行链路
    from backend.app.application.services.industry_fill.report import (
        render_text,
        save_report,
    )

    result = None
    try:
        result = run_pipeline(
            engine,
            config,
            cli_args={
                "database": args.database,
                "limit": args.limit,
                "offset": args.offset,
                "apply": args.apply,
                "replace": args.replace,
                "max_retries": args.max_retries,
                "backoff_seconds": args.backoff_seconds,
                "provider": args.provider,
                "retry_empty": args.retry_empty,
            },
        )
    except RuntimeError as exc:
        # 门禁失败/resume 不匹配/基准重建失败等：失败即停，退出码 1（零写入由服务层保证）
        print(f"[FAIL] {exc}")
        return 1
    finally:
        # 异常路径同样释放连接池（复核整改：连续运行不遗留资源）
        engine.dispose()

    report = result.report
    mode = "apply" if args.apply else "dry-run"
    text = render_text(report, title=f"行业补全 {mode} 报告（库 {args.database}）")
    print(text)
    if result.run_dir is not None:
        saved = save_report(report, result.run_dir / "report.json")
        print(f"报告已保存: {saved}")
        print(f"staging 目录: {result.run_dir}")

    problems = report.get("gate_problems") or []
    if problems:
        print(f"[FAIL] 质量门禁失败 {len(problems)} 项，不得进入 apply")
        return 1
    if args.apply:
        print(
            "apply 完成。提醒：行业分位基准已重建（若未跳过）；"
            "请按档案 §9 复验覆盖率与来源分布。"
        )
    return 0


def _akshare_version() -> str:
    try:
        from importlib.metadata import version

        return version("akshare")
    except Exception:  # noqa: BLE001
        return "not-installed"


def _report_only() -> int:
    """只读覆盖率报告（档案批次 A：不修改数据库）。"""
    from sqlalchemy import create_engine

    from backend.app.core.config import settings
    from backend.app.application.services.industry_fill.db import (
        current_database,
        fetch_coverage_stats,
    )
    from backend.app.application.services.industry_fill.guards import (
        verify_selected_database,
    )

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url)
    try:
        verify_selected_database(current_database(engine), settings.MYSQL_DATABASE)
        stats = fetch_coverage_stats(engine)
    finally:
        engine.dispose()
    import json

    print("=== 行业覆盖率只读报告 ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _probe() -> int:
    """AkShare 接口探测（不连库）。"""
    import json

    from backend.app.application.services.industry_fill.akshare_provider import (
        AkShareProvider,
    )
    from backend.app.application.services.industry_fill.normalizer import (
        mapping_version,
    )

    provider = AkShareProvider(
        mapping_version=mapping_version(), dataset_version="probe"
    )
    info = provider.probe()
    print("=== AkShare 接口探测 ===")
    print(json.dumps(info, ensure_ascii=False, indent=2, default=str))
    if not info.get("endpoints"):
        print("[FAIL] 无可用接口，需先安装/修复 akshare")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
