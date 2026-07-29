#!/usr/bin/env python
r"""从 research_reports 回填 companies.sec_name。

名称选择规则（众数优先 + 最新兜底）：
  1. 对 research_reports 按 (wind_code, sec_name) 分组，统计出现次数和最新日期
  2. 每个 wind_code 选出现次数最多的 sec_name
  3. 次数并列时，以 publish_date 最新者胜出
  4. 置信度分级：
     - high: 次数 > 1 且无并列
     - low:  次数 = 1 或有并列 — 仅写入 diff 报告，不自动更新
  5. 仅更新 companies.sec_name 为空或等于 wind_code 的行
  6. 不插入、不改 aliases
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.app.core.config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


class Candidate(NamedTuple):
    sec_name: str
    count: int
    latest_date: str


def _get_engine() -> Engine:
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url, echo=False)


def _load_candidates(engine: Engine) -> dict[str, list[Candidate]]:
    """按 wind_code 分组返回所有候选名称（已按 count DESC, latest_date DESC 排序）。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wind_code, sec_name, COUNT(*) AS cnt, "
                "MAX(publish_date) AS latest_date "
                "FROM research_reports "
                "WHERE sec_name IS NOT NULL "
                "AND TRIM(sec_name) != '' "
                "AND sec_name != wind_code "
                "AND is_latest = 1 "
                "GROUP BY wind_code, sec_name "
                "ORDER BY wind_code, cnt DESC, latest_date DESC"
            )
        ).fetchall()

    log.info("研报 (wind_code, sec_name) 分组数: %d", len(rows))

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for wc, sn, cnt, ld in rows:
        grouped[wc].append(Candidate(sec_name=sn, count=cnt, latest_date=ld or ""))

    log.info("唯一 wind_code 数（研报侧）: %d", len(grouped))
    return grouped


def _select_best(
    candidates: dict[str, list[Candidate]],
) -> dict[str, dict]:
    """每个 wind_code 选出最佳名称，返回 {wind_code: {name, count, confidence}}。

    confidence='high': 次数>1 且无并列；confidence='low': 次数=1 或有并列。
    """
    result: dict[str, dict] = {}
    for wc, cands in candidates.items():
        best = cands[0]
        is_tie = len(cands) > 1 and cands[1].count == best.count
        result[wc] = {
            "sec_name": best.sec_name,
            "count": best.count,
            "confidence": "high" if best.count > 1 and not is_tie else "low",
            "all_candidates": cands,  # 仅 diff 用
        }
    return result


def cmd_diff(engine: Engine, best: dict[str, dict]) -> int:
    """只读报告：所有差异，含置信度标记。"""
    with engine.connect() as conn:
        current_rows = conn.execute(
            text(
                "SELECT wind_code, sec_name FROM companies "
                "WHERE is_latest = 1 AND sec_name IS NOT NULL AND TRIM(sec_name) != ''"
            )
        ).fetchall()

    diff_high = 0
    diff_low = 0
    for wc, current_name in current_rows:
        if wc not in best:
            continue
        info = best[wc]
        if current_name == info["sec_name"]:
            continue

        if info["confidence"] == "high":
            diff_high += 1
            label = "⚠ HIGH_CONSENSUS"
        else:
            diff_low += 1
            label = "  LOW"

        # 显示所有候选名称（最多 3 个）
        cand_strs = [f"{c.sec_name}(×{c.count})" for c in info["all_candidates"][:3]]
        total = diff_high + diff_low
        if total <= 40:
            log.info(
                "%s %s: 当前=%s, 候选=[%s]",
                label,
                wc,
                current_name,
                ", ".join(cand_strs),
            )

    log.info(
        "差异汇总: %d 条 (HIGH_CONSENSUS=%d, LOW=%d — LOW 仅报告不更新)",
        diff_high + diff_low,
        diff_high,
        diff_low,
    )
    return 0


def cmd_update(engine: Engine, best: dict[str, dict], dry_run: bool = False) -> int:
    """标准回填：仅HIGH_CONSENSUS映射 + 仅更新空/等于 wind_code 的行。"""
    with engine.connect() as conn:
        need_update = conn.execute(
            text(
                "SELECT wind_code, sec_name FROM companies "
                "WHERE is_latest = 1 "
                "AND (sec_name IS NULL OR TRIM(sec_name) = '' OR sec_name = wind_code)"
            )
        ).fetchall()

    log.info("companies 需更新行数: %d", len(need_update))

    updates: dict[str, str] = {}
    high_skipped = 0  # HIGH_CONSENSUS但名称无效
    low_confidence = 0  # 低一致性不更新
    unmatched = 0

    for wc, _current_name in need_update:
        if wc not in best:
            unmatched += 1
            continue

        info = best[wc]
        new_name = info["sec_name"]

        if not new_name or new_name.strip() == "" or new_name == wc:
            high_skipped += 1
            continue

        if info["confidence"] == "low":
            low_confidence += 1
            continue

        updates[wc] = new_name

    log.info("将更新（HIGH_CONSENSUS）: %d", len(updates))
    log.info("低一致性跳过（仅报告，不更新）: %d", low_confidence)
    log.info("无效映射跳过: %d", high_skipped)
    log.info("无匹配研报: %d", unmatched)

    if low_confidence > 0:
        log.info("--- 低一致性明细 ---")
        for wc, _current_name in need_update:
            if wc not in best:
                continue
            info = best[wc]
            if info["confidence"] != "low":
                continue
            new_name = info["sec_name"]
            if not new_name or new_name.strip() == "" or new_name == wc:
                continue
            cand_strs = [
                f"{c.sec_name}(×{c.count})" for c in info["all_candidates"][:3]
            ]
            log.info(
                "  %s: → %s, 候选=[%s]",
                wc,
                new_name,
                ", ".join(cand_strs),
            )

    if dry_run:
        log.info("[DRY-RUN] 不会实际写入数据库")
        for i, (wc, new_name) in enumerate(updates.items()):
            if i >= 10:
                log.info("...(共 %d 条)", len(updates))
                break
            log.info("  %s → %s", wc, new_name)
        return 0

    if not updates:
        log.info("无需更新，退出")
        return 0

    try:
        with engine.begin() as write_conn:
            updated = 0
            for wind_code, new_sec_name in updates.items():
                result = write_conn.execute(
                    text(
                        "UPDATE companies "
                        "SET sec_name = :sec_name, updated_at = UTC_TIMESTAMP() "
                        "WHERE wind_code = :wind_code "
                        "AND is_latest = 1 "
                        "AND ("
                        "  sec_name IS NULL "
                        "  OR TRIM(sec_name) = '' "
                        "  OR sec_name = wind_code"
                        ")"
                    ),
                    {"sec_name": new_sec_name, "wind_code": wind_code},
                )
                updated += result.rowcount

        log.info("已更新: %d 行", updated)
        log.info("低一致性跳过: %d", low_confidence)
        log.info("无效映射跳过: %d", high_skipped)
        log.info("无匹配研报: %d", unmatched)
    except Exception:
        log.exception("更新失败，事务已回滚")
        return 1
    return 0


def main():
    p = argparse.ArgumentParser(description="从 research_reports 回填公司名称")
    p.add_argument("--dry-run", action="store_true", help="仅统计，不执行更新")
    p.add_argument(
        "--diff",
        action="store_true",
        help="只读：对比当前 sec_name 与众数选出的名称差异（含置信度）",
    )
    args = p.parse_args()

    engine = _get_engine()
    candidates = _load_candidates(engine)

    if not candidates:
        log.warning("研报无有效公司名称，退出")
        return 0

    best = _select_best(candidates)
    high_count = sum(1 for v in best.values() if v["confidence"] == "high")
    low_count = sum(1 for v in best.values() if v["confidence"] == "low")
    log.info("HIGH_CONSENSUS: %d, 低一致性: %d", high_count, low_count)

    if args.diff:
        return cmd_diff(engine, best)

    return cmd_update(engine, best, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
