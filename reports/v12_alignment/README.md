# V12 对齐报告

> 基于 `TruthNet_综合设计方案_V12(2).md` 设计目标，对当前仓库进行差异审计和增量重构。
> 生成时间：2026-07-17

## 报告索引

| 报告 | 说明 |
|------|------|
| [current_repo_inventory.md](current_repo_inventory.md) | 当前仓库完整清单 |
| [v12_gap_analysis.md](v12_gap_analysis.md) | V12 差异审计表 |
| [refactor_decision.md](refactor_decision.md) | 保留/修改/新增/废弃决策 |
| [environment_delta.md](environment_delta.md) | 环境变化记录 |
| [dependency_delta.md](dependency_delta.md) | 依赖变化记录 |
| [adapter_boundary_report.md](adapter_boundary_report.md) | Adapter 边界报告 |
| [api_contract_migration.md](api_contract_migration.md) | API 契约迁移记录 |
| [websocket_contract_migration.md](websocket_contract_migration.md) | WebSocket 契约迁移记录 |
| [test_results.md](test_results.md) | 测试结果 |
| [command_log.md](command_log.md) | 命令执行日志 |
| [final_report.md](final_report.md) | 最终报告 |
| [user_confirmation_needed.md](user_confirmation_needed.md) | 需要用户确认事项 |

## 核心原则

1. **不全面推倒重建**：保留 Prompt1-Prompt4 工程基线
2. **增量重构**：新增分层，保留旧接口兼容
3. **Adapter + Profile**：lite/full 双 profile，不强制 MySQL/Neo4j
4. **契约优先**：Pydantic V2 schema → 文档 → mock → 实现
5. **测试不回归**：所有已有测试继续通过
