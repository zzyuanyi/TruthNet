"""任务⑤：行业分类 akshare 补全
================================
从三表 CSV 提取所有股票代码 → 与研报已有行业匹配 →
缺失部分用 akshare 逐只查询 → 输出行业映射表 CSV

输出: data/processed/industry_mapping.csv
列: wind_code | stock_name | industry_l1 | industry_l2 | source
"""

import sys
import io
import re
import time
from pathlib import Path

import pandas as pd
import akshare as ak

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(r"d:\projects\TruthNet\data\raw\比赛数据")
OUTPUT_DIR = Path(r"d:\projects\TruthNet\data\processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 第一步：从三表 CSV 提取所有股票代码 ──
print("=" * 60)
print("Step 1: Extract all stock codes from 3 CSVs")
print("=" * 60)

codes_all = set()
for fname in ["asharebalancesheet_202605261517", "asharecashflow_202605261518", "ashareincome_202605261519"]:
    df = pd.read_csv(BASE / "4" / f"{fname}.csv", low_memory=False, usecols=["s_info_windcode"])
    codes_all.update(df["s_info_windcode"].dropna().unique())

# 只保留标准格式: 6位数字.SZ/SH/BJ
PATTERN = re.compile(r"^(\d{6})\.(SZ|SH|BJ)$")
standard_codes = {}
nonstandard_codes = []
for c in sorted(codes_all):
    m = PATTERN.match(c)
    if m:
        standard_codes[c] = m.group(1)  # wind_code → number part
    else:
        nonstandard_codes.append(c)

print(f"Total unique codes: {len(codes_all)}")
print(f"Standard (6-digit.SZ/SH/BJ): {len(standard_codes)}")
print(f"Non-standard: {len(nonstandard_codes)}")

# ── 第二步：从研报提取已有行业分类 ──
print("\n" + "=" * 60)
print("Step 2: Extract existing industry from research reports")
print("=" * 60)

df_rr = pd.read_csv(
    BASE / "5" / "rr_main_202605281537.csv",
    low_memory=False,
    usecols=["sec_code", "sec_name", "industry_l1", "industry_l2", "industry_l3"],
)
# 筛出有行业数据的研报行
df_rr_ind = df_rr[df_rr["industry_l1"].notna()].copy()
# 按 sec_code 去重，取第一条（通常行业分类一致）
df_rr_ind = df_rr_ind.drop_duplicates(subset="sec_code", keep="first")
# sec_code 是如 '600518' 的无后缀格式，补零对齐
df_rr_ind["sec_code"] = df_rr_ind["sec_code"].astype(str).str.zfill(6)

print(f"Research reports with industry: {len(df_rr_ind)} unique securities")

# 构建映射: number_part → {name, l1, l2, l3}
report_map = {}
for _, row in df_rr_ind.iterrows():
    report_map[row["sec_code"]] = {
        "name": row["sec_name"],
        "l1": row["industry_l1"],
        "l2": row["industry_l2"],
        "l3": row["industry_l3"],
    }

# ── 第三步：找出缺失行业分类的股票 ──
print("\n" + "=" * 60)
print("Step 3: Identify stocks missing industry classification")
print("=" * 60)

# 也构建 level2→level1 的映射（从研报中学习 + 硬编码补充）
L2_TO_L1 = {}

# 先从研报中学习映射
for _, row in df_rr_ind.iterrows():
    if pd.notna(row["industry_l2"]) and pd.notna(row["industry_l1"]):
        L2_TO_L1[row["industry_l2"]] = row["industry_l1"]

# 关键补充（常见申万行业分类）
L2_TO_L1.update({
    "白酒Ⅱ": "食品饮料",
    "中药Ⅱ": "医药生物",
    "房地产开发": "房地产",
    "银行Ⅱ": "银行",
    "证券Ⅱ": "非银金融",
    "保险Ⅱ": "非银金融",
    "一般零售": "商贸零售",
    "基础建设": "建筑装饰",
    "轨交设备Ⅱ": "机械设备",
    "综合Ⅱ": "综合",
    "化学制药": "医药生物",
    "生物制品": "医药生物",
    "医疗器械": "医药生物",
    "医药商业": "医药生物",
    "医疗服务": "医药生物",
    "电力": "公用事业",
    "风电设备": "电力设备",
    "光伏设备": "电力设备",
    "电网设备": "电力设备",
    "电池": "电力设备",
    "半导体": "电子",
    "光学光电子": "电子",
    "消费电子": "电子",
    "元件": "电子",
    "软件开发": "计算机",
    "计算机设备": "计算机",
    "IT服务Ⅱ": "计算机",
    "通信设备": "通信",
    "通信服务": "通信",
    "化学纤维": "基础化工",
    "化学制品": "基础化工",
    "农化制品": "基础化工",
    "塑料": "基础化工",
    "橡胶": "基础化工",
    "钢铁": "钢铁",
    "工业金属": "有色金属",
    "贵金属": "有色金属",
    "小金属": "有色金属",
})

have_industry = set(report_map.keys())
need_akshare = []
already_have = []

for wind_code, number in sorted(standard_codes.items()):
    if number in have_industry:
        already_have.append((wind_code, number, report_map[number]))
    else:
        need_akshare.append((wind_code, number))

print(f"Already have industry (from reports): {len(already_have)}")
print(f"Need akshare query: {len(need_akshare)}")

# ── 第四步：用 akshare 逐只查询 ──
print("\n" + "=" * 60)
print(f"Step 4: Query akshare for {len(need_akshare)} stocks")
print("=" * 60)

akshare_results = {}
batch_size = 50
total = len(need_akshare)
success_count = 0
fail_count = 0
empty_count = 0

for i, (wind_code, number) in enumerate(need_akshare):
    try:
        info = ak.stock_individual_info_em(symbol=number)

        # 提取股票简称
        name_row = info[info["item"] == "股票简称"]
        name = name_row["value"].values[0] if len(name_row) > 0 else ""

        # 提取行业 (申万二级)
        ind_row = info[info["item"] == "行业"]
        industry_l2 = ind_row["value"].values[0] if len(ind_row) > 0 else ""

        if industry_l2 and industry_l2 != "-":
            industry_l1 = L2_TO_L1.get(industry_l2, "")
            akshare_results[wind_code] = {
                "wind_code": wind_code,
                "number": number,
                "name": name,
                "industry_l1": industry_l1,
                "industry_l2": industry_l2,
                "source": "akshare",
            }
            # 顺带补充 level2→level1 映射
            if industry_l1 and industry_l2 not in L2_TO_L1:
                L2_TO_L1[industry_l2] = industry_l1
            success_count += 1
        else:
            akshare_results[wind_code] = {
                "wind_code": wind_code,
                "number": number,
                "name": name,
                "industry_l1": "",
                "industry_l2": "",
                "source": "akshare_empty",
            }
            empty_count += 1

    except Exception as e:
        akshare_results[wind_code] = {
            "wind_code": wind_code,
            "number": number,
            "name": "",
            "industry_l1": "",
            "industry_l2": "",
            "source": f"akshare_error",
        }
        fail_count += 1

    # 进度打印
    if (i + 1) % 200 == 0 or (i + 1) == total:
        print(
            f"  Progress: {i+1}/{total} | "
            f"success={success_count} empty={empty_count} fail={fail_count}"
        )

    # 小幅延时，避免被封
    if (i + 1) % 20 == 0:
        time.sleep(0.5)

print(f"\nQuery complete:")
print(f"  Success (with industry): {success_count}")
print(f"  Empty (industry='-'):    {empty_count}")
print(f"  Error:                   {fail_count}")

# ── 第五步：合并所有结果并输出 ──
print("\n" + "=" * 60)
print("Step 5: Merge & export industry mapping")
print("=" * 60)

rows = []

# 来自研报的
for wind_code, number, info in already_have:
    rows.append({
        "wind_code": wind_code,
        "stock_name": info.get("name", ""),
        "industry_l1": info.get("l1", ""),
        "industry_l2": info.get("l2", ""),
        "industry_l3": info.get("l3", ""),
        "source": "research_report",
    })

# 来自 akshare
for wind_code, info in sorted(akshare_results.items()):
    rows.append({
        "wind_code": wind_code,
        "stock_name": info.get("name", ""),
        "industry_l1": info.get("industry_l1", ""),
        "industry_l2": info.get("industry_l2", ""),
        "industry_l3": "",
        "source": info.get("source", "akshare"),
    })

df_out = pd.DataFrame(rows)
df_out = df_out.sort_values("wind_code").reset_index(drop=True)

# 统计
total = len(df_out)
has_ind = (df_out["industry_l1"].notna() & (df_out["industry_l1"] != "")).sum()
print(f"Total records: {total}")
print(f"With industry_l1: {has_ind} ({has_ind/total*100:.1f}%)")
print(f"Sources breakdown:")
print(df_out["source"].value_counts().to_string())

# 保存
output_path = OUTPUT_DIR / "industry_mapping.csv"
df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"\nSaved to: {output_path}")

# 另存一份 JSON 方便阅读
output_json = OUTPUT_DIR / "industry_mapping.json"
df_out.to_json(output_json, orient="records", force_ascii=False, indent=2)
print(f"Saved to: {output_json}")

# ── 第六步：统计缺失 level1 且 level2 存在的，尝试补充映射 ──
print("\n" + "=" * 60)
print("Step 6: Check remaining gaps")
print("=" * 60)

missing_l1 = df_out[
    (df_out["industry_l1"].isna() | (df_out["industry_l1"] == "")) &
    (df_out["industry_l2"].notna() & (df_out["industry_l2"] != ""))
]
if len(missing_l1) > 0:
    unique_l2_missing = missing_l1["industry_l2"].unique()
    print(f"Missing level1 but have level2: {len(missing_l1)} records")
    print(f"Unique level2 without level1 mapping: {list(unique_l2_missing)}")
else:
    print("All records with level2 also have level1 mapping. Good!")

print("\nDone! Task 5 complete.")
