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

# 0. 准备 processed 产物（data/processed/ 不提交 Git，需按序生成）
#    依赖链：industry_mapping.csv（行业字段）→ security_master.csv（sec_name 权威）
#    → import_data.py（**强制**读取 security_master.csv，缺失会失败关闭）。
#    首次搭建且无 industry_mapping.csv 时：先跑 import_data 的备用路径
#    （自动从三表提取代码），导入完成后执行 industry_fill.py 生成映射，
#    再重跑 security_master.py 与 import_data.py。

# 1. 证券主表（import_data.py 强制前置）
python scripts/security_master.py            # 生成 data/processed/security_master.csv + 审计报告

# 2. MySQL 全量入库（7 表，~83 万行）
python scripts/import_data.py --data-root data/raw --dry-run
python scripts/import_data.py --data-root data/raw

# 3. 公告情绪分类
python scripts/announcement_sentiment.py --data-file data/raw/3/clean.xlsx --dict-file data/raw/3/ditct.txt --update-mysql

# 4. 公司名称回填
python scripts/backfill_company_names.py --dry-run
python scripts/backfill_company_names.py

# 5. Neo4j 全量图谱
#    默认幂等增量（不删已有关系）；重建/替换旧图时加 --replace-graph-version
#    （防误删保护：导入前不清理旧图，失败只删本次新建，验收通过后才删旧关系）
python scripts/neo4j_full_import.py --data-file data/raw/2/clean.xlsx --graph-version equity-competition-2026 --dataset-version competition-2026
# 重建（替换旧图，危险操作）：
# python scripts/neo4j_full_import.py --data-file data/raw/2/clean.xlsx --graph-version equity-competition-2026 --dataset-version competition-2026 --replace-graph-version

# 6. Chroma 嵌入链路（先安装依赖：pip install -r requirements-chroma.txt）
python scripts/chroma_embed.py --output-dir data/processed/chroma-full
python scripts/chroma_import.py --input-dir data/processed/chroma-full --rebuild

# 7. 行业分类补全（读取 MySQL 研报生成 industry_mapping.csv；生成后需重跑
#    步骤 1-2 使行业字段与主表名称生效）
python scripts/industry_fill.py
```
