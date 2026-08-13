#!/usr/bin/env python
"""补齐 companies 表中缺失的行业分类（industry_l1 / industry_l2）。

数据源：eastmoney push2 接口（curl 直连，规避 Python requests 的 TLS 兼容问题）
  - clist 全市场列表 f100 = 申万二级行业
  - 二级 → 一级 映射：优先用 industry_mapping.csv 现有映射，缺失时用硬编码补充
兜底：股票名称关键词推断（离线）

用法：
  python scripts/fill_missing_industry.py --dry-run    # 只统计，不写库
  python scripts/fill_missing_industry.py              # 实际写入 MySQL + 重生成 CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

import pymysql

REPO = Path(__file__).resolve().parent.parent
ENV = {}
for _line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        ENV[_k.strip()] = _v.strip()

CLIST_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"  # 沪深主板 + 创业板 + 科创板
CLIST_FIELDS = "f12,f14,f100"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _fetch(url: str, retries: int = 4) -> dict | None:
    """curl 拉取 eastmoney JSON，空响应/失败时退避重试."""
    for attempt in range(retries):
        r = subprocess.run(
            ["curl", "-s", "-m", "25", url, "-H", f"User-Agent: {UA}",
             "-H", "Referer: https://quote.eastmoney.com/"],
            capture_output=True,
        )
        raw = r.stdout.decode("utf-8", "ignore").strip()
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        time.sleep(1.5 * (attempt + 1))
    return None


def market_for(wc: str) -> str:
    """根据 wind_code 推断 eastmoney market 前缀（1=沪 0=深/北）."""
    wc = (wc or "").strip()
    if wc.endswith(".SH"):
        return "1"
    if wc.endswith((".SZ", ".BJ")):
        return "0"
    digits = "".join(ch for ch in wc if ch.isdigit())
    return "1" if digits.startswith("6") else "0"


def fetch_missing_l2(missing: list[dict]) -> dict[str, str]:
    """批量查询缺失股票的申万二级行业 f100，返回 code(6位) -> l2."""
    code2l2: dict[str, str] = {}
    batch = 60
    for i in range(0, len(missing), batch):
        chunk = missing[i : i + batch]
        secids = ",".join(
            f"{market_for(m['wc'])}.{bare_code(m['wc'])}" for m in chunk
        )
        url = (
            "https://push2.eastmoney.com/api/qt/ulist.np/get"
            f"?secids={secids}&fields=f12,f14,f100&fltt=2&invt=2"
        )
        d = _fetch(url)
        if d is not None and "data" in d and d["data"] is not None:
            diff = d["data"].get("diff") or []
            items = diff.items() if isinstance(diff, dict) else enumerate(diff)
            for _, it in items:
                code = str(it.get("f12", ""))
                l2 = it.get("f100", "")
                if code:
                    code2l2[code] = l2 or ""
        else:
            print(f"  [warn] batch {i // batch} fetch failed", file=sys.stderr)
        if (i // batch + 1) % 5 == 0:
            print(f"  已查询 {min(i + batch, len(missing))}/{len(missing)}", file=sys.stderr)
        time.sleep(1.2)
    return code2l2


def norm_l2(s: str) -> str:
    """归一化申万二级名称（去掉 Ⅱ/III 后缀等）."""
    for ch in ("Ⅱ", "II", "Ⅲ", "III", "I"):
        s = s.replace(ch, "")
    return s.strip()


def build_l2l1_map() -> dict[str, str]:
    """二级 -> 一级 映射：权威申万映射优先，CSV 仅兜底（key 归一化去 Ⅱ 后缀）."""
    l2l1: dict[str, str] = {}
    for k, v in SW_L2_TO_L1_SUPPLEMENT.items():
        k = norm_l2(k)
        if k:
            l2l1[k] = v
    with open(REPO / "data" / "processed" / "industry_mapping.csv",
              encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            l1 = (row.get("industry_l1") or "").strip()
            l2 = norm_l2(row.get("industry_l2") or "")
            if l1 and l2 and l2 not in l2l1:
                l2l1[l2] = l1
    return l2l1


# 申万二级 -> 一级（仅补充 CSV 未覆盖的；一级名称与现有数据保持一致）
SW_L2_TO_L1_SUPPLEMENT = {
    "种植业": "农林牧渔", "渔业": "农林牧渔", "林业": "农林牧渔", "饲料": "农林牧渔",
    "农产品加工": "农林牧渔", "养殖业": "农林牧渔", "动物保健": "农林牧渔",
    "化学原料": "基础化工", "化学制品": "基础化工", "化学纤维": "基础化工",
    "塑料": "基础化工", "橡胶": "基础化工", "农化制品": "基础化工",
    "非金属材料": "基础化工", "油气开采": "石油石化", "油服工程": "石油石化",
    "炼化及贸易": "石油石化", "普钢": "钢铁", "特钢": "钢铁", "冶钢原料": "钢铁",
    "煤炭开采": "煤炭", "焦炭": "煤炭", "金属新材料": "有色金属",
    "工业金属": "有色金属", "贵金属": "有色金属", "小金属": "有色金属",
    "能源金属": "有色金属", "半导体": "电子", "元件": "电子", "光学光电子": "电子",
    "消费电子": "电子", "电子化学品": "电子", "其他电子": "电子",
    "白色家电": "家用电器", "黑色家电": "家用电器", "小家电": "家用电器",
    "厨卫电器": "家用电器", "照明设备": "家用电器", "家电零部件": "家用电器",
    "其他家电": "家用电器", "白酒": "食品饮料", "非白酒": "食品饮料",
    "饮料乳品": "食品饮料", "休闲食品": "食品饮料", "调味发酵品": "食品饮料",
    "食品加工": "食品饮料", "保健品": "食品饮料", "纺织制造": "纺织服饰",
    "服装家纺": "纺织服饰", "饰品": "纺织服饰", "造纸": "轻工制造",
    "包装印刷": "轻工制造", "家居用品": "轻工制造", "文娱用品": "轻工制造",
    "化学制药": "医药生物", "中药": "医药生物", "生物制品": "医药生物",
    "医药商业": "医药生物", "医疗器械": "医药生物", "医疗服务": "医药生物",
    "化学原料药": "医药生物", "电力": "公用事业", "燃气": "公用事业",
    "水务": "公用事业", "铁路公路": "交通运输", "航空机场": "交通运输",
    "航运港口": "交通运输", "公交": "交通运输", "房地产开发": "房地产",
    "房地产服务": "房地产", "一般零售": "商贸零售", "专业连锁": "商贸零售",
    "贸易": "商贸零售", "互联网电商": "商贸零售", "旅游及景区": "社会服务",
    "酒店餐饮": "社会服务", "教育": "社会服务", "专业服务": "社会服务",
    "体育": "社会服务", "综合": "综合", "水泥": "建筑材料", "玻璃玻纤": "建筑材料",
    "装修建材": "建筑材料", "耐火材料": "建筑材料", "房屋建设": "建筑装饰",
    "基础建设": "建筑装饰", "专业工程": "建筑装饰", "工程咨询服务": "建筑装饰",
    "装饰园林": "建筑装饰", "电机": "电力设备", "电网设备": "电力设备",
    "电池": "电力设备", "光伏设备": "电力设备", "风电设备": "电力设备",
    "其他电源设备": "电力设备", "通用设备": "机械设备", "专用设备": "机械设备",
    "轨交设备": "机械设备", "工程机械": "机械设备", "自动化设备": "机械设备",
    "农用机械": "机械设备", "航天装备": "国防军工", "航空装备": "国防军工",
    "地面兵装": "国防军工", "航海装备": "国防军工", "军工电子": "国防军工",
    "汽车整车": "汽车", "汽车零部件": "汽车", "汽车服务": "汽车",
    "摩托车": "汽车", "计算机设备": "计算机", "软件开发": "计算机",
    "IT服务": "计算机", "游戏": "传媒", "广告营销": "传媒", "影视院线": "传媒",
    "数字媒体": "传媒", "社交": "传媒", "出版": "传媒", "通信设备": "通信",
    "通信服务": "通信", "国有大型银行": "银行", "股份制银行": "银行",
    "城商行": "银行", "农商行": "银行", "其他银行": "银行", "证券": "非银金融",
    "保险": "非银金融", "多元金融": "非银金融", "环境治理": "环保",
    "环保设备": "环保", "个护用品": "美容护理", "化妆品": "美容护理",
    "医疗美容": "美容护理",
    # 补充：CSV/研报未覆盖的二级
    "电视广播": "传媒", "旅游零售": "商贸零售", "装修装饰": "建筑装饰",
    "农业综合": "农林牧渔",
}

# 名称关键词 -> 一级行业（兜底，顺序匹配）
_NAME_KEYWORDS = [
    ("银行", "银行"), ("保险", "非银金融"), ("证券", "非银金融"), ("信托", "非银金融"),
    ("期货", "非银金融"), ("地产", "房地产"), ("置业", "房地产"),
    ("钢铁", "钢铁"), ("煤炭", "煤炭"), ("煤业", "煤炭"), ("能源", "煤炭"),
    ("石油", "石油石化"), ("石化", "石油石化"), ("化工", "基础化工"),
    ("化学", "基础化工"), ("化肥", "基础化工"), ("医药", "医药生物"),
    ("制药", "医药生物"), ("生物", "医药生物"), ("药业", "医药生物"),
    ("医疗", "医药生物"), ("电力", "公用事业"), ("水电", "公用事业"),
    ("水务", "公用事业"), ("燃气", "公用事业"), ("环保", "环保"),
    ("建筑", "建筑装饰"), ("建设", "建筑装饰"), ("建材", "建筑材料"),
    ("水泥", "建筑材料"), ("玻璃", "建筑材料"), ("汽车", "汽车"),
    ("航空", "交通运输"), ("机场", "交通运输"), ("铁路", "交通运输"),
    ("高速", "交通运输"), ("港口", "交通运输"), ("物流", "交通运输"),
    ("航运", "交通运输"), ("食品", "食品饮料"), ("饮料", "食品饮料"),
    ("酒", "食品饮料"), ("乳", "食品饮料"), ("农业", "农林牧渔"),
    ("种业", "农林牧渔"), ("林业", "农林牧渔"), ("渔业", "农林牧渔"),
    ("牧业", "农林牧渔"), ("通信", "通信"), ("计算机", "计算机"),
    ("软件", "计算机"), ("数据", "计算机"), ("电子", "电子"),
    ("半导体", "电子"), ("芯片", "电子"), ("光电", "电子"),
    ("传媒", "传媒"), ("影视", "传媒"), ("广告", "传媒"), ("文化", "传媒"),
    ("军工", "国防军工"), ("国防", "国防军工"), ("航天", "国防军工"),
    ("航空装备", "国防军工"), ("机械", "机械设备"), ("重工", "机械设备"),
    ("电器", "电力设备"), ("电气", "电力设备"), ("新能源", "电力设备"),
    ("电池", "电力设备"), ("光伏", "电力设备"), ("风电", "电力设备"),
    ("家电", "家用电器"), ("纺织", "纺织服饰"), ("服装", "纺织服饰"),
    ("旅游", "社会服务"), ("酒店", "社会服务"), ("商贸", "商贸零售"),
    ("零售", "商贸零售"), ("百货", "商贸零售"), ("有色", "有色金属"),
    ("黄金", "有色金属"), ("金属", "有色金属"), ("轻工", "轻工制造"),
    ("造纸", "轻工制造"), ("包装", "轻工制造"), ("家居", "轻工制造"),
    ("矿山", "有色金属"), ("资源", "有色金属"), ("新材", "建筑材料"),
]


def infer_by_name(name: str) -> str | None:
    if not name:
        return None
    for kw, l1 in _NAME_KEYWORDS:
        if kw in name:
            return l1
    return None


def _db():
    return pymysql.connect(
        host=ENV.get("MYSQL_HOST", "localhost"),
        port=int(ENV.get("MYSQL_PORT", 3306)),
        user=ENV.get("MYSQL_USER"),
        password=ENV.get("MYSQL_PASSWORD"),
        database=ENV.get("MYSQL_DATABASE"),
        charset="utf8mb4",
    )


def load_missing(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT wind_code, sec_name, industry_source FROM companies "
        "WHERE industry_l1 IS NULL OR industry_l1 = '' ORDER BY wind_code"
    )
    rows = [
        {"wc": r[0], "name": r[1], "src": r[2]} for r in cur.fetchall()
    ]
    return rows


def reconcile_l1(conn, l2l1: dict[str, str]) -> int:
    """用权威映射校正所有公司 industry_l1（基于 industry_l2 重推导）."""
    cur = conn.cursor()
    cur.execute(
        "SELECT wind_code, industry_l2, industry_l1 FROM companies "
        "WHERE industry_l2 IS NOT NULL AND industry_l2 != '' AND industry_l2 != '-'"
    )
    fixed = 0
    for wc, l2, l1 in cur.fetchall():
        std = l2l1.get(norm_l2(l2 or ""))
        if std and std != l1:
            cur.execute(
                "UPDATE companies SET industry_l1=%s WHERE wind_code=%s", (std, wc)
            )
            fixed += 1
    conn.commit()
    return fixed


def bare_code(wc: str) -> str:
    """从 wind_code 提取 6 位数字代码."""
    wc = (wc or "").strip()
    digits = "".join(ch for ch in wc if ch.isdigit())
    return digits[:6] if digits else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("== 1. 读取缺失行业公司 ==")
    conn = _db()
    missing = load_missing(conn)
    print(f"  缺失 {len(missing)} 家")

    print("== 2. 批量查询申万二级行业 (eastmoney ulist) ==")
    code2l2 = fetch_missing_l2(missing)
    print(f"  查到 {len(code2l2)} 只，有行业 {sum(1 for v in code2l2.values() if v)} 只")

    l2l1 = build_l2l1_map()
    print(f"  L2->L1 映射 {len(l2l1)} 条")

    print("== 3. 计算填充方案 ==")
    filled = []  # (wind_code, l1, l2, source)
    unfilled = []
    for m in missing:
        code = bare_code(m["wc"])
        l2 = code2l2.get(code, "")
        l1 = l2l1.get(norm_l2(l2), "") if l2 else ""
        if l1:
            filled.append((m["wc"], l1, l2, "eastmoney"))
            continue
        # 名称兜底
        l1n = infer_by_name(m["name"])
        if l1n:
            filled.append((m["wc"], l1n, l2 or None, "name_inference"))
            continue
        unfilled.append(m)

    n_em = sum(1 for f in filled if f[3] == "eastmoney")
    n_ni = sum(1 for f in filled if f[3] == "name_inference")
    print(f"  eastmoney 填充: {n_em}")
    print(f"  name_inference 填充: {n_ni}")
    print(f"  仍无法填充: {len(unfilled)}")

    # 覆盖后总量
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM companies")
        total = cur.fetchone()[0]
    final = total - len(unfilled)
    print(f"  覆盖率: {final}/{total} = {final / total * 100:.1f}%")

    if args.dry_run:
        print("\n[dry-run] 未写库。unfilled 样例:")
        for m in unfilled[:30]:
            print(f"    {m['wc']}  {m['name']}")
        conn.close()
        return 0

    print("\n== 4. 写入 MySQL ==")
    cur = conn.cursor()
    updated = 0
    for wc, l1, l2, src in filled:
        cur.execute(
            "UPDATE companies SET industry_l1=%s, industry_l2=%s, "
            "industry_source=%s, industry_as_of=CURDATE() WHERE wind_code=%s",
            (l1, l2, src, wc),
        )
        updated += 1
    conn.commit()
    print(f"  更新 {updated} 家")

    print("== 4b. 校正存量 industry_l1（权威映射重推导）==")
    fixed = reconcile_l1(conn, l2l1)
    print(f"  校正 {fixed} 家")

    print("== 5. 重生成 industry_mapping.csv ==")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT wind_code, sec_name, industry_l1, industry_l2, industry_source "
            "FROM companies ORDER BY wind_code"
        )
        allrows = cur.fetchall()
    out = REPO / "data" / "processed" / "industry_mapping.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["wind_code", "stock_name", "industry_l1", "industry_l2",
                    "industry_l3", "source"])
        for r in allrows:
            w.writerow([r[0], r[1], r[2] or "", r[3] or "", "", r[4] or ""])
    print(f"  已写 {out} ({len(allrows)} 行)")

    conn.close()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
