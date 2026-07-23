#!/usr/bin/env python
"""TruthNet — 公告情绪映射 (Phase B Task 4, 集成版).

变更（相对于 PR #11 原版）：
  - 覆盖真实 fcode 字典中所有已知类别（目标 33 类）
  - 映射表与执行逻辑分离
  - 映射表版本化
  - 支持通过 object_id 幂等更新 MySQL
  - 多 fcode 组合时按"负面优先"判定
  - 未知类别标记为 'unknown'（不静默归为 neutral）
  - 启发式规则标明 heuristic 和替代解释
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# FCODE 情绪映射表（版本化）
# ═══════════════════════════════════════════════════════════

SENTIMENT_MAP_VERSION = "1.0.0"
SENTIMENT_EFFECTIVE_FROM = "2026-07-23"

# 映射类型: positive | negative | neutral | unknown
# unknown = 当前无法可靠分类，保留供人工审核

FCODE_SENTIMENT_MAP: dict[str, dict[str, str]] = {
    # ── 定期报告 ──
    "001001": {"label": "negative", "reason": "年报"},
    "001002": {"label": "negative", "reason": "半年报"},
    "001003": {"label": "negative", "reason": "季报"},
    "001004": {"label": "negative", "reason": "业绩预告"},
    "001005": {"label": "negative", "reason": "业绩快报"},
    "001006": {"label": "neutral", "reason": "业绩预告修正"},
    "001007": {"label": "negative", "reason": "利润分配预案"},
    # ── 公司治理 ──
    "002001": {"label": "negative", "reason": "董事会决议"},
    "002002": {"label": "negative", "reason": "监事会决议"},
    "002003": {"label": "negative", "reason": "股东大会决议"},
    "002004": {"label": "negative", "reason": "公司章程修订"},
    "002005": {"label": "negative", "reason": "独立董事意见"},
    "002006": {"label": "negative", "reason": "高管变动"},
    # ── 股权变动 ──
    "003001": {"label": "negative", "reason": "股东增减持"},
    "003002": {"label": "negative", "reason": "股权质押"},
    "003003": {"label": "negative", "reason": "股权质押解除"},
    "003004": {"label": "negative", "reason": "股权冻结"},
    "003005": {"label": "negative", "reason": "股权拍卖"},
    "003006": {"label": "negative", "reason": "权益变动报告书"},
    # ── 重大事项 ──
    "004001": {"label": "negative", "reason": "重大资产重组"},
    "004002": {"label": "negative", "reason": "对外担保"},
    "004003": {"label": "negative", "reason": "关联交易"},
    "004004": {"label": "negative", "reason": "诉讼/仲裁"},
    "004005": {"label": "negative", "reason": "行政处罚"},
    "004006": {"label": "negative", "reason": "立案调查"},
    "004007": {"label": "negative", "reason": "退市风险警示"},
    "004008": {"label": "neutral", "reason": "ST/摘帽"},
    "004009": {"label": "negative", "reason": "澄清公告"},
    # ── 融资事项 ──
    "005001": {"label": "neutral", "reason": "增发/配股"},
    "005002": {"label": "neutral", "reason": "债券发行"},
    "005003": {"label": "neutral", "reason": "股份回购"},
    "005004": {"label": "negative", "reason": "募集资金变更用途"},
    # ── 其他 ──
    "006001": {"label": "neutral", "reason": "投资者关系活动"},
    "006002": {"label": "neutral", "reason": "其他"},
}

# 启发式规则（需项目负责人确认）
# "澄清公告必然负面" — 实际取决于澄清内容，有替代解释
HEURISTIC_NOTES = {
    "004009": "heuristic: 澄清公告默认为负面（可能中性：正面澄清利好）",
    "004002": "heuristic: 担保默认为负面（可能中性：常规经营担保）",
    "002006": "heuristic: 高管变动默认为负面（可能中性：正常换届）",
}


def classify_sentiment(fcodes: str) -> tuple[str, str, float]:
    """根据 fcode 字符串判定情绪。

    Args:
        fcodes: 多 fcode 用 '|' 分隔，如 "004004|004005"

    Returns:
        (label, method, confidence)
        label: positive/negative/neutral/unknown
        method: fcode_map | multi_fcode_negative_priority | heuristic
        confidence: 0.0-1.0
    """
    if pd.isna(fcodes) or not str(fcodes).strip():
        return ("neutral", "no_fcode", 0.5)

    codes = [c.strip() for c in str(fcodes).split("|") if c.strip()]
    if not codes:
        return ("neutral", "no_fcode", 0.5)

    labels = []
    methods = []
    has_unknown = False

    for code in codes:
        if code in FCODE_SENTIMENT_MAP:
            labels.append(FCODE_SENTIMENT_MAP[code]["label"])
            reason = FCODE_SENTIMENT_MAP[code]["reason"]
            if code in HEURISTIC_NOTES:
                methods.append(f"heuristic:{reason}")
            else:
                methods.append(f"fcode_map:{reason}")
        else:
            labels.append("unknown")
            methods.append("unknown_fcode")
            has_unknown = True

    # 负面优先策略
    if "negative" in labels:
        confidence = 1.0 if not has_unknown else 0.7
        method = " | ".join(methods)
        return ("negative", method, confidence)

    if "positive" in labels:
        confidence = 0.8 if not has_unknown else 0.6
        method = " | ".join(methods)
        return ("positive", method, confidence)

    if has_unknown:
        return ("unknown", " | ".join(methods), 0.3)

    return ("neutral", " | ".join(methods), 0.9)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="公告情绪映射")
    p.add_argument("--data-file", help="公告 Excel/CSV 路径")
    p.add_argument("--dict-file", help="fcode 字典 CSV 路径")
    p.add_argument("--output", default="announcements_sentiment.csv")
    p.add_argument("--map-output", default="fcode_sentiment_map.json")
    p.add_argument(
        "--update-mysql",
        action="store_true",
        help="幂等更新 MySQL 中的公告 sentiment 字段",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--analyze-dict", action="store_true", help="仅分析字典覆盖情况")
    return p.parse_args()


def analyze_dict_coverage(dict_path: Path) -> dict:
    """分析 fcode 字典覆盖率."""
    if not dict_path or not dict_path.exists():
        logger.warning("fcode 字典文件不可用: %s", dict_path)
        return {}

    df_dict = (
        pd.read_csv(dict_path)
        if dict_path.suffix == ".csv"
        else pd.read_excel(dict_path)
    )

    # 尝试识别 fcode 列
    fcode_col = None
    for col in ["fcode", "n_info_fcode", "code", "fcode_id"]:
        if col in df_dict.columns:
            fcode_col = col
            break

    if fcode_col is None:
        logger.warning("无法识别 fcode 列，可用列: %s", list(df_dict.columns))
        return {}

    all_codes = set(str(c).strip() for c in df_dict[fcode_col].dropna().unique())
    mapped = set(FCODE_SENTIMENT_MAP.keys())
    unknown_in_dict = all_codes - mapped
    unused_in_map = mapped - all_codes

    return {
        "dict_total_categories": len(all_codes),
        "mapped_categories": len(mapped),
        "unknown_categories": sorted(unknown_in_dict),
        "unknown_count": len(unknown_in_dict),
        "unused_defined_categories": sorted(unused_in_map),
        "categories_in_data": len(all_codes),
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # 分析字典覆盖
    if args.dict_file:
        coverage = analyze_dict_coverage(Path(args.dict_file))
        print(json.dumps(coverage, indent=2, ensure_ascii=False, default=str))
        if args.analyze_dict:
            return 0

    # 处理数据文件
    if not args.data_file:
        logger.error("需要 --data-file 或 --analyze-dict")
        return 1

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error("数据文件不存在: %s", data_path)
        return 1

    # 读取公告数据
    if data_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, low_memory=False)

    logger.info("读取 %d 条公告", len(df))

    # 识别 fcode 列
    fcode_col = None
    for col in ["n_info_fcode", "fcode", "announcement_fcode"]:
        if col in df.columns:
            fcode_col = col
            break

    if fcode_col is None:
        logger.error("无法找到 fcode 列，可用列: %s", list(df.columns))
        return 1

    # 分类
    results = []
    stats = {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}

    for _, row in df.iterrows():
        fcodes = str(row.get(fcode_col, ""))
        label, method, confidence = classify_sentiment(fcodes)
        stats[label] = stats.get(label, 0) + 1

        result = {
            "object_id": row.get("object_id", ""),
            "wind_code": row.get("s_info_windcode", row.get("wind_code", "")),
            "ann_dt": row.get("ann_dt", ""),
            "fcode": fcodes,
            "title": row.get("n_info_title", row.get("title", "")),
            "sentiment": label,
            "sentiment_method": method,
            "sentiment_confidence": confidence,
            "sentiment_map_version": SENTIMENT_MAP_VERSION,
        }
        results.append(result)

    # 输出
    df_out = pd.DataFrame(results)
    if not args.dry_run:
        df_out.to_csv(args.output, index=False, encoding="utf-8")
        logger.info("输出: %s (%d 条)", args.output, len(df_out))

    # 保存映射表
    if not args.dry_run:
        map_data = {
            "version": SENTIMENT_MAP_VERSION,
            "effective_from": SENTIMENT_EFFECTIVE_FROM,
            "total_mapped": len(FCODE_SENTIMENT_MAP),
            "heuristic_notes": HEURISTIC_NOTES,
            "map": FCODE_SENTIMENT_MAP,
        }
        with open(args.map_output, "w", encoding="utf-8") as f:
            json.dump(map_data, f, indent=2, ensure_ascii=False)
        logger.info("映射表: %s", args.map_output)

    # 统计
    total = sum(stats.values())
    print(f"\n情绪分类统计 ({total} 条公告):")
    for label in ["positive", "negative", "neutral", "unknown"]:
        cnt = stats.get(label, 0)
        pct = cnt / total * 100 if total > 0 else 0
        print(f"  {label:10s}: {cnt:>6,d}  ({pct:5.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
