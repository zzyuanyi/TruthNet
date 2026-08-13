#!/usr/bin/env python3
"""任务④：公司名称 + 公司类型回填脚本（Phase C 口径修正版）
============================================================
多源策略：
  Phase 1 (离线) — 公司类型回填：
      扫描 raw/4/ 全部三表 CSV（balance_sheet / income / cash_flow）的 comp_type_code，
      规范化 + 确定性仲裁（来源优先级 balance_sheet > income > cash_flow，再按最新报告期，
      冲突用确定性多数规则），仅回填 DB 中 comp_type_code 为 NULL 或非法（不在 1/2/3/4）
      的记录；单事务、可回滚、幂等（第二次执行更新数为 0）。
  Phase 2 (离线) — 公司名称回填：
      本地来源优先级 companies 历史版本 > research_reports.sec_name > 公告标题简称；
      低置信度不写入；不覆盖已有真实名称；绝不把 wind_code 当作名称。
  Phase 3 (在线) — akshare 逐只查询（仅显式 --online，默认不运行；CI 不运行）。

用法：
  python scripts/task4_name_backfill.py               # 离线名称 + 公司类型回填
  python scripts/task4_name_backfill.py --dry-run     # 只计算，不写数据库
  python scripts/task4_name_backfill.py --verify-only # 只输出覆盖统计
  python scripts/task4_name_backfill.py --online      # 离线完成后补在线名称

输出（data/processed/）:
  company_metadata_backfill_summary.json   回填摘要（统计）
  company_metadata_backfill_report.csv     更新明细
  company_metadata_conflicts.csv           类型/名称冲突清单
  company_metadata_missing.csv             本地无可靠来源的缺失清单
"""

import argparse
import csv as csv_mod
import io
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pymysql

# 仅作为脚本运行时重设 stdout 编码；作为模块导入（测试）时不劫持
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── 配置 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import settings  # noqa: E402

DB_CONFIG = {
    "host": settings.MYSQL_HOST,
    "port": settings.MYSQL_PORT,
    "user": settings.MYSQL_USER,
    "password": settings.MYSQL_PASSWORD,
    "database": settings.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "autocommit": False,
}
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc)

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "4"
# 来源优先级（数值越小越权威）
RAW_SOURCES = [
    ("balance_sheet", "asharebalancesheet_*.csv"),
    ("income", "ashareincome_*.csv"),
    ("cash_flow", "asharecashflow_*.csv"),
]
_SRC_RANK = {"balance_sheet": 0, "income": 1, "cash_flow": 2}

NAME_SOURCE_RANK = {
    "companies_history": 0,
    "research_reports": 1,
    "announcements": 2,
}

# 需要检查的数据来源表（名称/插入统计用）
DATA_TABLES = [
    "balance_sheet",
    "cash_flow",
    "income_statement",
    "top_shareholders",
    "announcements",
    "research_reports",
]

VALID_TYPES = (1, 2, 3, 4)


def log(msg: str) -> None:
    print(msg, flush=True)


def _now_str() -> str:
    return NOW.strftime("%Y-%m-%d %H:%M:%S")


# ====================================================================
# 规范化
# ====================================================================


def normalize_wind_code(raw) -> str | None:
    """wind_code 规范化：去空格、后缀大写、保留 .SH/.SZ/.BJ、拒绝非法代码."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if not s:
        return None
    if "." in s:
        num, suffix = s.rsplit(".", 1)
        if suffix in ("SH", "SZ", "BJ") and num.isdigit() and len(num) == 6:
            return f"{num}.{suffix}"
    return None


def normalize_comp_type(raw) -> int | None:
    """comp_type_code 规范化：允许 1/2/3/4 及 "1"、1.0 等安全转换；非法/未知 → None.

    禁止把 NULL、0、非法值默认转换为 1。
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        v = int(float(s))
    except (TypeError, ValueError):
        return None
    return v if v in VALID_TYPES else None


# ====================================================================
# Phase 1: 公司类型 — 扫描全部 raw CSV + 确定性仲裁
# ====================================================================


def scan_raw_comp_types() -> tuple[dict, dict]:
    """扫描全部三表 CSV，返回 (per_code, stats).

    per_code: wind_code -> {
        "rows": [(src_rank, report_period, normalized_type), ...],
        "candidate_types": set[int]  # 全部合法类型
    }
    """
    per_code: dict[str, dict] = {}
    stats = {
        "files": [],
        "total_rows": 0,
        "distinct_wind_code": 0,
    }
    for src_name, pattern in RAW_SOURCES:
        files = sorted(RAW_DIR.glob(pattern))
        if not files:
            log(f"  WARN: 未找到 {RAW_DIR}/{pattern}")
            continue
        stats["files"].extend(str(f.name) for f in files)
        rank = _SRC_RANK[src_name]
        for f in files:
            with open(f, encoding="utf-8-sig", newline="") as fh:
                reader = csv_mod.DictReader(fh)
                for r in reader:
                    stats["total_rows"] += 1
                    wc = normalize_wind_code(r.get("wind_code"))
                    if not wc:
                        continue
                    rp = (r.get("report_period") or "").strip()
                    ct = normalize_comp_type(r.get("comp_type_code"))
                    info = per_code.setdefault(
                        wc, {"rows": [], "candidate_types": set()}
                    )
                    info["rows"].append((rank, rp, ct))
                    if ct is not None:
                        info["candidate_types"].add(ct)
    stats["distinct_wind_code"] = len(per_code)
    return per_code, stats


def resolve_comp_type(rows: list) -> tuple[int | None, str, dict]:
    """确定性仲裁单公司类型.

    规则:
      1. 按 (来源优先级, 最新报告期) 取最优组；
      2. 组内合法类型多数决定；平票/无法确定 → 不写入（冲突）；
      3. selection_reason 记录仲裁路径。

    Returns:
        (selected_type, selection_reason, detail)
    """
    valid = [r for r in rows if r[2] in VALID_TYPES]
    if not valid:
        return None, "no_valid_type", {"candidates": []}
    ordered = sorted(valid, key=lambda x: (x[0], -(int(x[1]) if x[1].isdigit() else 0)))
    top_src, top_rp = ordered[0][0], ordered[0][1]
    group = [r[2] for r in ordered if r[0] == top_src and r[1] == top_rp]
    cnt = Counter(group)
    best_type, best_cnt = cnt.most_common(1)[0]
    total = len(group)
    if best_cnt > total / 2:
        reason = (
            f"source_priority={top_src};latest_period={top_rp};"
            f"majority={best_type}({best_cnt}/{total})"
        )
        return best_type, reason, {"group": sorted(cnt.items())}
    return None, "conflict_tie", {"group": sorted(cnt.items())}


def collect_type_decisions(per_code: dict) -> tuple[dict, list, dict]:
    """对全部公司执行仲裁，返回 (decisions, conflicts, stats).

    decisions: wind_code -> {type, reason, sources}
    """
    decisions: dict[str, dict] = {}
    conflicts: list[dict] = []
    stats = {"with_valid_type": 0, "conflicts": 0, "no_valid": 0}
    for wc, info in per_code.items():
        sel, reason, detail = resolve_comp_type(info["rows"])
        if sel is None:
            if reason == "conflict_tie":
                stats["conflicts"] += 1
                conflicts.append(
                    {
                        "wind_code": wc,
                        "candidate_types": sorted(
                            {t for t, _c in detail.get("group", []) if t in VALID_TYPES}
                        ),
                        "group_detail": detail.get("group"),
                        "selection_reason": reason,
                        "status": "CONFLICT",
                    }
                )
            else:
                stats["no_valid"] += 1
                conflicts.append(
                    {
                        "wind_code": wc,
                        "candidate_types": [],
                        "group_detail": detail.get("group"),
                        "selection_reason": reason,
                        "status": "NO_VALID",
                    }
                )
            continue
        stats["with_valid_type"] += 1
        decisions[wc] = {"type": sel, "reason": reason}
    return decisions, conflicts, stats


# ====================================================================
# 公司类型写库计划（只回填 NULL / 非法）
# ====================================================================


def plan_type_updates(conn, decisions: dict) -> tuple[list[dict], list[dict]]:
    """规划类型更新：仅回填 DB 中 comp_type_code 为 NULL 或非法（不在 1/2/3/4）的公司.

    Returns:
        (updates, skips): updates 计划执行；skips 为已有有效类型但 raw 决议不同（记录不覆盖）。
    """
    updates: list[dict] = []
    skips: list[dict] = []
    cur = conn.cursor()
    cur.execute("SELECT wind_code, comp_type_code FROM companies WHERE is_latest = 1")
    for wc, dbct in cur.fetchall():
        if wc not in decisions:
            continue
        resolved = decisions[wc]["type"]
        if dbct is None or dbct not in VALID_TYPES:
            updates.append(
                {
                    "wind_code": wc,
                    "old_type": dbct,
                    "new_type": resolved,
                    "reason": decisions[wc]["reason"],
                }
            )
        elif dbct != resolved:
            # 已有有效类型但与 raw 决议不同 → 不自动覆盖，记入报告
            skips.append(
                {
                    "wind_code": wc,
                    "old_type": dbct,
                    "raw_type": resolved,
                    "reason": "existing_valid_type_not_overwritten",
                }
            )
    return updates, skips


# ====================================================================
# Phase 2: 公司名称 — 离线本地来源
# ====================================================================


def build_name_map_from_companies_history(conn) -> dict[str, str]:
    """companies 历史有效版本中的真实 sec_name（排除 is_latest=1 且名称=代码的占位）。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT wind_code, sec_name FROM companies "
        "WHERE sec_name IS NOT NULL "
        "AND TRIM(sec_name) <> '' "
        "AND sec_name <> wind_code "
        "AND is_latest = 1"
    )
    rows = cur.fetchall()
    # 最新版本优先（同代码多版本取 is_latest 版本）
    name_map: dict[str, str] = {}
    for wc, name in rows:
        if wc and wc not in name_map and name and name.strip():
            name_map[wc] = name.strip()
    return name_map


def build_name_map_from_reports(conn) -> dict[str, str]:
    """research_reports.sec_name — 取每代码最常出现且非占位的名称。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT wind_code, sec_name, COUNT(*) AS cnt "
        "FROM research_reports "
        "WHERE sec_name IS NOT NULL AND TRIM(sec_name) <> '' "
        "GROUP BY wind_code, sec_name "
        "ORDER BY wind_code, cnt DESC"
    )
    rows = cur.fetchall()
    name_map: dict[str, str] = {}
    for wc, name, _cnt in rows:
        if wc not in name_map and name and name.strip():
            candidate = name.strip()
            # 低置信度清洗：名称不能等于代码，不能过短
            if candidate == wc or len(candidate) < 2:
                continue
            name_map[wc] = candidate
    return name_map


def build_name_map_from_announcements(conn) -> dict[str, str]:
    """公告标题 '公司简称:...' 前缀提取 — 清洗非公司名片段.

    保留 ST / *ST 等有意义标记；对每代码取全部标题前缀的多数决定（mode）。
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT wind_code, n_info_title FROM announcements "
        "WHERE n_info_title IS NOT NULL AND LENGTH(TRIM(n_info_title)) > 0"
    )
    rows = cur.fetchall()
    per_code_prefixes: dict[str, list[str]] = defaultdict(list)
    for wc, title in rows:
        if not wc or not title:
            continue
        short = str(title).split(":", 1)[0].strip()
        # 低置信度过滤：仅保留像公司简称的片段（2-12 字，中文/字母数字/*，不含停用词）
        if (
            2 <= len(short) <= 12
            and re.fullmatch(r"[一-鿿A-Za-z0-9*]+", short)
            and not re.search(
                r"(公告|报告|提示|关于|召开|审计|独立|监事会|董事会|股东|股票|交易|提示性)",
                short,
            )
        ):
            per_code_prefixes[wc].append(short)
    name_map: dict[str, str] = {}
    for wc, prefixes in per_code_prefixes.items():
        cnt = Counter(prefixes)
        # 多数决定；平票时取最长（更具体），仍平票取最短合理简称
        name_map[wc] = sorted(cnt.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[
            0
        ][0]
    return name_map


def collect_name_candidates(conn) -> tuple[dict, dict]:
    """合并各本地名称来源（按优先级），返回 (candidates, source_stats).

    candidates: wind_code -> {"name": str, "source": str, "confidence": str}
    """
    source_maps = {
        "companies_history": build_name_map_from_companies_history(conn),
        "research_reports": build_name_map_from_reports(conn),
        "announcements": build_name_map_from_announcements(conn),
    }
    source_stats = {k: len(v) for k, v in source_maps.items()}
    candidates: dict[str, dict] = {}
    for src in sorted(source_maps, key=lambda s: NAME_SOURCE_RANK[s]):
        for wc, name in source_maps[src].items():
            if wc not in candidates:
                candidates[wc] = {
                    "name": name,
                    "source": src,
                    "confidence": "high" if src == "companies_history" else "medium",
                }
    return candidates, source_stats


def plan_name_updates(conn, candidates: dict) -> tuple[list[dict], list[dict]]:
    """规划名称更新：缺失定义 = NULL / "" / 仅空白 / == wind_code.

    只更新缺失公司；已有真实名称不覆盖。
    Returns:
        (updates, skipped_low_confidence)
    """
    updates: list[dict] = []
    skipped: list[dict] = []
    cur = conn.cursor()
    cur.execute("SELECT wind_code, sec_name FROM companies WHERE is_latest = 1")
    for wc, cur_name in cur.fetchall():
        missing = (
            cur_name is None
            or str(cur_name).strip() == ""
            or str(cur_name).strip() == wc
        )
        if not missing:
            continue
        cand = candidates.get(wc)
        if not cand or not cand.get("name"):
            skipped.append(
                {"wind_code": wc, "old_name": cur_name, "reason": "no_local_source"}
            )
            continue
        updates.append(
            {
                "wind_code": wc,
                "old_name": cur_name,
                "new_name": cand["name"],
                "source": cand["source"],
                "confidence": cand["confidence"],
            }
        )
    return updates, skipped


# ====================================================================
# 写库（单事务 + rollback + 幂等）
# ====================================================================


def apply_type_updates(conn, updates: list[dict]) -> int:
    """批量更新 comp_type_code（单事务）。返回更新行数。"""
    if not updates:
        return 0
    cur = conn.cursor()
    updated = 0
    for u in updates:
        cur.execute(
            "UPDATE companies SET comp_type_code = %s, updated_at = %s "
            "WHERE wind_code = %s AND is_latest = 1",
            (u["new_type"], _now_str(), u["wind_code"]),
        )
        updated += cur.rowcount
    return updated


def apply_name_updates(conn, updates: list[dict]) -> int:
    """批量更新 sec_name（单事务）。返回更新行数。"""
    if not updates:
        return 0
    cur = conn.cursor()
    updated = 0
    for u in updates:
        cur.execute(
            "UPDATE companies SET sec_name = %s, updated_at = %s "
            "WHERE wind_code = %s AND is_latest = 1",
            (u["new_name"], _now_str(), u["wind_code"]),
        )
        updated += cur.rowcount
    return updated


# ====================================================================
# 报告
# ====================================================================


def write_reports(
    summary: dict,
    report_rows: list[dict],
    conflicts: list[dict],
    missing: list[dict],
) -> None:
    """输出 4 个报告文件（UTF-8，字段稳定，无密码/连接串）。"""
    summary_path = OUTPUT_DIR / "company_metadata_backfill_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    if report_rows:
        pd.DataFrame(report_rows).to_csv(
            OUTPUT_DIR / "company_metadata_backfill_report.csv",
            index=False,
            encoding="utf-8-sig",
        )
    if conflicts:
        pd.DataFrame(conflicts).to_csv(
            OUTPUT_DIR / "company_metadata_conflicts.csv",
            index=False,
            encoding="utf-8-sig",
        )
    else:
        (OUTPUT_DIR / "company_metadata_conflicts.csv").write_text(
            "wind_code,candidate_types,selection_reason,status\n",
            encoding="utf-8",
            newline="\n",
        )
    if missing:
        pd.DataFrame(missing).to_csv(
            OUTPUT_DIR / "company_metadata_missing.csv",
            index=False,
            encoding="utf-8-sig",
        )
    else:
        (OUTPUT_DIR / "company_metadata_missing.csv").write_text(
            "wind_code,kind,reason\n", encoding="utf-8", newline="\n"
        )
    log(f"  摘要: {summary_path}")
    log(f"  报告: {OUTPUT_DIR / 'company_metadata_backfill_report.csv'}")
    log(f"  冲突: {OUTPUT_DIR / 'company_metadata_conflicts.csv'}")
    log(f"  缺失: {OUTPUT_DIR / 'company_metadata_missing.csv'}")


# ====================================================================
# 验证 / 统计
# ====================================================================


def collect_companies_stats(conn) -> dict:
    """companies 名称/类型缺失统计（is_latest=1）。"""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM companies WHERE is_latest = 1")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM companies WHERE is_latest = 1 AND "
        "(sec_name IS NULL OR TRIM(sec_name) = '' OR sec_name = wind_code)"
    )
    missing_name = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM companies WHERE is_latest = 1 AND "
        "(comp_type_code IS NULL OR comp_type_code NOT IN (1,2,3,4))"
    )
    missing_or_invalid_type = cur.fetchone()[0]
    cur.execute(
        "SELECT comp_type_code, COUNT(*) FROM companies WHERE is_latest = 1 "
        "GROUP BY comp_type_code ORDER BY comp_type_code"
    )
    type_dist = {str(k): v for k, v in cur.fetchall()}
    return {
        "latest_company_count": total,
        "missing_name": missing_name,
        "missing_or_invalid_type": missing_or_invalid_type,
        "comp_type_code_distribution": type_dist,
    }


def verify(conn) -> dict:
    """输出回填后覆盖统计。"""
    return collect_companies_stats(conn)


# ====================================================================
# 在线补名（P2，仅 --online）
# ====================================================================


def query_akshare_batch(codes: list[str]) -> dict[str, str | None]:
    """多源在线名称查询（默认不运行）。网络失败不回滚离线结果。"""
    import requests

    try:
        import akshare as ak
    except ImportError:
        log("  akshare not installed, skipping online phase")
        return {}

    results: dict[str, str | None] = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        df = ak.stock_info_a_code_name()
        name_map = {}
        for _, row in df.iterrows():
            code = str(row["code"]).strip()
            name = str(row["name"]).strip()
            if code and name:
                name_map[code] = name
        log(f"  akshare: {len(name_map)} stocks")
        for wc in codes:
            num = wc.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            name = name_map.get(num)
            if name:
                results[wc] = name
    except (ImportError, OSError) as e:
        log(f"  akshare: FAILED ({e})")

    remaining = [c for c in codes if c not in results]
    for wc in remaining:
        if ".BJ" in wc:
            continue
        num = wc.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        prefix = "sh" if ".SH" in wc else "sz"
        try:
            r = requests.get(
                f"https://hq.sinajs.cn/list={prefix}{num}",
                headers=headers,
                timeout=10,
            )
            data = r.text.strip()
            if data and '="' in data and "," in data:
                name = data.split('="')[1].split(",")[0].strip()
                if name and name not in ("", ";"):
                    results[wc] = name
        except (requests.RequestException, OSError):
            pass
    for c in codes:
        results.setdefault(c, None)
    return results


# ====================================================================
# Main
# ====================================================================


def _conn():
    return pymysql.connect(**DB_CONFIG)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只计算，不写数据库")
    ap.add_argument("--verify-only", action="store_true", help="只输出覆盖统计")
    ap.add_argument("--online", action="store_true", help="离线完成后补在线名称")
    args = ap.parse_args(argv)

    t0 = time.time()
    log(f"Task 4: Company Metadata Backfill [{_now_str()}]")
    log(
        f"Mode: {'DRY-RUN' if args.dry_run else 'WRITE'} "
        f"| verify_only={args.verify_only} | online={args.online}"
    )
    log(f"DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    conn = _conn()

    # ── 基线统计 ──
    baseline = collect_companies_stats(conn)
    log(
        f"  baseline: total={baseline['latest_company_count']} "
        f"missing_name={baseline['missing_name']} "
        f"missing_or_invalid_type={baseline['missing_or_invalid_type']}"
    )

    if args.verify_only:
        log("== verify-only ==")
        stats = verify(conn)
        for k, v in stats.items():
            log(f"  {k}: {v}")
        conn.close()
        return 0

    # ── Phase 1: 类型仲裁 ──
    log("=" * 60)
    log("Phase 1: Offline — comp_type_code from raw 3-table CSV")
    log("=" * 60)
    per_code, scan_stats = scan_raw_comp_types()
    log(f"  文件: {scan_stats['files']}")
    log(
        f"  扫描行: {scan_stats['total_rows']} | distinct wind_code: {scan_stats['distinct_wind_code']}"
    )
    decisions, type_conflicts, type_arb_stats = collect_type_decisions(per_code)
    log(
        f"  可确定类型: {type_arb_stats['with_valid_type']} | "
        f"冲突/无法确定: {type_arb_stats['conflicts'] + type_arb_stats['no_valid']}"
    )

    type_updates, type_skips = plan_type_updates(conn, decisions)
    log(f"  类型待更新: {len(type_updates)} | 已有有效类型不覆盖: {len(type_skips)}")

    # ── Phase 2: 名称候选 ──
    log("=" * 60)
    log("Phase 2: Offline — sec_name from local sources")
    log("=" * 60)
    candidates, source_stats = collect_name_candidates(conn)
    log(
        f"  名称候选: companies_history={source_stats['companies_history']} "
        f"reports={source_stats['research_reports']} "
        f"announcements={source_stats['announcements']} | 合并唯一={len(candidates)}"
    )

    name_updates, name_skips = plan_name_updates(conn, candidates)
    log(f"  名称待更新: {len(name_updates)} | 低置信度/无来源跳过: {len(name_skips)}")

    # ── Phase 3: 在线（仅 --online）──
    online_phase_run = False
    online_updated = 0
    if args.online:
        online_phase_run = True
        missing_codes = [s["wind_code"] for s in name_skips]
        if missing_codes:
            online_results = query_akshare_batch(missing_codes)
            online_plan = [
                {
                    "wind_code": wc,
                    "old_name": None,
                    "new_name": nm,
                    "source": "online",
                    "confidence": "medium",
                }
                for wc, nm in online_results.items()
                if nm
            ]
            log(f"  在线候选: {len(online_plan)}")
            if not args.dry_run:
                online_updated = apply_name_updates(conn, online_plan)
        else:
            log("  无缺失名称需要在线补全")

    # ── 写库（单事务）──
    type_updated = 0
    name_updated = 0
    if args.dry_run:
        log(
            "\nDRY-RUN: 不写数据库。类型更新=%d 名称更新=%d"
            % (len(type_updates), len(name_updates))
        )
    else:
        try:
            type_updated = apply_type_updates(conn, type_updates)
            name_updated = apply_name_updates(conn, name_updates)
            conn.commit()
            log(
                f"\n  事务提交: type_updated={type_updated} name_updated={name_updated} "
                f"online_updated={online_updated}"
            )
        except Exception:
            conn.rollback()
            log("\n  ERROR: 事务回滚，未写入任何变更")
            raise

    # ── 写库后统计与缺失清单（conn 仍打开）──
    post_stats = baseline
    if not args.dry_run:
        post_stats = collect_companies_stats(conn)

    missing = [
        {
            "wind_code": s["wind_code"],
            "kind": "sec_name",
            "reason": s.get("reason", "no_local_source"),
        }
        for s in name_skips
        if s.get("reason") == "no_local_source"
    ]
    missing += [
        {
            "wind_code": s["wind_code"],
            "kind": "comp_type",
            "reason": "no_valid_type_in_raw",
        }
        for s in type_skips
    ]
    # raw 中存在但无法确定类型（冲突/无有效类型）
    for wc in per_code:
        if wc not in decisions:
            missing.append(
                {"wind_code": wc, "kind": "comp_type", "reason": "no_type_in_raw"}
            )
    # DB 中 NULL/非法类型且 raw 无来源（如退市/境外/BJ 股，不在三表内）
    if not args.dry_run:
        cur = conn.cursor()
        cur.execute(
            "SELECT wind_code FROM companies WHERE is_latest = 1 AND "
            "(comp_type_code IS NULL OR comp_type_code NOT IN (1,2,3,4))"
        )
        for (wc,) in cur.fetchall():
            if wc not in decisions:
                missing.append(
                    {"wind_code": wc, "kind": "comp_type", "reason": "no_type_in_raw"}
                )
    # 去重（保持顺序）
    seen_missing: set[tuple[str, str]] = set()
    deduped_missing: list[dict] = []
    for m in missing:
        key = (m["wind_code"], m["kind"])
        if key not in seen_missing:
            seen_missing.add(key)
            deduped_missing.append(m)
    missing = deduped_missing

    # ── 报告 ──
    report_rows: list[dict] = []
    for u in type_updates:
        report_rows.append(
            {
                "wind_code": u["wind_code"],
                "kind": "comp_type",
                "old": u["old_type"],
                "new": u["new_type"],
                "reason": u["reason"],
                "status": "APPLIED" if not args.dry_run else "DRY-RUN",
            }
        )
    for u in name_updates:
        report_rows.append(
            {
                "wind_code": u["wind_code"],
                "kind": "sec_name",
                "old": u["old_name"],
                "new": u["new_name"],
                "reason": f"source={u['source']}",
                "status": "APPLIED" if not args.dry_run else "DRY-RUN",
            }
        )

    if not args.dry_run:
        conn.close()

    summary = {
        "status": "dry_run" if args.dry_run else "applied",
        "generated_at": _now_str(),
        "baseline": baseline,
        "type": {
            "raw_source_covered": type_arb_stats["with_valid_type"],
            "planned_updates": len(type_updates),
            "applied_updates": type_updated if not args.dry_run else None,
            "conflicts": len(type_conflicts),
            "existing_valid_not_overwritten": len(type_skips),
        },
        "name": {
            "offline_candidates": len(candidates),
            "planned_updates": len(name_updates),
            "applied_updates": name_updated if not args.dry_run else None,
            "low_confidence_skipped": len(name_skips),
        },
        "online": {
            "phase_run": online_phase_run,
            "applied_updates": online_updated if not args.dry_run else None,
        },
        "post": post_stats,
    }
    write_reports(summary, report_rows, type_conflicts, missing)

    log(f"\nTotal time: {(time.time() - t0):.1f}s")
    log(
        f"Done. type_updates={len(type_updates)} name_updates={len(name_updates)} "
        f"(second run should be 0/0 for idempotency)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
