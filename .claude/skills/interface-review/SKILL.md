---
name: interface-review
description: 接口变更审查清单。每次修改接口、Schema、数据库、Agent 输出时自动激活。
---

# 接口变更审查

## 触发条件

当以下任一发生变更时，必须进行审查：

- `backend/app/schemas/` 下的 Pydantic 模型
- `docs/API_CONTRACT.md` 中的接口定义
- SQLite 表结构
- NetworkX 节点/边类型
- ChromaDB collection 结构
- Agent 输出结构

## 审查清单

每次接口变更时，逐项检查：

### Schema 变更

- [ ] 是否改了字段名？
  - 如果改了：旧字段名是否影响前端？是否需要兼容层？
- [ ] 是否改了字段类型？
  - 如 `int` → `float`, `str` → `list[str]`
  - 确认前端能否处理新类型
- [ ] 是否删除了字段？
  - 确认前端是否还在使用该字段
  - 考虑标记为 deprecated 而非直接删除
- [ ] 是否新增了必填字段？
  - 前端不传会报错，需要协调升级

### 文档同步

- [ ] 是否更新了 `docs/API_CONTRACT.md`？
- [ ] 是否更新了 `docs/DATA_CONTRACT.md`？
- [ ] 是否更新了 `docs/INTERFACE_CHANGELOG.md`？
- [ ] 如果是破坏性修改，是否添加了：
  - 变更原因
  - 影响范围
  - 迁移方式
  - 兼容说明

### Mock 同步

- [ ] 是否更新了对应的 mock JSON？
- [ ] Mock 是否与新的 Schema 一致？
- [ ] 前端是否能直接用新 mock 继续开发？

### 兼容性

- [ ] 如果是破坏性修改，是否请求了**用户审阅**？
- [ ] 是否评估了前端影响？
- [ ] 是否评估了数据组影响？
- [ ] 是否提供了迁移路径？

## 接口稳定性约定

> **接口一旦进入 `dev` 分支，默认视为稳定。**
> 除非用户同意，不做破坏性修改。

### 允许的修改（无需特殊流程）

- 向响应对象追加新字段
- 向请求对象追加可选字段（带默认值）
- 新增全新接口
- 修改接口实现的内部逻辑（不改变输入输出）

### 需要完整流程的修改

- 修改已有字段名
- 修改已有字段类型
- 删除已有字段
- 修改接口路径或 HTTP 方法
- 修改统一响应结构

## 执行

当检测到接口相关变更时，本 skill 自动激活并输出审查结果。对于破坏性修改，额外提示需要用户确认。

---

## V12 更新（2026-07-17）

### V12 审查范围扩展

接口变更审查现在还需覆盖：

- `backend/app/api/v1/schemas/` — V12 新 schema
- `backend/app/domain/` — 领域模型
- `backend/app/application/ports/` — Port 协议
- `docs/API_CONTRACT_V1.md` — V12 API 文档
- `docs/WEBSOCKET_CONTRACT_V1.md` — V12 WebSocket 文档
- `docs/DATA_CONTRACT.md` — V12 数据契约

### V12 新增审查项

- [ ] 是否使用 V12 `{data, meta, warnings}` envelope？
- [ ] 错误响应是否使用 RFC 9457 Problem Details？
- [ ] WebSocket 消息是否使用 V12 event envelope？
- [ ] 是否向后兼容旧格式？
- [ ] lite/full profile 下行为是否正确？
- [ ] Port 协议是否保持接口稳定性？
