# API 契约迁移记录 — V12 Alignment

> 生成时间：2026-07-17

## 迁移摘要

| 维度 | 旧（Prompt4） | 新（V12） | 策略 |
|------|-------------|----------|------|
| 文档 | `docs/API_CONTRACT.md` | `docs/API_CONTRACT_V1.md` | 旧文档保留，新文档追加 |
| 响应格式 | `{code, data, message, trace_id}` | `{data, meta, warnings}` | 共存，旧格式兼容 |
| 错误格式 | `{code, message, trace_id, details}` | RFC 9457 Problem Details | 新增，旧格式保留 |
| 健康检查 | `GET /health` | `GET /api/v1/healthz` | 旧端点 deprecated |
| 就绪检查 | 无 | `GET /api/v1/readyz` | 新增 |
| 公司搜索 | 无 | `GET /api/v1/companies?query=` | 新增 |
| 对话 | `POST /api/v1/chat` | 同路径，V12 envelope | 旧格式优先匹配，兼容 |

## 新增端点

| 方法 | 路径 | 格式 | 状态 |
|------|------|------|------|
| GET | `/api/v1/healthz` | V12 envelope | ✅ 可用 |
| GET | `/api/v1/readyz` | V12 envelope | ✅ 可用 |
| GET | `/api/v1/companies` | V12 envelope | ✅ 可用 (mock) |

## 向后兼容

- 所有旧端点和旧格式保持不变
- 旧测试无需修改即可通过
- 新客户端使用 V12 envelope，旧客户端继续使用旧格式
