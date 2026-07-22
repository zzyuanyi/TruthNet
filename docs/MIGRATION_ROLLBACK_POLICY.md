# Migration 回滚策略 — TruthNet V12

## 当前政策

生产数据库和共享开发数据库采用 **forward-only migration** 策略。

### 保证的回滚级别

| 操作 | 支持 |
|------|------|
| `alembic upgrade head` | ✅ |
| `alembic downgrade -1` (head → previous head) | ✅ |
| `alembic downgrade base` (完整回退) | ❌ 不支持 |

### 不支持完整 downgrade base 的原因

1. 历史 migration `f5d9389bbef0` (v1_initial_14_tables) 的 `downgrade()` 存在外键删除顺序缺陷：
   - `ix_rule_evaluations_rule_id` 在被外键引用时无法直接 DROP
   - 需要先 DROP FOREIGN KEY 再 DROP INDEX
2. 修改已进入 `main` 的历史 migration 违反 Alembic 最佳实践

### 回滚方案

#### 方案 A: 数据库备份恢复（推荐）
```bash
# 执行 migration 前备份
mysqldump -u user -p truthnet > backup_before_migration.sql
# 如需回滚
mysql -u user -p truthnet < backup_before_migration.sql
```

#### 方案 B: 开发数据库重建
```bash
# 适用于开发/测试环境
mysql -u user -p -e "DROP DATABASE truthnet; CREATE DATABASE truthnet CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
alembic upgrade head
```

### 跟踪 Issue

- **Issue**: `f5d9389bbef0` downgrade FK order defect
- **Severity**: P2 (不影响正常 upgrade 和使用)
- **Remediation**: 后续 corrective migration 或新数据库初始化脚本

### 版本

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-07-22 | 1.0 | 初始策略，伴随 Task 4-6 PR |
