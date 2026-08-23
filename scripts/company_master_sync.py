#!/usr/bin/env python
"""用当前沪深京 A 股快照幂等补齐 companies 主表（默认 dry-run）。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.app.application.services.industry_fill.guards import (  # noqa: E402
    resolve_database_env,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/company_master_sync.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    resolve_database_env(args.database, ROOT / ".env")

    from sqlalchemy import create_engine, text

    from backend.app.application.services.company_master_sync import (
        fetch_existing_wind_codes,
        insert_missing_companies,
        plan_missing_companies,
    )
    from backend.app.application.services.industry_fill.guards import (
        verify_selected_database,
    )
    from backend.app.application.services.industry_fill.universe import (
        fetch_current_a_share_universe,
    )
    from backend.app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            actual = str(conn.execute(text("SELECT DATABASE()")).scalar() or "")
        verify_selected_database(actual, args.database)
        snapshot = fetch_current_a_share_universe()
        before = fetch_existing_wind_codes(engine)
        planned = plan_missing_companies(before, snapshot)
        inserted = (
            insert_missing_companies(
                engine,
                planned,
                dataset_version=settings.DATASET_VERSION,
                snapshot=snapshot,
            )
            if args.apply
            else 0
        )
        after = fetch_existing_wind_codes(engine)
        remaining = plan_missing_companies(after, snapshot)
    finally:
        engine.dispose()

    report = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "database": args.database,
        "mode": "apply" if args.apply else "dry-run",
        **snapshot.report_fields(),
        "planned_count": len(planned),
        "inserted_count": inserted,
        "remaining_count": len(remaining),
        "planned": [row.__dict__ for row in planned],
        "remaining": [row.__dict__ for row in remaining],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "mode",
                    "current_universe_count",
                    "planned_count",
                    "inserted_count",
                    "remaining_count",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if (not args.apply or not remaining) else 1


if __name__ == "__main__":
    raise SystemExit(main())
