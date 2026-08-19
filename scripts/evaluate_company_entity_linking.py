"""公司实体链接离线评测 runner — v3.3.1 §9.2（可复现、只读、非临时脚本）.

- 只读连接 truthnet_test（启动后 SELECT DATABASE() 二次确认，禁连演示库）；
- 显式构造 suggest selector 与 mentionness classifier（不经生产全局模式；
  生产 lifespan 已拒绝非 off，本脚本独立运行）；
- 输入脱敏 JSONL；输出 JSONL + 汇总报告；
- 每样本记录 query、期望、确定性结果、suggestion、verifier 状态、
  attempts、错误、耗时；对权威结果做 before/after 深比较，任何非
  audit 差异令样本 status=authority_mismatch（suggest 只读验证）；
- 不写 sessions/turns/evidence。

用法:
  # Phase E B0：确定性基线回归（对基线评分）
  python scripts/evaluate_company_entity_linking.py `
    --input data/evaluation/company_entity_linking.jsonl `
    --output data/reports/company_entity_linking_baseline.jsonl `
    --db truthnet_test `
    --selector-mode off --score-target deterministic

  # Phase E B1：suggest 语义识别（对被测 result 评分，零越权安全门禁）
  python scripts/evaluate_company_entity_linking.py `
    --input data/evaluation/company_entity_linking.jsonl `
    --output data/reports/company_entity_linking_suggest.jsonl `
    --db truthnet_test `
    --selector-mode suggest --interpreter-mode off `
    --score-target result --authority-strict off
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / ".env")

_AUDIT_FIELDS = {
    "selector_status",
    "semantic_suggestion",
    "semantic_attempts",
    "semantic_validation_error",
    "mentionness_verdicts",
}


def _compare_sample(expected: dict, result) -> dict:
    """最终续审 §7 D3：一个样本联合验证全部已标注维度。

    - expected_selected_codes：集合精确相等（非包含关系）；
    - expected_relation：intent 相等；
    - expected_roles：{code: role} 全等；
    - expected_nil：零绑定期望；
    - comparison 强制：intent=comparison 但 <2 个不同 code → 必失败。

    任一已标注维度失败 → 样本整体失败；无支持字段 → overall=None
    （不计分母，单独计数）。兼容旧格式（wind_code/relation 单字段）。
    """
    selected_codes = {str(c.wind_code) for c in result.selected_companies}
    dims: dict[str, bool] = {}
    if "expected_selected_codes" in expected:
        exp = {str(c) for c in expected["expected_selected_codes"]}
        dims["identity_set"] = exp == selected_codes
    elif expected.get("wind_code"):
        dims["identity_set"] = {str(expected["wind_code"])} == selected_codes
    if expected.get("expected_relation"):
        dims["relation"] = result.intent == expected["expected_relation"]
    elif expected.get("relation"):
        dims["relation"] = result.intent == expected["relation"]
    if "expected_roles" in expected:
        by_code = {
            str(m.selected_wind_code): m.role
            for m in result.mentions
            if m.selected_wind_code
        }
        dims["roles"] = {
            str(k): v for k, v in expected["expected_roles"].items()
        } == by_code
    if "expected_nil" in expected:
        dims["nil"] = (not result.selected_companies) == bool(expected["expected_nil"])
    if result.intent == "comparison" and len(selected_codes) < 2:
        dims["comparison_participants"] = False
    if not dims:
        return {"overall": None, "dims": {}, "detail": "no supported expected field"}
    return {
        "overall": all(dims.values()),
        "dims": dims,
        "detail": "",
    }


def _authority_signature(result) -> dict:
    """权威结果签名（排除 audit 字段）——suggest 前后必须深一致。"""
    return {
        "intent": result.intent,
        "mentions": [m.model_dump() for m in result.mentions],
        "selected_companies": [
            c.model_dump() if hasattr(c, "model_dump") else dict(c)
            for c in result.selected_companies
        ],
        "unresolved_mentions": result.unresolved_mentions,
        "needs_confirmation": result.needs_confirmation,
        "reason_code": result.reason_code,
        "resolution_issues": [i.model_dump() for i in result.resolution_issues],
        "segmentation_alternatives": [
            a.model_dump() for a in result.segmentation_alternatives
        ],
    }


def _authority_diff_keys(baseline, result) -> list[str]:
    """Phase E B1：权威签名差异的顶层字段列表（诊断，不判失败）。

    suggest 新模式中 mentionness 的 non_company 删除/子实体重链会产生
    合法差异；差异字段逐个记录供人工核对，而非把样本标 authority_mismatch。
    """
    if result is None:
        return ["<no-result>"]
    b = _authority_signature(baseline)
    r = _authority_signature(result)
    return sorted(k for k in b if b[k] != r[k])


def _safety(result, baseline, expected) -> dict:
    """Phase E B2：suggest 新模式安全维度（必须可证明零越权）。

    - fabricated_code：result 任一绑定 wind_code 不在其 mention 候选集内
      （结构上不允许，检测回归）；
    - auto_bind_on_ambiguity：expected.requires_confirmation=True 时，
      结果不得产生确定性基线之外的新绑定——语义层（suggest/auto/
      mentionness 子实体重链）不得在歧义样本上自动绑定公司身份。
      （零绑定的 no_company/needs_confirmation 均属安全——不过度确认
      不算越权；基线已确认的绑定也安全。）
    """
    out = {"fabricated_code": False, "auto_bind_on_ambiguity": False, "detail": ""}
    if result is None:
        out["detail"] = "no result"
        return out
    for m in result.mentions:
        if m.selected_wind_code and m.candidates:
            allowed = {c.company.wind_code for c in m.candidates}
            if m.selected_wind_code not in allowed:
                out["fabricated_code"] = True
                out["detail"] += f"fabricated {m.selected_wind_code}@{m.text}; "
    if expected.get("requires_confirmation"):
        base_codes = {str(c.wind_code) for c in baseline.selected_companies}
        res_codes = {str(c.wind_code) for c in result.selected_companies}
        if res_codes - base_codes:
            out["auto_bind_on_ambiguity"] = True
            out["detail"] += (
                f"new bindings {sorted(res_codes - base_codes)} "
                "beyond deterministic on ambiguous sample; "
            )
    return out


def _confirm_database(target_db: str, settings) -> None:
    """启动后 SELECT DATABASE() 二次确认（v3.3.1 §9.2 / 测试库铁律）。

    连接身份：优先 MYSQL_TEST_* 三件套（与 tests/conftest.py 同一
    守卫口径——truthnet 演示库用户通常无 truthnet_test 权限）。
    """
    from sqlalchemy import URL, create_engine, text

    user = settings.MYSQL_TEST_USER or settings.MYSQL_USER
    password = settings.MYSQL_TEST_PASSWORD or settings.MYSQL_PASSWORD
    if settings.MYSQL_TEST_DATABASE and not settings.MYSQL_TEST_USER:
        sys.exit("[REFUSE] MYSQL_TEST_DATABASE 已设但 MYSQL_TEST_USER 为空")
    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=target_db,
    )
    engine = create_engine(url, echo=False)
    with engine.connect() as conn:
        actual = conn.execute(text("SELECT DATABASE()")).scalar()
    if actual != target_db:
        sys.exit(
            f"[REFUSE] SELECT DATABASE()={actual!r} != {target_db!r}，"
            "本 runner 只允许连接 truthnet_test"
        )
    print(f"[OK] SELECT DATABASE() == {actual}（user={user}）")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="脱敏 JSONL 输入路径")
    parser.add_argument("--output", required=True, help="输出 JSONL 路径")
    parser.add_argument(
        "--db", default="truthnet_test", help="目标测试库（默认 truthnet_test）"
    )
    parser.add_argument(
        "--selector-mode",
        default="off",
        choices=["off", "suggest", "auto"],
        help="语义选择模式（最终续审 §7 D2：与 Interpreter 模式分离）",
    )
    parser.add_argument(
        "--interpreter-mode",
        default="off",
        choices=["off", "shadow", "fallback"],
        help="Interpreter 模式（实际注入 QuerySubjectInterpreter）",
    )
    parser.add_argument(
        "--score-target",
        default="result",
        choices=["result", "deterministic", "auto"],
        help="评分对象（Phase E B1/B2）：result=对被测 resolver 输出评分"
        "（suggest 新模式——mentionness 允许合法删除 non_company、子实体"
        "重链，result 可与确定性基线不同，按人工期望评）；deterministic="
        "对确定性基线评分（B0 回归比较）；auto=旧语义（仅 auto/fallback "
        "模式评 result，其余评基线）",
    )
    parser.add_argument(
        "--authority-strict",
        default="off",
        choices=["off", "on"],
        help="authority 差异处理（Phase E B1）：off=记录 authority_diff "
        "但样本不判失败（suggest 只读验证 + mentionness 合法差异）；on=旧"
        "语义：任何非 audit 差异 → authority_mismatch",
    )
    parser.add_argument(
        "--selector-budget-seconds",
        type=float,
        default=20.0,
        help="selector query 级总预算秒数",
    )
    parser.add_argument(
        "--interpreter-budget-seconds",
        type=float,
        default=5.0,
        help="Interpreter 单次硬预算秒数（默认保持 5s fail-closed）",
    )
    args = parser.parse_args()

    target_db = args.db
    if target_db not in ("truthnet_test",):
        sys.exit(f"[REFUSE] --db 只允许 truthnet_test，收到 {target_db!r}")

    # 在 import settings 之前注入目标库（pydantic-settings 实例化时读取）
    os.environ["SQL_BACKEND"] = "mysql"
    os.environ["MYSQL_DATABASE"] = target_db

    from app.core.config import settings

    # 测试身份优先（与 tests/conftest.py 同口径）：MYSQL_TEST 三件套
    # 非空时以测试身份连库（truthnet 演示库用户通常无 truthnet_test 权限）
    if settings.MYSQL_TEST_DATABASE:
        if not (settings.MYSQL_TEST_USER and settings.MYSQL_TEST_PASSWORD):
            sys.exit("[REFUSE] MYSQL_TEST 三件套不完整")
        settings.MYSQL_DATABASE = settings.MYSQL_TEST_DATABASE
        settings.MYSQL_USER = settings.MYSQL_TEST_USER
        settings.MYSQL_PASSWORD = settings.MYSQL_TEST_PASSWORD

    _confirm_database(target_db, settings)

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

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"[REFUSE] 输入文件不存在: {input_path}")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    samples = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    if not samples:
        sys.exit("[REFUSE] 输入为空")

    repo = MySQLCompanyRepository()
    selector = CompanySemanticSelector(
        mode=args.selector_mode,
        total_budget_seconds=args.selector_budget_seconds,
    )
    mentionness = CompanyMentionnessClassifier(
        mode=args.selector_mode,
        total_budget_seconds=args.selector_budget_seconds,
    )
    from app.application.services.query_subject_interpreter import (
        QuerySubjectInterpreter,
    )

    interpreter = QuerySubjectInterpreter(
        mode=args.interpreter_mode,
        budget_seconds=args.interpreter_budget_seconds,
    )
    deterministic_resolver = CompanyEntityResolver(repo)
    tested_resolver = CompanyEntityResolver(
        repo, selector=selector, mentionness=mentionness, interpreter=interpreter
    )

    # 最终续审 §7 D2 + Phase E B1/B2：authority 差异处理——默认 off
    # （suggest 新模式允许 mentionness 合法差异，差异记录 authority_diff
    # 但不判样本失败）；--authority-strict on 恢复旧语义（任何非 audit
    # 差异 → authority_mismatch）。
    authority_strict = args.authority_strict == "on"
    # 评分对象（Phase E B1）：suggest 新模式对被测 result 评分
    # （mentionness 删除/子实体重链属合法差异，按人工期望评）；B0 回归
    # 用 --score-target deterministic 对基线评分；auto 保留旧语义。
    score_target_is_result = {
        "result": True,
        "deterministic": False,
        "auto": args.selector_mode == "auto" or args.interpreter_mode == "fallback",
    }[args.score_target]

    rows: list[dict] = []
    stats: dict = {
        "ok": 0,
        "authority_mismatch": 0,
        "selector": {},
        "total_ms": 0.0,
        "expected": {"overall": {"pass": 0, "total": 0}},
        "dims": {},
        "unsupported_expected": 0,
        "llm_calls": 0,
        "safety": {"fabricated_code": 0, "auto_bind_on_ambiguity": 0},
        "elapsed_samples": [],
    }

    def _active_after(result) -> str:
        """本轮结束后的活跃主体（与 persist_turn 终态守卫同语义）。"""
        if result is None:
            return ""
        primaries = [
            str(m.selected_wind_code)
            for m in result.mentions
            if m.role == "primary" and m.selected_wind_code
        ]
        return primaries[0] if len(primaries) == 1 else ""

    # 最终续审 §7 D4：多轮模式——含 session_id/turn_index 的样本按
    # session 分组、turn_index 升序执行，上一轮 active 构造下一轮
    # MemoryContext；单轮样本（无 session_id）保持独立执行
    from app.agents.state import MemoryContext

    current_by_session: dict[str, str] = {}
    # 按 (session_id, turn_index) 稳定排序：多轮顺序执行、单轮互不干扰
    ordered = sorted(
        enumerate(samples),
        key=lambda t: (
            str((t[1].get("session_id") or "")) or f"single_{t[0]}",
            int(t[1].get("turn_index", 0)),
        ),
    )
    for orig_idx, sample in ordered:
        query = str(sample.get("query") or "").strip()
        if not query:
            continue
        expected = sample.get("expected") or {}
        session_id = str(sample.get("session_id") or "")

        memory = None
        if session_id and current_by_session.get(session_id):
            code = current_by_session[session_id]
            memory = MemoryContext(
                resolved_company_code=code,
                resolved_entity_name="",
                is_anaphora=False,
                previous_company_codes=[code],
                current_company_code=code,
            )
        current_before = current_by_session.get(session_id, "") if session_id else ""

        # 权威 before：纯确定性解析
        baseline = deterministic_resolver.resolve(query, memory=memory)

        started = time.perf_counter()
        try:
            result = tested_resolver.resolve(query, memory=memory)
            status = "ok"
        except Exception as exc:  # noqa: BLE001 — 样本级失败记录，不中断批
            result = None
            status = f"error: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000
        stats["total_ms"] += elapsed_ms
        stats["elapsed_samples"].append(elapsed_ms)

        authority_diff: list[str] = []
        if result is not None:
            authority_diff = _authority_diff_keys(baseline, result)
            if authority_strict and authority_diff:
                status = "authority_mismatch"
            else:
                stats["ok"] += 1
            if session_id:
                active = _active_after(result)
                if active:
                    current_by_session[session_id] = active

        # D3：联合验证（评分对象按模式——fallback/auto 评 result）
        score_target = (
            result if score_target_is_result and result is not None else baseline
        )
        comparison = _compare_sample(expected, score_target)
        if comparison["overall"] is None:
            stats["unsupported_expected"] += 1
        else:
            b = stats["expected"]["overall"]
            b["total"] += 1
            if comparison["overall"]:
                b["pass"] += 1
            for dim, ok in comparison["dims"].items():
                db = stats["dims"].setdefault(dim, {"pass": 0, "total": 0})
                db["total"] += 1
                if ok:
                    db["pass"] += 1
        # D4：active_after 维度（多轮标注）
        if "expected_active_after" in expected:
            got = _active_after(result) if result is not None else ""
            db = stats["dims"].setdefault("active_after", {"pass": 0, "total": 0})
            db["total"] += 1
            if got == str(expected["expected_active_after"] or ""):
                db["pass"] += 1
            if comparison["overall"] is not None:
                comparison["dims"]["active_after"] = got == str(
                    expected["expected_active_after"] or ""
                )
                comparison["overall"] = (
                    comparison["overall"] and comparison["dims"]["active_after"]
                )
        if result is not None and result.semantic_attempts > 0:
            stats["llm_calls"] += 1

        selector_status = result.selector_status if result is not None else "failed"
        stats["selector"][selector_status] = (
            stats["selector"].get(selector_status, 0) + 1
        )

        # Phase E B2：安全维度（suggest 不得越权自动绑定/不得伪造代码）
        safety = _safety(result, baseline, expected)
        for flag in ("fabricated_code", "auto_bind_on_ambiguity"):
            if safety[flag]:
                db = stats["safety"].setdefault(flag, 0)
                stats["safety"][flag] = db + 1

        rows.append(
            {
                "session_id": session_id or None,
                "turn_index": int(sample.get("turn_index", 0)) if session_id else None,
                "current_company_before": current_before or None,
                "query": query,
                "status": status,
                "authority_diff": authority_diff,
                "safety": safety,
                "score_target": "result" if score_target_is_result else "deterministic",
                "elapsed_ms": round(elapsed_ms, 1),
                "expected": expected,
                "expected_overall": comparison["overall"],
                "expected_dims": comparison["dims"],
                "expected_detail": comparison["detail"],
                "deterministic": baseline.model_dump(),
                "result": result.model_dump() if result is not None else None,
                "suggestion": (
                    result.semantic_suggestion.model_dump()
                    if result is not None and result.semantic_suggestion
                    else None
                ),
                "selector_status": selector_status,
                "attempts": (result.semantic_attempts if result is not None else 0),
                "validation_error": (
                    result.semantic_validation_error if result is not None else ""
                ),
                "mentionness_verdicts": (
                    [v.model_dump() for v in result.mentionness_verdicts]
                    if result is not None
                    else []
                ),
            }
        )

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    elapsed_sorted = sorted(stats["elapsed_samples"])
    n = max(len(elapsed_sorted), 1)
    p50 = elapsed_sorted[int(n * 0.5)] if elapsed_sorted else 0.0
    p95 = elapsed_sorted[min(int(n * 0.95), n - 1)] if elapsed_sorted else 0.0

    def _acc(kind: str) -> float | None:
        b = stats["dims"].get(kind)
        if not b or not b["total"]:
            return None
        return round(b["pass"] / b["total"], 4)

    def _overall_acc() -> float | None:
        b = stats["expected"]["overall"]
        return round(b["pass"] / b["total"], 4) if b["total"] else None

    # 最终续审 §7 D2：记录代码 SHA 与 dirty 状态（可复现性元数据）
    import subprocess

    git_sha = ""
    git_dirty = True
    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
            timeout=10,
        ).stdout.strip()
        git_dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=str(_ROOT),
                timeout=10,
            ).stdout.strip()
        )
    except Exception:  # noqa: BLE001 — 元数据失败不阻断评测
        pass

    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "db": target_db,
        "selector_mode": args.selector_mode,
        "interpreter_mode": args.interpreter_mode,
        "selector_budget_seconds": args.selector_budget_seconds,
        "interpreter_budget_seconds": args.interpreter_budget_seconds,
        "llm_backend": settings.LLM_BACKEND,
        "llm_model": getattr(settings, "DEEPSEEK_MODEL", ""),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "total": len(rows),
        "ok": stats["ok"],
        "authority_mismatch": sum(
            1 for r in rows if r["status"] == "authority_mismatch"
        ),
        "errors": sum(1 for r in rows if r["status"].startswith("error")),
        "selector_distribution": stats["selector"],
        "avg_elapsed_ms": round(stats["total_ms"] / max(len(rows), 1), 1),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        # D3：联合评分（None=该维度无标注样本，不计分母）
        "sample_accuracy": _overall_acc(),
        "identity_set_accuracy": _acc("identity_set"),
        "relation_accuracy": _acc("relation"),
        "roles_accuracy": _acc("roles"),
        "nil_accuracy": _acc("nil"),
        "comparison_participants_violations": stats["dims"]
        .get("comparison_participants", {})
        .get("total", 0)
        - stats["dims"].get("comparison_participants", {}).get("pass", 0),
        "unsupported_expected_samples": stats["unsupported_expected"],
        "llm_call_sample_rate": round(stats["llm_calls"] / max(len(rows), 1), 4),
        # Phase E B2：安全维度计数（suggest 零越权门禁）
        "safety_violations": stats["safety"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
