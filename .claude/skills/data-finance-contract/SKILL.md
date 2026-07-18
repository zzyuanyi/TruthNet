---
name: data-finance-contract
description: 数据与财务契约。统一数据目录、SQLite schema、财务勾稽规则、标注流程和评测指标。
---

# 数据与财务契约

## 数据目录规范

```text
data/
  raw/           ← 原始数据源（不提交大文件）
    .gitkeep
  processed/     ← 处理后数据（不提交大文件）
    .gitkeep
  README.md
```

规则：
- `data/raw/` 只保留 `.gitkeep`，不提交 PDF/Excel/CSV 大文件
- `data/processed/` 不提交数据库文件、向量数据
- 数据文件通过 `.gitignore` 排除，通过团队内部文件共享传递

## SQLite Schema 变更流程

1. 先修改 `backend/app/core/schema.sql`（建表 SQL 文件）
2. 更新 `docs/DATA_CONTRACT.md` 中对应的表结构说明
3. 更新 `docs/INTERFACE_CHANGELOG.md`
4. 如果有破坏性变更（删表、改字段名、改类型），写迁移说明

### 当前表结构（草案）

- `companies` — 公司基本信息
- `financial_statements` — 财务报表（按科目存储）
- `ownership_relations` — 股权关系

## 财务勾稽规则格式

每条勾稽规则必须用以下结构定义：

```json
{
  "rule_id": "CHECK_R001",
  "rule_name": "营收与现金流入勾稽",
  "formula": "abs(营业收入 - 销售商品收到的现金) / 营业收入",
  "required_fields": ["营业收入", "销售商品收到的现金"],
  "threshold": 0.30,
  "severity": "high",
  "explanation": "当营收与现金流入偏差超过30%时，可能存在虚构收入或应收账款异常",
  "evidence_fields": ["营业收入", "销售商品收到的现金", "应收账款", "应收票据"]
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `rule_id` | 唯一规则 ID，格式 CHECK_Rxxx |
| `rule_name` | 规则中文简称 |
| `formula` | 计算公式（Python 可评估表达式或自然语言描述） |
| `required_fields` | 计算所需的财报科目字段 |
| `threshold` | 触发预警的阈值 |
| `severity` | 严重程度：high / medium / low |
| `explanation` | 对该规则的文字说明（为什么这可能是造假信号） |
| `evidence_fields` | 输出预警时需要附带的相关字段 |

## 标注流程

1. **先定规则**：财务背景成员编写勾稽规则，统一格式
2. **小样本试算**：在 3-5 家公司的真实数据上手工验证规则
3. **调整阈值**：根据试算结果调整 threshold
4. **批量标注**：在确认规则合理后进行规模化标注
5. **保持一致**：同一规则必须使用同一套标准和同一数据源

## 评测指标

### 核心指标

| 指标 | 说明 | 目标 |
|------|------|------|
| 长对话关键事实召回 | 10 轮对话中正确记住的关键事实比例 | > 90% |
| 工具调用 Precision | Agent 正确选择工具的准确率 | > 85% |
| 自纠错成功率 | 首次失败后第二次成功的比例 | > 70% |
| 股权穿透端到端准确率 | 正确识别最终控制人的比例 | > 80% |
| 时间线关键节点 Recall | 事件时间线的关键节点覆盖 | > 85% |
| 风险预警 F1 | 财务造假的 F1 score | — |

### 评测数据

- 评测集不提交到仓库（避免数据泄露）
- 评测集的构造标准在此文档中说明
- 评测结果记录在 `docs/evaluation/` 目录

## 数据组交付规范

给后端组的文件格式：
- JSON（推荐，UTF-8 编码）
- CSV（UTF-8 编码，逗号分隔）
- 文件名：`{公司代码}_{数据类型}_{版本}.{格式}`
  - 例：`600519_financial_v1.json`

## 禁止

- ❌ 提交真实财务数据文件到仓库
- ❌ 标注规则不经试算直接批量使用
- ❌ 前后端各自维护不同的字段名
- ❌ 评测集与训练集混用

---

## V12 更新（2026-07-17）

### V12 数据存储架构

| 层级 | lite | full |
|------|------|------|
| 关系数据 | SQLite | MySQL 8.0 + SQLAlchemy |
| 图数据 | NetworkX | Neo4j |
| 向量数据 | ChromaDB local | ChromaDB persistent |
| Migration | Alembic (SQLite) | Alembic (MySQL) |

### V12 新增数据模型

- `EvidenceRef`: 证据引用（id, type, source, field, value, page, retrieval_score）
- `Claim`: 结论声明（id, statement, confidence, evidence, counter_evidence）
- `EvidenceType`: financial_statement / ownership_record / news_article / regulation / calculation / expert_opinion
- `ConfidenceLevel`: high / medium / low / unverified

### 数据契约文档

V12 数据契约主文档：`docs/DATA_CONTRACT.md`
旧文档保留作为历史参考。

### 禁止额外 requirements 文件

所有依赖仍写入唯一 `requirements.txt`。
