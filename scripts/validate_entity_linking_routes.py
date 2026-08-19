"""B6 路由/模块级实体语义验证 — Phase E Task B.

对五大业务模块（finance/equity/events/comparison/unsupported）的真实用户
查询形态，跑公司实体解析（deterministic 基线 + suggest 语义层），验证：

- 模块场景下 query 绑定正确公司（wind_code 集与人工期望一致）；
- 无公司场景（unsupported / 概念 / 大盘）零绑定（nil 保持）；
- suggest 语义层不引入错误绑定 / 不伪造 wind_code（安全不变式）。

只连接 truthnet_test；不写库；不调用 --apply 类入口。

用法（truthnet conda 环境）：
    python scripts/validate_entity_linking_routes.py \
        --output data/reports/company_entity_linking_routes.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_ROOT / "backend"))

# ── 模块场景集（路由层真实查询形态 + 人工期望）───────────────
# expected_codes：期望绑定 wind_code 集；None=期望 nil；relation 参考值
MODULE_SCENARIOS: list[dict] = [
    # ── finance：财务指标/财务数据 ──────────────────────────
    {
        "module": "finance",
        "query": "分析康美药业的财务状况",
        "expected_codes": ["600518.SH"],
        "expected_relation": "single",
    },
    {
        "module": "finance",
        "query": "看看贵州茅台的营收",
        "expected_codes": ["600519.SH"],
        "expected_relation": "single",
    },
    {
        "module": "finance",
        "query": "康美的存贷比",
        "expected_codes": ["600518.SH"],
        "expected_relation": "single",
        "note": "确定性弱项：动作词吞 sub_span（B0/B1 均未绑定）",
    },
    {
        "module": "finance",
        "query": "五粮液的净利润是多少",
        "expected_codes": ["000858.SZ"],
        "expected_relation": "single",
    },
    {
        "module": "finance",
        "query": "分析康美的存贷比",
        "expected_codes": ["600518.SH"],
        "expected_relation": "single",
        "note": "B1 LLM 建议 select 600518 但 suggest 只读不应用",
    },
    # ── equity：股权穿透 ────────────────────────────────────
    {
        "module": "equity",
        "query": "看看康美药业的股权结构",
        "expected_codes": ["600518.SH"],
        "expected_relation": "single",
    },
    {
        "module": "equity",
        "query": "查询宁德时代的股权穿透",
        "expected_codes": ["300750.SZ"],
        "expected_relation": "single",
    },
    {
        "module": "equity",
        "query": "比亚迪的股东有哪些",
        "expected_codes": ["002594.SZ"],
        "expected_relation": "single",
    },
    {
        "module": "equity",
        "query": "中国平安的股权关系",
        "expected_codes": ["601318.SH"],
        "expected_relation": "single",
    },
    # ── events：公告 / 舆情 ─────────────────────────────────
    {
        "module": "events",
        "query": "康美药业最近有什么公告",
        "expected_codes": ["600518.SH"],
        "expected_relation": "single",
    },
    {
        "module": "events",
        "query": "查一下五粮液的舆情",
        "expected_codes": ["000858.SZ"],
        "expected_relation": "single",
    },
    {
        "module": "events",
        "query": "宁德时代有什么重大事件",
        "expected_codes": ["300750.SZ"],
        "expected_relation": "single",
    },
    # ── comparison：跨公司对比 ──────────────────────────────
    {
        "module": "comparison",
        "query": "对比贵州茅台和五粮液",
        "expected_codes": ["600519.SH", "000858.SZ"],
        "expected_relation": "comparison",
    },
    {
        "module": "comparison",
        "query": "康美和茅台谁更赚钱",
        "expected_codes": ["600518.SH", "600519.SH"],
        "expected_relation": "comparison",
        "note": "确定性弱项：谁更赚钱句式未识别为 comparison",
    },
    {
        "module": "comparison",
        "query": "宁德时代和比亚迪哪个好",
        "expected_codes": ["300750.SZ", "002594.SZ"],
        "expected_relation": "comparison",
    },
    {
        "module": "comparison",
        "query": "茅台和康美的股价，谁先跌的",
        "expected_codes": ["600519.SH", "600518.SH"],
        "expected_relation": "comparison",
        "note": "确定性弱项：谁先跌句式未识别为 comparison",
    },
    {
        "module": "comparison",
        "query": "泸州老窖和五粮液哪个更稳",
        "expected_codes": ["000568.SZ", "000858.SZ"],
        "expected_relation": "comparison",
    },
    # ── unsupported：无公司 / 概念 / 大盘 ───────────────────
    {
        "module": "unsupported",
        "query": "为什么今天大盘跌了",
        "expected_codes": None,
        "expected_relation": "no_company",
    },
    {
        "module": "unsupported",
        "query": "财务造假的手段有哪些",
        "expected_codes": None,
        "expected_relation": "no_company",
    },
    {
        "module": "unsupported",
        "query": "存贷双高是什么意思",
        "expected_codes": None,
        "expected_relation": "no_company",
        "note": "B1 mentionness 判 non_company 删除 → no_company（改善）",
    },
    {
        "module": "unsupported",
        "query": "分析一下宏观环境",
        "expected_codes": None,
        "expected_relation": "no_company",
    },
    {
        "module": "unsupported",
        "query": "帮我看看今天的金融板块",
        "expected_codes": None,
        "expected_relation": "no_company",
    },
    {
        "module": "unsupported",
        "query": "应收账款周转率怎么算",
        "expected_codes": None,
        "expected_relation": "no_company",
    },
]


def _confirm_database(settings, target_db: str) -> None:
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{target_db}"
    )
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        actual = conn.execute(text("SELECT DATABASE()")).scalar()
    if actual != target_db:
        sys.exit(f"[REFUSE] SELECT DATABASE()={actual!r} != {target_db!r}")
    print(f"[OK] SELECT DATABASE() == {actual}（user={settings.MYSQL_USER}）")


def _codes(result) -> list[str]:
    return [str(c.wind_code) for c in (result.selected_companies or [])]


def _safety_violation(result, scenario: dict, baseline_codes: list[str]) -> dict:
    """安全不变式：suggest 不得伪造 code / 不得在期望 nil 或对比场景误绑定。"""
    out = {"fabricated_code": False, "unexpected_binding": False, "detail": ""}
    for m in result.mentions:
        if m.selected_wind_code and m.candidates:
            allowed = {c.company.wind_code for c in m.candidates}
            if m.selected_wind_code not in allowed:
                out["fabricated_code"] = True
                out["detail"] += f"fabricated {m.selected_wind_code}@{m.text}; "
    if scenario["expected_codes"] is None and _codes(result):
        out["unexpected_binding"] = True
        out["detail"] += f"unsupported 场景误绑定 {_codes(result)}（期望零绑定）; "
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="输出 JSONL 路径")
    parser.add_argument(
        "--db", default="truthnet_test", help="目标测试库（默认 truthnet_test）"
    )
    args = parser.parse_args()

    target_db = args.db
    if target_db not in ("truthnet_test",):
        sys.exit(f"[REFUSE] --db 只允许 truthnet_test，收到 {target_db!r}")

    os.environ["SQL_BACKEND"] = "mysql"
    os.environ["MYSQL_DATABASE"] = target_db

    from app.core.config import settings

    if settings.MYSQL_TEST_DATABASE:
        if not (settings.MYSQL_TEST_USER and settings.MYSQL_TEST_PASSWORD):
            sys.exit("[REFUSE] MYSQL_TEST 三件套不完整")
        settings.MYSQL_DATABASE = settings.MYSQL_TEST_DATABASE
        settings.MYSQL_USER = settings.MYSQL_TEST_USER
        settings.MYSQL_PASSWORD = settings.MYSQL_TEST_PASSWORD

    _confirm_database(settings, target_db)

    from app.application.services.company_entity_resolver import (
        CompanyEntityResolver,
    )
    from app.application.services.company_mentionness_classifier import (
        CompanyMentionnessClassifier,
    )
    from app.application.services.company_semantic_selector import (
        CompanySemanticSelector,
    )
    from app.infrastructure.persistence.mysql.company_repository import (
        MySQLCompanyRepository,
    )

    repo = MySQLCompanyRepository()
    det_resolver = CompanyEntityResolver(repo)
    sug_resolver = CompanyEntityResolver(
        repo,
        selector=CompanySemanticSelector(mode="suggest", total_budget_seconds=20.0),
        mentionness=CompanyMentionnessClassifier(
            mode="suggest", total_budget_seconds=20.0
        ),
    )

    rows: list[dict] = []
    by_module: dict[str, dict] = {}
    for s in MODULE_SCENARIOS:
        det = det_resolver.resolve(s["query"], memory={})
        sug = sug_resolver.resolve(s["query"], memory={})
        det_codes = _codes(det)
        sug_codes = _codes(sug)
        exp = s["expected_codes"]
        det_ok = exp is not None and sorted(det_codes) == sorted(exp)
        sug_ok = exp is not None and sorted(sug_codes) == sorted(exp)
        if exp is None:
            det_ok = not det_codes
            sug_ok = not sug_codes
        safety = _safety_violation(sug, s, det_codes)
        row = {
            "module": s["module"],
            "query": s["query"],
            "expected_codes": exp,
            "expected_relation": s["expected_relation"],
            "deterministic_codes": det_codes,
            "deterministic_relation": det.intent,
            "deterministic_ok": bool(det_ok),
            "suggest_codes": sug_codes,
            "suggest_relation": sug.intent,
            "suggest_ok": bool(sug_ok),
            "safety": safety,
            "note": s.get("note", ""),
        }
        rows.append(row)
        m = by_module.setdefault(
            s["module"],
            {"total": 0, "det_ok": 0, "sug_ok": 0, "safety_violations": 0},
        )
        m["total"] += 1
        m["det_ok"] += 1 if det_ok else 0
        m["sug_ok"] += 1 if sug_ok else 0
        if safety["fabricated_code"] or safety["unexpected_binding"]:
            m["safety_violations"] += 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n=== B6 模块级汇总 ===")
    print(
        f"{'module':12s} {'n':>2s} {'det_ok':>6s} {'sug_ok':>6s} {'safety_viol':>11s}"
    )
    for mod, m in by_module.items():
        print(
            f"{mod:12s} {m['total']:>2d} {m['det_ok']:>6d} {m['sug_ok']:>6d} "
            f"{m['safety_violations']:>11d}"
        )
    print(f"\n输出: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
