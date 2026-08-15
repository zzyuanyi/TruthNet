# 金融企业字段映射与覆盖报告

> 任务⑤ 金融企业字段前置（数据组 A · P0 · 后端 #11 依赖）
> 交付日期：2026-08-13

---

## 0. 结论摘要（给后端 #11 的三句话）

1. **comp_type_code 已填**：6,071 家有值（非金融 5,973 / 银行 48 / 保险 5 / 证券 45），410 家无值（境外股/新三板退市股，本无 A 股财报）。
2. **41 个金融专属字段已导入 MySQL**（银行 24 / 证券 15 / 保险相关 18，跨三表去重），银行、证券字段覆盖率 90%+。
3. **保险字段样本严重不足**：5 家保险股中仅中国人寿（601628.SH）有 1 条保费数据，其余保费/准备金/赔付字段全空 → 后端 #11 对保险规则必须走 `insufficient_data` 路径。

---

## 1. comp_type_code 填充

| 公司类型 | 代码 | companies 表数量 |
|---|---|---|
| 非金融 | 1 | 5,973 |
| 银行 | 2 | 48 |
| 保险 | 3 | 5 |
| 证券 | 4 | 45 |
| 无值（境外股/退市） | NULL | 410 |

- 数据来源：**原始三表 CSV 的 `comp_type_code` 列**（Wind 官方分类，非 akshare 推导）
- 三表交叉校验：6,713 只股票中仅 5 只存在跨表冲突，已按众数处理
- 脚本：`scripts/task4_name_backfill.py`（Phase C 口径修正版，来源优先级 balance_sheet > income > cash_flow，最新报告期 + 确定性多数仲裁，仅回填 NULL/非法值；主线上已合入）

---

## 2. 已导入的金融专属字段（41 个）

### 2.1 银行类（贷款/利息/存款/同业）

| 字段 | 含义 | 表 | 银行覆盖率 |
|---|---|---|---|
| loans_and_adv_granted | 发放贷款及垫款 | BS | 93.6% |
| cash_deposits_central_bank | 现金及存放中央银行款项 | BS | 99.6% |
| asset_dep_oth_banks_fin_inst | 存放同业和其它金融机构款项 | BS | 92.8% |
| borrow_central_bank | 向中央银行借款 | BS | 90.2% |
| liab_dep_oth_banks_fin_inst | 同业和其它金融机构存放款项 | BS | 89.4% |
| cust_bank_dep | 吸收存款 | BS | 90.2% |
| precious_metals | 贵金属 | BS | 38.0% |
| int_inc | 利息收入 | IS | 100.0% |
| net_int_inc | 利息净收入 | IS | 99.6% |
| less_int_exp | 利息支出 | IS | 100.0% |
| net_incr_dep_cob | 客户存款和同业存放净增加额 | CF | 86.2% |
| net_incr_int_handling_chrg | 收取利息和手续费净增加额 | CF | 98.9% |
| net_incr_loans_central_bank | 向中央银行借款净增加额 | CF | 51.7% |
| net_incr_dep_cbob | 存放央行和同业净增加额 | CF | 50.4% |

### 2.2 证券类（客户资金/手续费/投资）

| 字段 | 含义 | 表 | 证券覆盖率 |
|---|---|---|---|
| clients_cap_deposit | 客户资金存款 | BS | 95.6% |
| clients_rsrv_settle | 客户备付金 | BS | 95.6% |
| acting_trading_sec | 代理买卖证券款 | BS | 95.6% |
| mrgn_paid | 存出保证金 | BS | 95.6% |
| lending_funds | 融出资金 | BS | 95.6% |
| settle_rsrv | 结算备付金 | BS | 95.6% |
| handling_chrg_comm_inc | 手续费及佣金收入 | IS | 95.6% |
| net_handling_chrg_comm_inc | 手续费及佣金净收入 | IS | 96.5% |
| net_inc_sec_trading_brok_bus | 代理买卖证券业务净收入 | IS | 95.6% |
| net_inc_sec_uw_bus | 证券承销业务净收入 | IS | 95.0% |
| net_inc_ec_asset_mgmt_bus | 受托客户资产管理业务净收入 | IS | 58.2% |
| handling_chrg_paid | 支付手续费的现金 | CF | 95.6% |
| securitie_netcash_received | 代理买卖证券收到的现金净额 | CF | 71.3% |
| melt_money_net_increase | 融出资金净增加额 | CF | 56.1% |

### 2.3 保险类（保费/准备金/赔付 — ⚠️ 样本不足）

| 字段 | 含义 | 表 | 保险覆盖率 |
|---|---|---|---|
| prem_rcv | 应收保费 | BS | 2.0%（1 条） |
| rsrv_insur_cont | 保险合同准备金 | BS | 2.0% |
| unearned_prem_rsrv | 未到期责任准备金 | BS | 2.0% |
| out_loss_rsrv | 未决赔款准备金 | BS | 2.0% |
| life_insur_rsrv | 寿险责任准备金 | BS | 2.0% |
| claims_payable | 应付赔付款 | BS | 2.0% |
| prem_inc | 保费业务收入 | IS | 2.0% |
| insur_prem_unearned | 已赚保费 | IS | 2.0% |
| tot_claim_exp | 赔付总支出 | IS | 2.0% |
| prepay_surr | 退保金 | IS | 2.0% |
| chg_insur_cont_rsrv | 提取保险责任准备金 | IS | 2.0% |
| cash_recp_prem_orig_inco | 收到原保险合同保费取得的现金 | CF | 2.0% |
| cash_pay_claims_orig_inco | 支付原保险合同赔付款项的现金 | CF | 2.0% |

> ⚠️ **保险样本不足的根因**：`comp_type_code=3` 的 5 家保险股（中国平安 601318 / 中国人保 601319 / 新华保险 601336 / 中国太保 601601 / 中国人寿 601628）中，只有**中国人寿**在原始 CSV 里保留了保费类数据（且仅 1 条记录）。其余 4 家保费/准备金/赔付字段在赛题原始数据中即为空。这是**原始数据源限制**，非导入问题。

---

## 3. 覆盖率统计口径

- **全量样本**：三表 CSV 共 6,713 只股票（资产负债表 39,019 行 / 利润表 38,210 行 / 现金流 39,985 行）
- **银行样本**：comp_type_code=2，48 家（利润表 476 条）
- **保险样本**：comp_type_code=3，5 家（利润表 50 条）
- **证券样本**：comp_type_code=4，45 家（利润表 345 条）

---

## 4. 导入方式

- **schema**：Alembic v11 迁移（`f1a2b3c4d5e6_v11_finance_fields`）新增 41 列，全部 `FLOAT NULL`，与既有财务字段（monetary_cap 等）一致
- **脚本**：`scripts/import_finance_fields.py`（默认 dry-run 零写入，`--apply` 才写库；fail-closed 数据库守卫 + 单事务回滚）
- **对齐键**：`wind_code + report_period + statement_type + ann_dt`
- **幂等**：可重复执行，只更新金融字段列（`INSERT ... ON DUPLICATE KEY UPDATE`）

---

## 5. Fixture

- **路径**：`data/fixtures/finance_enterprises.sql`（72KB，5 家金融企业全量三表 + 公司信息）
- **覆盖企业**：
  - 银行：平安银行（000001.SZ）、工商银行（601398.SH）
  - 保险：中国人寿（601628.SH）、中国太保（601601.SH）
  - 证券：中信证券（600030.SH）
- **用途**：后端 #11 开发差异化规则时不依赖全量数据

---

## 6. 后端 #11 对接建议

| 企业类型 | 字段可用性 | 规则建议 |
|---|---|---|
| 银行（2） | 贷款/利息/存款字段覆盖率 90%+ | 可用真实字段写专属规则（如存贷比、净息差 NIM） |
| 证券（3→4） | 客户资金/手续费字段覆盖率 95%+ | 可用真实字段写专属规则（如手续费依赖度、客户保证金） |
| 保险（3） | 保费/准备金字段仅 1 条样本 | **必须走 `insufficient_data`**，不得套用通用规则 |

> 注意 comp_type_code 编码：`1=非金融 2=银行 3=保险 4=证券`（与任务手册一致；证券是 4 不是 3）。

---

## 7. 遗留事项（非阻塞）

1. **410 家无 comp_type_code**：境外股（索尼/任天堂/软银等）+ 新三板退市股 + CDR，本无 A 股财报，建议后续从 companies 表清理或标记。
2. **保险字段数据源**：若需真实保险数据，需向赛题方或额外数据源补充（如 Wind/Choice 的保险专表），原始三表 CSV 无此数据。
