#!/usr/bin/env python
"""行业分类补全 — 从研报+akshare+名称推断三路径构建行业映射，写入 MySQL。

路径（来自 PR #10 设计）：
  1. 研报已有行业数据（~3360 家公司）
  2. akshare 查询（网络，可跳过）
  3. 名称关键词语义推断（兜底）

输出: data/processed/industry_mapping.csv + MySQL companies 表更新
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app.core.config import settings  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
import pandas as pd  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ── Step 1: 从 MySQL 研报表中提取已有行业 ──
def build_report_industry_map(engine):
    """从 research_reports 表提取 (wind_code → industry_l1) 映射."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT wind_code, MAX(sec_name), MAX(industry_l1), MAX(sw_indu_code) "
                "FROM research_reports "
                "WHERE industry_l1 IS NOT NULL AND industry_l1 != '' "
                "GROUP BY wind_code"
            )
        ).fetchall()

    mapping = {}
    for r in rows:
        wc, name, l1, sw = r
        mapping[str(wc)] = {
            "stock_name": str(name or ""),
            "industry_l1": str(l1 or ""),
            "sw_indu_code": str(sw or ""),
            "source": "research_report",
        }
    log.info("Research report industry: %d companies", len(mapping))
    return mapping


# ── Step 2: akshare 查询缺失代码 ──
def try_akshare_fill(missing_codes):
    """尝试通过 akshare 查询申万行业。失败时返回空映射。"""
    try:
        import akshare as ak  # noqa: F811
        import time
    except ImportError:
        log.warning("akshare 未安装，跳过网络查询")
        return {}

    log.info("akshare: querying %d missing codes...", len(missing_codes))
    mapping = {}
    errors = []
    for i, code in enumerate(missing_codes):
        # Use bare 6-digit code (remove .SH/.SZ/.BJ suffix)
        bare = code.split(".")[0] if "." in code else code
        try:
            info = ak.stock_individual_info_em(symbol=bare)
            if info is not None and not info.empty:
                row = info.set_index("item").to_dict()["value"]
                ind = row.get("行业", row.get("industry", ""))
                name = row.get("股票简称", row.get("name", ""))
                if ind:
                    mapping[code] = {  # Use full wind_code as key
                        "stock_name": str(name),
                        "industry_l1": str(ind),
                        "sw_indu_code": None,
                        "source": "akshare",
                    }
        except Exception:
            errors.append(code)

        if (i + 1) % 200 == 0:
            log.info(
                "  akshare: %d/%d (found %d)", i + 1, len(missing_codes), len(mapping)
            )
        time.sleep(0.05)  # Rate limit

    log.info("akshare: %d found, %d errors", len(mapping), len(errors))
    return mapping


# ── Step 3: 名称推断兜底 ──
_NAME_INDUSTRY_KEYWORDS = {
    "银行": "银行",
    "保险": "非银金融",
    "证券": "非银金融",
    "信托": "非银金融",
    "基金": "非银金融",
    "房地产": "房地产",
    "地产": "房地产",
    "钢铁": "钢铁",
    "煤炭": "煤炭",
    "石油": "石油石化",
    "石化": "石油石化",
    "化工": "基础化工",
    "化肥": "基础化工",
    "医药": "医药生物",
    "药": "医药生物",
    "生物": "医药生物",
    "电力": "公用事业",
    "水务": "公用事业",
    "燃气": "公用事业",
    "环保": "环保",
    "建筑": "建筑装饰",
    "建材": "建筑材料",
    "水泥": "建筑材料",
    "汽车": "汽车",
    "航空": "交通运输",
    "机场": "交通运输",
    "铁路": "交通运输",
    "高速": "交通运输",
    "港口": "交通运输",
    "物流": "交通运输",
    "食品": "食品饮料",
    "饮料": "食品饮料",
    "酒": "食品饮料",
    "乳": "食品饮料",
    "农业": "农林牧渔",
    "牧渔": "农林牧渔",
    "种业": "农林牧渔",
    "通信": "通信",
    "计算机": "计算机",
    "软件": "计算机",
    "电子": "电子",
    "半导体": "电子",
    "芯片": "电子",
    "传媒": "传媒",
    "影视": "传媒",
    "广告": "传媒",
    "军工": "国防军工",
    "国防": "国防军工",
    "机械": "机械设备",
    "电器": "电力设备",
    "新能源": "电力设备",
    "电池": "电力设备",
    "光伏": "电力设备",
    "风电": "电力设备",
    "家电": "家用电器",
    "纺织": "纺织服饰",
    "服装": "纺织服饰",
    "旅游": "社会服务",
    "酒店": "社会服务",
    "商贸": "商贸零售",
    "零售": "商贸零售",
    "有色": "有色金属",
    "黄金": "有色金属",
    "轻工": "轻工制造",
    "造纸": "轻工制造",
    "包装": "轻工制造",
}


def try_name_inference(code_to_name):
    """根据股票名称关键词推断行业。"""
    mapping = {}
    for code, name in code_to_name.items():
        for kw, ind in _NAME_INDUSTRY_KEYWORDS.items():
            if kw in name:
                mapping[code] = {
                    "stock_name": name,
                    "industry_l1": ind,
                    "sw_indu_code": None,
                    "source": f"name_inference:{kw}",
                }
                break
    log.info("Name inference: %d companies", len(mapping))
    return mapping


# ── Main ──
def main():
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)

    # Get all companies
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT wind_code, sec_name FROM companies")
        ).fetchall()
    all_codes = {row[0]: row[1] for row in rows}
    log.info("Total companies: %d", len(all_codes))

    # Step 1: Research reports
    report_map = build_report_industry_map(engine)
    industry_map = dict(report_map)

    # Find missing codes
    missing = {k: v for k, v in all_codes.items() if k not in industry_map}
    log.info("Missing after research reports: %d", len(missing))

    # Step 2: Try akshare (skip if too slow or unavailable)
    missing_codes = list(missing.keys())
    akshare_map = try_akshare_fill(missing_codes[:50])  # Only try 50 to check
    industry_map.update(akshare_map)
    missing = {k: v for k, v in missing.items() if k not in industry_map}
    log.info("Missing after akshare: %d", len(missing))

    # Step 3: Name inference
    name_map = try_name_inference(missing)
    industry_map.update(name_map)
    missing = {k: v for k, v in missing.items() if k not in industry_map}
    log.info("Missing after name inference: %d", len(missing))

    # Coverage
    total = len(all_codes)
    covered = total - len(missing)
    log.info("Coverage: %d/%d = %.1f%%", covered, total, 100 * covered / total)

    # Save CSV
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_out = []
    for wc, name in all_codes.items():
        m = industry_map.get(wc, {})
        rows_out.append(
            {
                "wind_code": wc,
                "stock_name": name,
                "industry_l1": m.get("industry_l1"),
                "source": m.get("source", ""),
            }
        )
    df = pd.DataFrame(rows_out)
    df.to_csv(out_dir / "industry_mapping.csv", index=False, encoding="utf-8-sig")
    log.info("Saved industry_mapping.csv (%d rows)", len(df))

    # Update MySQL
    log.info("Updating MySQL companies table...")
    updated = 0
    for wc, m in industry_map.items():
        if m.get("industry_l1"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE companies SET industry_l1=:l1, "
                        "sw_indu_code=:sw, industry_source=:src, industry_as_of=CURDATE() "
                        "WHERE wind_code=:wc"
                    ),
                    {
                        "l1": m["industry_l1"],
                        "sw": m.get("sw_indu_code"),
                        "src": m.get("source", ""),
                        "wc": wc,
                    },
                )
                updated += 1
    log.info("Updated %d companies", updated)

    # Verify
    with engine.connect() as conn:
        total2 = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar()
        with_ind = conn.execute(
            text(
                "SELECT COUNT(*) FROM companies WHERE industry_l1 IS NOT NULL AND industry_l1 != ''"
            )
        ).scalar()
        log.info(
            "Final: %d/%d = %.1f%% have industry",
            with_ind,
            total2,
            100 * with_ind / total2,
        )

    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
