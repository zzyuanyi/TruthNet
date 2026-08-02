"""事件簇交接数据导入工具 — Phase C 任务 15.

逐行 JSONL，Pydantic 校验 + 幂等 upsert。

用法：
  python scripts/import_event_clusters.py --input <path> --validate-only
  python scripts/import_event_clusters.py --input <path> --dry-run
  python scripts/import_event_clusters.py --input <path>

约束：
  - 校验失败时不部分写入；
  - 同 ID 同内容 → skipped；同 ID 不同内容 → conflicted（不覆盖）；
  - 不访问网络；不修改 announcements。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.domain.events.contracts import EventClusterRecord  # noqa: E402
from app.infrastructure.persistence.mysql.event_cluster_repository import (  # noqa: E402
    MySQLEventClusterRepository,
)


def _parse_jsonl(path: Path) -> list[tuple[int, dict]]:
    """逐行读取 JSONL，返回 [(行号, dict)]，保留原始行号."""
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {lineno} 行 JSON 解析失败: {exc}") from exc
            lines.append((lineno, obj))
    return lines


def main():
    parser = argparse.ArgumentParser(description="事件簇 JSONL 导入")
    parser.add_argument("--input", required=True, help="JSONL 文件路径")
    parser.add_argument("--validate-only", action="store_true", help="仅校验")
    parser.add_argument("--dry-run", action="store_true", help="预览不写入")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"输入文件不存在: {path}")
        sys.exit(2)

    # 1. 逐行解析 + Pydantic 校验
    raw_lines = _parse_jsonl(path)
    records: list[tuple[int, EventClusterRecord]] = []
    errors: list[str] = []

    for lineno, obj in raw_lines:
        try:
            rec = EventClusterRecord.model_validate(obj)
            records.append((lineno, rec))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"第 {lineno} 行校验失败: {exc}")

    if errors:
        print("=== 校验失败（不写入） ===")
        for e in errors:
            print("  ", e)
        print(f"共 {len(errors)} 行失败，{len(records)} 行通过。")
        sys.exit(1)

    print(f"校验通过: {len(records)} 行。")

    if args.validate_only:
        print("validate-only: 未写入。")
        return

    if args.dry_run:
        print("dry-run: 未写入。")
        for lineno, rec in records[:10]:
            print(f"  行{lineno}: {rec.event_cluster_id} {rec.wind_code} {rec.topic}")
        return

    # 2. 幂等导入
    repo = MySQLEventClusterRepository()
    counts = {"inserted": 0, "updated": 0, "skipped": 0, "conflicted": 0}
    for lineno, rec in records:
        try:
            result = repo.upsert(rec)
            status = result["status"]
            counts[status] = counts.get(status, 0) + 1
            if status == "conflicted":
                print(f"  行{lineno} 冲突: {rec.event_cluster_id} — 拒绝覆盖")
        except Exception as exc:  # noqa: BLE001
            print(f"  行{lineno} 导入异常: {rec.event_cluster_id} — {exc}")
            counts["conflicted"] = counts.get("conflicted", 0) + 1

    print(
        "导入结果: "
        f"inserted={counts['inserted']} updated={counts['updated']} "
        f"skipped={counts['skipped']} conflicted={counts['conflicted']}"
    )


if __name__ == "__main__":
    main()
