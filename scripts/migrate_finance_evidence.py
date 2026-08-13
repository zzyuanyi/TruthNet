"""存量财务 Evidence 身份修正（v3.4 ③ + v3.5 + v3.6）— 两阶段受控迁移.

背景：v3.1 时代落库的财务证据 field_path=rule_Rx（如 rule_R1），而
canonical ID 由真实财务字段生成（如 acct_rcv）——六元组身份不一致，
且 v3.4 方向 A 后新落库（field_path=真实字段）与存量同 ID 冲突。

v3.6 两阶段流程（审查要求）：
  phase 1（只读）：--dry-run --plan-out <path> 生成机器可读计划
      （含 fix_count/skip_count/fixes/skips/rows_sha256/plan_sha256），
      人工复核后记录文件 SHA256；
  phase 2（只写）：--apply-plan <path> --expected-plan-sha256 <sha>
      --confirm <db> **只执行指定计划**——禁止重新扫描；文件 SHA、
      内部 plan_sha256、数据库名、行数、旧值任一不符立即退出零写入。

执行事务（v3.6）：
- skip_count != 0 拒绝执行；
- 目标库专用凭据连接 + SELECT DATABASE() 二次确认；
- 按 evidence_id 排序对全部计划行 SELECT ... FOR UPDATE；
- 比较完整旧身份（source_type/source_record_id/field_path/period/
  dataset_version/company_code/source_title——NULL 原样比较）；
- 从锁定后的真实旧行生成备份并以 O_EXCL 写盘；
- 批量 UPDATE，每条 rowcount == 1；NULL 字段原样保存——
  UPDATE 条件使用 MySQL NULL-safe 比较 `source_title <=> %s`，
  不再把 NULL 转空串；
- 提交前验证 field_path/source_title/canonical ID；
- 断言计划内全部迁移 + 全库目标范围 rule_% == 0；
- 任一步失败整批 rollback。

安全 rollback（v3.6）：
  --rollback <backup.json> --expected-backup-sha256 <sha> --confirm <db>
- 备份必须是对象格式且 schema 受支持（旧版数组备份明确报
  "legacy backup unsupported"，不抛 AttributeError、不写库）；
- 验证 backup.database == --db、文件 SHA、rows_sha256、行数；
- 当前行完整等于迁移后的身份与 new_source_title；
- 全部行先 FOR UPDATE；精确恢复旧值（含 NULL）；任一不一致整批回滚。

候选计算在**目标库**执行（v3.6：同时切换 MYSQL_DATABASE/USER/PASSWORD
（必要时 HOST/PORT）；演示库用演示账号、测试库用 MYSQL_TEST_*；
清 _fetch._ENGINES 前先 dispose() 防连接泄漏）。

用法：
    # phase 1 生成计划（只读）
    python scripts/migrate_finance_evidence.py --db truthnet --dry-run \
        --plan-out data/backups/finance_evidence_plan_truthnet.json
    # phase 2 只执行指定计划（人工复核 SHA 后）
    python scripts/migrate_finance_evidence.py --db truthnet \
        --apply-plan data/backups/finance_evidence_plan_truthnet.json \
        --expected-plan-sha256 <SHA256> --confirm truthnet
    # 安全回滚
    python scripts/migrate_finance_evidence.py --db truthnet \
        --rollback data/backups/<backup>.json \
        --expected-backup-sha256 <SHA256> --confirm truthnet
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

_SCRIPT_VERSION = "3.6.1"
_PLAN_SCHEMA = "1.0"
# v3.6.1：备份 schema 与脚本版本拆分——脚本升级不得使旧备份不可回滚；
# 校验 schema 支持集合；script_version 保留作审计（同样走支持集合）。
# 注：3.6.0 从未产出过真实备份（schema 1.0 无审计字段），故不在支持集合内；
# legacy 数组备份（如 evidence_field_migration_truthnet_test.json）仅审计，
# 不可用于当前 rollback。
_BACKUP_SCHEMA = "1.1"
_SUPPORTED_BACKUP_SCHEMAS = {"1.1"}
_SUPPORTED_BACKUP_SCRIPT_VERSIONS = {"3.6.1"}
# 计划同样绑定生成脚本版本——新版本脚本只接受本版本生成的计划，
# 避免用新逻辑执行旧扫描口径。
_SUPPORTED_PLAN_SCRIPT_VERSIONS = {"3.6.1"}
_SOURCE_TITLE = "母公司报表 · 财务反欺诈规则字段证据"


class MigrateError(Exception):
    """迁移内部错误（整批回滚场景）。"""


# ── 目标库白名单与凭据 ──────────────────────────────────


def validate_db_arg(db: str) -> None:
    """--db 只允许严格等于 MYSQL_DATABASE 或 MYSQL_TEST_DATABASE。"""
    allowed = {
        os.environ.get("MYSQL_DATABASE", ""),
        os.environ.get("MYSQL_TEST_DATABASE", ""),
    }
    if db not in allowed or not db:
        raise SystemExit(
            f"[migrate] --db {db!r} 不在白名单（MYSQL_DATABASE/MYSQL_TEST_DATABASE）"
        )


def is_test_db(db: str) -> bool:
    return db == os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")


def _connect(db: str):
    """目标库专用凭据连接（演示库用演示账号、测试库用测试账号）+ SELECT DATABASE 确认。"""
    import pymysql

    user_key = "MYSQL_TEST_USER" if is_test_db(db) else "MYSQL_USER"
    pwd_key = "MYSQL_TEST_PASSWORD" if is_test_db(db) else "MYSQL_PASSWORD"
    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get(user_key, ""),
        password=os.environ.get(pwd_key, ""),
        database=db,
        charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        actual = cur.fetchone()[0]
    if (actual or "").lower() != db.lower():
        conn.close()
        raise SystemExit(
            f"[migrate] SELECT DATABASE()={actual!r} != 期望 {db!r}（拒绝）"
        )
    return conn


# ── 候选计算（目标库规则引擎 + v3.6 全凭据切换） ─────────


def _run_rules_on_db(db: str, wind_code: str, as_of: str) -> dict:
    """在**目标库**上跑规则引擎（v3.6：同时保存/切换/恢复数据库与账号凭据）。

    演示库用演示账号、测试库用 MYSQL_TEST_USER/PASSWORD；必要时
    HOST/PORT 一并切换。清 _fetch._ENGINES 前先 dispose() 防连接泄漏。
    """
    from app.core.config import settings
    from app.domain.finance._fetch import _ENGINES

    saved = {
        "database": settings.MYSQL_DATABASE,
        "user": settings.MYSQL_USER,
        "password": settings.MYSQL_PASSWORD,
        "host": settings.MYSQL_HOST,
        "port": settings.MYSQL_PORT,
    }
    if is_test_db(db):
        settings.MYSQL_DATABASE = db
        settings.MYSQL_USER = os.environ.get("MYSQL_TEST_USER", "")
        settings.MYSQL_PASSWORD = os.environ.get("MYSQL_TEST_PASSWORD", "")
    else:
        settings.MYSQL_DATABASE = db
        settings.MYSQL_USER = os.environ.get("MYSQL_USER", "")
        settings.MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    try:
        engine = _ENGINES.get("mysql")
        if engine is not None:
            engine.dispose()
            _ENGINES.clear()
        from app.domain.finance.rule_engine import evaluate_all_rules

        return evaluate_all_rules(wind_code, as_of)
    finally:
        settings.MYSQL_DATABASE = saved["database"]
        settings.MYSQL_USER = saved["user"]
        settings.MYSQL_PASSWORD = saved["password"]
        settings.MYSQL_HOST = saved["host"]
        settings.MYSQL_PORT = saved["port"]
        engine = _ENGINES.get("mysql")
        if engine is not None:
            engine.dispose()
        _ENGINES.clear()


def _candidate_fields(db: str, wind_code: str, as_of: str) -> dict[str, set[str]]:
    """对某公司期间跑规则引擎：legacy evidence_id → 真实字段候选集合。"""
    try:
        results = _run_rules_on_db(db, wind_code, as_of)
    except Exception:  # noqa: BLE001 — 数据不足等：无候选
        return {}
    out: dict[str, set[str]] = {}
    for rid, r in results.items():
        if r is None:
            continue
        fields: set[str] = set()
        for legacy in r.evidence_ids:
            parts = legacy.split("_")
            field = legacy
            if legacy.startswith("ev_") and len(parts) >= 3:
                field = "_".join(parts[2:]).removesuffix(f"_{as_of}")
            fields.add(field)
        out[rid] = fields
    return out


# ── 行自洽校验与 candidate ID（用存量行自身值） ──────────


def parse_source_record_id(rec: str) -> tuple[str, str] | None:
    """解析 source_record_id（wind_code|as_of）；无 '|' 返回 None。"""
    if not rec or "|" not in rec:
        return None
    wind_code, as_of = rec.split("|", 1)
    if not wind_code or not as_of:
        return None
    return wind_code, as_of


def validate_row_identity(row: dict) -> str | None:
    """canonical 六元组自洽校验；不自洽返回原因（None 表示自洽）。"""
    rec = row.get("source_record_id") or ""
    parsed = parse_source_record_id(rec)
    if parsed is None:
        return "source_record_id 无 wind_code|as_of"
    wind_code, as_of = parsed
    if (row.get("company_code") or "") != wind_code:
        return (
            f"company_code({row.get('company_code')}) != source_record_id "
            f"的 wind_code({wind_code})"
        )
    if (row.get("period") or "") != as_of:
        return f"period({row.get('period')}) != source_record_id 的 as_of({as_of})"
    if not row.get("dataset_version"):
        return "dataset_version 为空（六元组缺失）"
    return None


def candidate_id(field: str, row: dict) -> str:
    """用存量行自身六元组重算 candidate ID（不以 settings 为准）。"""
    from app.domain.provenance.id_factory import NS_FINANCE, make_evidence_id

    return make_evidence_id(
        source_namespace=NS_FINANCE,
        source_type="financial_statement",
        source_record_id=row["source_record_id"],
        field_path=field,
        period=row.get("period") or "",
        dataset_version=row.get("dataset_version") or "",
        company_code=row.get("company_code") or "",
    )


def plan_row(row: dict, candidate_fields: dict[str, set[str]]) -> dict:
    """单行计划：唯一候选匹配 → fix；零/多匹配 → skip（纯函数）。"""
    parsed = parse_source_record_id(row.get("source_record_id") or "")
    if parsed is None:
        return {**row, "reason": "source_record_id 无 wind_code|as_of"}
    identity_issue = validate_row_identity(row)
    if identity_issue:
        return {**row, "reason": f"canonical 六元组不自洽: {identity_issue}"}
    matched: list[str] = []
    matched_rules: dict[str, str] = {}
    seen_fields: set[str] = set()
    for rule_id, fields in candidate_fields.items():
        for field in fields:
            if field in seen_fields:
                continue
            seen_fields.add(field)
            if candidate_id(field, row) == row["evidence_id"]:
                matched.append(field)
                matched_rules[field] = rule_id
    if len(matched) == 1:
        return {
            "evidence_id": row["evidence_id"],
            "source_type": row.get("source_type") or "financial_statement",
            "old_field_path": row["field_path"],
            "old_source_title": row.get("source_title"),  # NULL 原样保留
            "new_field_path": matched[0],
            "new_source_title": _SOURCE_TITLE,
            "rule_id": matched_rules[matched[0]],
            "company_code": row["company_code"],
            "period": row["period"],
            "source_record_id": row["source_record_id"],
            "dataset_version": row["dataset_version"],
        }
    return {
        **row,
        "reason": f"候选匹配 {len(matched)} 个（唯一才修正）: {matched}",
    }


# ── SHA 辅助（v3.6）───────────────────────────────────


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def plan_sha256_of(payload: dict) -> str:
    """内部 plan_sha256：去掉自身键后的规范化 JSON 哈希（自洽可复算）。"""
    inner = {k: v for k, v in payload.items() if k != "plan_sha256"}
    return sha256_bytes(
        json.dumps(inner, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def rows_sha256_of(fixes: list[dict]) -> str:
    return sha256_bytes(
        json.dumps(fixes, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def write_exclusive(path: Path, payload: dict) -> str:
    """独占创建（O_EXCL 禁止覆盖旧文件）；返回文件 SHA256。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise MigrateError(f"文件已存在，拒绝覆盖: {path}") from None
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return file_sha256(path)


# ── 计划生成（phase 1，只读） ─────────────────────────


def build_plan(db: str, fixes: list[dict], skips: list[dict]) -> dict:
    """机器可读计划（v3.6）：fixes 完整旧身份+新值；rows/plan 双 SHA。"""
    payload = {
        "schema_version": _PLAN_SCHEMA,
        "script_version": _SCRIPT_VERSION,
        "database": db,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fix_count": len(fixes),
        "skip_count": len(skips),
        "fixes": fixes,
        "skips": skips,
        "rows_sha256": rows_sha256_of(fixes),
    }
    payload["plan_sha256"] = plan_sha256_of(payload)
    return payload


def _scan(conn, db: str) -> tuple[list[dict], list[dict]]:
    """扫描 rule_% 记录 → (fixes, skips)。候选在目标库计算。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT evidence_id, source_type, source_record_id, field_path, "
            "period, dataset_version, company_code, source_title "
            "FROM evidence_refs WHERE source_type='financial_statement' "
            "AND field_path LIKE 'rule_%' ORDER BY evidence_id"
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    fixes: list[dict] = []
    skips: list[dict] = []
    cache: dict[tuple[str, str], dict[str, set[str]]] = {}
    for row in rows:
        parsed = parse_source_record_id(row.get("source_record_id") or "")
        if parsed is None:
            skips.append({**row, "reason": "source_record_id 无 wind_code|as_of"})
            continue
        identity_issue = validate_row_identity(row)
        if identity_issue:
            skips.append({**row, "reason": f"canonical 六元组不自洽: {identity_issue}"})
            continue
        wind_code, as_of = parsed
        key = (wind_code, as_of)
        if key not in cache:
            cache[key] = _candidate_fields(db, wind_code, as_of)
        outcome = plan_row(row, cache[key])
        if "reason" in outcome:
            skips.append(outcome)
        else:
            fixes.append(outcome)
    return fixes, skips


# ── 计划执行（phase 2：只执行指定计划，禁止重扫） ───────


def validate_plan(payload: dict, db: str, expected_sha: str, plan_path: Path) -> None:
    """计划校验（任一不符立即退出零写入）。"""
    actual_sha = file_sha256(plan_path)
    if actual_sha != expected_sha:
        raise MigrateError(f"计划文件 SHA 不符: 期望 {expected_sha}，实际 {actual_sha}")
    if not isinstance(payload, dict):
        raise MigrateError("计划不是对象格式（预期 schema_version=1.0 计划 JSON）")
    if payload.get("schema_version") != _PLAN_SCHEMA:
        raise MigrateError(f"计划 schema 不支持: {payload.get('schema_version')!r}")
    if payload.get("database") != db:
        raise MigrateError(f"计划数据库 {payload.get('database')!r} != --db {db!r}")
    if payload.get("script_version") not in _SUPPORTED_PLAN_SCRIPT_VERSIONS:
        raise MigrateError(
            f"计划 script_version 不支持: {payload.get('script_version')!r} "
            f"（支持: {sorted(_SUPPORTED_PLAN_SCRIPT_VERSIONS)}）"
        )
    if payload.get("plan_sha256") != plan_sha256_of(payload):
        raise MigrateError("计划内部 plan_sha256 不一致（文件被篡改?）")
    fixes = payload.get("fixes", [])
    skips = payload.get("skips", [])
    if payload.get("fix_count") != len(fixes):
        raise MigrateError(
            f"fix_count({payload.get('fix_count')}) != fixes 行数({len(fixes)})"
        )
    if payload.get("skip_count") != len(skips):
        raise MigrateError(
            f"skip_count({payload.get('skip_count')}) != skips 行数({len(skips)})"
        )
    if payload.get("skip_count", 0) != 0:
        raise MigrateError(
            f"计划含 {payload.get('skip_count')} 条 skips——拒绝执行（必须 0）"
        )
    if payload.get("rows_sha256") != rows_sha256_of(fixes):
        raise MigrateError("计划 rows_sha256 不一致（fixes 内容被篡改?）")


def apply_plan(
    conn,
    payload: dict,
    db: str,
    *,
    expected_plan_sha256: str,
    backup_dir: Path | None = None,
) -> tuple[dict, Path]:
    """单事务执行指定计划；任一不一致整批回滚（抛异常并显式回滚）。

    v3.6.1：
    - expected_plan_sha256：人工审核的计划文件 SHA——备份绑定
      source_plan_file_sha256，可追溯到本次审核的文件；
    - backup_dir 可注入（测试传 tmp_path，失败路径无残留）；
    - 备份 schema 独立版本（_BACKUP_SCHEMA=1.1），含 row_count 与
      source_plan_sha256/source_plan_file_sha256 审计元数据；
    - 异常统一 except Exception: conn.rollback(); raise（不依赖连接关闭回滚）。
    返回 (backup_payload, backup_path)。备份从**锁定后的真实旧行**生成，
    O_EXCL 写盘；NULL 字段原样保存（source_title <=> %s）。
    """
    fixes = list(payload["fixes"])
    fixes.sort(key=lambda f: f["evidence_id"])  # 确定性顺序
    backup_rows: list[dict] = []
    backup_root = backup_dir or (_REPO_ROOT / "data" / "backups")
    try:
        with conn.cursor() as cur:
            # 1. 按 evidence_id 排序 SELECT ... FOR UPDATE，比较完整旧身份
            for f in fixes:
                cur.execute(
                    "SELECT source_type, source_record_id, field_path, period, "
                    "dataset_version, company_code, source_title "
                    "FROM evidence_refs WHERE evidence_id=%s FOR UPDATE",
                    (f["evidence_id"],),
                )
                row = cur.fetchone()
                if row is None:
                    raise MigrateError(
                        f"FOR UPDATE 未找到行（并发删除?）: {f['evidence_id']}"
                    )
                (
                    cur_st,
                    cur_srid,
                    cur_fp,
                    cur_period,
                    cur_dv,
                    cur_cc,
                    cur_title,
                ) = row
                if (
                    cur_st != f.get("source_type", "financial_statement")
                    or cur_srid != f["source_record_id"]
                    or cur_fp != f["old_field_path"]
                    or cur_period != f["period"]
                    or cur_dv != f["dataset_version"]
                    or cur_cc != f["company_code"]
                    or cur_title != f["old_source_title"]  # NULL 原样比较
                ):
                    raise MigrateError(
                        f"FOR UPDATE 旧值不一致（dry-run 后行被修改?）: "
                        f"{f['evidence_id']}"
                    )
                # 2. 从锁定后的真实旧行生成备份行（含 NULL，原样保存）
                backup_rows.append(
                    {
                        "evidence_id": f["evidence_id"],
                        "source_type": cur_st,
                        "source_record_id": cur_srid,
                        "old_field_path": cur_fp,
                        "old_source_title": cur_title,
                        "new_field_path": f["new_field_path"],
                        "new_source_title": f["new_source_title"],
                        "rule_id": f.get("rule_id", ""),
                        "company_code": cur_cc,
                        "period": cur_period,
                        "dataset_version": cur_dv,
                    }
                )
        # 3. 备份 O_EXCL 写盘（锁定后真实旧行）；时间戳含毫秒防同秒冲突
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"
        backup_path = (
            backup_root / f"evidence_field_migration_{db.replace('.', '_')}_{ts}.json"
        )
        backup_payload = {
            "schema_version": _BACKUP_SCHEMA,
            "script_version": _SCRIPT_VERSION,
            "database": db,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            # v3.6.1 审计元数据：行数 + 内部计划哈希 + 人工审核文件哈希
            "row_count": len(backup_rows),
            "source_plan_sha256": payload.get("plan_sha256", ""),
            "source_plan_file_sha256": expected_plan_sha256,
            "rows_sha256": rows_sha256_of(backup_rows),
            "rows": backup_rows,
        }
        backup_sha = write_exclusive(backup_path, backup_payload)
        print(f"[migrate] 备份 {backup_path} SHA256={backup_sha}")
    except Exception:
        conn.rollback()
        raise

    # 4. 批量 UPDATE（NULL-safe：source_title <=> %s；每条 rowcount == 1）
    try:
        with conn.cursor() as cur:
            for f in fixes:
                n = cur.execute(
                    "UPDATE evidence_refs SET field_path=%s, source_title=%s "
                    "WHERE evidence_id=%s AND field_path=%s AND source_title <=> %s",
                    (
                        f["new_field_path"],
                        f["new_source_title"],
                        f["evidence_id"],
                        f["old_field_path"],
                        f["old_source_title"],  # None → NULL，原样
                    ),
                )
                if n != 1:
                    raise MigrateError(
                        f"乐观 UPDATE rowcount={n} != 1: {f['evidence_id']}"
                    )
            # 5. 提交前验证：field_path/source_title/canonical ID
            for f in fixes:
                new_cid = candidate_id(f["new_field_path"], f)
                if new_cid != f["evidence_id"]:
                    raise MigrateError(
                        f"提交前重算 canonical ID 不一致: {f['evidence_id']} "
                        f"重算={new_cid}"
                    )
                cur.execute(
                    "SELECT field_path, source_title FROM evidence_refs "
                    "WHERE evidence_id=%s",
                    (f["evidence_id"],),
                )
                check = cur.fetchone()
                if (
                    check is None
                    or check[0] != f["new_field_path"]
                    or check[1] != f["new_source_title"]
                ):
                    raise MigrateError(
                        f"提交前新字段校验失败: {f['evidence_id']} -> {check}"
                    )
            # 6. 断言计划内全部迁移 + 全库目标范围 rule_% == 0
            cur.execute(
                "SELECT COUNT(*) FROM evidence_refs "
                "WHERE source_type='financial_statement' AND field_path LIKE 'rule_%'"
            )
            rule_left = cur.fetchone()[0]
            if rule_left != 0:
                raise MigrateError(
                    f"提交前断言失败: 全库 rule_% 残留 {rule_left} 条（应为 0）"
                )
        conn.commit()
        print(f"[migrate] 已按计划修正 {len(fixes)} 条 field_path（单事务提交）")
    except Exception:
        conn.rollback()
        raise
    return backup_payload, backup_path


# ── 安全 rollback（v3.6） ─────────────────────────────


def validate_backup(payload, db: str, expected_sha: str, backup_path: Path) -> None:
    """备份校验（v3.6.1）：对象格式 + schema 支持集合 + script_version 支持
    集合 + database + SHA + row_count + rows_sha256 + 计划绑定。

    script_version 不作严格等于当前版本——脚本升级后仍可回滚旧版合法备份
    （支持集合 _SUPPORTED_BACKUP_SCRIPT_VERSIONS）。
    """
    actual_sha = file_sha256(backup_path)
    if actual_sha != expected_sha:
        raise MigrateError(f"备份文件 SHA 不符: 期望 {expected_sha}，实际 {actual_sha}")
    if isinstance(payload, list):
        # 旧版数组备份：明确拒绝，不抛 AttributeError、不写库
        raise MigrateError(
            "legacy backup unsupported: 备份是数组格式（v3.4 旧版）；"
            "v3.6.1 仅支持对象格式备份"
        )
    if not isinstance(payload, dict):
        raise MigrateError(f"备份不是对象格式: {type(payload)!r}")
    if payload.get("schema_version") not in _SUPPORTED_BACKUP_SCHEMAS:
        raise MigrateError(
            f"备份 schema 不支持: {payload.get('schema_version')!r} "
            f"（支持 {sorted(_SUPPORTED_BACKUP_SCHEMAS)}）"
        )
    if payload.get("script_version") not in _SUPPORTED_BACKUP_SCRIPT_VERSIONS:
        raise MigrateError(
            f"备份 script_version 不支持: {payload.get('script_version')!r} "
            f"（支持 {sorted(_SUPPORTED_BACKUP_SCRIPT_VERSIONS)}）"
        )
    if payload.get("database") != db:
        raise MigrateError(
            f"备份数据库 {payload.get('database')!r} != --db {db!r}（错库拒绝）"
        )
    rows = payload.get("rows", [])
    if payload.get("row_count") != len(rows):
        raise MigrateError(
            f"备份 row_count({payload.get('row_count')}) != rows 行数({len(rows)})"
        )
    if payload.get("rows_sha256") != rows_sha256_of(rows):
        raise MigrateError("备份 rows_sha256 不一致（内容被篡改?）")
    # v3.6.1：计划绑定审计元数据（缺任一 → 拒绝）
    if not payload.get("source_plan_sha256") or not payload.get(
        "source_plan_file_sha256"
    ):
        raise MigrateError(
            "备份缺计划绑定（source_plan_sha256/source_plan_file_sha256）"
        )


def rollback_from_backup(conn, backup_path: Path, db: str, expected_sha: str) -> int:
    """基于备份精确恢复旧字段（含 NULL）；任一不一致整批回滚。"""
    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    validate_backup(payload, db, expected_sha, backup_path)
    rows = payload.get("rows", [])
    if not rows:
        print("[migrate] 备份无 rows，无需恢复")
        return 0
    restored = 0
    try:
        with conn.cursor() as cur:
            # 1. 全部行 FOR UPDATE + 当前行完整等于迁移后身份
            for f in rows:
                cur.execute(
                    "SELECT source_type, source_record_id, field_path, period, "
                    "dataset_version, company_code, source_title "
                    "FROM evidence_refs WHERE evidence_id=%s FOR UPDATE",
                    (f["evidence_id"],),
                )
                row = cur.fetchone()
                if row is None:
                    raise MigrateError(
                        f"rollback FOR UPDATE 未找到行: {f['evidence_id']}"
                    )
                (
                    cur_st,
                    cur_srid,
                    cur_fp,
                    cur_period,
                    cur_dv,
                    cur_cc,
                    cur_title,
                ) = row
                if (
                    cur_st != f["source_type"]
                    or cur_srid != f["source_record_id"]
                    or cur_fp != f["new_field_path"]  # 当前应为迁移后的值
                    or cur_period != f["period"]
                    or cur_dv != f["dataset_version"]
                    or cur_cc != f["company_code"]
                    or cur_title != f["new_source_title"]
                ):
                    raise MigrateError(
                        f"rollback 当前行 != 迁移后身份: {f['evidence_id']}"
                    )
            # 2. 精确恢复旧值（含 NULL：source_title <=> %s）
            for f in rows:
                n = cur.execute(
                    "UPDATE evidence_refs SET field_path=%s, source_title=%s "
                    "WHERE evidence_id=%s AND field_path=%s AND source_title <=> %s",
                    (
                        f["old_field_path"],
                        f["old_source_title"],
                        f["evidence_id"],
                        f["new_field_path"],
                        f["new_source_title"],
                    ),
                )
                if n != 1:
                    raise MigrateError(
                        f"rollback 乐观 UPDATE rowcount={n} != 1: {f['evidence_id']}"
                    )
                restored += 1
        conn.commit()
        print(f"[migrate] 已从备份精确恢复 {restored} 条（含 NULL，单事务提交）")
    except Exception:
        conn.rollback()
        raise
    return restored


# ── 主流程（命令分发） ─────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    )
    parser.add_argument("--dry-run", action="store_true", help="只审计不修改")
    parser.add_argument("--plan-out", default="", help="dry-run 时输出机器可读计划")
    parser.add_argument("--apply-plan", default="", help="只执行指定计划文件")
    parser.add_argument(
        "--expected-plan-sha256", default="", help="人工复核的计划文件 SHA256"
    )
    parser.add_argument("--rollback", default="", help="从备份文件恢复原字段")
    parser.add_argument(
        "--expected-backup-sha256", default="", help="人工复核的备份文件 SHA256"
    )
    parser.add_argument("--confirm", default="", help="执行确认：必须显式输入目标库名")
    args = parser.parse_args()

    validate_db_arg(args.db)

    # ── phase 1：生成计划（只读） ──
    if args.dry_run:
        conn = _connect(args.db)
        try:
            fixes, skips = _scan(conn, args.db)
        finally:
            conn.close()
        print(f"[migrate] 审计完成：共 {len(fixes) + len(skips)} 条 rule_% 记录")
        print(f"  → 可修正（唯一候选匹配）: {len(fixes)}")
        for f in fixes:
            print(
                f"    {f['evidence_id']} {f['old_field_path']} → "
                f"{f['new_field_path']} ({f['rule_id']})"
            )
        print(f"  → 跳过（不自洽/零或多匹配）: {len(skips)}")
        for s in skips[:10]:
            print(
                f"    {s['evidence_id']} {s.get('field_path', '')}: {s.get('reason', '')}"
            )
        if args.plan_out:
            plan_path = Path(args.plan_out)
            payload = build_plan(args.db, fixes, skips)
            try:
                sha = write_exclusive(plan_path, payload)
            except MigrateError as exc:
                print(f"[migrate] ✗ {exc}")
                return 1
            print(f"[migrate] 计划已写入 {plan_path}")
            print(f"[migrate] 计划文件 SHA256={sha}")
            print(
                f"[migrate] fix_count={len(fixes)} skip_count={len(skips)} "
                f"rows_sha256={payload['rows_sha256']} plan_sha256={payload['plan_sha256']}"
            )
        else:
            print("[migrate] dry-run：未修改任何数据（--plan-out 可输出机器可读计划）")
        return 0

    # ── phase 2：只执行指定计划（禁止重新扫描） ──
    if args.apply_plan:
        if not args.confirm or args.confirm != args.db:
            raise SystemExit(
                f"[migrate] apply-plan 必须 --confirm {args.db}（执行确认）"
            )
        if not args.expected_plan_sha256:
            raise SystemExit("[migrate] 缺少 --expected-plan-sha256（人工复核的 SHA）")
        plan_path = Path(args.apply_plan)
        if not plan_path.is_file():
            raise SystemExit(f"[migrate] 计划文件不存在: {plan_path}")
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        try:
            validate_plan(payload, args.db, args.expected_plan_sha256, plan_path)
        except Exception as exc:  # v3.6.1：非 MigrateError 也输出原因
            print(f"[migrate] ✗ 计划校验失败（零写入）: {exc}")
            return 1
        conn = _connect(args.db)
        try:
            backup_payload, backup_path = apply_plan(
                conn,
                payload,
                args.db,
                expected_plan_sha256=args.expected_plan_sha256,
            )
        except Exception as exc:
            print(f"[migrate] ✗ 执行失败（事务已回滚，未提交）: {exc}")
            print("  备份如已生成仅供审计——事务已回滚，无需再次 rollback")
            return 1
        finally:
            conn.close()
        print(f"[migrate] 备份 {backup_path} 已生成（用于 rollback）")
        return 0

    # ── 安全回滚 ──
    if args.rollback:
        if not args.confirm or args.confirm != args.db:
            raise SystemExit(
                f"[migrate] rollback 必须 --confirm {args.db}（无 confirm 拒绝）"
            )
        if not args.expected_backup_sha256:
            raise SystemExit(
                "[migrate] 缺少 --expected-backup-sha256（人工复核的 SHA）"
            )
        backup_path = Path(args.rollback)
        if not backup_path.is_file():
            raise SystemExit(f"[migrate] 备份文件不存在: {backup_path}")
        conn = _connect(args.db)
        try:
            rollback_from_backup(
                conn, backup_path, args.db, args.expected_backup_sha256
            )
        except Exception as exc:  # v3.6.1：非 MigrateError 也输出原因
            print(f"[migrate] ✗ 回滚失败（未提交）: {exc}")
            return 1
        finally:
            conn.close()
        return 0

    # ── 其他：禁止裸 confirm 直接执行（v3.6：必须走计划） ──
    raise SystemExit(
        "[migrate] 正式执行必须两阶段：--dry-run --plan-out 生成计划 → "
        "人工复核 → --apply-plan --expected-plan-sha256 <SHA> --confirm <db>"
    )


if __name__ == "__main__":
    sys.exit(main())
