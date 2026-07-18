# 数据契约

本文档定义前后端数据交互的边界和格式，以及数据组/后端组的协作规范。

> 2026-07-03 更新：基于官方数据集实际结构重写，替代 V5 早期假设的 EAV 模型。

---

## 数据存储边界

### SQLite（关系型数据）

**路径**：`data/truthnet.db`（不提交到 Git）

**主键约定**：跨表关联使用 `s_info_windcode`（Wind 代码，如 `300838.SZ`），不使用上交所/深交所股票代码（如 `600519`）。

#### 核心表

```sql
-- 公司基本信息（从三表 + 股东数据提取）
CREATE TABLE companies (
    wind_code TEXT PRIMARY KEY,       -- Wind 代码，如 "300838.SZ"
    stock_code TEXT,                  -- 股票代码，如 "300838"（不含后缀）
    name TEXT NOT NULL,               -- 公司全称
    industry TEXT,                    -- 行业分类（申万一级）
    comp_type_code INTEGER,           -- 1=非金融，2=银行，3=保险，4=证券
    exchange TEXT                     -- 交易所：XSHG(上交所)/XSHE(深交所)
);

-- 资产负债表（直接映射 CSV 字段）
CREATE TABLE balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT UNIQUE NOT NULL,    -- UUID 行标识
    wind_code TEXT NOT NULL,
    report_period TEXT NOT NULL,       -- 报告期，如 "2024-12-31"
    ann_dt TEXT,                       -- 公告日期
    statement_type TEXT,               -- 408001000=合并报表（推荐主口径）
    -- 资产
    monetary_cap REAL,                 -- 货币资金
    acct_rcv REAL,                     -- 应收账款
    inventories REAL,                  -- 存货
    tot_cur_assets REAL,              -- 流动资产合计
    fix_assets REAL,                   -- 固定资产
    intang_assets REAL,               -- 无形资产
    goodwill REAL,                     -- 商誉
    long_term_eqy_invest REAL,        -- 长期股权投资
    tot_assets REAL,                   -- 资产总计
    -- 负债
    st_borrow REAL,                    -- 短期借款
    acct_payable REAL,                 -- 应付账款
    tot_cur_liab REAL,                -- 流动负债合计
    lt_borrow REAL,                    -- 长期借款
    bonds_payable REAL,               -- 应付债券
    tot_non_cur_liab REAL,           -- 非流动负债合计
    tot_liab REAL,                     -- 负债合计
    -- 权益
    cap_stk REAL,                      -- 股本
    cap_rsrv REAL,                     -- 资本公积
    surplus_rsrv REAL,                -- 盈余公积
    undistributed_profit REAL,        -- 未分配利润
    tot_shrhldr_eqy_incl_min_int REAL,-- 股东权益（含少数股东）
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);

-- 利润表
CREATE TABLE income_statement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT UNIQUE NOT NULL,
    wind_code TEXT NOT NULL,
    report_period TEXT NOT NULL,
    ann_dt TEXT,
    statement_type TEXT,               -- 408001000=合并报表（推荐主口径）
    -- 收入
    tot_oper_rev REAL,                 -- 营业总收入
    oper_rev REAL,                     -- 营业收入
    -- 成本费用
    less_oper_cost REAL,               -- 营业成本
    less_selling_dist_exp REAL,       -- 销售费用
    less_gerl_admin_exp REAL,         -- 管理费用
    less_fin_exp REAL,                 -- 财务费用
    -- 利润
    oper_profit REAL,                  -- 营业利润
    tot_profit REAL,                   -- 利润总额
    net_profit_excl_min_int_inc REAL, -- 净利润（不含少数股东）
    net_profit_after_ded_nr_lp REAL,  -- 扣非净利润
    -- 每股
    s_fa_eps_basic REAL,              -- 基本每股收益
    s_fa_eps_diluted REAL,            -- 稀释每股收益
    -- 衍生
    ebit REAL,                         -- 息税前利润
    ebitda REAL,                       -- 息税折旧摊销前利润
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);

-- 现金流量表
CREATE TABLE cash_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT UNIQUE NOT NULL,
    wind_code TEXT NOT NULL,
    report_period TEXT NOT NULL,
    ann_dt TEXT,
    statement_type TEXT,               -- 408001000=合并报表（推荐主口径）
    -- 经营活动
    cash_recp_sg_and_rs REAL,         -- 销售商品、提供劳务收到的现金
    net_cash_flows_oper_act REAL,     -- 经营活动现金流量净额
    -- 投资活动
    cash_paid_invest REAL,            -- 投资支付的现金
    net_cash_flows_inv_act REAL,     -- 投资活动现金流量净额
    -- 筹资活动
    cash_recp_borrow REAL,            -- 取得借款收到的现金
    net_cash_flows_fnc_act REAL,     -- 筹资活动现金流量净额
    -- 汇总
    net_incr_cash_cash_equ REAL,     -- 现金及现金等价物净增加额
    cash_cash_equ_end_period REAL,   -- 期末现金及现金等价物余额
    -- 补充
    net_profit REAL,                   -- 净利润（间接法）
    free_cash_flow REAL,              -- 企业自由现金流（FCFF）
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);

-- 十大股东
CREATE TABLE top_shareholders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wind_code TEXT NOT NULL,
    ann_dt TEXT,                       -- 公告日期
    s_holder_enddate TEXT,            -- 股东数据截止日期
    report_period TEXT,                -- 报告期
    s_holder_name TEXT NOT NULL,       -- 股东名称
    s_holder_holdercategory INTEGER,  -- 1=个人，2=企业
    s_holder_pct REAL,                -- 持股比例（%）
    s_holder_quantity REAL,           -- 持股数量（股）
    s_holder_nat TEXT,                -- 股东性质
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);

-- 公司公告
CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT UNIQUE NOT NULL,
    wind_code TEXT NOT NULL,
    ann_dt TEXT NOT NULL,              -- 公告日期
    title TEXT NOT NULL,               -- 公告标题
    fcode TEXT,                        -- 公告类型代码，多条用 '|' 分隔
    fcode_name TEXT,                   -- 公告类型名称（根据 dict 映射）
    link TEXT,                         -- 公告 PDF 链接
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);

-- 研报摘要
CREATE TABLE research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER UNIQUE NOT NULL,
    wind_code TEXT,                    -- 证券代码
    sec_name TEXT,                     -- 证券简称
    title TEXT NOT NULL,               -- 研报标题
    org_name TEXT,                     -- 发布机构
    author TEXT,                       -- 作者
    publish_date TEXT,                 -- 发布日期
    report_type TEXT,                  -- 研报类型（公司研究/行业研究）
    report_sub_type TEXT,             -- 细分类型（业绩点评/公司深度/调研纪要）
    rating_org TEXT,                   -- 原始评级（买入/增持…）
    rating_change TEXT,               -- 评级变动（维持/上调/下调）
    abstract TEXT,                     -- 摘要全文（入向量库的核心字段）
    industry_l1 TEXT,                  -- 申万一级行业
    industry_l2 TEXT,                  -- 申万二级行业
    FOREIGN KEY (wind_code) REFERENCES companies(wind_code)
);
```

> **表设计说明**：三表（BS/IS/CF）采用宽表映射 CSV 列，不再使用早期 EAV 模型（`item_name`/`item_value`）。建表时仅选取勾稽相关核心字段（各 ~20 列），完整字段定义见各 `*_dict.txt`。数值字段以 DECIMAL 存储，空值统一为 NULL。

> **数据筛选建议**：`statement_type='408001000'`（合并报表）为主口径；`comp_type_code=1`（非金融）排除金融企业特殊科目。实际 SQL 见 `backend/app/core/schema.sql`（Phase 0 创建）。

---

### NetworkX（图数据）

**使用场景**：股权穿透、关联方网络分析

**数据来源**：`top_shareholders` 表，通过 `s_info_windcode` → `s_holder_name` → `s_holder_pct` 构建有向图

**节点类型**：

| 类型 | 说明 | 数据来源 |
|------|------|------|
| `listed_company` | 上市公司 | `top_shareholders.wind_code` |
| `person` | 自然人股东 | `s_holder_holdercategory=1` |
| `company` | 企业股东（壳公司/投资实体） | `s_holder_holdercategory=2` |

**边类型**：

| 类型 | 说明 | 属性 |
|------|------|------|
| `holds` | 持股关系 | `ratio`（持股比例%，从 `s_holder_pct`），`date`（截止日期） |

**穿透机制**：从目标上市公司出发，沿 `holds` 边反向 BFS/DFS 遍历，连乘路径上各边 `ratio/100`，输出 "自然人→壳→上市公司" 带权重链路。

> 设计简化说明：V5 早期设计了 4 种节点类型（Person/Company/Plan/ListedCo），但官方股东数据仅区分个人/企业两类，无法直接识别"资管计划"。如需标记资管产品，需在 Phase 1 根据股东名称规则匹配（如含"信托计划""资管计划""私募基金"等关键词）。

---

### ChromaDB（向量数据）

**使用场景**：研报摘要检索、公告语义搜索

| Collection | 用途 | 元数据字段 | 数据来源 |
|------------|------|------------|------|
| `research_reports` | 研报摘要检索 | `wind_code`, `sec_name`, `publish_date`, `org_name`, `rating_org` | 文件夹5（`abstract` 字段） |
| `announcements` | 公告标题/摘要检索 | `wind_code`, `ann_dt`, `fcode_name`, `title` | 文件夹3 |

> V5 早期设计了 `news_events`（舆情新闻）和 `regulations`（法规），实际数据不含新闻流和法规全文，`regulations` 删除，`news_events` 改为 `announcements`。

---

## 数据组 → 后端组交付格式

### 数据预处理约定

1. 三表 CSV 直接入库，不需 JSON 中转——数据组交付 `truthnet.db` 即可
2. 数值字段转为 DECIMAL，空字符串转为 NULL
3. `statement_type` 默认筛选 `408001000`（合并报表）
4. `comp_type_code` 默认筛选 `1`（非金融）
5. 所有表以 `s_info_windcode` 为主键关联

### 股权关系数据交付

数据组直接交付 SQLite `top_shareholders` 表，后端组读取后通过脚本构建 NetworkX 图。

---

## 后端 → 前端 Mock 数据

Mock JSON 格式与 `docs/API_CONTRACT.md` 中响应示例一致，前端可直接将其作为 stub server 返回。

前端 mock 开发建议：
1. 复制 API_CONTRACT.md 中的响应 JSON
2. 使用 `msw`（Mock Service Worker）或 `json-server` 搭建 mock 服务
3. 接口字段变更时必须同步更新 mock

---

## 数据变更流程

1. 数据组在 `data/raw/` 目录下更新源数据
2. 如需修改数据结构，先更新本文档的对应章节
3. 通知后端组更新 schema 和数据处理管道
4. 后端组更新 `backend/app/schemas/` 中的 Pydantic 模型
5. 更新 `docs/INTERFACE_CHANGELOG.md`

---

## 禁止事项

- 禁止提交 `.db` / `.sqlite` 文件到 Git
- 禁止提交 `data/raw/` 和 `data/processed/` 下的真实数据文件
- 禁止在 ChromaDB 持久化目录中提交向量数据
- 前端不得私自修改后端定义的字段名和类型
