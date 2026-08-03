#!/usr/bin/env python
"""公告覆盖 Gate 报告 — Phase C 数据任务 8.

统计 announcements 真实覆盖情况，输出：
  - docs/reports/ANNOUNCEMENT_COVERAGE_PHASE_C.md
  - data/processed/announcement_coverage.json

验收（开发手册 数据任务 8）:
  - 覆盖公司数 / 公告总记录数 / 最早最晚日期
  - 每家公司公告数 / Top 10 公司
  - 无公告公司数
  - 康美/茅台/平安覆盖状态
  - 至少一家公告>=10 的专项验收公司（如 603377.SH 36 条）及真实公告数量

用法:
    python scripts/report_announcement_coverage.py --dry-run
    python scripts/report_announcement_coverage.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402

# 专项验收公司（公告>=10 候选）
TARGET_COMPANIES = ["600518.SH", "600519.SH", "601318.SH"]  # 康美/茅台/平安
MIN_ANNOUNCEMENTS = 10


def _engine():
    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
    else:
        url = f"sqlite:///{settings.SQLITE_PATH}"
    return create_engine(url, pool_pre_ping=True)


def build_coverage(engine) -> dict:
    with engine.connect() as conn:
        total_records = conn.execute(
            text("SELECT COUNT(*) FROM announcements")
        ).scalar()
        covered_companies = conn.execute(
            text("SELECT COUNT(DISTINCT wind_code) FROM announcements")
        ).scalar()
        min_dt = conn.execute(text("SELECT MIN(ann_dt) FROM announcements")).scalar()
        max_dt = conn.execute(text("SELECT MAX(ann_dt) FROM announcements")).scalar()

        # 每家公司公告数
        rows = conn.execute(
            text(
                "SELECT wind_code, COUNT(*) AS cnt FROM announcements "
                "WHERE is_latest = 1 GROUP BY wind_code ORDER BY cnt DESC"
            )
        ).fetchall()
        top10 = rows[:10]

        # 无公告公司数（companies 全量 - 有公告公司）
        total_companies = conn.execute(
            text("SELECT COUNT(*) FROM companies WHERE is_latest = 1")
        ).scalar()
        no_announcement = total_companies - covered_companies

        # 目标公司覆盖状态
        target_status = {}
        for code in TARGET_COMPANIES:
            cnt = conn.execute(
                text("SELECT COUNT(*) FROM announcements WHERE wind_code = :c"),
                {"c": code},
            ).scalar()
            target_status[code] = cnt

        # 专项验收公司：公告>=10 且公告数最多的公司
        candidates = [r for r in rows if r[1] >= MIN_ANNOUNCEMENTS]
        acceptance = (
            {"wind_code": candidates[0][0], "announcements": candidates[0][1]}
            if candidates
            else None
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": settings.DATASET_VERSION or "competition-2026",
        "covered_companies": covered_companies,
        "total_announcements": total_records,
        "earliest_date": min_dt,
        "latest_date": max_dt,
        "companies_without_announcements": no_announcement,
        "total_companies": total_companies,
        "top10": [{"wind_code": r[0], "announcements": r[1]} for r in top10],
        "target_companies": {k: {"announcements": v} for k, v in target_status.items()},
        "acceptance_company": acceptance,
        "companies_with_ge10": len(candidates),
    }


def _md(coverage: dict) -> str:
    t = coverage
    lines = [
        "# TruthNet · 公告覆盖报告 — Phase C",
        "",
        f"> 生成时间: {t['generated_at']} | 数据集版本: {t['dataset_version']}",
        "> 数据来源: MySQL `announcements` 表实测（非历史报告数字）",
        "",
        "## 覆盖总览",
        "",
        f"- 覆盖公司数: **{t['covered_companies']}**",
        f"- 公告总记录数: **{t['total_announcements']}**",
        f"- 最早公告日期: **{t['earliest_date']}**",
        f"- 最晚公告日期: **{t['latest_date']}**",
        f"- 公司总数: {t['total_companies']}",
        f"- 无公告公司数: **{t['companies_without_announcements']}**",
        f"- 公告数 >= {MIN_ANNOUNCEMENTS} 的公司数: {t['companies_with_ge10']}",
        "",
        "## Top 10 公司（按公告数）",
        "",
        "| 排名 | 公司 | 公告数 |",
        "|---:|---|---:|",
    ]
    for i, c in enumerate(t["top10"], 1):
        lines.append(f"| {i} | {c['wind_code']} | {c['announcements']} |")

    lines += [
        "",
        "## 目标公司覆盖状态",
        "",
        "| 公司 | 公告数 | 状态 |",
        "|---|---:|---|",
    ]
    for code, st in t["target_companies"].items():
        cnt = st["announcements"]
        state = "无公告 → NO_ANNOUNCEMENT_DATA" if cnt == 0 else f"有公告 {cnt} 条"
        lines.append(f"| {code} | {cnt} | {state} |")

    lines += [
        "",
        "## 专项验收公司",
        "",
    ]
    if t["acceptance_company"]:
        a = t["acceptance_company"]
        lines += [
            f"- **验收公司**: `{a['wind_code']}`",
            f"- **公告数量**: {a['announcements']} 条",
            "- **用途**: 作为事件 Skill（后端任务 2/10）专项验收对象，须产生 >= 3 个真实事件簇",
        ]
    else:
        lines.append("- 无公告 >= 10 条的公司，无法完成事件专项验收")

    lines += [
        "",
        "## 康美/茅台/平安无公告处理方案",
        "",
        "三者在 MySQL announcements 中均无公告记录。按 Phase C 方案：",
        "- 返回空时间线 + `NO_ANNOUNCEMENT_DATA` warning + 数据覆盖说明",
        "- **不 Mock、不补数据**",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="公告覆盖 Gate 报告")
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
    args = parser.parse_args()

    engine = _engine()
    coverage = build_coverage(engine)

    print(
        f"覆盖公司 {coverage['covered_companies']} | 公告 {coverage['total_announcements']} 条 "
        f"| 日期 {coverage['earliest_date']} ~ {coverage['latest_date']} "
        f"| 无公告 {coverage['companies_without_announcements']} 家"
    )
    if coverage["acceptance_company"]:
        a = coverage["acceptance_company"]
        print(f"专项验收公司: {a['wind_code']}（{a['announcements']} 条公告）")
    else:
        print("警告: 无公告 >= 10 条的公司")

    if args.dry_run:
        print("dry-run 完成，未写文件。")
        return 0

    out_dir = Path("docs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ANNOUNCEMENT_COVERAGE_PHASE_C.md").write_text(
        _md(coverage), encoding="utf-8", newline="\n"
    )
    proc_dir = Path("data/processed")
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "announcement_coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print("已写入 docs/reports/ANNOUNCEMENT_COVERAGE_PHASE_C.md")
    print("已写入 data/processed/announcement_coverage.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
