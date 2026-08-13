#!/usr/bin/env python
r"""证券主数据审计与修复（安全修复 P2：台积电类污染）。

背景
----
companies.sec_name 曾由 industry_mapping.csv 的 stock_name 覆盖（import_data.py
旧逻辑），该 CSV 含人工生成噪声（如 002330.SZ → "台积电"，实为得利斯）。
本脚本建立"经审核证券主表"作为 sec_name 权威源：

  - 权威来源 1：研报 research_reports 的 Wind 官方 sec_name（众数优先）
  - 权威来源 2：公告标题"简称:标题"格式提取简称（众数优先，格式噪声归一化）
  - 权威来源 3：人工定点修复（MANUAL_FIXES，仅确认污染）

审计分类（不自动改动的项进 review 报告）：
  - ok_rr / ok_ann：与权威源一致
  - fill_placeholder：现有 sec_name = wind_code（占位）且权威源可补 → 可自动补
  - conflict_review：公告简称与现有名称归一化后仍不一致 → 不自动改
  - suspicious：启发式可疑（海外知名公司名/超长）→ 仅 MANUAL_FIXES 内自动修
  - unverified：无任何权威源覆盖 → 保留现状

用法
----
  python scripts/security_master.py --dry-run      # 生成主表 + 审计报告，不写库
  python scripts/security_master.py --apply        # 幂等修复 companies.sec_name

产物（data/processed/）：
  security_master.csv          证券主表（wind_code/sec_name/exchange/as_of/source）
  security_audit_report.csv    审计报告（每行：状态/现状/权威名/来源）
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from backend.app.core.config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

RAW_5_DIR = _repo_root / "data" / "raw" / "5"
RAW_3_XLSX = _repo_root / "data" / "raw" / "3" / "clean.xlsx"
PROCESSED_DIR = _repo_root / "data" / "processed"
MASTER_CSV = PROCESSED_DIR / "security_master.csv"
AUDIT_CSV = PROCESSED_DIR / "security_audit_report.csv"
MAPPING_CSV = PROCESSED_DIR / "industry_mapping.csv"

# 人工定点修复：已确认的污染（002330.SZ 实为得利斯，A 股客观事实）
MANUAL_FIXES: dict[str, str] = {
    "002330.SZ": "得利斯",
}

# 启发式可疑：海外知名公司名（A 股主表不可能出现）
_SUSPICIOUS_NAMES = (
    "台积电",
    "苹果",
    "特斯拉",
    "微软",
    "谷歌",
    "亚马逊",
    "英伟达",
    "英特尔",
    "三星",
    "丰田",
    "大众",
    "波音",
    "可口可乐",
    "麦当劳",
    "IBM",
    "甲骨文",
    "脸书",
    "奈飞",
    "优步",
    "推特",
)
_SUSPICIOUS_LEN = 12  # A 股证券简称一般 ≤ 10 字


def _get_engine() -> Engine:
    return create_engine(
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        "?charset=utf8mb4",
        pool_pre_ping=True,
    )


# ── 权威源构建 ─────────────────────────────────────────────


def build_from_research_reports() -> dict[str, tuple[str, str]]:
    """研报权威名：wind_code → (sec_name, exchange)。

    取 publish_date 最新日期的名称（公司更名后研报名随之更新，
    旧众数逻辑会选中历史旧名，如 601211 的"国泰君安"→"国泰海通"）。
    最新日期并列时取众数。
    """
    if not (RAW_5_DIR / "rr_main_202605281537.csv").exists():
        log.warning("研报 CSV 缺失，跳过研报源")
        return {}
    rr = pd.read_csv(
        RAW_5_DIR / "rr_main_202605281537.csv",
        usecols=["sec_code", "sec_name", "exchange_code", "publish_date"],
        low_memory=False,
    )
    rr["sec_code"] = rr["sec_code"].astype(str).str.strip()
    rr["sec_name"] = rr["sec_name"].astype(str).str.strip()
    suffix = {"XSHG": ".SH", "XSHE": ".SZ", "XBEI": ".BJ"}
    rr["wind_code"] = rr["sec_code"].str.zfill(6) + rr["exchange_code"].map(
        suffix
    ).fillna("")
    rr = rr[rr["wind_code"].str.endswith((".SH", ".SZ", ".BJ"))]
    rr = rr[rr["sec_name"].notna() & (rr["sec_name"] != "") & (rr["sec_name"] != "nan")]
    result: dict[str, tuple[str, str]] = {}
    for wc, grp in rr.groupby("wind_code"):
        latest = grp[grp["publish_date"] == grp["publish_date"].max()]
        mode = latest["sec_name"].mode()
        name = mode.iloc[0] if not mode.empty else latest["sec_name"].iloc[0]
        exchange = (
            latest["exchange_code"].mode().iloc[0]
            if not latest["exchange_code"].mode().empty
            else ""
        )
        result[wc] = (name, exchange)
    log.info("研报权威名(最新日期): %d 家", len(result))
    return result


def _norm_brief(s: str) -> str:
    """公告简称归一化：去空格/全角空格/（代码）后缀，全角字母转半角。"""
    s = s.replace(" ", "").replace("　", "")
    s = re.sub(r"[（(]\d{6}[）)]", "", s)
    # 全角字母/数字 → 半角（如"粤宏远Ａ"→"粤宏远A"）
    s = "".join(
        chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in s
    )
    return s.strip()


def build_from_announcements() -> dict[str, str]:
    """公告标题简称：wind_code → 简称（众数优先，已归一化）。"""
    if not RAW_3_XLSX.exists():
        log.warning("公告 xlsx 缺失，跳过公告源")
        return {}
    df = pd.read_excel(RAW_3_XLSX, sheet_name="Sheet2")
    df["wc"] = df["s_info_windcode"].astype(str).str.strip().str.upper()

    def _brief(t):
        m = re.match(r"^([^:：]{1,20}?)[:：]", str(t).strip())
        return _norm_brief(m.group(1)) if m else None

    df["brief"] = df["n_info_title"].apply(_brief)
    df = df[df["brief"].notna() & (df["brief"] != "")]
    result: dict[str, str] = {}
    for wc, grp in df.groupby("wc"):
        mode = grp["brief"].mode()
        result[wc] = mode.iloc[0] if not mode.empty else grp["brief"].iloc[0]
    log.info("公告权威名: %d 家", len(result))
    return result


# ── 审计 ───────────────────────────────────────────────────


def _strip_st(s: str) -> str:
    """去掉 ST/*ST/S 前缀，用于同公司不同简称状态比较。"""
    return re.sub(r"^(\*ST|ST|SST|S)\*?", "", s or "")


def _selection_reason(status: str, is_placeholder: bool) -> str:
    """审计选择原因（P1-4，可核验）。"""
    reasons = {
        "ok_rr": "研报权威名与现有一致",
        "ok_ann": "公告简称与现有一致（归一化）",
        "ok_manual": "人工定点修复已生效",
        "manual_fix": "人工确认污染，采用权威名",
        "fill_placeholder": "占位名称被权威源覆盖",
        "conflict_review": "归一化后仍冲突，保留现有（不选任一候选）",
        "suspicious": "启发式可疑，仅人工定点修复",
        "unverified": (
            "占位名留空待审" if is_placeholder else "无权威源，保留现有名称（低置信）"
        ),
    }
    return reasons.get(status, "")


def audit(
    mapping_df: pd.DataFrame,
    rr_names: dict[str, tuple[str, str]],
    ann_names: dict[str, str],
) -> pd.DataFrame:
    """逐行分类现状 vs 权威源，产出审计报告。"""
    rows = []
    for _, r in mapping_df.iterrows():
        wc = str(r.get("wind_code", "")).strip().upper()
        cur = str(r.get("stock_name", "") or "").strip()
        rr = rr_names.get(wc)
        ann = ann_names.get(wc)
        master: str | None = None
        source: str | None = None
        status = ""

        is_placeholder = cur == wc
        if rr:
            master, _ = rr
            source = "research_reports"
            status = (
                "ok_rr"
                if cur == master
                else ("fill_placeholder" if is_placeholder else "conflict_review")
            )
        elif ann:
            master = ann
            source = "announcements"
            if is_placeholder:
                status = "fill_placeholder"
            elif cur == ann or _strip_st(cur) == _strip_st(ann):
                status = "ok_ann"
            else:
                status = "conflict_review"
        elif wc in MANUAL_FIXES:
            master = MANUAL_FIXES[wc]
            source = "manual_review"
            status = "manual_fix" if cur != master else "ok_manual"
        elif is_placeholder:
            status = "unverified"  # 无权威源，保留占位
        else:
            suspicious = (
                any(kw in cur for kw in _SUSPICIOUS_NAMES) or len(cur) > _SUSPICIOUS_LEN
            )
            status = "suspicious" if suspicious else "unverified"

        rows.append(
            {
                "wind_code": wc,
                "current_sec_name": cur,
                "master_sec_name": master or "",
                "source": source or "",
                "status": status,
                # P1-4：候选值与选择原因（审计可核验）
                "candidates": "、".join(
                    filter(None, [rr[0] if rr else "", ann if ann else ""])
                ),
                "selection_reason": _selection_reason(status, is_placeholder),
                "fixable": status in ("fill_placeholder", "manual_fix"),
            }
        )
    audit_df = pd.DataFrame(rows)
    log.info("审计分类: %s", audit_df["status"].value_counts().to_dict())
    return audit_df


# ── 执行 ───────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(description="证券主数据审计与修复")
    p.add_argument("--apply", action="store_true", help="执行幂等修复（默认仅审计）")
    args = p.parse_args()

    rr_names = build_from_research_reports()
    ann_names = build_from_announcements()

    mapping_df = pd.read_csv(MAPPING_CSV)
    mapping_df["wind_code"] = (
        mapping_df["wind_code"].astype(str).str.strip().str.upper()
    )
    audit_df = audit(mapping_df, rr_names, ann_names)

    # 主表（P1-4 三类策略）：
    #   approved/fixable → 权威名称
    #   unverified 非占位 → 保留现有名称（低置信来源标记）
    #   unverified 占位 → 中性占位（代码）+ quality_flag=name_unverified（留空待审）
    #   conflict_review → 保留现有名称 + quality_flag=name_conflict（核验修订：
    #     冲突不自动选任一候选——此前主表用了 master_sec_name，与策略相反）
    master_rows = []
    for _, r in audit_df.iterrows():
        wc = r["wind_code"]
        cur = r["current_sec_name"]
        status = r["status"]
        if status == "unverified" and cur == wc:
            name = wc  # 中性占位（新库插入时不选择任一候选）
            qflag = "name_unverified"
            src = "unverified"
        elif status == "conflict_review":
            name = cur  # 保留现状，不选任一冲突候选
            qflag = "name_conflict"
            src = r["source"] or "unverified"
        else:
            name = r["master_sec_name"] or cur
            qflag = ""
            src = r["source"] or ("unverified")
        master_rows.append(
            {
                "wind_code": wc,
                "sec_name": name,
                "exchange": _exchange_from_wind(wc),
                "as_of": date.today().isoformat(),
                "source": src,
                "quality_flag": qflag,
            }
        )
    master_df = pd.DataFrame(master_rows)
    MASTER_CSV.parent.mkdir(parents=True, exist_ok=True)
    master_df.to_csv(MASTER_CSV, index=False, encoding="utf-8-sig")
    audit_df.to_csv(AUDIT_CSV, index=False, encoding="utf-8-sig")
    log.info("主表: %s (%d 行)", MASTER_CSV, len(master_df))
    log.info("审计报告: %s", AUDIT_CSV)

    if not args.apply:
        fixable = audit_df[audit_df["fixable"]]
        log.info(
            "可修复 %d 行（fill_placeholder + manual_fix）——加 --apply 执行",
            len(fixable),
        )
        print(
            fixable[["wind_code", "current_sec_name", "master_sec_name", "source"]]
            .head(10)
            .to_string()
        )
        return

    # ── 幂等修复 ──
    engine = _get_engine()
    changes = 0
    with engine.begin() as conn:
        for _, r in audit_df[audit_df["fixable"]].iterrows():
            new_name = r["master_sec_name"]
            before = conn.execute(
                text(
                    "SELECT sec_name FROM companies "
                    "WHERE wind_code = :wc AND is_latest = 1"
                ),
                {"wc": r["wind_code"]},
            ).scalar()
            if before == new_name:
                continue
            conn.execute(
                text(
                    "UPDATE companies SET sec_name = :new, updated_at = UTC_TIMESTAMP() "
                    "WHERE wind_code = :wc AND is_latest = 1"
                ),
                {"new": new_name, "wc": r["wind_code"]},
            )
            log.info(
                "修复 %s: %r → %r (source=%s)",
                r["wind_code"],
                before,
                new_name,
                r["source"],
            )
            changes += 1
    log.info("修复完成，共 %d 条", changes)


def _exchange_from_wind(wind_code: str) -> str | None:
    """wind_code 后缀 → 交易所代码（与 import_data.py 一致）。"""
    if wind_code.endswith(".SH"):
        return "SH"
    if wind_code.endswith(".SZ"):
        return "SZ"
    if wind_code.endswith(".BJ"):
        return "BJ"
    return None


if __name__ == "__main__":
    main()
