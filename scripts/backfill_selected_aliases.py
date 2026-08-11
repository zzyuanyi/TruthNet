#!/usr/bin/env python
"""精选别名幂等回填 — 8.11 P0（审查）：公司歧义确认需要别名数据。

背景：真库 companies.aliases 全为 NULL，候选查询（完整名/别名）无法触发
歧义确认，"分析国药的财务风险" 会静默沿用历史公司。本脚本按版本化
fixture（data/fixtures/selected_aliases_v1.json）幂等回填：

  - 仅填写 aliases 为空（NULL 或 ''）的记录，绝不覆盖已有别名；
  - 只回填 fixture 列出的精选别名（演示/联调用），不批量生成两字前缀别名；
  - 默认 --dry-run 预检；--confirm 才写库。

用法:
    python scripts/backfill_selected_aliases.py              # 预检
    python scripts/backfill_selected_aliases.py --confirm    # 正式回填
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import create_engine, text  # noqa: E402

FIXTURE = _REPO_ROOT / "data" / "fixtures" / "selected_aliases_v1.json"


def _engine():
    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url)


def _process(conn, entries: list[dict], execute: bool) -> tuple[int, int, list[str]]:
    """遍历 fixture 条目：返回 (回填行数, 已有别名跳过数, 未找到公司列表)。"""
    updated = 0
    skipped = 0
    missing: list[str] = []
    for entry in entries:
        alias = str(entry["alias"]).strip()
        for code in entry["wind_codes"]:
            row = conn.execute(
                text(
                    "SELECT sec_name, aliases FROM companies "
                    "WHERE wind_code = :code AND is_latest = 1 LIMIT 1"
                ),
                {"code": code},
            ).first()
            if row is None:
                missing.append(code)
                continue
            sec_name, current = row[0], str(row[1] or "")
            if current.strip() not in ("", "None"):
                skipped += 1
                print(f"  [跳过(已有别名)] {code} {sec_name}: {current}")
                continue
            if execute:
                conn.execute(
                    text(
                        "UPDATE companies SET aliases = :a "
                        "WHERE wind_code = :code AND is_latest = 1 "
                        "AND (aliases IS NULL OR aliases = '')"
                    ),
                    {"a": json.dumps([alias], ensure_ascii=False), "code": code},
                )
            print(f"  {'[回填]' if execute else '[预检]'} {code} {sec_name} → {alias}")
            updated += 1
    return updated, skipped, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="精选别名幂等回填")
    parser.add_argument(
        "--confirm", action="store_true", help="正式回填（默认 dry-run）"
    )
    args = parser.parse_args()

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    execute = args.confirm
    engine = _engine()

    if execute:
        with engine.begin() as conn:
            updated, skipped, missing = _process(conn, fixture["aliases"], execute=True)
    else:
        with engine.connect() as conn:
            updated, skipped, missing = _process(
                conn, fixture["aliases"], execute=False
            )
    engine.dispose()

    print(f"\n将回填/已回填: {updated} 行 | 已有别名跳过: {skipped}")
    if missing:
        print(f"⚠️ 未找到公司: {missing}")
    if not execute:
        print("预检模式（--dry-run），未写库；确认执行加 --confirm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
