# TruthNet 评测数据口径定义

> 版本：1.0.0 | 日期：2026-07-30 | Phase C 初稿
> 交付任务：⑦ 评测框架 + ⑨ 评测数据口径定义

---

## 1. 评测数据集

### 1.1 数据集概览

| 数据集 | 规模 | 用途 | 评测方式 |
|---|---|---|---|
| 问答测试集 | 35 会话、1,410 问 | 全量自动评测 | 脚本自动化 |
| 深度题 | 77 问（从 1,410 中筛选） | 深度人工评测 | 人工 + 脚本辅助 |
| 简单题 | 1,333 问 | 基线评测 | 脚本自动化 |

### 1.2 数据来源

- 文件路径：`赛题数据/1/clean.xlsx`
- 格式：Excel，字段含 session_id, query, expected_company, expected_risk_level 等
- 来源：赛方官方提供，35 会话覆盖多轮对话场景

### 1.3 隔离原则（来自开发手册 v2）

> 评测数据与规则调参用的训练数据必须物理隔离。

- 规则阈值调整只能使用 `data/raw/2-5/` 中的财务/股权/公告/研报数据
- `data/raw/1/` 中的问答测试集**仅用于评测**，不得用于规则调优
- Phase D 若需校准阈值，使用独立验证集（从财务数据中随机抽样），而非评测集

---

## 2. 九项指标详解

### 指标 1：结果准确率

| 维度 | 值 |
|---|---|
| 输入集 | 77 道深度题的系统输出 vs 标准答案 |
| 标签来源 | 赛方提供标准答案（若有），否则通过人工标注 |
| 计算公式 | `correct / total`，其中 correct = 预测与标准一致的样本数 |
| 目标值 | ≥ 70% |
| Phase C 状态 | 函数已定义（`metrics.accuracy()`），Phase D 接入真实答案 |

### 指标 2：证据覆盖率

| 维度 | 值 |
|---|---|
| 输入集 | 全部 Claim（来自 CrossValidate + BuildClaims 节点输出） |
| 标签来源 | 系统自检（evidence_ids 非空即为有证据） |
| 计算公式 | `with_evidence / total_claims` |
| 目标值 | ≥ 90% |
| Phase C 状态 | 函数已定义（`metrics.evidence_coverage()`） |

### 指标 3：多轮主体保持率

| 维度 | 值 |
|---|---|
| 输入集 | 深度题中的多轮对话（每 session 取前 10 轮） |
| 标签来源 | 赛题数据中标注的主体公司 |
| 计算公式 | `correct_turns / total_turns` |
| 目标值 | ≥ 85% |
| Phase C 状态 | 函数已定义（`metrics.entity_retention_rate()`） |

### 指标 4：无证据 Claim 比例

| 维度 | 值 |
|---|---|
| 输入集 | 同指标 2 |
| 计算公式 | `unverified / total_claims`（= 1 - 指标 2） |
| 目标值 | ≤ 10% |
| Phase C 状态 | 函数已定义（`metrics.unverified_claim_ratio()`） |

### 指标 5：partial 比例

| 维度 | 值 |
|---|---|
| 输入集 | 全部 turn 的 module_status |
| 标签来源 | 系统自检 |
| 计算公式 | `(partial_count + failed_count) / total_modules` |
| 目标值 | ≤ 20% |
| Phase C 状态 | 函数已定义（`metrics.partial_response_rate()`） |

### 指标 6：模块超时率

| 维度 | 值 |
|---|---|
| 输入集 | 全部模块执行记录 |
| 参考 deadline | finance=3s, equity=4s, events=3s（V12 §13.2） |
| 目标值 | ≤ 10% |
| Phase C 状态 | 函数已定义（`metrics.module_timeout_rate()`） |

### 指标 7：风险等级校准

| 维度 | 值 |
|---|---|
| 输入集 | 77 道深度题 |
| 标签来源 | 人工标注风险等级（red/orange/yellow/green/unknown） |
| 计算公式 | Cohen's Kappa（剔除随机一致后的校准度） |
| 目标值 | Kappa ≥ 0.6（substantial agreement） |
| Phase C 状态 | 函数已定义（`metrics.risk_calibration()`），等待人工标注 |

### 指标 8：行业分位差异

| 维度 | 值 |
|---|---|
| 输入集 | 全量评测结果，按 industry_l1 分组 |
| 计算公式 | 行业间某指标的均值标准差 |
| 目标值 | std_dev ≤ 0.15 |
| Phase C 状态 | 函数已定义（`metrics.industry_variance()`） |

### 指标 9：LLM 输出格式合规率

| 维度 | 值 |
|---|---|
| 输入集 | 全部 LLM 结构化输出 |
| 标签来源 | Pydantic 校验结果 |
| 计算公式 | `compliant / total_responses` |
| 目标值 | ≥ 95% |
| Phase C 状态 | 函数已定义（`metrics.schema_compliance_rate()`） |

---

## 3. Phase D 接入计划

Phase C 交付：9 个指标函数 + runner.py + 本口径文档

Phase D 待办：
1. 从赛题数据 `1/clean.xlsx` 中解析标准答案格式
2. 对 77 道深度题进行人工风险等级标注
3. 将 `runner.py` 的 mock 数据替换为真实评测数据
4. 输出完整评测报告（JSON 或 Markdown 格式）
