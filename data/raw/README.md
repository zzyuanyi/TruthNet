# 原始数据目录

> **数据不提交 Git**（`.gitignore` 已排除，仅保留本文件）。
> 首次搭建时从团队共享渠道获取数据文件，放入对应子目录。

## 获取数据

1. 从微信群/网盘下载赛方原始数据压缩包（~300MB）
2. 解压后按下方结构放入 `data/raw/` 各子目录
3. 确认所有文件就位后执行 `python scripts/import_data.py --dry-run`

## 目录结构

```text
data/raw/
├── README.md            ← 本文件
├── 1/                   ← 问答测试集
│   └── clean.xlsx
├── 2/                   ← 股东持股数据
│   ├── clean.xlsx
│   └── dict.txt
├── 3/                   ← 公司公告数据
│   ├── clean.xlsx
│   └── ditct.txt
├── 4/                   ← A股财务报表（三表）
│   ├── asharebalancesheet_*.csv
│   ├── asharecashflow_*.csv
│   ├── ashareincome_*.csv
│   ├── balancesheet_dict.txt
│   ├── cashflow_dict.txt
│   └── income_dict.txt
└── 5/                   ← 研报数据
    ├── rr_main_*.csv
    └── rr_main_dict.txt
```

## 全量导入顺序

> 先在仓库根目录执行，确保 `.env` 已配置 MySQL/Neo4j 连接。

```bash
# 0. 建表
alembic upgrade head

# 1. MySQL 全量入库（7 表，~83 万行）
python scripts/import_data.py --data-root data/raw --dry-run
python scripts/import_data.py --data-root data/raw

# 2. 公告情绪分类
python scripts/announcement_sentiment.py --data-file data/raw/3/clean.xlsx --dict-file data/raw/3/ditct.txt --update-mysql

# 3. 公司名称回填
python scripts/backfill_company_names.py --dry-run
python scripts/backfill_company_names.py

# 4. Neo4j 全量图谱
python scripts/neo4j_full_import.py --data-file data/raw/2/clean.xlsx --graph-version equity-competition-2026 --dataset-version competition-2026

# 5. Chroma 嵌入链路（先安装依赖：pip install -r requirements-chroma.txt）
python scripts/chroma_embed.py --output-dir data/processed/chroma-full
python scripts/chroma_import.py --input-dir data/processed/chroma-full --rebuild

# 6. 行业分类补全（可选，Phase C 任务）
# python scripts/industry_fill.py
```
