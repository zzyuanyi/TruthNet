#!/usr/bin/env python3
"""
TruthNet · 公告情绪映射 — 可复现脚本
======================================
Phase B 任务4：对 7,311 条公告按 fcode 类型标注情绪（positive/negative/neutral）。
29 类基础 fcode 全覆盖，多 fcode 组合按"负面优先"原则判定。

用法:
    python announcement_sentiment.py --data-file <公告Excel> --dict-file <字典txt>
    python announcement_sentiment.py --verify     # 仅验收检查

输出:
    .local/generated/announcements_sentiment.csv   # 标注结果
    .local/generated/fcode_sentiment_map.json      # 情绪映射表
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────

TRUTHNET_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = TRUTHNET_ROOT / ".local" / "generated"

# 由命令行 --data-file / --dict-file 参数指定（非 verify 模式必填）
DATA_FILE: Path | None = None
DICT_FILE: Path | None = None

# ═══════════════════════════════════════════════════════════
#  情绪映射表（版本 1.0.0）
#  29 类基础 fcode → positive / negative / neutral
#  判定依据：每类公告的金融含义
# ═══════════════════════════════════════════════════════════

FCODE_SENTIMENT: dict[str, str] = {
    # ── 正面（4类） ──
    "5107000000": "positive",   # 利润分配 — 分红回报股东
    "5219000000": "positive",   # 回购股权 — 公司回购彰显信心
    "5506050000": "positive",   # 重大合同 — 获得重要合同
    "5506220000": "positive",   # 员工持股 — 员工激励计划

    # ── 负面（9类） ──
    "5203000000": "negative",   # 质押冻结 — 股权质押/冻结，风险信号
    "5502010000": "negative",   # 特别处理 — ST/*ST 标记
    "5502040000": "negative",   # 终止上市 — 退市风险
    "5506040000": "negative",   # 风险提示 — 主动揭示风险
    "5506100000": "negative",   # 澄清公告 — 通常回应负面传闻
    "5506170000": "negative",   # 法律纠纷 — 涉及诉讼仲裁
    "5507060000": "negative",   # 违纪违规 — 监管处罚/整改
    "5507240000": "negative",   # 借贷担保 — 对外担保或有负债
    "5508000000": "negative",   # 函件 — 监管函/问询函

    # ── 中性（16类） ──
    "5230000000": "neutral",    # 权益变动 — 增减持方向不明
    "5404000000": "neutral",    # 补充更正 — 信息修正
    "5406000000": "neutral",    # 业绩预告 — 有预增有预减，Phase C 细化
    "5506010000": "neutral",    # 股东大会 — 常规治理程序
    "5506140000": "neutral",    # 停牌提示 — 例行提示
    "5506160000": "neutral",    # 中介公告 — 券商/审计等意见
    "5506180000": "neutral",    # 公司资料变更 — 常规变更
    "5506190000": "neutral",    # 个股其他公告 — 中性兜底
    "5506200000": "neutral",    # 其他补充更正
    "5507040000": "neutral",    # 关联交易 — 有正常也有异常
    "5507200000": "neutral",    # 股份增减持 — 增减持方向不同
    "5507210000": "neutral",    # 资金投向 — 需具体看
    "5507220000": "neutral",    # 资产重组 — 有利有弊
    "5507230000": "neutral",    # 收购兼并 — 效果待验证
    "5507260000": "neutral",    # 政策影响 — 利好/利空不明
    "5507270000": "neutral",    # 人事变动 — 性质中性
}

# ═══════════════════════════════════════════════════════════
#  情绪判定逻辑
# ═══════════════════════════════════════════════════════════

def classify_sentiment(fcode_str) -> tuple[str, str]:
    """根据 fcode 字符串（可能含多个 '|' 分隔）判定情绪。

    Args:
        fcode_str: 如 "5507060000" 或 "5507060000|5506190000"

    Returns:
        (sentiment, method) 元组
        sentiment: "positive" | "negative" | "neutral"
        method: 判定方式说明
    """
    if fcode_str is None or str(fcode_str).strip() == "" or str(fcode_str) == "nan":
        return "neutral", "fallback_empty"

    codes = str(fcode_str).split("|")
    sentiments = []
    unknown_codes = []

    for code in codes:
        code = code.strip()
        if code in FCODE_SENTIMENT:
            sentiments.append(FCODE_SENTIMENT[code])
        else:
            sentiments.append("neutral")
            unknown_codes.append(code)

    # 判定方法名
    if "negative" in sentiments:
        method = "rule_multi_negative_first"
    elif "positive" in sentiments:
        method = "rule_multi_positive"
    else:
        method = "rule_multi_neutral"

    if unknown_codes:
        method += f"_unknown_{len(unknown_codes)}"

    # 负面优先 → 正面次之 → 中性兜底
    if "negative" in sentiments:
        return "negative", method
    elif "positive" in sentiments:
        return "positive", method
    return "neutral", method


# ═══════════════════════════════════════════════════════════
#  加载 fcode 字典（仅用于展示，不参与判定）
# ═══════════════════════════════════════════════════════════

def load_fcode_dict() -> dict[str, str]:
    fcode_to_name = {}
    with open(DICT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 2 and parts[0].isdigit():
                fcode_to_name[parts[0]] = parts[1]
    return fcode_to_name


# ═══════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════

def run():
    import pandas as pd

    print("=" * 60)
    print("TruthNet · 公告情绪映射 (Phase B 任务4)")
    print("=" * 60)

    # ── 1. 加载数据 ──
    print(f"\n[1/4] 加载数据: {DATA_FILE}")
    df = pd.read_excel(DATA_FILE)
    print(f"       记录数: {len(df):,}  股票数: {df['s_info_windcode'].nunique():,}")

    # ── 2. 执行标注 ──
    print("\n[2/4] 执行情绪标注...")
    results = []
    for _, row in df.iterrows():
        sentiment, method = classify_sentiment(row["n_info_fcode"])
        results.append({
            "object_id": row["object_id"],
            "wind_code": row["s_info_windcode"],
            "ann_dt": str(row["ann_dt"]),
            "title": str(row["n_info_title"]),
            "fcode_raw": str(row["n_info_fcode"]),
            "sentiment": sentiment,
            "sentiment_method": method,
        })

    result_df = pd.DataFrame(results)

    # ── 3. 统计 ──
    print("\n[3/4] 统计结果:")
    dist = result_df["sentiment"].value_counts()
    for s in ["negative", "positive", "neutral"]:
        cnt = dist.get(s, 0)
        pct = cnt / len(result_df) * 100
        bar = "█" * int(pct / 2)
        print(f"       {s:10s} {cnt:>6,} ({pct:5.1f}%) {bar}")

    # fcode 覆盖率
    all_base_fcodes = set()
    for fc in df["n_info_fcode"].dropna():
        for c in str(fc).split("|"):
            all_base_fcodes.add(c.strip())
    covered = all_base_fcodes & set(FCODE_SENTIMENT.keys())
    uncovered = all_base_fcodes - set(FCODE_SENTIMENT.keys())
    print(f"       fcode 覆盖: {len(covered)}/{len(all_base_fcodes)} (未定义: {len(uncovered)})")
    if uncovered:
        print(f"       未定义: {uncovered}")

    # 判定方法分布
    print("\n       判定方法分布:")
    for m, c in result_df["sentiment_method"].value_counts().head(10).items():
        print(f"         {m}: {c:>6,}")

    # ── 4. 保存 ──
    print("\n[4/4] 保存结果...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "announcements_sentiment.csv"
    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"       → {csv_path}")

    map_path = OUTPUT_DIR / "fcode_sentiment_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0.0",
            "date": "2026-07-23",
            "total_fcodes_defined": len(FCODE_SENTIMENT),
            "total_records": len(result_df),
            "sentiment_distribution": {k: int(v) for k, v in dist.items()},
            "mapping": FCODE_SENTIMENT,
        }, f, ensure_ascii=False, indent=2)
    print(f"       → {map_path}")

    # ── 验收 ──
    print("\n" + "=" * 60)
    null_count = result_df["sentiment"].isna().sum()
    invalid = (~result_df["sentiment"].isin(["positive", "negative", "neutral"])).sum()
    total_ok = len(result_df) == 7311

    checks = [
        ("空值情绪 = 0", null_count == 0),
        ("非法值 = 0", invalid == 0),
        ("记录数 = 7,311", total_ok),
        ("29类 fcode 已定义", len(FCODE_SENTIMENT) >= 29),
    ]
    all_pass = True
    for label, ok in checks:
        status = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {status} {label}")

    # 字典定义的 fcode 覆盖率
    dict_map = load_fcode_dict()
    for code, name in sorted(dict_map.items()):
        mapped = FCODE_SENTIMENT.get(code, "NOT_DEFINED")
        cnt = (result_df["fcode_raw"].str.contains(code, regex=False, na=False)).sum()
        print(f"       {code} {name:12s} → {mapped:10s} (出现 {cnt:>5,} 次)")

    if all_pass:
        print("\n  验收结论: ALL PASS")
    else:
        print("\n  验收结论: SOME FAILED")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

def main():
    global DATA_FILE, DICT_FILE
    parser = argparse.ArgumentParser(description="TruthNet 公告情绪映射")
    parser.add_argument("--data-file", type=Path, default=None,
                        help="公告数据 Excel 文件路径 (如 赛题数据/3/clean.xlsx)")
    parser.add_argument("--dict-file", type=Path, default=None,
                        help="公告字典 txt 文件路径 (如 赛题数据/3/ditct.txt)")
    parser.add_argument("--verify", action="store_true", help="仅验收检查（读取已有 CSV）")
    args = parser.parse_args()

    if args.verify:
        _verify_only()
    else:
        if not args.data_file or not args.dict_file:
            print("错误: 非验证模式需要 --data-file 和 --dict-file 参数")
            sys.exit(1)
        DATA_FILE = args.data_file.resolve()
        DICT_FILE = args.dict_file.resolve()
        if not DATA_FILE.exists():
            print(f"错误: 找不到数据文件 {DATA_FILE}")
            sys.exit(1)
        if not DICT_FILE.exists():
            print(f"错误: 找不到字典文件 {DICT_FILE}")
            sys.exit(1)
        run()


def _verify_only():
    import pandas as pd

    csv_path = OUTPUT_DIR / "announcements_sentiment.csv"
    if not csv_path.exists():
        print(f"❌ 文件不存在: {csv_path}")
        print("   请先运行: python announcement_sentiment.py")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    print(f"读取: {csv_path} ({len(df):,} 条)")

    null_count = df["sentiment"].isna().sum()
    invalid = (~df["sentiment"].isin(["positive", "negative", "neutral"])).sum()

    print(f"  空值: {null_count} {'✅' if null_count == 0 else '❌'}")
    print(f"  非法: {invalid} {'✅' if invalid == 0 else '❌'}")

    dist = df["sentiment"].value_counts()
    for s in ["negative", "positive", "neutral"]:
        print(f"  {s}: {dist.get(s, 0):,}")

    if null_count == 0 and invalid == 0:
        print("验收通过 ✅")
    else:
        print("验收失败 ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
