# 数据契约

本文档定义前后端数据交互的边界和格式，以及数据组/后端组的协作规范。

---

## 数据存储边界

### SQLite（关系型数据）

**路径**：`data/truthnet.db`（不提交到 Git）

**草案表结构**：

```sql
-- 公司基本信息
CREATE TABLE companies (
    id TEXT PRIMARY KEY,          -- 股票代码，如 "600519"
    name TEXT NOT NULL,           -- 公司全称
    short_name TEXT,              -- 简称
    industry TEXT,                -- 行业分类
    listing_date TEXT,            -- 上市日期
    status TEXT DEFAULT 'active'  -- 状态
);

-- 财务报表（简化版，按科目存储）
CREATE TABLE financial_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    report_type TEXT NOT NULL,    -- 'balance_sheet' / 'income' / 'cash_flow'
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT,           -- 'Q1' / 'Q2' / 'Q3' / 'Q4' / 'FY'
    item_name TEXT NOT NULL,      -- 科目名称
    item_value REAL,              -- 金额（亿元）
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- 股权关系
CREATE TABLE ownership_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL,
    to_entity TEXT NOT NULL,
    stake_ratio REAL,             -- 持股比例 0-1
    relation_type TEXT,           -- 'direct' / 'indirect' / 'concerted'
    data_source TEXT,             -- 数据来源
    updated_at TEXT
);
```

> 实际建表 SQL 放在 `backend/app/core/schema.sql`（后续创建），本文档仅定义契约。

---

### NetworkX（图数据）

**使用场景**：股权穿透、关联方网络分析

**节点类型**：

| 类型 | 说明 | 属性 |
|------|------|------|
| `company` | 公司节点 | `name`, `code`, `listed(true/false)`, `industry` |
| `person` | 自然人 | `name`, `role` (董事/监事/高管) |
| `entity` | 其他实体 | `name`, `type` (政府/投资机构/基金会) |

**边类型**：

| 类型 | 说明 | 属性 |
|------|------|------|
| `owns` | 持股关系 | `ratio` (0-1), `level` (直接/间接) |
| `controls` | 实际控制 | `path`, `total_stake` |
| `related` | 关联关系 | `type` (同控/同董事/担保) |

---

### ChromaDB（向量数据）

**使用场景**：财报片段检索、舆情语义搜索

**Collection 草案**：

| Collection | 用途 | 元数据字段 |
|------------|------|------------|
| `financial_reports` | 财报文本片段 | `company_id`, `year`, `section`, `page` |
| `news_events` | 舆情新闻 | `company_id`, `date`, `source`, `sentiment` |
| `regulations` | 会计准则、法规 | `title`, `chapter`, `category` |

---

## 数据组 → 后端组交付格式

### 财务报表数据

```json
{
  "company_id": "600519",
  "company_name": "贵州茅台酒股份有限公司",
  "reports": {
    "2023": {
      "balance_sheet": [
        {"item": "货币资金", "value": 690.07, "unit": "亿元"},
        {"item": "应收账款", "value": 0.58, "unit": "亿元"}
      ],
      "income": [
        {"item": "营业收入", "value": 1505.60, "unit": "亿元"},
        {"item": "营业成本", "value": 317.24, "unit": "亿元"}
      ],
      "cash_flow": [
        {"item": "销售商品收到的现金", "value": 1652.35, "unit": "亿元"}
      ]
    }
  }
}
```

### 股权关系数据

```json
{
  "company_id": "600519",
  "relations": [
    {
      "from": "贵州省国资委",
      "to": "茅台集团",
      "stake": 1.0,
      "type": "direct",
      "source": "企查查/天眼查"
    },
    {
      "from": "茅台集团",
      "to": "贵州茅台酒股份有限公司",
      "stake": 0.54,
      "type": "direct",
      "source": "2023年报"
    }
  ]
}
```

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

- 禁止在 `data/raw/` 和 `data/processed/` 提交真实大文件（PDF > 1MB, Excel > 500KB）
- 禁止在仓库中提交 `.db` / `.sqlite` 文件
- 禁止在 ChromaDB 持久化目录中提交向量数据
- 前端不得私自修改后端定义的字段名和类型
