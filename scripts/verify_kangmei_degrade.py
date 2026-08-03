"""康美无公告降级场景验收脚本（Phase C 完成标志第一条）.

验证康美（600518.SH）降级链路：
  - 实体解析 → 康美
  - 财务规则 0 触发（重整后数据正常化口径，R6 数据不足 / R7 不适用）
  - 股权链路正常（股东数据存在）
  - 无公告 → 空时间线 + NO_ANNOUNCEMENT_DATA warning，不 Mock
  - 第二轮验证指代延续（不重复要求公告 warning，该问题不调 Events）

用法:
  D:/anaconda/envs/truthnet/python.exe scripts/verify_kangmei_degrade.py

前置:
  - MySQL 全量数据 + comp_type_code 回填（康美 comp_type_code=1）
  - .env 配置 SQL_BACKEND=mysql
"""

from __future__ import annotations

import argparse
import io
import sys
import uuid
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

ROUND1 = "康美药业有财务造假风险吗"
ROUND2 = "它的股权结构怎么样"

_CHECK: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _CHECK.append((name, ok, detail))
    print(f"  [{'✅' if ok else '❌'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="", help="已启动的后端地址（默认 TestClient）")
    args = ap.parse_args()

    session_id = f"ses_kangmei_{uuid.uuid4().hex[:12]}"
    if args.url:
        import requests

        def ask(q: str) -> dict:
            r = requests.post(
                f"{args.url.rstrip('/')}/api/v1/chat",
                json={"question": q, "session_id": session_id},
                timeout=120,
            )
            return r.json()["data"]

    else:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        def ask(q: str) -> dict:
            return client.post(
                "/api/v1/chat", json={"question": q, "session_id": session_id}
            ).json()["data"]

    print("=" * 70)
    print("  康美无公告降级场景验收 — 600518.SH")
    print("=" * 70)

    # ── 第 1 轮：完整链路 + 无公告降级 ─────────────────────
    print(f"\n第 1 轮 | {ROUND1}")
    d1 = ask(ROUND1)
    ans1 = d1.get("answer", "")
    warns1 = d1.get("warnings") or []
    claims1 = d1.get("claims") or []

    _check("实体解析到康美（600518.SH）", "600518" in ans1 or "康美药业" in ans1, ans1[:40])
    _check(
        "无公告降级：NO_ANNOUNCEMENT_DATA warning",
        any("NO_ANNOUNCEMENT_DATA" in w for w in warns1),
        "；".join(w for w in warns1 if "NO_ANNOUNCEMENT" in w),
    )
    _check(
        "财务 0 触发口径（无规则明细展开）",
        "触发规则明细" not in ans1,
        ans1[-40:],
    )
    _check(
        "无事件维度描述（公告无数据不伪造事件）",
        "事件维度" not in ans1,
        ans1[-60:],
    )
    _check(
        "回答不包含假数据（无公告/事件数据仍可回答）",
        "公告" not in ans1 or "无公告" in ans1 or "NO_ANNOUNCEMENT" in ans1,
        "；".join(w for w in warns1 if "公告" in w),
    )
    print(f"\n【第 1 轮回答】\n{ans1}\n")

    # ── 第 2 轮：指代延续 + 股权（不重复要求公告 warning）──
    print(f"第 2 轮 | {ROUND2}")
    d2 = ask(ROUND2)
    ans2 = d2.get("answer", "")

    _check("指代延续（'它'→康美）", "600518" in ans2 or "康美药业" in ans2, ans2[:40])
    _check("股权链路返回（股东数据存在）", "股权维度" in ans2 and "控制链" in ans2, ans2[:60])
    print(f"\n【第 2 轮回答】\n{ans2}\n")

    # ── 汇总 ───────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in _CHECK if ok)
    print("=" * 70)
    print(f"  康美降级场景验收：{passed}/{len(_CHECK)} 通过")
    print("=" * 70)
    return 0 if passed == len(_CHECK) else 1


if __name__ == "__main__":
    raise SystemExit(main())
