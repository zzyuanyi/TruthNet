# 需要用户确认事项 — V12 Alignment

> 生成时间：2026-07-17

## 需要确认

1. **V12 设计文档缺失**：`TruthNet_综合设计方案_V12(2).md` 不在仓库中。本轮以任务指令中的 V12 描述为准。请确认是否有该文件的最新版本需要放入仓库。

2. **版本号升级**：应用版本从 `0.1.0` 升级到 `0.2.0`。请确认是否合适。

3. **新增依赖安装**：`requirements.txt` 新增 6 个包。请在激活 conda 环境后运行：
   ```bash
   pip install -r requirements.txt
   ```

4. **CI 配置**：`ci.yml` 未修改。当前 CI 基础 job 不依赖 MySQL/Neo4j。如需在 CI 中增加 V12 特定检查，需要后续配置。

5. **前端更新**：`frontend/src/types/api.ts` 需要更新以匹配 V12 新 schema。本轮未修改前端代码。

6. **Alembic 初始化**：`alembic init` 尚未运行，`backend/app/infrastructure/persistence/migrations/` 为空骨架。

7. **Git 提交**：本轮产生了约 60 个文件的新增/修改。按规范，不应自动 commit。请审阅后手动提交。

## 无需确认（自动决策）

- lite/full profile 机制：已实现，默认 lite
- 旧接口保留：全部保留兼容
- Python 3.11 目标：不变
- 单一 requirements.txt：不变
- 不强制 MySQL/Neo4j：已实现，lite profile 独立运行

## 风险提示

- 预存的 sklearn/numpy 兼容问题未修复（非本轮范围）
- WebSocket 测试在异步环境中偶发超时（预存问题）
- full adapter 为骨架，未经过真实服务验证
