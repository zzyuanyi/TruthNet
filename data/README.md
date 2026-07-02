# 数据目录

## 目录结构

```text
data/
  raw/           ← 原始数据（不提交到 Git）
    .gitkeep
  processed/     ← 处理后的数据（不提交到 Git）
    .gitkeep
  README.md      ← 本文件
```

## 规范

1. **不提交原始数据大文件**（PDF、Excel、CSV > 500KB）
2. **不提交数据库文件**（`*.db`、`*.sqlite`）
3. **不提交 ChromaDB 持久化目录**（`chroma_db/`）
4. 数据文件通过团队内部共享（网盘、内部服务器等）
5. 测试用小数据样例可放在 `data/samples/` 目录下（控制在 < 100KB）

## 数据格式

- 财务报表数据交付格式：JSON（UTF-8）
- 股权关系数据：JSON
- 舆情数据：JSON Lines

## 数据版本

数据文件命名规范：
```
{公司代码}_{数据类型}_{日期}.json
例：600519_financial_2024-03-31.json
```

## 联系人

- 数据组负责人：待分配
