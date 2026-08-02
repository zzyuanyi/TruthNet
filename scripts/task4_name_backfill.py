"""任务④：公司名称 + 公司类型回填脚本
====================================
多源策略：
  Phase 1 (离线) — 从 MySQL research_reports + announcements 公告标题前缀
                  提取 wind_code → sec_name 映射，直接补齐
  Phase 2 (离线) — 从 raw 资产负债表 CSV 回填 companies.comp_type_code
  Phase 3 (在线) — 用 akshare 逐只查询（需网络，单独执行 --online）

Phase C 集成修正:
  - collect_missing_codes 将 sec_name == wind_code 视为缺失（否则 3460 家
    被误判为已命名）；
  - 新增公告标题简称提取（n_info_title '公司简称:' 前缀）；
  - 新增 comp_type_code 回填（raw/4/*.csv 数据源）；
  - DB 连接改为 app.core.config.settings（禁止硬编码凭据）。

用法：
  python scripts/task4_name_backfill.py           # 仅离线（研报+公告+类型）
  python scripts/task4_name_backfill.py --online  # 离线 + akshare 在线补全

输出: data/processed/name_backfill_report.csv（补名记录）
"""

import io
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pymysql

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
}
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc)

# 需要检查的数据来源表
DATA_TABLES = [
    "balance_sheet",
    "cash_flow",
    "income_statement",
    "top_shareholders",
    "announcements",
    "research_reports",
]

BATCH_INTERVAL = 50


def log(msg: str) -> None:
    print(msg, flush=True)


# ====================================================================
# Phase 1: 离线 — 从研报表提取名称
# ====================================================================


def build_name_map_from_reports() -> dict[str, str]:
    """从 research_reports 表提取 wind_code → sec_name 映射.

    取每个 wind_code 最常出现的 sec_name（处理同一股票多份研报的情况）。
    """
    log("=" * 60)
    log("Phase 1: Offline — build name map from research_reports")
    log("=" * 60)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        SELECT wind_code, sec_name, COUNT(*) AS cnt
        FROM research_reports
        WHERE sec_name IS NOT NULL AND sec_name != ''
        GROUP BY wind_code, sec_name
        ORDER BY wind_code, cnt DESC
    """)
    rows = cur.fetchall()
    conn.close()

    name_map: dict[str, str] = {}
    for wind_code, sec_name, _cnt in rows:
        if wind_code not in name_map and sec_name.strip():
            name_map[wind_code] = sec_name.strip()

    log(f"  Unique wind_codes with names: {len(name_map)}")
    return name_map


def build_name_map_from_announcements() -> dict[str, str]:
    """从 announcements.n_info_title 提取 wind_code → 简称 映射.

    公告标题格式为 '公司简称:公告标题...'，取冒号前片段作为公司简称。
    """
    log("=" * 60)
    log("Phase 1b: Offline — name map from announcement titles")
    log("=" * 60)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT wind_code, n_info_title FROM announcements "
        "WHERE n_info_title IS NOT NULL AND LENGTH(n_info_title) > 0"
    )
    rows = cur.fetchall()
    conn.close()

    name_map: dict[str, str] = {}
    for wind_code, title in rows:
        if wind_code in name_map or not title:
            continue
        short = str(title).split(":", 1)[0].strip()
        if 2 <= len(short) <= 10 and re.fullmatch(r"[一-鿿A-Za-z0-9]+", short):
            name_map[wind_code] = short

    log(f"  Unique wind_codes with announcement names: {len(name_map)}")
    return name_map


def backfill_comp_type_from_raw() -> int:
    """从 raw 资产负债表 CSV 回填 companies.comp_type_code.

    原始数据源: data/raw/4/asharebalancesheet_*.csv（含 comp_type_code 列）。
    MySQL balance_sheet 未导入该列，故直接读 CSV。
    """
    log("=" * 60)
    log("Phase 2: Offline — backfill comp_type_code from raw balance sheet CSV")
    log("=" * 60)

    raw_dir = PROJECT_ROOT / "data" / "raw" / "4"
    csv_files = sorted(raw_dir.glob("asharebalancesheet_*.csv"))
    if not csv_files:
        log(f"  WARN: 未找到 {raw_dir}/asharebalancesheet_*.csv")
        return 0

    df = pd.read_csv(
        csv_files[0], low_memory=False, usecols=["wind_code", "comp_type_code"]
    )
    comp = df.dropna(subset=["comp_type_code"]).drop_duplicates(subset="wind_code")
    log(f"  CSV comp_type 记录: {len(comp)}")

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    updated = 0
    for _, r in comp.iterrows():
        cur.execute(
            "UPDATE companies SET comp_type_code = %s "
            "WHERE wind_code = %s AND (comp_type_code IS NULL OR comp_type_code = 0)",
            (int(r["comp_type_code"]), r["wind_code"]),
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    log(f"  comp_type_code 回填: {updated}")
    return updated


# ====================================================================
# Phase 3: 在线 — akshare 查询
# ====================================================================


def query_akshare_batch(codes: list[str]) -> dict[str, str | None]:
    """多源名称查询：akshare 全量 + 新浪财经 + 腾讯财经.

    优先顺序:
      1. akshare stock_info_a_code_name() — 沪深京全量（走 BSE 官网，稳定）
      2. 新浪财经 hq.sinajs.cn — 沪深（cURL 稳定）
      3. 腾讯财经 qt.gtimg.cn nq 前缀 — 新三板/北交所老代码
    """
    import requests

    try:
        import akshare as ak
    except ImportError:
        log("  akshare not installed, skipping online phase")
        return {}

    log("\n" + "=" * 60)
    log("Phase 2: Online — multi-source name lookup")
    log("=" * 60)

    results: dict[str, str | None] = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # ── Source 1: akshare 全量列表 ──
    t0 = time.time()
    name_map: dict[str, str] = {}
    try:
        df = ak.stock_info_a_code_name()
        for _, row in df.iterrows():
            code = str(row["code"]).strip()
            name = str(row["name"]).strip()
            if code and name:
                name_map[code] = name
        log(f"  akshare: {len(name_map)} stocks ({time.time()-t0:.1f}s)")
    except (ImportError, OSError) as e:
        log(f"  akshare: FAILED ({e})")

    for wind_code in codes:
        if wind_code in results:
            continue
        num = wind_code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        name = name_map.get(num)
        if name:
            results[wind_code] = name

    akshare_hit = len(results)
    log(f"  akshare matched: {akshare_hit}/{len(codes)}")

    # ── Source 2: 新浪财经（沪深）──
    remaining = [c for c in codes if c not in results]
    sina_hit = 0
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
                if name and name != "" and name != ";":
                    results[wc] = name
                    sina_hit += 1
        except (requests.RequestException, OSError):
            pass  # network issue, skip this source
    log(f"  Sina matched: {sina_hit}")

    # ── Source 3: 腾讯财经（新三板/北交所老代码）──
    remaining = [c for c in codes if c not in results]
    tencent_hit = 0
    for wc in remaining:
        num = wc.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        # 优先 nq (新三板) 前缀
        for prefix in ("nq", "sz", "sh"):
            try:
                r = requests.get(
                    f"https://qt.gtimg.cn/q={prefix}{num}",
                    headers=headers,
                    timeout=10,
                )
                data = r.text.strip()
                if data and "~" in data and "none" not in data.lower():
                    parts = data.split("~")
                    if len(parts) > 1:
                        name = parts[1].strip()
                        if name and name != "" and name != "-":
                            # 去掉退市前缀标记
                            import re

                            name = re.sub(r"^无效", "", name) or name
                            results[wc] = name
                            tencent_hit += 1
                            break
            except (requests.RequestException, OSError):
                pass  # network issue
    log(f"  Tencent matched: {tencent_hit}")

    # assign None for unmatched
    for c in codes:
        if c not in results:
            results[c] = None

    total_hit = sum(1 for v in results.values() if v)
    log(f"  Total online: {total_hit}/{len(codes)}")
    return results


# ====================================================================
# 收集 & 写回
# ====================================================================


def collect_missing_codes() -> tuple[list[str], list[str]]:
    """收集需要补全的 wind_code: (to_update, to_insert)."""
    log("\n" + "=" * 60)
    log("Step: Collect wind_codes needing backfill")
    log("=" * 60)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 缺失 = NULL/空串/仍为股票代码（sec_name == wind_code 视为未回填）
    cur.execute(
        "SELECT wind_code FROM companies "
        "WHERE sec_name IS NULL OR sec_name = '' OR sec_name = wind_code"
    )
    to_update = list({row[0] for row in cur.fetchall()})
    log(f"  Missing sec_name in companies: {len(to_update)}")

    union_q = " UNION ".join(
        f"SELECT DISTINCT wind_code FROM `{t}`" for t in DATA_TABLES
    )
    cur.execute(f"""
        SELECT DISTINCT src.wind_code FROM ({union_q}) src
        LEFT JOIN companies c ON src.wind_code = c.wind_code
        WHERE c.wind_code IS NULL
    """)
    to_insert = list({row[0] for row in cur.fetchall()})
    log(f"  wind_codes NOT in companies:  {len(to_insert)}")

    conn.close()
    log(f"  Total: {len(to_update) + len(to_insert)}")
    return to_update, to_insert


def write_back(results: dict[str, str | None]) -> dict:
    """将名称写回 companies 表（UPDATE 已有 / INSERT 新增）."""
    log("\n" + "=" * 60)
    log("Step: Write back to MySQL")
    log("=" * 60)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    stats = {"updated": 0, "inserted": 0, "skipped": 0}
    report: list[dict] = []

    for code, name in sorted(results.items()):
        if not name:
            stats["skipped"] += 1
            report.append({"wind_code": code, "name": None, "action": "SKIPPED"})
            continue

        # 检查 wind_code 是否已存在
        cur.execute("SELECT entity_id FROM companies WHERE wind_code = %s", (code,))
        existing = cur.fetchone()

        if existing:
            cur.execute(
                "UPDATE companies SET sec_name = %s, updated_at = %s WHERE wind_code = %s",
                (name, NOW.strftime("%Y-%m-%d %H:%M:%S"), code),
            )
            stats["updated"] += 1
            report.append({"wind_code": code, "name": name, "action": "UPDATE"})
        else:
            # 生成 entity_id — 优先纯数字，冲突时带交易所后缀
            base_id = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            exc_map = {".SZ": "XSHE", ".SH": "XSHG", ".BJ": "XBJ"}
            exchange_code = None
            for s, e in exc_map.items():
                if s in code:
                    exchange_code = e
                    break

            # 检查 entity_id 是否被其他 wind_code 占用
            cur.execute(
                "SELECT wind_code FROM companies WHERE entity_id = %s", (base_id,)
            )
            collision = cur.fetchone()
            entity_id = base_id
            if collision and collision[0] != code:
                # 冲突：加交易所后缀
                suffix = code.split(".")[-1] if "." in code else "XX"
                entity_id = f"{base_id}_{suffix}"

            cur.execute(
                """INSERT INTO companies
                   (entity_id, wind_code, sec_name, exchange_code, industry_source,
                    dataset_version, revision_no, is_latest, ingested_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id,
                    code,
                    name,
                    exchange_code,
                    "name_backfill",
                    "competition-2026",
                    1,
                    True,
                    NOW.strftime("%Y-%m-%d %H:%M:%S"),
                    NOW.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            stats["inserted"] += 1
            report.append({"wind_code": code, "name": name, "action": "INSERT"})

    conn.commit()
    conn.close()

    log(
        f"  Updated: {stats['updated']} | Inserted: {stats['inserted']} | Skipped: {stats['skipped']}"
    )

    df = pd.DataFrame(report)
    path = OUTPUT_DIR / "name_backfill_report.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"  Report: {path}")

    return stats


def verify() -> None:
    """验证回填后数据完整性."""
    log("\n" + "=" * 60)
    log("Step: Verify")
    log("=" * 60)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM companies "
        "WHERE sec_name IS NULL OR sec_name = '' OR sec_name = wind_code"
    )
    log(f"  Companies missing sec_name: {cur.fetchone()[0]}")

    union_q = " UNION ".join(
        f"SELECT DISTINCT wind_code FROM `{t}`" for t in DATA_TABLES
    )
    cur.execute(f"""
        SELECT COUNT(DISTINCT src.wind_code) FROM ({union_q}) src
        LEFT JOIN companies c ON src.wind_code = c.wind_code
        WHERE c.wind_code IS NULL
    """)
    log(f"  wind_codes still not in companies: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM companies")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM companies "
        "WHERE sec_name IS NOT NULL AND sec_name != '' AND sec_name != wind_code"
    )
    named = cur.fetchone()[0]
    log(f"  Total: {total} | Named: {named} ({named/total*100:.1f}%)")

    conn.close()


# ====================================================================
# Main
# ====================================================================
if __name__ == "__main__":
    t0 = time.time()
    use_online = "--online" in sys.argv

    log(f"Task 4: Company Name Backfill [{NOW.strftime('%Y-%m-%d %H:%M:%S')}]")
    log(f"Mode: {'ONLINE + offline' if use_online else 'OFFLINE only'}")
    log(f"DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    # Phase 1: 离线 — 研报表 + 公告标题名称映射
    name_map = build_name_map_from_reports()
    name_map.update(build_name_map_from_announcements())

    # 收集需要补全的代码
    to_update, to_insert = collect_missing_codes()
    all_codes = to_update + to_insert

    if not all_codes:
        log("\nNo codes need backfill. Done.")
        verify()
        sys.exit(0)

    # 先尝试离线匹配
    results: dict[str, str | None] = {}
    offline_hit = 0
    offline_miss: list[str] = []

    for code in all_codes:
        if code in name_map:
            results[code] = name_map[code]
            offline_hit += 1
        else:
            results[code] = None
            offline_miss.append(code)

    log(f"\n  Offline (reports+announcements) hit: {offline_hit}/{len(all_codes)}")
    log(f"  Offline miss: {len(offline_miss)}")

    # Phase 3: 在线补全
    if use_online and offline_miss:
        online_results = query_akshare_batch(offline_miss)
        for code, name in online_results.items():
            if name:
                results[code] = name

    # 写回 MySQL（名称）
    stats = write_back(results)

    # Phase 2: 离线 — comp_type_code 回填（置于写回后，覆盖新建公司）
    backfill_comp_type_from_raw()

    # 验证
    verify()

    elapsed = time.time() - t0
    log(f"\nTotal time: {elapsed/60:.1f} min")
    log(
        f"Task 4 complete! (offline_hit={offline_hit}, "
        f"updated={stats['updated']}, inserted={stats['inserted']})"
    )
