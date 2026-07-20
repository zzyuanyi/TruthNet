# 数据库 Migration 核查清单

> 后端交付给数据组前，逐项确认以下 5 类检查。
> 全部通过后数据组才能基于这些表执行全量入库。

---

## A. V12 字段完整性（逐表对照）

### A1  companies（V12 §10.3）

| V12 要求 | 已实现 | 类型 | 说明 |
|------|:--:|------|------|
| `entity_id` VARCHAR PK | ✅ | VARCHAR(64) | 内部稳定实体ID |
| `wind_code` VARCHAR UNIQUE NOT NULL | ✅ | VARCHAR(20) | 如 `600519.SH` |
| `sec_name` VARCHAR NOT NULL | ✅ | VARCHAR(128) | 证券简称 |
| `aliases` JSON | ✅ | JSON | 曾用名/别名 |
| `exchange_code` VARCHAR | ✅ | VARCHAR(16) | XSHG/XSHE |
| `industry_l1` VARCHAR | ✅ | VARCHAR(64) | 申万一级 |
| `industry_l2` VARCHAR | ✅ | VARCHAR(64) | 申万二级 |
| `sw_indu_code` VARCHAR | ✅ | VARCHAR(16) | |
| `comp_type_code` SMALLINT | ✅ | SMALLINT | 1/2/3/4 |
| `listing_date` DATE | ✅ | DATE | |
| `industry_source` VARCHAR | ✅ | VARCHAR(64) | |
| `industry_as_of` DATE | ✅ | DATE | |
| 系统字段 11 个 | ✅ | — | revision_no/is_latest/checksum… |

### A2  balance_sheet（V12 §10.4）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `wind_code` | ✅ | VARCHAR(20) |
| `report_period` | ✅ | VARCHAR(10) |
| `statement_type` | ✅ | VARCHAR(16) |
| `ann_dt` | ✅ | DATE |
| `monetary_cap` | ✅ | DECIMAL(25,4) |
| `acct_rcv` | ✅ | DECIMAL(25,4) |
| `oth_rcv` | ✅ | DECIMAL(25,4) |
| `inventories` | ✅ | DECIMAL(25,4) |
| `tot_cur_assets` | ✅ | DECIMAL(25,4) |
| `fix_assets` | ✅ | DECIMAL(25,4) |
| `goodwill` | ✅ | DECIMAL(25,4) |
| `tot_assets` | ✅ | DECIMAL(25,4) |
| `st_borrow` | ✅ | DECIMAL(25,4) |
| `lt_borrow` | ✅ | DECIMAL(25,4) |
| `acct_payable` | ✅ | DECIMAL(25,4) |
| `tot_cur_liab` | ✅ | DECIMAL(25,4) |
| `tot_liab` | ✅ | DECIMAL(25,4) |
| `tot_shrhldr_eqy_incl_min_int` | ✅ | DECIMAL(25,4) |
| `(wind_code, report_period, statement_type, ann_dt, revision_no)` UNIQUE | ✅ | — |

### A3  income_statement（V12 §10.4）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `wind_code` | ✅ | VARCHAR(20) |
| `report_period` | ✅ | VARCHAR(10) |
| `statement_type` | ✅ | VARCHAR(16) |
| `ann_dt` | ✅ | DATE |
| `oper_rev` | ✅ | DECIMAL(25,4) |
| `tot_oper_rev` | ✅ | DECIMAL(25,4) |
| `less_oper_cost` | ✅ | DECIMAL(25,4) |
| `less_selling_dist_exp` | ✅ | DECIMAL(25,4) |
| `less_gerl_admin_exp` | ✅ | DECIMAL(25,4) |
| `less_fin_exp` | ✅ | DECIMAL(25,4) |
| `oper_profit` | ✅ | DECIMAL(25,4) |
| `tot_profit` | ✅ | DECIMAL(25,4) |
| `net_profit_excl_min_int_inc` | ✅ | DECIMAL(25,4) |
| `net_profit_after_ded_nr_lp` | ✅ | DECIMAL(25,4) |
| UNIQUE 同 BS | ✅ | — |

### A4  cash_flow（V12 §10.4）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `wind_code` | ✅ | VARCHAR(20) |
| `report_period` | ✅ | VARCHAR(10) |
| `statement_type` | ✅ | VARCHAR(16) |
| `ann_dt` | ✅ | DATE |
| `net_cash_flows_oper_act` | ✅ | DECIMAL(25,4) |
| `net_cash_flows_inv_act` | ✅ | DECIMAL(25,4) |
| `net_cash_flows_fnc_act` | ✅ | DECIMAL(25,4) |
| `net_incr_cash_cash_equ` | ✅ | DECIMAL(25,4) |
| `free_cash_flow` | ✅ | DECIMAL(25,4) |
| UNIQUE 同 BS | ✅ | — |

### A5  top_shareholders（V12 §10.5）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `wind_code` | ✅ | VARCHAR(20) |
| `ann_dt` | ✅ | DATE |
| `s_holder_enddate` | ✅ | DATE |
| `s_holder_name` | ✅ | VARCHAR(256) |
| `s_holder_aname` | ✅ | VARCHAR(256) |
| `s_holder_pct` | ✅ | DECIMAL(10,4) |
| `s_holder_quantity` | ✅ | DECIMAL(20,0) |
| `s_holder_holdercategory` | ✅ | SMALLINT |
| `s_holder_sequence` | ✅ | INTEGER |
| `report_period` | ✅ | VARCHAR(10) |
| `holder_entity_id` | ✅ | VARCHAR(64) |
| `entity_match_confidence` | ✅ | FLOAT |

### A6  announcements（V12 §10.6）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `object_id` | ✅ | VARCHAR(64) UNIQUE |
| `wind_code` | ✅ | VARCHAR(20) |
| `ann_dt` | ✅ | DATE |
| `n_info_title` | ✅ | TEXT |
| `n_info_fcode` | ✅ | VARCHAR(256) |
| `sentiment` | ✅ | VARCHAR(16) |
| `sentiment_method` | ✅ | VARCHAR(32) |
| `source_uri` | ✅ | VARCHAR(1024) |
| `content_hash` | ✅ | VARCHAR(64) |

### A7  research_reports（V12 §10.7）

| V12 要求 | 已实现 | 类型 |
|------|:--:|------|
| `report_id` | ✅ | INTEGER UNIQUE |
| `wind_code` | ✅ | VARCHAR(20) |
| `sec_code` | ✅ | VARCHAR(16) |
| `exchange_code` | ✅ | VARCHAR(16) |
| `sec_name` | ✅ | VARCHAR(128) |
| `org_name` | ✅ | VARCHAR(256) |
| `title` | ✅ | TEXT |
| `publish_date` | ✅ | DATE |
| `abstract` | ✅ | TEXT |
| `rating_org` | ✅ | VARCHAR(64) |
| `rating_change` | ✅ | VARCHAR(16) |
| `industry_l1` | ✅ | VARCHAR(64) |
| `sw_indu_code` | ✅ | VARCHAR(16) |
| `source_uri` | ✅ | VARCHAR(1024) |
| `content_hash` | ✅ | VARCHAR(64) |

---

## B. 数据组入库可行性（实际 CSV 字段映射）

> 数据组用 Pandas 读 CSV → `df.to_sql()` 或 `INSERT` 入库。以下确认关键映射。

| 数据集 | 表 | 关键映射检查 |
|------|------|------|
| 文件夹2 股东 | `top_shareholders` | `s_info_windcode` → `wind_code`；`s_holder_pct` 为百分比（如 54.0），`DECIMAL(10,4)` 足够 |
| 文件夹3 公告 | `announcements` | `object_id` 是 UUID；`n_info_fcode` 多值用 `\|` 分隔，`VARCHAR(256)` 够用 |
| 文件夹4 BS | `balance_sheet` | CSV 列名与表字段一致；数值为字符串需转 DECIMAL |
| 文件夹4 IS | `income_statement` | 同上 |
| 文件夹4 CF | `cash_flow` | 同上 |
| 文件夹5 研报 | `research_reports` | `sec_code` 是数字（如 `601033`），`wind_code` 需拼接后缀 |
| — | `companies` | 需从三表/股东中提取去重后 INSERT |

### 可能的问题

| # | 问题 | 状态 |
|:--:|------|:--:|
| 1 | `companies.wind_code` 格式 `600519.SH` vs CSV 中的 `s_info_windcode` 格式 `600519.SH` — 需确认是否一致 | ⚠️ 待数据组确认 |
| 2 | `companies.entity_id` 如何生成？内部规则需与数据组对齐（如 `company_600519_SH`） | ⚠️ 待确认 |
| 3 | `report_period` 格式：CSV 中可能是 `2024-12-31` 或 `20241231`，需统一 | ⚠️ 待数据组确认 |
| 4 | `balance_sheet.monetary_cap` 等 DECIMAL(25,4) — A 股公司市值可达万亿，`25,4` 表示最大 10^21 量级，足够 | ✅ |
| 5 | JSON 字段（`aliases`、`quality_flags`）：Pandas 写入 MySQL JSON 需 `import json` 序列化 | ⚠️ 需在入库脚本中处理 |

---

## C. 设计规范遵守

| # | 规范 | V12 要求 | 状态 |
|:--:|------|------|:--:|
| 1 | 不用 ENUM | VARCHAR + CHECK 或字典表 | ✅ |
| 2 | 财务唯一约束 | `(wind_code, report_period, statement_type, ann_dt, revision_no)` | ✅ |
| 3 | 系统审计字段 | 每表 11 个 | ✅ |
| 4 | 字符集 | `utf8mb4` + `utf8mb4_0900_ai_ci` | ✅ |
| 5 | 数值精度 | DECIMAL，不用 FLOAT/DOUBLE | ✅ |
| 6 | downgrade 可逆 | 逆序 DROP TABLE | ✅ |
| 7 | 索引 | 高频查询列有索引 | ✅ |

---

## D. 运行时验证（迁移执行后）

```sql
-- 1. 确认 7 表存在
SHOW TABLES FROM truthnet;
-- 预期: announcements, balance_sheet, cash_flow, companies,
--        income_statement, research_reports, top_shareholders

-- 2. 确认字符集
SELECT TABLE_NAME, TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'truthnet';
-- 预期: 全部 utf8mb4_0900_ai_ci

-- 3. 确认唯一约束
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'truthnet' AND CONSTRAINT_TYPE = 'UNIQUE';

-- 4. 验证 downgrade 可逆
-- alembic -c backend/alembic.ini downgrade -1
-- 然后重新 upgrade，两方向均无错误

-- 5. 测试插入一条记录
INSERT INTO companies (entity_id, wind_code, sec_name, dataset_version, revision_no, is_latest)
VALUES ('test_001', '000001.SZ', '测试公司', 'test', 1, 1);
-- 预期: 成功
DELETE FROM companies WHERE entity_id = 'test_001';
```

---

## E. 交付前最终确认

| # | 检查项 | 通过标准 | 责任人 | 状态 |
|:--:|------|------|:--:|:--:|
| 1 | 所有 V12 字段已包含 | A1-A7 每行打勾 | 后端 | ✅ |
| 2 | 类型与 CSV 数据兼容 | B 类问题已确认/已解决 | 数据组 | ⬜ |
| 3 | 设计规范全覆盖 | C 类 7 项全部符合 | 后端 | ✅ |
| 4 | 本地 MySQL 可执行 migration | `alembic upgrade head` 成功 | 后端 | ⬜ |
| 5 | downgrade 可逆 | `downgrade -1` → `upgrade head` 两方向成功 | 后端 | ⬜ |
| 6 | 数据组试插入成功 | 各表 INSERT 1 条真实 CSV 数据不报错 | 数据组 | ⬜ |
| 7 | CI 中 migration 可通过（若有） | — | 后端 | ⬜ |

---

> 后端组逐项确认 E1-E5，交付给数据组后数据组确认 E2 和 E6。
