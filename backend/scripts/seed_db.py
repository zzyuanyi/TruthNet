"""TruthNet 一键初始化脚本：从 seed 重建本地 SQLite 库（含康美演示数据 + 6 簇舆情）。

用法（项目根目录）：
    python scripts/seed_db.py            # backend/scripts/seed_db.py 同目录亦可
    # 或
    python -m scripts.seed_db

只需在首次 clone 后运行一次；库已存在且有数据时自动跳过（除非 --force）。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
PROJECT = ROOT.parent  # 项目根
SEED = PROJECT / "data" / "fixtures" / "truthnet_seed.sqlite.sql"
DEFAULT_DB = PROJECT / "data" / "truthnet.db"
PULSE_DB = PROJECT / "data" / "market_pulse.db"  # 舆情库由后台爬取自建，无需 seed


def main() -> int:
    ap = argparse.ArgumentParser(description="重建 truthnet.db（seed：康美演示数据）")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="目标 SQLite 文件路径")
    ap.add_argument("--force", action="store_true", help="库已存在也强制重建")
    args = ap.parse_args()

    db = Path(args.db)
    if not SEED.exists():
        print(f"[seed] 找不到 seed 文件：{SEED}（跳过，库留空）")
        return 0

    db.parent.mkdir(parents=True, exist_ok=True)
    exists = db.exists()
    if exists and not args.force:
        try:
            n = (
                sqlite3.connect(db)
                .execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                .fetchone()[0]
            )
        except Exception:  # noqa: BLE001
            n = 0
        if n:
            print(f"[seed] {db} 已存在且有 {n} 张表，跳过（--force 可强制重建）")
            return 0

    if exists and args.force:
        # 先移除旧库及其 WAL 伴随文件，否则 seed SQL 中的 CREATE TABLE 会因
        # 原有表仍在而失败，--force 也就失去了“重建”的意义。
        for path in (db, Path(f"{db}-wal"), Path(f"{db}-shm")):
            path.unlink(missing_ok=True)

    sql = SEED.read_text(encoding="utf-8")
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    rows = sum(
        conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0] for t in tables
    )
    print(f"[seed] 完成：{len(tables)} 张表 / {rows} 行 → {db}")
    print("[seed] 舆情库 market_pulse.db 无需 seed，后端启动后每 10 分钟自动爬取累积")
    return 0


if __name__ == "__main__":
    sys.exit(main())
